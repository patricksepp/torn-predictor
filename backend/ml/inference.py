import numpy as np
from ml.train import get_active_model
from ml.features import build_single_feature_vector

# Module-level cache so the model is loaded once per process
_model = None
_version = None


def _ensure_model():
    global _model, _version
    if _model is None:
        _model, _version = get_active_model()
    return _model, _version


def ml_predict(profile: dict) -> dict | None:
    """
    Runs inference using the active XGBoost model.
    Returns a prediction dict, or None if no model is available.
    """
    model, version = _ensure_model()
    if model is None:
        return None

    ps = profile.get("personalstats") or {}
    X  = build_single_feature_vector(profile, ps)

    log_pred  = model.predict(X)[0]
    pred_tbs  = int(np.expm1(log_pred))

    return {
        "predicted_tbs": pred_tbs,
        "predicted_str": pred_tbs // 4,
        "predicted_def": pred_tbs // 4,
        "predicted_spd": pred_tbs // 4,
        "predicted_dex": pred_tbs // 4,
        "confidence":    "medium",
        "method":        "ml",
        "model_version": version,
    }


def reload_model():
    """Forces a reload of the model from disk (call after retraining)."""
    global _model, _version
    _model, _version = get_active_model()
