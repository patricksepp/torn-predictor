from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from utils.auth_deps import get_current_user
from db.users import get_user_by_torn_id
from services.training import process_attacks_for_user

router = APIRouter()


class UploadResponse(BaseModel):
    inserted: int
    skipped: int
    own_tbs: int | None = None
    message: str = ""


@router.post("/upload-attacks", response_model=UploadResponse)
async def upload_attacks(current_user: dict = Depends(get_current_user)):
    torn_id = current_user["torn_id"]

    user = await get_user_by_torn_id(torn_id)
    if not user:
        raise HTTPException(404, "User not found — please log in again")

    if user["api_key_status"] != "active":
        raise HTTPException(403, f"API key is {user['api_key_status']}")

    result = await process_attacks_for_user(torn_id)

    if "error" in result:
        raise HTTPException(400, result["error"])

    inserted = result["inserted"]
    msg = (
        f"Processed {inserted} new attack(s) into training data."
        if inserted > 0
        else "No new attacks to process."
    )

    return UploadResponse(
        inserted=inserted,
        skipped=result["skipped"],
        own_tbs=result.get("own_tbs"),
        message=msg,
    )
