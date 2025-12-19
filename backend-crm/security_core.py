from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from core_client import fetch_core_entitlements, fetch_core_user

security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: int
    email: str
    status: str | None = None
    token: str | None = None
    entitlements: dict | None = None


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
        token=token,
    )


async def require_crm_access(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    entitlements = fetch_core_entitlements(current_user.token or "")

    product_entries = entitlements.get("products", []) if isinstance(entitlements, dict) else []
    has_crm = any(
        entry.get("product_code") == "crm" and entry.get("status") == "active"
        for entry in product_entries
    )

    if not has_crm:
        raise HTTPException(status_code=403, detail="Assinatura do produto CRM ausente ou inativa")

    current_user.entitlements = entitlements
    return current_user
