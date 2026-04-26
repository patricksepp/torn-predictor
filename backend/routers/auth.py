from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.torn_api import (
    validate_api_key,
    TornAPIError, TornUserInactiveError, TornKeyPausedError, TornAccessError,
)
from db.users import (
    get_user_by_torn_id, create_user, update_user_on_login,
)
from utils.jwt_utils import create_jwt

router = APIRouter()


class LoginRequest(BaseModel):
    api_key: str


class LoginResponse(BaseModel):
    token: str
    torn_id: int
    torn_name: str
    role: str
    subscription_tier: str
    is_new_user: bool


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(400, "API key is required")

    # 1. Validate via Torn API
    try:
        info = await validate_api_key(api_key)
    except TornUserInactiveError:
        raise HTTPException(403, "API key is inactive (user not active for 7 days)")
    except TornKeyPausedError:
        raise HTTPException(403, "API key is paused")
    except TornAccessError:
        raise HTTPException(403, "API key access level too low (Limited or higher required)")
    except TornAPIError as e:
        raise HTTPException(400, f"Torn API error: {e.message}")

    torn_id   = info["torn_id"]
    torn_name = info["name"]

    # 2. Look up by torn_id (NOT api_key — identity never changes)
    try:
        existing = await get_user_by_torn_id(torn_id)
        is_new   = existing is None

        if existing:
            user = await update_user_on_login(torn_id, torn_name, api_key)
            role = user["role"]
            tier = user["subscription_tier"]
        else:
            user = await create_user(torn_id, torn_name, api_key)
            role = "user"
            tier = "free"
    except Exception as e:
        raise HTTPException(500, f"Database error: {type(e).__name__}: {e}")

    # 3. Return JWT (identity = torn_id)
    token = create_jwt(torn_id=torn_id, torn_name=torn_name, role=role)

    return LoginResponse(
        token=token,
        torn_id=torn_id,
        torn_name=torn_name,
        role=role,
        subscription_tier=tier,
        is_new_user=is_new,
    )
