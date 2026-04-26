from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from config import settings

ALGORITHM = "HS256"
EXPIRE_DAYS = 90


def create_jwt(torn_id: int, torn_name: str, role: str = "user") -> str:
    payload = {
        "sub": str(torn_id),
        "name": torn_name,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def verify_jwt(token: str) -> dict:
    """Tagastab payload või tõstab JWTError."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def get_torn_id_from_token(token: str) -> int:
    payload = verify_jwt(token)
    return int(payload["sub"])
