from datetime import datetime, timezone
from db.supabase_client import get_supabase


async def get_subscription(torn_id: int) -> dict:
    """Returns {'tier': str, 'active': bool, 'ends_at': str|None}"""
    sb = get_supabase()
    r = (
        sb.table("users")
        .select("subscription_tier,subscription_end,role")
        .eq("torn_id", torn_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return {"tier": "free", "active": False, "ends_at": None}

    row     = r.data[0]
    tier    = row["subscription_tier"]
    role    = row["role"]
    end_str = row["subscription_end"]

    # Admins and moderators always have active access
    if role in ("admin", "moderator"):
        return {"tier": "premium", "active": True, "ends_at": end_str}

    if not end_str:
        return {"tier": tier, "active": False, "ends_at": None}

    ends_at = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
    active  = ends_at > datetime.now(timezone.utc)
    return {"tier": tier, "active": active, "ends_at": end_str}
