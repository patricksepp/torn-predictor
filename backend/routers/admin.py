from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from utils.auth_deps import require_admin, require_moderator
from db.supabase_client import get_supabase
from db.training import count_training_samples, get_active_model_version

router = APIRouter()


# ---------------------------------------------------------------------------
# ML
# ---------------------------------------------------------------------------

class TrainResponse(BaseModel):
    version: str
    samples: int
    train_mape: float
    train_rmse: float
    cv_rmse: float
    cv_folds: int


@router.post("/ml/train", response_model=TrainResponse)
async def trigger_training(admin=Depends(require_admin)):
    from services.predictor import retrain_and_reload
    try:
        summary = await retrain_and_reload()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Training failed: {e}")
    return TrainResponse(**summary)


@router.get("/ml/stats")
async def ml_stats(user=Depends(require_moderator)):
    sample_count = await count_training_samples()
    model_meta   = await get_active_model_version()
    return {
        "training_samples": sample_count,
        "active_model":     model_meta,
        "ml_ready":         model_meta is not None and sample_count >= 100,
    }


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/users")
async def list_users(user=Depends(require_moderator)):
    sb = get_supabase()
    r = (
        sb.table("users")
        .select("torn_id,torn_name,role,subscription_tier,subscription_end,api_key_status,last_seen,created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return r.data or []


@router.get("/users/{torn_id}")
async def get_user(torn_id: int, user=Depends(require_moderator)):
    sb = get_supabase()
    r = (
        sb.table("users")
        .select("torn_id,torn_name,role,subscription_tier,subscription_end,api_key_status,last_seen,created_at")
        .eq("torn_id", torn_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        raise HTTPException(404, f"User {torn_id} not found")
    return r.data[0]


class RoleUpdate(BaseModel):
    role: str  # user | moderator | admin


@router.put("/users/{torn_id}/role")
async def update_role(torn_id: int, body: RoleUpdate, admin=Depends(require_admin)):
    if body.role not in ("user", "moderator", "admin"):
        raise HTTPException(400, "Invalid role. Must be: user, moderator, admin")

    sb = get_supabase()
    sb.table("users").update({"role": body.role}).eq("torn_id", torn_id).execute()

    # Audit log
    sb.table("admin_audit_log").insert({
        "admin_torn_id":  admin["torn_id"],
        "action":         "role_change",
        "target_torn_id": torn_id,
        "details":        {"new_role": body.role},
    }).execute()

    return {"torn_id": torn_id, "role": body.role}


class SubscriptionUpdate(BaseModel):
    tier: str
    end_date: str | None = None  # ISO date string, null = remove subscription


@router.put("/users/{torn_id}/subscription")
async def update_subscription(torn_id: int, body: SubscriptionUpdate, admin=Depends(require_admin)):
    sb = get_supabase()
    sb.table("users").update({
        "subscription_tier": body.tier,
        "subscription_end":  body.end_date,
    }).eq("torn_id", torn_id).execute()

    sb.table("admin_audit_log").insert({
        "admin_torn_id":  admin["torn_id"],
        "action":         "subscription_edit",
        "target_torn_id": torn_id,
        "details":        {"tier": body.tier, "end_date": body.end_date},
    }).execute()

    return {"torn_id": torn_id, "subscription_tier": body.tier, "subscription_end": body.end_date}


@router.delete("/users/{torn_id}")
async def delete_user(torn_id: int, admin=Depends(require_admin)):
    sb = get_supabase()
    sb.table("predictions_cache").delete().eq("torn_id", torn_id).execute()
    # Anonymise training contributions (GDPR: keep data, remove identity)
    sb.table("training_data").update({"contributed_by": None}).eq("contributed_by", torn_id).execute()
    sb.table("users").delete().eq("torn_id", torn_id).execute()

    sb.table("admin_audit_log").insert({
        "admin_torn_id":  admin["torn_id"],
        "action":         "user_deleted",
        "target_torn_id": torn_id,
        "details":        {},
    }).execute()

    return {"deleted": torn_id}


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@router.get("/stats/overview")
async def overview(user=Depends(require_moderator)):
    sb = get_supabase()

    users_r     = sb.table("users").select("id", count="exact").execute()
    training_r  = sb.table("training_data").select("id", count="exact").execute()
    cache_r     = sb.table("predictions_cache").select("torn_id", count="exact").execute()
    model_meta  = await get_active_model_version()

    return {
        "total_users":      users_r.count or 0,
        "training_samples": training_r.count or 0,
        "cached_predictions": cache_r.count or 0,
        "active_model":     model_meta,
    }


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@router.get("/payments")
async def list_payments(user=Depends(require_moderator)):
    sb = get_supabase()
    r = sb.table("payments").select("*").order("created_at", desc=True).execute()
    return r.data or []


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@router.get("/audit-log")
async def get_audit_log(limit: int = 100, user=Depends(require_moderator)):
    sb = get_supabase()
    r = (
        sb.table("admin_audit_log")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return r.data or []
