from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .catalog import router as catalog_router
from .subscriptions import router as subscriptions_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(catalog_router)
api_router.include_router(subscriptions_router)

__all__ = ["api_router"]
