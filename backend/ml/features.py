import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "level", "donordays", "age_days",
    "xantaken", "energydrinkused",
    "gymstrength", "gymspeed", "gymdefense", "gymdexterity",
    "attackswon", "statenhancersused", "refills", "nerverefills",
]

# Median fill values used when a column is entirely null in training data.
# These are updated after each training run.
_FALLBACK_MEDIANS: dict[str, float] = {
    "level": 30, "donordays": 0, "age_days": 1000,
    "xantaken": 50, "energydrinkused": 100,
    "gymstrength": 0, "gymspeed": 0, "gymdefense": 0, "gymdexterity": 0,
    "attackswon": 100, "statenhancersused": 0, "refills": 200, "nerverefills": 50,
}


def build_feature_matrix(rows: list[dict]) -> np.ndarray:
    """
    Converts a list of DB rows into a (n_samples, n_features) numpy array.
    Fills nulls with column medians so the model never sees NaN.
    """
    df = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
        median = df[col].median()
        if pd.isna(median):
            median = _FALLBACK_MEDIANS.get(col, 0)
        df[col] = df[col].fillna(median)
    return df[FEATURE_COLUMNS].values.astype(np.float32)


def build_single_feature_vector(profile: dict, personalstats: dict) -> np.ndarray:
    """Builds a single (1, n_features) matrix from a Torn API profile."""
    from datetime import datetime, timezone
    signup = profile.get("signup")
    if signup:
        try:
            signup_dt = datetime.strptime(signup, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - signup_dt).days
        except Exception:
            age_days = _FALLBACK_MEDIANS["age_days"]
    else:
        age_days = _FALLBACK_MEDIANS["age_days"]

    row = {
        "level":             profile.get("level") or _FALLBACK_MEDIANS["level"],
        "donordays":         profile.get("donordays") or 0,
        "age_days":          age_days,
        "xantaken":          personalstats.get("xantaken") or 0,
        "energydrinkused":   personalstats.get("energydrinkused") or 0,
        "gymstrength":       personalstats.get("gymstrength") or 0,
        "gymspeed":          personalstats.get("gymspeed") or 0,
        "gymdefense":        personalstats.get("gymdefense") or 0,
        "gymdexterity":      personalstats.get("gymdexterity") or 0,
        "attackswon":        personalstats.get("attackswon") or 0,
        "statenhancersused": personalstats.get("statenhancersused") or 0,
        "refills":           personalstats.get("refills") or 0,
        "nerverefills":      personalstats.get("nerverefills") or 0,
    }
    return build_feature_matrix([row])
