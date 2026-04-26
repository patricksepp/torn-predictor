from services.torn_api import fetch_player_profile
from ml.rank_predictor import rank_predict
from ml.inference import ml_predict, reload_model
from db.predictions import get_cached_prediction, set_cached_prediction
from db.training import count_training_samples, get_active_model_version

# NPC player IDs that should never be predicted (from BSP reference)
NPC_IDS = {4, 7, 8, 9, 10, 15, 17, 19, 20, 21, 23}

ML_THRESHOLD = 100  # minimum training samples before switching to ML


def is_npc(target_id: int) -> bool:
    return target_id in NPC_IDS


async def predict(target_id: int, requester_api_key: str) -> dict:
    """
    Hybrid prediction pipeline:
    1. Check cache
    2. Fetch target profile from Torn API
    3. ML prediction (if model available + enough samples) or rank-based fallback
    4. Store in cache
    """
    # 1. Cache hit
    cached = await get_cached_prediction(target_id)
    if cached:
        return {**cached, "from_cache": True}

    # 2. Fetch target profile
    profile = await fetch_player_profile(target_id, requester_api_key)
    rank  = profile.get("rank", "Experienced")
    level = profile.get("level", 1)
    name  = profile.get("name", str(target_id))

    # 3. Choose prediction method
    sample_count = await count_training_samples()
    model_meta   = await get_active_model_version()

    result = None
    if model_meta and sample_count >= ML_THRESHOLD:
        result = ml_predict(profile)

    if result is None:
        result = rank_predict(rank, level)

    result["target_id"]        = target_id
    result["target_name"]      = name
    result["from_cache"]       = False
    result["training_samples"] = sample_count

    # 4. Cache result
    model_ver = model_meta["version"] if model_meta else "rank-v1"
    await set_cached_prediction(target_id, result, model_version=model_ver)
    return result


async def retrain_and_reload() -> dict:
    """Trains a new model and hot-reloads it into the inference module."""
    from ml.train import train_model
    summary = train_model()
    reload_model()
    return summary
