from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from utils.auth_deps import get_current_user
from utils.crypto import decrypt
from db.users import get_user_by_torn_id
from db.subscriptions import get_subscription
from services.predictor import predict, is_npc
from services.torn_api import TornAPIError, TornUserInactiveError, TornKeyPausedError

router = APIRouter()


class PredictResponse(BaseModel):
    target_id: int
    target_name: str = ""
    predicted_tbs: int
    predicted_str: int | None = None
    predicted_def: int | None = None
    predicted_spd: int | None = None
    predicted_dex: int | None = None
    confidence: str
    method: str
    from_cache: bool
    training_samples: int = 0


@router.get("/{target_id}", response_model=PredictResponse)
async def get_prediction(
    target_id: int,
    current_user: dict = Depends(get_current_user),
):
    if is_npc(target_id):
        raise HTTPException(400, "NPCs cannot be predicted")

    torn_id = current_user["torn_id"]

    user = await get_user_by_torn_id(torn_id)
    if not user:
        raise HTTPException(404, "User not found — please log in again")

    if user["api_key_status"] != "active":
        raise HTTPException(403, f"Your API key is {user['api_key_status']} — please update your key")

    # Free tier users can use rank-based predictions; subscription required for premium ML
    sub = await get_subscription(torn_id)
    if not sub["active"] and user["role"] == "user":
        raise HTTPException(
            402,
            "Subscription expired. Premium: 1 xanax / 30 days sent to our Torn account."
        )

    try:
        api_key = decrypt(user["torn_api_key_encrypted"])
    except Exception:
        raise HTTPException(500, "Failed to decrypt API key")

    try:
        result = await predict(target_id, api_key, requester_torn_id=torn_id)
    except TornUserInactiveError:
        raise HTTPException(403, "Your API key is inactive")
    except TornKeyPausedError:
        raise HTTPException(403, "Your API key is paused")
    except TornAPIError as e:
        if e.code == 6:
            raise HTTPException(404, f"Player {target_id} not found on Torn")
        raise HTTPException(400, f"Torn API error: {e.message}")

    return PredictResponse(**result)
