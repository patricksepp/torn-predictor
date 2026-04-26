#!/usr/bin/env python3
"""
seed_from_baldr.py — seeds training_data + predictions_cache from Baldr's spy list.

Fetches real spy stats (str/def/spd/dex) for hundreds of players, enriches
each one with personalstats from the Torn API, then saves everything to DB.

Run from the backend/ directory:
    python scripts/seed_from_baldr.py [--api-key KEY] [--train] [--no-api]

Flags:
    --api-key KEY   Torn API key (overrides OUR_TORN_API_KEY from .env)
    --train         Run XGBoost training immediately after seeding
    --no-api        Skip Torn API enrichment (inserts with level + spy stats only)
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

# Run from backend/ directory — add it to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from db.supabase_client import get_supabase

BALDR_DATA_URL = (
    "https://raw.githubusercontent.com/oranweb/tc-baldrs-levelling-list/master/data.json"
)
TORN_BASE      = "https://api.torn.com"
BATCH_SIZE     = 50
# 0.65 s per request keeps us under the 100 req/min Torn API limit
RATE_LIMIT_SLEEP = 0.65


# ---------------------------------------------------------------------------
# Step 1 — fetch Baldr data
# ---------------------------------------------------------------------------

def fetch_baldr_data() -> dict:
    print("Fetching Baldr data.json from GitHub...")
    r = httpx.get(BALDR_DATA_URL, timeout=30, follow_redirects=True)
    r.raise_for_status()
    data = r.json()
    print(f"  Lists found: {list(data.keys())}")
    return data


def collect_unique_players(data: dict) -> list[dict]:
    """Flatten all lists, deduplicate by torn_id."""
    seen: dict[int, dict] = {}
    for list_name, players in data.items():
        for p in players:
            tid = p.get("id")
            if not tid:
                continue
            if tid not in seen:
                def _int(v):
                    try: return int(v) if v is not None else None
                    except (TypeError, ValueError): return None
                seen[tid] = {
                    "torn_id": int(tid),
                    "name":    p.get("name", ""),
                    "lvl":     _int(p.get("lvl") or p.get("level")),
                    "total":   _int(p.get("total")),
                    "spy_str": _int(p.get("str")),
                    "spy_def": _int(p.get("def")),
                    "spy_spd": _int(p.get("spd")),
                    "spy_dex": _int(p.get("dex")),
                    "list":    list_name,
                }
    return list(seen.values())


# ---------------------------------------------------------------------------
# Step 2 — check which IDs are already seeded
# ---------------------------------------------------------------------------

def get_existing_baldr_ids(sb) -> set[int]:
    r = (
        sb.table("training_data")
        .select("torn_id")
        .like("source_attack_id", "baldr_%")
        .execute()
    )
    return {row["torn_id"] for row in (r.data or [])}


# ---------------------------------------------------------------------------
# Step 3 — Torn API enrichment
# ---------------------------------------------------------------------------

def fetch_torn_profile(torn_id: int, api_key: str) -> dict | None:
    try:
        r = httpx.get(
            f"{TORN_BASE}/user/{torn_id}",
            params={"selections": "profile,personalstats", "key": api_key},
            timeout=15,
        )
        data = r.json()
        if "error" in data:
            code = data["error"]["code"]
            msg  = data["error"]["error"]
            print(f"    Torn error {code}: {msg}")
            return None
        return data
    except Exception as e:
        print(f"    Request failed: {e}")
        return None


def _age_days(profile: dict) -> int | None:
    signup = profile.get("signup")
    if not signup:
        return None
    try:
        dt = datetime.strptime(signup, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Step 4 — build DB rows
# ---------------------------------------------------------------------------

def build_training_row(player: dict, profile: dict | None) -> dict:
    """Merge Baldr spy data with Torn API personalstats into a training_data row."""
    # Use actual spy total; fall back to summing individual stats
    spy_total = (player["total"] or 0) or (
        (player["spy_str"] or 0)
        + (player["spy_def"] or 0)
        + (player["spy_spd"] or 0)
        + (player["spy_dex"] or 0)
    )

    row: dict = {
        "torn_id":           player["torn_id"],
        "estimated_tbs":     spy_total,
        "source_attack_id":  f"baldr_{player['torn_id']}",
        "contributed_by":    None,
        # Pre-fill from Baldr; overwritten by Torn API values below
        "level":             player.get("lvl"),
        "donordays":         None,
        "age_days":          None,
        "xantaken":          None,
        "energydrinkused":   None,
        "gymstrength":       None,
        "gymspeed":          None,
        "gymdefense":        None,
        "gymdexterity":      None,
        "attackswon":        None,
        "statenhancersused": None,
        "refills":           None,
        "nerverefills":      None,
    }

    if profile:
        ps = profile.get("personalstats") or {}
        row.update({
            "level":             profile.get("level") or player.get("lvl"),
            "donordays":         profile.get("donordays"),
            "age_days":          _age_days(profile),
            "xantaken":          ps.get("xantaken"),
            "energydrinkused":   ps.get("energydrinkused"),
            "gymstrength":       ps.get("gymstrength"),
            "gymspeed":          ps.get("gymspeed"),
            "gymdefense":        ps.get("gymdefense"),
            "gymdexterity":      ps.get("gymdexterity"),
            "attackswon":        ps.get("attackswon"),
            "statenhancersused": ps.get("statenhancersused"),
            "refills":           ps.get("refills"),
            "nerverefills":      ps.get("nerverefills"),
        })

    return row


def build_cache_row(player: dict) -> dict | None:
    """Build a predictions_cache row using real spy stats — confidence=high."""
    total = player.get("total") or 0
    if total <= 0:
        return None

    expires = datetime.now(timezone.utc) + timedelta(days=90)
    return {
        "torn_id":       player["torn_id"],
        "predicted_tbs": total,
        "predicted_str": player.get("spy_str"),
        "predicted_def": player.get("spy_def"),
        "predicted_spd": player.get("spy_spd"),
        "predicted_dex": player.get("spy_dex"),
        "confidence":    "high",
        "method":        "spy",
        "model_version": "baldr",
        "expires_at":    expires.isoformat(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def enrich_existing(players_by_id: dict, api_key: str, sb) -> None:
    """
    Update existing baldr rows in training_data with Torn API personalstats.
    Runs after --no-api seed to backfill NULL feature columns.
    """
    existing_ids = get_existing_baldr_ids(sb)
    to_enrich    = [players_by_id[tid] for tid in existing_ids if tid in players_by_id]
    print(f"Enriching {len(to_enrich)} existing rows with Torn API personalstats...")

    updated = 0
    for i, player in enumerate(to_enrich, 1):
        tid  = player["torn_id"]
        name = player["name"] or "?"
        print(f"[{i:3}/{len(to_enrich)}] {tid} {name:20s}  fetching...", end="", flush=True)
        profile = fetch_torn_profile(tid, api_key)
        time.sleep(RATE_LIMIT_SLEEP)

        if not profile:
            print(" skipped")
            continue

        ps = profile.get("personalstats") or {}
        update_data = {
            "level":             profile.get("level") or player.get("lvl"),
            "donordays":         profile.get("donordays"),
            "age_days":          _age_days(profile),
            "xantaken":          ps.get("xantaken"),
            "energydrinkused":   ps.get("energydrinkused"),
            "gymstrength":       ps.get("gymstrength"),
            "gymspeed":          ps.get("gymspeed"),
            "gymdefense":        ps.get("gymdefense"),
            "gymdexterity":      ps.get("gymdexterity"),
            "attackswon":        ps.get("attackswon"),
            "statenhancersused": ps.get("statenhancersused"),
            "refills":           ps.get("refills"),
            "nerverefills":      ps.get("nerverefills"),
        }
        sb.table("training_data")\
          .update(update_data)\
          .eq("source_attack_id", f"baldr_{tid}")\
          .execute()
        updated += 1
        print(" ok")

    print(f"\nEnrichment complete: {updated}/{len(to_enrich)} rows updated.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed training data from Baldr's spy list")
    parser.add_argument("--api-key", default=None, help="Torn API key")
    parser.add_argument(
        "--train", action="store_true",
        help="Run XGBoost training after seeding/enriching"
    )
    parser.add_argument(
        "--no-api", action="store_true",
        help="Skip Torn API calls — insert spy stats + level only"
    )
    parser.add_argument(
        "--enrich", action="store_true",
        help="Backfill personalstats for rows already inserted without API data"
    )
    args = parser.parse_args()

    api_key = args.api_key or settings.our_torn_api_key
    if not api_key and not args.no_api:
        print("ERROR: No Torn API key. Use --api-key KEY or set OUR_TORN_API_KEY in .env")
        sys.exit(1)

    # 1. Fetch + deduplicate
    raw     = fetch_baldr_data()
    players = collect_unique_players(raw)
    print(f"\nUnique players: {len(players)} across {len(raw)} lists")

    sb = get_supabase()
    players_by_id = {p["torn_id"]: p for p in players}

    # --enrich mode: update existing rows instead of inserting new ones
    if args.enrich:
        if not api_key:
            print("ERROR: --enrich requires an API key")
            sys.exit(1)
        enrich_existing(players_by_id, api_key, sb)
    else:
        # 2. Filter already-seeded
        existing_ids = get_existing_baldr_ids(sb)
        to_process   = [p for p in players if p["torn_id"] not in existing_ids]
        print(f"Already in DB:  {len(existing_ids)}")
        print(f"New to insert:  {len(to_process)}")

        if not to_process:
            print("\nNothing new to insert.")
        else:
            training_rows: list[dict] = []
            cache_rows:    list[dict] = []

            for i, player in enumerate(to_process, 1):
                tid  = player["torn_id"]
                name = player["name"] or "?"
                tbs  = int(player["total"] or 0)

                if args.no_api:
                    print(f"[{i:3}/{len(to_process)}] {tid} {name:20s}  TBS={tbs:>12,}")
                    profile = None
                else:
                    print(f"[{i:3}/{len(to_process)}] {tid} {name:20s}  TBS={tbs:>12,}  fetching API...", end="", flush=True)
                    profile = fetch_torn_profile(tid, api_key)
                    time.sleep(RATE_LIMIT_SLEEP)
                    print(" ok" if profile else " (no profile)")

                training_rows.append(build_training_row(player, profile))
                cr = build_cache_row(player)
                if cr:
                    cache_rows.append(cr)

            # 3. Insert training_data
            print(f"\nInserting {len(training_rows)} training rows...")
            for i in range(0, len(training_rows), BATCH_SIZE):
                chunk = training_rows[i : i + BATCH_SIZE]
                sb.table("training_data").insert(chunk).execute()
                print(f"  Batch {i // BATCH_SIZE + 1}: {len(chunk)} rows inserted")

            # 4. Upsert predictions_cache (real spy data — confidence=high)
            print(f"\nUpserting {len(cache_rows)} predictions_cache rows...")
            for i in range(0, len(cache_rows), BATCH_SIZE):
                chunk = cache_rows[i : i + BATCH_SIZE]
                sb.table("predictions_cache").upsert(chunk, on_conflict="torn_id").execute()
                print(f"  Batch {i // BATCH_SIZE + 1}: {len(chunk)} rows upserted")

            print(f"\nSeeding complete. training_data +{len(training_rows)}, predictions_cache +{len(cache_rows)}")

    # 5. Optional model training
    if args.train:
        print("\nStarting XGBoost training...")
        from ml.train import train_model
        try:
            result = train_model()
            print(f"Training complete: {result}")
        except Exception as e:
            print(f"Training failed: {e}")


if __name__ == "__main__":
    main()
