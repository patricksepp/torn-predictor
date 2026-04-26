from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from utils.jwt_utils import verify_jwt

bearer = HTTPBearer()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    try:
        payload = verify_jwt(creds.credentials)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return {
        "torn_id":   int(payload["sub"]),
        "torn_name": payload.get("name", ""),
        "role":      payload.get("role", "user"),
    }


def require_moderator(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("moderator", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Moderator access required")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
