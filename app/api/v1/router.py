from fastapi import APIRouter

from app.api.v1.endpoints.appointments import router as appointments_router
from app.api.v1.endpoints.payments_webhook import router as payments_router
from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.media import router as media_router
from app.api.v1.endpoints.config import router as config_router
from app.api.v1.endpoints.tenants import router as tenants_router
from app.api.v1.endpoints.resources import router as resources_router
from app.api.v1.endpoints.customers import router as customers_router
from app.api.v1.endpoints.services import router as services_router
from app.api.v1.endpoints.providers import router as providers_router
from app.api.v1.endpoints.availabilities import router as availabilities_router
from app.api.v1.endpoints.appointments_crud import router as appointments_crud_router
from app.api.v1.endpoints.payments_crud import router as payments_crud_router
from app.api.v1.endpoints.media_crud import router as media_crud_router
from app.api.v1.endpoints.chat_messages import router as chat_messages_router
from app.api.v1.endpoints.stats import router as stats_router
from app.api.v1.endpoints.resource_context import router as resource_context_router
from app.api.v1.endpoints.traces import router as traces_router
from app.api.v1.endpoints.whatsapp import whatsapp_router, whatsapp_admin_router
from app.api.v1.endpoints.knowledge import router as knowledge_router

api_router = APIRouter()
api_router.include_router(appointments_router)
api_router.include_router(payments_router)
api_router.include_router(ai_router)
api_router.include_router(media_router)
api_router.include_router(config_router)
api_router.include_router(whatsapp_router)
api_router.include_router(whatsapp_admin_router)

api_router.include_router(tenants_router, prefix="", tags=["Tenants"])
api_router.include_router(resources_router, prefix="", tags=["Resources"])
api_router.include_router(customers_router, prefix="", tags=["Customers"])
api_router.include_router(services_router, prefix="", tags=["Services"])
api_router.include_router(providers_router, prefix="", tags=["Providers"])
api_router.include_router(availabilities_router, prefix="", tags=["Availabilities"])
api_router.include_router(appointments_crud_router, prefix="", tags=["Appointments"])
api_router.include_router(payments_crud_router, tags=["Payments"])
api_router.include_router(media_crud_router, tags=["Media"])
api_router.include_router(chat_messages_router, tags=["Chat"])
api_router.include_router(stats_router, tags=["Stats"])
api_router.include_router(resource_context_router, tags=["ResourceContext"])
api_router.include_router(traces_router, prefix="", tags=["Traces"])
api_router.include_router(knowledge_router, tags=["Knowledge"])