from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .users import router as users_router
from .catalog import router as catalog_router
from .subscriptions import router as subscriptions_router
from .ai_profiles import router as ai_profiles_router
from .whatsapp_connections import router as whatsapp_connections_router
from .whatsapp_instances import router as whatsapp_instances_router
from .whatsapp_send import router as whatsapp_send_router
from .webhooks_kiwify import router as webhooks_kiwify_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(webhooks_kiwify_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(catalog_router)
api_router.include_router(subscriptions_router)
api_router.include_router(ai_profiles_router)
api_router.include_router(whatsapp_connections_router)
api_router.include_router(whatsapp_instances_router)
api_router.include_router(whatsapp_send_router)

__all__ = ["api_router"]
