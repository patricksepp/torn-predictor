from db.supabase_client import get_supabase


async def count_training_samples() -> int:
    sb = get_supabase()
    r = sb.table("training_data").select("id", count="exact").execute()
    return r.count or 0


async def get_active_model_version() -> dict | None:
    sb = get_supabase()
    r = (
        sb.table("model_versions")
        .select("*")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return r.data[0] if r.data else None
