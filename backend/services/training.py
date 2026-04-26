from datetime import datetime, timezone
from db.supabase_client import get_supabase
from db.users import get_user_by_torn_id
from ml.rank_predictor import fair_fight_estimate, rank_predict
from services.torn_api import fetch_attacks, fetch_basic_profile
from utils.crypto import decrypt

# Minimum fair_fight value to consider an attack usable for training.
# Values near 1.0 give the most accurate defender TBS estimates.
# We exclude extreme ratios where the estimate becomes unreliable.
# Torn fair_fight modifier ranges 1.0–3.0.
# Values < 1.5 give unreliable TBS estimates (defender vastly weaker than attacker).
MIN_FF = 1.5
MAX_FF = 3.0


async def process_attacks_for_user(torn_id: int) -> dict:
    """
    Fetches the user's attack log, derives defender TBS via fair_fight,
    and stores new training rows. Returns a summary.
    """
    user = await get_user_by_torn_id(torn_id)
    if not user:
        return {"error": "User not found", "inserted": 0, "skipped": 0}

    api_key = decrypt(user["torn_api_key_encrypted"])

    # Fetch attacker's own stats so we can compute defender TBS
    own_profile  = await fetch_basic_profile(api_key)
    own_tbs      = _extract_own_tbs(own_profile)
    own_features = _extract_features(own_profile)

    if own_tbs is None:
        return {"error": "Could not determine own TBS from profile", "inserted": 0, "skipped": 0}

    attacks = await fetch_attacks(api_key)
    if not attacks:
        return {"inserted": 0, "skipped": 0, "reason": "No attacks found"}

    existing_ids = await _get_existing_attack_ids(torn_id)

    rows_to_insert = []
    skipped = 0

    for attack_id, attack in attacks.items():
        # Only process attacks where this user was the attacker
        if str(attack.get("attacker_id")) != str(torn_id):
            skipped += 1
            continue

        # Skip already-processed attacks
        if attack_id in existing_ids:
            skipped += 1
            continue

        ff = _get_fair_fight(attack)
        if ff is None or not (MIN_FF <= ff <= MAX_FF):
            skipped += 1
            continue

        defender_id  = attack.get("defender_id")
        estimated_tbs = fair_fight_estimate(own_tbs, ff)

        if estimated_tbs <= 0:
            skipped += 1
            continue

        rows_to_insert.append({
            "torn_id":          defender_id,
            "estimated_tbs":    estimated_tbs,
            "source_attack_id": str(attack_id),
            "contributed_by":   torn_id,
            # Attacker's own features (used as ML proxy for defender features
            # when defender profile is not fetched — saves API quota)
            **own_features,
        })

    if rows_to_insert:
        sb = get_supabase()
        sb.table("training_data").insert(rows_to_insert).execute()

    return {
        "inserted": len(rows_to_insert),
        "skipped":  skipped,
        "own_tbs":  own_tbs,
    }


def _extract_own_tbs(profile: dict) -> int | None:
    """
    Tries to determine the caller's TBS with decreasing accuracy:
    1. battlestats direct values (Custom key, most accurate)
    2. gym visit counts * heuristic multiplier (Limited/Full key)
    3. rank + level estimate (fallback, least accurate)
    """
    # 1. Direct battlestats — API returns these as top-level keys (not nested)
    total = sum(profile.get(k) or 0 for k in ("strength", "defense", "speed", "dexterity"))
    if total > 0:
        return total

    # 2. Gym session counts (rough heuristic: ~5k stats per session on average)
    ps = profile.get("personalstats") or {}
    gym_total = sum(ps.get(k) or 0 for k in
                    ("gymstrength", "gymdefense", "gymspeed", "gymdexterity"))
    if gym_total > 0:
        return gym_total * 5_000

    # 3. Rank + level estimate as last resort
    rank  = profile.get("rank", "Experienced")
    level = profile.get("level", 1)
    if rank and level:
        return rank_predict(rank, level)["predicted_tbs"]

    return None


def _extract_features(profile: dict) -> dict:
    """Extracts ML feature columns from a player profile."""
    from ml.features import property_to_happy
    ps = profile.get("personalstats", {})
    return {
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
    }


def _age_days(profile: dict) -> int | None:
    signup = profile.get("signup")
    if not signup:
        return None
    try:
        signup_dt = datetime.strptime(signup, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - signup_dt).days
    except Exception:
        return None


def _get_fair_fight(attack: dict) -> float | None:
    modifiers = attack.get("modifiers") or {}
    ff = modifiers.get("fair_fight")
    if ff is None:
        return None
    try:
        return float(ff)
    except (TypeError, ValueError):
        return None


async def _get_existing_attack_ids(torn_id: int) -> set:
    """Returns set of source_attack_ids already stored for this contributor."""
    sb = get_supabase()
    r = (
        sb.table("training_data")
        .select("source_attack_id")
        .eq("contributed_by", torn_id)
        .execute()
    )
    return {row["source_attack_id"] for row in (r.data or []) if row["source_attack_id"]}
