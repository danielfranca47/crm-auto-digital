from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from core_client import fetch_core_user

security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: int
    email: str
    status: str | None = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authorization header ausente")

    token = credentials.credentials
    user_data = fetch_core_user(token)
    return CurrentUser(
        id=user_data.get("id"),
        email=user_data.get("email"),
        status=user_data.get("status"),
    )
