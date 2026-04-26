import math

RANK_RANGES: dict[str, tuple[int, int]] = {
    "Absolute beginner": (0, 2_000),
    "Beginner":          (2_000, 10_000),
    "Intermediate":      (10_000, 25_000),
    "Experienced":       (25_000, 75_000),
    "Veteran":           (75_000, 200_000),
    "Distinguished":     (200_000, 2_000_000),
    "Highly regarded":   (2_000_000, 10_000_000),
    "Idolized":          (10_000_000, 50_000_000),
    "Champion":          (50_000_000, 100_000_000),
    "Heroic":            (100_000_000, 200_000_000),
    "Legendary":         (200_000_000, 500_000_000),
    # Torn uses custom rank titles that map to standard ranges
    "Reasonable Alcoholic": (200_000, 2_000_000),
}

_NORMALIZED: dict[str, str] = {r.lower(): r for r in RANK_RANGES}


def _normalize_rank(rank: str) -> str:
    """Case-insensitive lookup; falls back to Experienced if unknown."""
    return _NORMALIZED.get(rank.lower(), "Experienced")


def split_by_gym(predicted_tbs: int, ps: dict) -> tuple[int, int, int, int]:
    """
    Splits predicted TBS into individual stats using gym visit counts as a proxy
    for how the player distributed their training. Falls back to equal split.
    """
    gym_str = ps.get("gymstrength") or 0
    gym_def = ps.get("gymdefense") or 0
    gym_spd = ps.get("gymspeed") or 0
    gym_dex = ps.get("gymdexterity") or 0
    gym_total = gym_str + gym_def + gym_spd + gym_dex

    if gym_total == 0:
        quarter = predicted_tbs // 4
        return quarter, quarter, quarter, quarter

    return (
        int(predicted_tbs * gym_str / gym_total),
        int(predicted_tbs * gym_def / gym_total),
        int(predicted_tbs * gym_spd / gym_total),
        int(predicted_tbs * gym_dex / gym_total),
    )


def rank_predict(rank: str, level: int, ps: dict | None = None) -> dict:
    """
    Phase 1 prediction using rank + level, with gym-ratio stat split when available.
    Returns predicted_tbs, confidence='low', method='rank'.
    """
    norm = _normalize_rank(rank)
    low, high = RANK_RANGES.get(norm, (25_000, 75_000))

    # Linear scale: level 1-100 maps to 30%-100% of the range
    level_factor  = min(level / 100, 1.0)
    predicted_tbs = int(low + (high - low) * (0.3 + 0.7 * level_factor))

    s, d, sp, dx = split_by_gym(predicted_tbs, ps or {})

    return {
        "predicted_tbs": predicted_tbs,
        "predicted_str": s,
        "predicted_def": d,
        "predicted_spd": sp,
        "predicted_dex": dx,
        "confidence":    "low",
        "method":        "rank",
        "rank_used":     norm,
    }


def fair_fight_estimate(attacker_tbs: int, fair_fight: float) -> int:
    """
    Derives defender TBS from a fair_fight modifier.
    Formula: fair_fight = sqrt(atk_tbs) / sqrt(def_tbs)
    Rearranged: def_tbs = (sqrt(atk_tbs) / fair_fight) ^ 2
    """
    if fair_fight <= 0:
        return 0
    return int((math.sqrt(attacker_tbs) / fair_fight) ** 2)
