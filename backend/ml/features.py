import numpy as np
import pandas as pd

# Columns stored in training_data that the model reads directly.
# NOTE: trainsreceived is intentionally excluded — employer "trains" give
# JOB stats (INT/MAN/END), not battle stats (STR/DEF/SPD/DEX).
STORED_COLUMNS = [
    "level", "donordays", "age_days",
    # Energy items — primary drivers of gym time → battle stat gain
    "xantaken",          # 250 energy each; biggest single source
    "energydrinkused",   # 100 energy each
    "candyused",         # 10 energy each
    "refills",           # fills bar to max energy (100 non-donor / 150 donor)
    # Gym session counts — direct stat indicator when available
    "gymstrength", "gymspeed", "gymdefense", "gymdexterity",
    # Direct stat boosts (bypass gym)
    "statenhancersused",
    # Activity / subscription
    "useractivity",      # total minutes online — strongest activity proxy
    "attackswon",        # combat activity
    "daysbeendonator",   # subscriber bonus (~10% extra stats per gym session)
    # Property → max happiness proxy (happiness is dominant gym gains multiplier)
    "property_happy",    # Shack=100, Penthouse=925, Private Island=3000
    # Rank trigger inputs — proxy for total game progression
    "crimes",            # criminaloffences count from personalstats
    "networth",          # player networth in $ from profile
]

# All features fed into XGBoost, including derived ones computed at build time.
FEATURE_COLUMNS = STORED_COLUMNS + [
    # energy_proxy: total energy available for gym sessions
    # refills give 150 (fill to max), xanax 250, drinks 100, candy 10
    "total_energy_proxy",
    # gym_total: sum of all gym visits — powerful when non-zero
    "gym_total",
    # level_triggers: number of rank trigger thresholds crossed by level alone
    # [2, 6, 11, 26, 31, 50, 71, 100] → max 8 triggers at level 100
    "level_triggers",
]

PROPERTY_HAPPY: dict[str, int] = {
    "Shack":          100,
    "Apartment":      200,
    "House":          400,
    "Ranch":          400,
    "Townhouse":      550,
    "Condominium":    650,
    "Mansion":        800,
    "Palace":         850,
    "Penthouse":      925,
    "Private Island": 3000,
}


def property_to_happy(property_name: str | None) -> int:
    """Maps Torn property type to approximate max happiness value."""
    if not property_name:
        return 400  # unknown → assume House as midpoint
    return PROPERTY_HAPPY.get(property_name, 400)


# Fallback medians when a column is entirely null in training data.
_FALLBACK_MEDIANS: dict[str, float] = {
    "level":              25,
    "donordays":           0,
    "age_days":         2000,
    "xantaken":            0,
    "energydrinkused":     0,
    "candyused":           0,
    "refills":             0,
    "gymstrength":         0,
    "gymspeed":            0,
    "gymdefense":          0,
    "gymdexterity":        0,
    "statenhancersused":   0,
    "trainsreceived":      0,
    "useractivity":     5000,
    "attackswon":          5,
    "nerverefills":        0,
    "daysbeendonator":     0,
    "property_happy":    400,
    "crimes":           5000,
    "networth":    500_000_000,
    "total_energy_proxy":  0,
    "gym_total":           0,
    "level_triggers":      4,
}


_LEVEL_TRIGGER_THRESHOLDS = [2, 6, 11, 26, 31, 50, 71, 100]


def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived features from stored columns."""
    # Refill restores to max: 150 for donators, 100 for non-donators.
    # We use 125 as a midpoint approximation; daysbeendonator is a separate feature
    # that lets the model learn the donator/non-donator split.
    df["total_energy_proxy"] = (
        df["xantaken"].fillna(0)        * 250 +
        df["energydrinkused"].fillna(0) * 100 +
        df["candyused"].fillna(0)       * 10  +
        df["refills"].fillna(0)         * 125
    )
    df["gym_total"] = (
        df["gymstrength"].fillna(0)  +
        df["gymspeed"].fillna(0)     +
        df["gymdefense"].fillna(0)   +
        df["gymdexterity"].fillna(0)
    )
    df["level_triggers"] = df["level"].fillna(0).apply(
        lambda lvl: sum(1 for t in _LEVEL_TRIGGER_THRESHOLDS if lvl >= t)
    )
    return df


def build_feature_matrix(rows: list[dict]) -> np.ndarray:
    """
    Converts a list of DB rows into a (n_samples, n_features) numpy array.
    Missing stored columns are filled with column medians; derived features
    are computed from the stored ones.
    """
    df = pd.DataFrame(rows)
    for col in STORED_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    df = _add_derived(df)

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
        median = df[col].median()
        if pd.isna(median):
            median = _FALLBACK_MEDIANS.get(col, 0)
        df[col] = df[col].fillna(median)

    return df[FEATURE_COLUMNS].values.astype(np.float32)


def build_single_feature_vector(profile: dict, personalstats: dict) -> np.ndarray:
    """Builds a single (1, n_features) matrix from a Torn API profile response."""
    from datetime import datetime, timezone

    signup = profile.get("signup")
    if signup:
        try:
            dt      = datetime.strptime(signup, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - dt).days
        except Exception:
            age_days = _FALLBACK_MEDIANS["age_days"]
    else:
        age_days = _FALLBACK_MEDIANS["age_days"]

    row = {
        "level":             profile.get("level")                      or _FALLBACK_MEDIANS["level"],
        "donordays":         profile.get("donordays")                  or 0,
        "age_days":          age_days,
        "xantaken":          personalstats.get("xantaken")             or 0,
        "energydrinkused":   personalstats.get("energydrinkused")      or 0,
        "candyused":         personalstats.get("candyused")            or 0,
        "refills":           personalstats.get("refills")              or 0,
        "gymstrength":       personalstats.get("gymstrength")          or 0,
        "gymspeed":          personalstats.get("gymspeed")             or 0,
        "gymdefense":        personalstats.get("gymdefense")           or 0,
        "gymdexterity":      personalstats.get("gymdexterity")         or 0,
        "statenhancersused": personalstats.get("statenhancersused")    or 0,
        "useractivity":      personalstats.get("useractivity")         or 0,
        "attackswon":        personalstats.get("attackswon")           or 0,
        "daysbeendonator":   personalstats.get("daysbeendonator")      or 0,
        "property_happy":    property_to_happy(profile.get("property")),
        "crimes":            personalstats.get("criminaloffences")     or 0,
        "networth":          profile.get("networth")                   or 0,
    }
    return build_feature_matrix([row])
