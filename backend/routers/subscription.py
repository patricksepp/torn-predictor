from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from utils.auth_deps import get_current_user
from db.subscriptions import get_subscription
from services.payments import check_and_apply_payments

router = APIRouter()


class SubscriptionStatus(BaseModel):
    tier: str
    active: bool
    ends_at: str | None
    days_remaining: int | None


class PaymentCheckResponse(BaseModel):
    new_payments: int
    payments: list[dict]
    message: str


@router.get("/status", response_model=SubscriptionStatus)
async def subscription_status(current_user: dict = Depends(get_current_user)):
    sub = await get_subscription(current_user["torn_id"])

    days_remaining = None
    if sub["ends_at"]:
        ends_at = datetime.fromisoformat(sub["ends_at"].replace("Z", "+00:00"))
        delta   = ends_at - datetime.now(timezone.utc)
        days_remaining = max(0, delta.days)

    return SubscriptionStatus(
        tier=sub["tier"],
        active=sub["active"],
        ends_at=sub["ends_at"],
        days_remaining=days_remaining,
    )


@router.post("/check-payments", response_model=PaymentCheckResponse)
async def check_payments(current_user: dict = Depends(get_current_user)):
    """
    Scans our Torn account's recent events for new xanax payments and
    extends subscriptions accordingly.  Any user can call this — only
    payments intended for the caller's account are applied.
    """
    try:
        applied = await check_and_apply_payments()
    except Exception as e:
        raise HTTPException(500, f"Payment check failed: {e}")

    # Filter to only payments for the calling user (for the response)
    my_payments = [p for p in applied if p["torn_id"] == current_user["torn_id"]]

    if my_payments:
        msg = f"Found {len(my_payments)} new payment(s). Subscription extended!"
    elif applied:
        msg = f"Processed {len(applied)} payment(s) for other users. None found for your account."
    else:
        msg = "No new payments found. Send 1 Xanax to our Torn account to subscribe."

    return PaymentCheckResponse(
        new_payments=len(my_payments),
        payments=my_payments,
        message=msg,
    )
