#!/usr/bin/env python3
"""
seed_manual.py — seeds training_data from manually verified TBS values.

Run from the backend/ directory:
    python scripts/seed_manual.py [--api-key KEY] [--train]
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from db.supabase_client import get_supabase
from ml.features import property_to_happy

TORN_BASE        = "https://api.torn.com"
RATE_LIMIT_SLEEP = 0.65

# (name, torn_id, tbs)
MANUAL_PLAYERS = [
    ("Ehjay",           2696958,  778_000_000),
    ("_CERBERUS_",      3158683, 1_000_000_000),
    ("Chrisppy",        2603563,  426_000_000),
    ("Dohmer",          3124244,  493_000_000),
    ("Bosshog77",       3362537,  189_000_000),
    ("Zhaan",           3158965,   19_000_000),
    ("dirtywhiteboy87", 3174570,   15_000_000),
    ("kushking9",       3326907,      855_000),
    ("BusinessFish",    3472029,    1_400_000),
    ("Dyllzz",          3136053,    2_100_000),
    ("junkie1",         3394080,   73_000_000),
    ("Kw33fChief",      3448090,  130_000_000),
    ("Nova42",          3219585,    2_100_000),
    ("WhyteKnight",     3671479,    1_000_000),
    ("Gertoid",         3451226,      350_000),
    ("fartballs",       2423420,   40_000_000),
    ("Lady420",         3327727,      575_000),
    ("moon02",          4129993,        9_100),
    ("Tone-Capone404",  4089826,        8_000),
    ("Dawniyale",       4025167,       17_000),
    ("ChangelingSwarm", 4068294,       15_000),
    ("JackieFrog",      4061040,       43_000),
    ("American_God",    4089813,       62_000),
]


def fetch_torn_profile(torn_id: int, api_key: str) -> dict | None:
    try:
        r = httpx.get(
            f"{TORN_BASE}/user/{torn_id}",
            params={"selections": "profile,personalstats", "key": api_key},
            timeout=15,
        )
        data = r.json()
        if "error" in data:
            print(f"    Torn error {data['error']['code']}: {data['error']['error']}")
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


def build_training_row(torn_id: int, tbs: int, profile: dict | None) -> dict:
    row: dict = {
        "torn_id":           torn_id,
        "estimated_tbs":     tbs,
        "source_attack_id":  f"manual_{torn_id}",
        "contributed_by":    None,
        "level":             None,
        "donordays":         None, "age_days":          None,
        "xantaken":          None, "energydrinkused":   None,
        "candyused":         None, "refills":           None,
        "gymstrength":       None, "gymspeed":          None,
        "gymdefense":        None, "gymdexterity":      None,
        "statenhancersused": None,
        "useractivity":      None, "attackswon":        None,
        "daysbeendonator":   None,
        "property_happy":    None,
    }
    if profile:
        ps = profile.get("personalstats") or {}
        row.update({
            "level":             profile.get("level"),
            "donordays":         profile.get("donordays"),
            "age_days":          _age_days(profile),
            "xantaken":          ps.get("xantaken"),
            "energydrinkused":   ps.get("energydrinkused"),
            "candyused":         ps.get("candyused"),
            "refills":           ps.get("refills"),
            "gymstrength":       ps.get("gymstrength"),
            "gymspeed":          ps.get("gymspeed"),
            "gymdefense":        ps.get("gymdefense"),
            "gymdexterity":      ps.get("gymdexterity"),
            "statenhancersused": ps.get("statenhancersused"),
            "useractivity":      ps.get("useractivity"),
            "attackswon":        ps.get("attackswon"),
            "daysbeendonator":   ps.get("daysbeendonator"),
            "property_happy":    property_to_happy(profile.get("property")),
        })
    return row


def build_cache_row(torn_id: int, tbs: int) -> dict:
    expires = datetime.now(timezone.utc) + timedelta(days=90)
    return {
        "torn_id":       torn_id,
        "predicted_tbs": tbs,
        "predicted_str": None,
        "predicted_def": None,
        "predicted_spd": None,
        "predicted_dex": None,
        "confidence":    "high",
        "method":        "spy",
        "model_version": "manual",
        "expires_at":    expires.isoformat(),
    }


def get_existing_manual_ids(sb) -> set[int]:
    r = (
        sb.table("training_data")
        .select("torn_id")
        .like("source_attack_id", "manual_%")
        .execute()
    )
    return {row["torn_id"] for row in (r.data or [])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()

    api_key = args.api_key or settings.our_torn_api_key
    if not api_key:
        print("ERROR: No Torn API key. Use --api-key KEY or set OUR_TORN_API_KEY in .env")
        sys.exit(1)

    sb = get_supabase()
    existing_ids = get_existing_manual_ids(sb)
    to_process   = [(n, tid, tbs) for n, tid, tbs in MANUAL_PLAYERS if tid not in existing_ids]

    print(f"Total manual entries : {len(MANUAL_PLAYERS)}")
    print(f"Already in DB        : {len(existing_ids)}")
    print(f"New to insert        : {len(to_process)}")

    if not to_process:
        print("Nothing new to insert.")
    else:
        training_rows = []
        cache_rows    = []

        for i, (name, torn_id, tbs) in enumerate(to_process, 1):
            print(f"[{i:2}/{len(to_process)}] {torn_id}  {name:20s}  TBS={tbs:>15,}  fetching...", end="", flush=True)
            profile = fetch_torn_profile(torn_id, api_key)
            time.sleep(RATE_LIMIT_SLEEP)
            print(" ok" if profile else " (no profile)")

            training_rows.append(build_training_row(torn_id, tbs, profile))
            cache_rows.append(build_cache_row(torn_id, tbs))

        print(f"\nInserting {len(training_rows)} training rows...")
        sb.table("training_data").insert(training_rows).execute()

        print(f"Upserting {len(cache_rows)} predictions_cache rows...")
        sb.table("predictions_cache").upsert(cache_rows, on_conflict="torn_id").execute()

        print(f"\nDone: training_data +{len(training_rows)}, predictions_cache +{len(cache_rows)}")

    if args.train:
        print("\nStarting XGBoost training...")
        from ml.train import train_model
        try:
            result = train_model()
            print(f"\nTraining complete:")
            print(f"  version    : {result['version']}")
            print(f"  samples    : {result['samples']}")
            print(f"  train_mape : {result['train_mape']}%")
            print(f"  cv_rmse    : {result['cv_rmse']}")
        except Exception as e:
            print(f"Training failed: {e}")


if __name__ == "__main__":
    main()
