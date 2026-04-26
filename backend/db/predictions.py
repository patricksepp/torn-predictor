from datetime import datetime, timezone, timedelta
from db.supabase_client import get_supabase

CACHE_DAYS = 5


async def get_cached_prediction(torn_id: int) -> dict | None:
    sb = get_supabase()
    r = (
        sb.table("predictions_cache")
        .select("*")
        .eq("torn_id", torn_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    row = r.data[0]

    expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if expires < datetime.now(timezone.utc):
        return None

    # Normalise DB field name to API field name
    row["target_id"] = row["torn_id"]
    row.setdefault("target_name", str(row["torn_id"]))
    row.setdefault("training_samples", 0)
    return row


async def set_cached_prediction(torn_id: int, prediction: dict, model_version: str = "rank-v1") -> None:
    sb = get_supabase()
    expires = (datetime.now(timezone.utc) + timedelta(days=CACHE_DAYS)).isoformat()
    row = {
        "torn_id":       torn_id,
        "predicted_tbs": prediction["predicted_tbs"],
        "predicted_str": prediction.get("predicted_str"),
        "predicted_def": prediction.get("predicted_def"),
        "predicted_spd": prediction.get("predicted_spd"),
        "predicted_dex": prediction.get("predicted_dex"),
        "confidence":    prediction["confidence"],
        "method":        prediction["method"],
        "model_version": model_version,
        "expires_at":    expires,
    }
    # target_name stored when migration 001 has been applied
    if prediction.get("target_name"):
        row["target_name"] = prediction["target_name"]
    try:
        sb.table("predictions_cache").upsert(row).execute()
    except Exception:
        # Column doesn't exist yet — retry without it
        row.pop("target_name", None)
        sb.table("predictions_cache").upsert(row).execute()


async def invalidate_cache(torn_id: int) -> None:
    sb = get_supabase()
    sb.table("predictions_cache").delete().eq("torn_id", torn_id).execute()
