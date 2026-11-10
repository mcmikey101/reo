from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.services import health as health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Состояние API, БД и ML")
async def health() -> HealthResponse:
    """Всегда 200: API работает. Состояние БД и ML — в полях `db` и `ml`."""
    return await health_service.get_health()
