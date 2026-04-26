import json
import os
from datetime import datetime, timezone

import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import cross_val_score
import joblib

from ml.features import FEATURE_COLUMNS, build_feature_matrix
from db.supabase_client import get_supabase

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MIN_SAMPLES = 20  # lower threshold so we can train even with little data


def _load_training_data() -> tuple[np.ndarray, np.ndarray]:
    """Loads all training rows from Supabase, returns (X, y)."""
    sb = get_supabase()
    cols = ",".join(["estimated_tbs"] + FEATURE_COLUMNS)
    r = sb.table("training_data").select(cols).execute()
    rows = r.data or []

    if len(rows) < MIN_SAMPLES:
        raise ValueError(f"Not enough training data: {len(rows)} rows (minimum {MIN_SAMPLES})")

    X = build_feature_matrix(rows)
    y = np.log1p([row["estimated_tbs"] for row in rows]).astype(np.float32)
    return X, y, len(rows)


def _compute_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    true_tbs = np.expm1(y_true)
    pred_tbs = np.expm1(y_pred)
    mask = true_tbs > 0
    return float(np.mean(np.abs(true_tbs[mask] - pred_tbs[mask]) / true_tbs[mask]) * 100)


def train_model() -> dict:
    """
    Full training pipeline:
    1. Load data from Supabase
    2. Train XGBRegressor on log(TBS)
    3. Cross-validate and compute MAPE + RMSE
    4. Save model to disk
    5. Register in model_versions table
    Returns a summary dict.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)

    X, y, n_samples = _load_training_data()

    model = XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    # Cross-validation (use 3-fold when samples are scarce)
    n_folds = min(5, max(3, n_samples // 10))
    cv_scores = cross_val_score(
        model, X, y,
        cv=n_folds,
        scoring="neg_root_mean_squared_error",
    )
    cv_rmse = float(-cv_scores.mean())

    # Train on full dataset
    model.fit(X, y)
    y_pred = model.predict(X)

    train_mape = _compute_mape(y, y_pred)
    train_rmse = float(np.sqrt(np.mean((y - y_pred) ** 2)))

    # Version string: date + sample count
    version = datetime.now(timezone.utc).strftime("xgb-%Y%m%d") + f"-n{n_samples}"
    model_path = os.path.join(MODELS_DIR, f"{version}.joblib")
    joblib.dump(model, model_path)

    # Register in DB
    _register_model_version(version, n_samples, train_rmse, train_mape, cv_rmse)

    return {
        "version":    version,
        "samples":    n_samples,
        "train_mape": round(train_mape, 2),
        "train_rmse": round(train_rmse, 4),
        "cv_rmse":    round(cv_rmse, 4),
        "cv_folds":   n_folds,
        "model_path": model_path,
    }


def _register_model_version(
    version: str, samples: int, rmse: float, mape: float, cv_rmse: float
) -> None:
    sb = get_supabase()
    # Deactivate previous active model
    sb.table("model_versions").update({"is_active": False}).eq("is_active", True).execute()
    # Insert new version
    sb.table("model_versions").insert({
        "version":          version,
        "training_samples": samples,
        "rmse":             rmse,
        "mape":             mape,
        "is_active":        True,
    }).execute()


def load_model(version: str):
    """Loads a saved model from disk by version string."""
    path = os.path.join(MODELS_DIR, f"{version}.joblib")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model file not found: {path}")
    return joblib.load(path)


def get_active_model():
    """Returns (model, version) for the currently active model, or (None, None)."""
    sb = get_supabase()
    r = sb.table("model_versions").select("version").eq("is_active", True).limit(1).execute()
    if not r.data:
        return None, None
    version = r.data[0]["version"]
    try:
        return load_model(version), version
    except FileNotFoundError:
        return None, None
