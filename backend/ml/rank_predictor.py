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
    # Torn custom lifestyle ranks — these are achievement titles, not stat ranks.
    # Do NOT add them here; unknown ranks fall back to "Experienced" via _normalize_rank.
}

_NORMALIZED: dict[str, str] = {r.lower(): r for r in RANK_RANGES}


def _normalize_rank(rank: str) -> str:
    """Case-insensitive lookup; falls back to Experienced if unknown."""
    return _NORMALIZED.get(rank.lower(), "Experienced")


def _combat_split(ps: dict) -> tuple[float, float, float, float]:
    """
    Infer stat distribution from combat record when gym counts are unavailable.

    Logic:
    - Active attacker with high win rate → STR-heavy build
    - Mostly defending with decent win rate → DEF-heavy build
    - Passive victim (huge defend losses, no attacks) → unknown, use default
    - Default: slight STR/DEF bias (typical combat build)

    Returns (str_ratio, def_ratio, spd_ratio, dex_ratio) summing to 1.0.
    """
    atk_won  = ps.get("attackswon",  0) or 0
    atk_lost = ps.get("attackslost", 0) or 0
    def_won  = ps.get("defendswon",  0) or 0
    def_lost = ps.get("defendslost", 0) or 0

    total_atk = atk_won + atk_lost
    total_def = def_won + def_lost

    atk_rate = atk_won / total_atk if total_atk >= 20 else None
    def_rate = def_won / total_def if total_def >= 20 else None

    # Passive punching-bag: massive defend losses, almost no attacks
    if total_def > 500 and total_atk < 20:
        return (0.25, 0.25, 0.25, 0.25)  # genuinely unknown

    # Strong attacker (≥70% win rate) → STR-heavy
    if atk_rate is not None and atk_rate >= 0.70:
        return (0.42, 0.28, 0.18, 0.12)

    # Moderate attacker
    if atk_rate is not None and atk_rate >= 0.50:
        return (0.36, 0.30, 0.20, 0.14)

    # Strong defender (≥40% win rate) → DEF-heavy
    if def_rate is not None and def_rate >= 0.40:
        return (0.26, 0.44, 0.18, 0.12)

    # Default: slight STR bias (most active torn combat builds)
    return (0.34, 0.30, 0.21, 0.15)


def split_by_gym(predicted_tbs: int, ps: dict) -> tuple[int, int, int, int]:
    """
    Splits predicted TBS into individual stats.
    Priority: (1) gym visit counts, (2) combat record ratios, (3) default split.
    """
    gym_str = ps.get("gymstrength") or 0
    gym_def = ps.get("gymdefense")  or 0
    gym_spd = ps.get("gymspeed")    or 0
    gym_dex = ps.get("gymdexterity") or 0
    gym_total = gym_str + gym_def + gym_spd + gym_dex

    if gym_total > 0:
        # Gym counts available — most accurate
        ratios = (gym_str / gym_total, gym_def / gym_total,
                  gym_spd / gym_total, gym_dex / gym_total)
    else:
        # Fall back to combat-record inference
        ratios = _combat_split(ps)

    sr, dr, spr, dxr = ratios
    return (
        int(predicted_tbs * sr),
        int(predicted_tbs * dr),
        int(predicted_tbs * spr),
        int(predicted_tbs * dxr),
    )


def clamp_to_rank(tbs: int, rank: str) -> int:
    """
    Clamps a TBS estimate to the known rank range (±15% margin for edge cases).
    Rank is a hard game mechanic — a prediction outside the range is impossible.
    """
    norm = _normalize_rank(rank)
    low, high = RANK_RANGES.get(norm, (0, 500_000_000))
    return max(int(low * 0.85), min(int(high * 1.15), tbs))


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
    Derives defender TBS from the Torn fair_fight modifier.

    Actual Torn formula:
        Score = √STR + √SPD + √DEF + √DEX  (battle stat score)
        FF = 1 + (8/3) × (DefScore / AtkScore)   [range: 1.0 – 3.0]

    Assuming both players have balanced 4-stat builds (Score = 2√TBS):
        DefScore / AtkScore = √def_tbs / √atk_tbs
        → def_tbs = atk_tbs × ((FF - 1) × 3/8)²

    NOTE: result is approximate; unbalanced builds introduce up to 2× error.
    FF values close to 3.0 (defenders ~56% of attacker) are most reliable.
    """
    if fair_fight <= 1.0:
        return 0
    ratio = (fair_fight - 1.0) * (3.0 / 8.0)
    return int(attacker_tbs * ratio ** 2)
