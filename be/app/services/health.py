"""Проверка состояния частей системы для GET /health."""

import asyncio
import logging

from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.clients import ml as ml_client
from app.config import get_settings
from app.db import get_engine
from app.schemas.health import HealthResponse, MlStatus, PartStatus

logger = logging.getLogger(__name__)


def check_db() -> PartStatus:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # /health не должен падать ни при какой ошибке БД
        logger.warning("Проверка БД не прошла: %r", exc)
        return "error"
    return "ok"


async def check_ml() -> MlStatus:
    settings = get_settings()
    try:
        status = await ml_client.get_health(settings.ml_url, settings.health_timeout)
    except Exception as exc:  # таймаут, отказ соединения, неверный JSON
        logger.warning("Проверка ML не прошла: %r", exc)
        return "error"
    if status == "error":
        logger.warning("ML-сервис не подтвердил готовность модели")
    return status


async def get_health() -> HealthResponse:
    db_status, ml_status = await asyncio.gather(run_in_threadpool(check_db), check_ml())
    return HealthResponse(db=db_status, ml=ml_status)
