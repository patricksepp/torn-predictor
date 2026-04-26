from services.torn_api import fetch_player_profile, fetch_basic_profile
from ml.rank_predictor import rank_predict
from ml.inference import ml_predict, reload_model
from db.predictions import get_cached_prediction, set_cached_prediction, invalidate_cache
from db.training import count_training_samples, get_active_model_version

# NPC player IDs that should never be predicted (from BSP reference)
NPC_IDS = {4, 7, 8, 9, 10, 15, 17, 19, 20, 21, 23}

ML_THRESHOLD = 100  # minimum training samples before switching to ML


def is_npc(target_id: int) -> bool:
    return target_id in NPC_IDS


async def predict(
    target_id: int,
    requester_api_key: str,
    requester_torn_id: int | None = None,
) -> dict:
    """
    Hybrid prediction pipeline:
    1. Check cache (invalidate stale rank-only entries if ML is now available)
    2. Own profile shortcut: fetch real battlestats when target == requester
    3. Fetch target profile from Torn API
    4. ML prediction (if model available + enough samples) or rank-based fallback
    5. Store in cache
    """
    sample_count = await count_training_samples()
    model_meta   = await get_active_model_version()
    ml_ready     = bool(model_meta and sample_count >= ML_THRESHOLD)

    # 1. Cache check — invalidate stale rank entries now that ML is active
    cached = await get_cached_prediction(target_id)
    if cached:
        if cached.get("method") == "rank" and ml_ready:
            # ML is available but cache has an old rank prediction — refresh it
            await invalidate_cache(target_id)
            cached = None
        else:
            # Always return live sample count, not the stale value from cache
            return {**cached, "from_cache": True, "training_samples": sample_count}

    # 2. Own profile: if Full/Custom key, Torn returns exact battlestats for /user/
    if requester_torn_id and target_id == requester_torn_id:
        own = await fetch_basic_profile(requester_api_key)
        bs  = own.get("battlestats") or {}
        str_v = int(bs.get("strength") or 0)
        def_v = int(bs.get("defense")  or 0)
        spd_v = int(bs.get("speed")    or 0)
        dex_v = int(bs.get("dexterity") or 0)
        total = str_v + def_v + spd_v + dex_v

        if total > 0:
            result = {
                "target_id":        target_id,
                "target_name":      own.get("name", str(target_id)),
                "predicted_tbs":    total,
                "predicted_str":    str_v,
                "predicted_def":    def_v,
                "predicted_spd":    spd_v,
                "predicted_dex":    dex_v,
                "confidence":       "high",
                "method":           "spy",
                "from_cache":       False,
                "training_samples": sample_count,
            }
            await set_cached_prediction(target_id, result, model_version="own-battlestats")
            return result

        # Key doesn't have battlestats access — fall through with the already-fetched profile
        profile = own
    else:
        # 3. Fetch target profile
        profile = await fetch_player_profile(target_id, requester_api_key)

    rank  = profile.get("rank", "Experienced")
    level = profile.get("level", 1)
    name  = profile.get("name", str(target_id))
    ps    = profile.get("personalstats") or {}

    # 4. Choose prediction method
    result = None
    if ml_ready:
        result = ml_predict(profile)

    if result is None:
        result = rank_predict(rank, level, ps)

    result["target_id"]        = target_id
    result["target_name"]      = name
    result["from_cache"]       = False
    result["training_samples"] = sample_count

    # 5. Cache result
    model_ver = model_meta["version"] if model_meta else "rank-v1"
    await set_cached_prediction(target_id, result, model_version=model_ver)
    return result


async def retrain_and_reload() -> dict:
    """Trains a new model and hot-reloads it into the inference module."""
    from ml.train import train_model
    summary = train_model()
    reload_model()
    return summary
