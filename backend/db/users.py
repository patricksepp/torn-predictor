from datetime import datetime, timezone, timedelta
from db.supabase_client import get_supabase
from utils.crypto import encrypt


async def get_user_by_torn_id(torn_id: int) -> dict | None:
    sb = get_supabase()
    r = sb.table("users").select("*").eq("torn_id", torn_id).limit(1).execute()
    return r.data[0] if r.data else None


async def create_user(torn_id: int, torn_name: str, api_key: str) -> dict:
    sb = get_supabase()
    sub_end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    row = {
        "torn_id": torn_id,
        "torn_name": torn_name,
        "torn_api_key_encrypted": encrypt(api_key),
        "api_key_status": "active",
        "role": "user",
        "subscription_tier": "free",
        "subscription_end": sub_end,
    }
    r = sb.table("users").insert(row).execute()
    return r.data[0]


async def update_user_on_login(torn_id: int, torn_name: str, api_key: str) -> dict:
    sb = get_supabase()
    r = sb.table("users").update({
        "torn_api_key_encrypted": encrypt(api_key),
        "torn_name": torn_name,
        "api_key_status": "active",
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }).eq("torn_id", torn_id).execute()
    return r.data[0]


async def set_api_key_status(torn_id: int, status: str) -> None:
    """status: 'active' | 'paused' | 'inactive' | 'invalid'"""
    sb = get_supabase()
    sb.table("users").update({"api_key_status": status}).eq("torn_id", torn_id).execute()


async def get_user_role(torn_id: int) -> str:
    user = await get_user_by_torn_id(torn_id)
    return user["role"] if user else "user"
