import re
from datetime import datetime, timezone, timedelta

from config import settings
from db.supabase_client import get_supabase
from db.users import get_user_by_torn_id
from services.torn_api import fetch_own_events

XANAX_DAYS = 30      # subscription days per xanax payment
# Torn item names that count as payment (case-insensitive)
PAYMENT_ITEMS = ["xanax"]

# Regex: extracts the first [player_id] from a Torn event string
_ID_RE   = re.compile(r'\[(\d+)\]')
# Regex: event mentions receiving one of the payment items
_ITEM_RE = re.compile(r'\b(' + '|'.join(PAYMENT_ITEMS) + r')\b', re.IGNORECASE)


def _parse_sender_id(event_text: str) -> int | None:
    m = _ID_RE.search(event_text)
    return int(m.group(1)) if m else None


def _is_payment_event(event_text: str) -> bool:
    return bool(_ITEM_RE.search(event_text))


async def _payment_already_recorded(event_id: str) -> bool:
    sb = get_supabase()
    r = (
        sb.table("payments")
        .select("id")
        .eq("xanax_trade_id", event_id)
        .limit(1)
        .execute()
    )
    return bool(r.data)


async def _extend_subscription(torn_id: int, days: int) -> str:
    """Extends (or starts) a user's premium subscription. Returns new end date string."""
    sb   = get_supabase()
    user = await get_user_by_torn_id(torn_id)
    now  = datetime.now(timezone.utc)

    if user and user.get("subscription_end"):
        current_end = datetime.fromisoformat(
            user["subscription_end"].replace("Z", "+00:00")
        )
        # If still active, extend from current end; if expired, restart from now
        base = current_end if current_end > now else now
    else:
        base = now

    new_end = (base + timedelta(days=days)).isoformat()
    sb.table("users").update({
        "subscription_tier": "premium",
        "subscription_end":  new_end,
    }).eq("torn_id", torn_id).execute()
    return new_end


async def _record_payment(torn_id: int, event_id: str, days: int) -> None:
    sb = get_supabase()
    sb.table("payments").insert({
        "torn_id":         torn_id,
        "xanax_trade_id":  event_id,
        "days_granted":    days,
    }).execute()


async def check_and_apply_payments() -> list[dict]:
    """
    Scans our Torn account's recent events for xanax payments and applies them.
    Returns a list of newly processed payments.
    """
    events = await fetch_own_events(settings.our_torn_api_key)
    applied = []

    for event_id, event_data in events.items():
        text = event_data.get("event", "")

        if not _is_payment_event(text):
            continue
        if await _payment_already_recorded(event_id):
            continue

        sender_id = _parse_sender_id(text)
        if not sender_id:
            continue

        user = await get_user_by_torn_id(sender_id)
        if not user:
            # Unknown user — record payment anyway so it can be applied later
            await _record_payment(sender_id, event_id, XANAX_DAYS)
            continue

        new_end = await _extend_subscription(sender_id, XANAX_DAYS)
        await _record_payment(sender_id, event_id, XANAX_DAYS)

        applied.append({
            "torn_id":     sender_id,
            "torn_name":   user.get("torn_name", str(sender_id)),
            "days_granted": XANAX_DAYS,
            "new_end":      new_end,
            "event_id":     event_id,
        })

    return applied


async def apply_pending_for_user(torn_id: int) -> bool:
    """
    After a new user registers, check if they had already paid before signing up.
    Re-scans all stored payments with matching torn_id that haven't been applied yet.
    Returns True if any subscription time was granted.
    """
    sb = get_supabase()
    r  = (
        sb.table("payments")
        .select("*")
        .eq("torn_id", torn_id)
        .execute()
    )
    if not r.data:
        return False

    granted = False
    for row in r.data:
        # payments were already inserted but subscription wasn't extended (user didn't exist yet)
        await _extend_subscription(torn_id, row["days_granted"])
        granted = True
    return granted
