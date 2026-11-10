"""Подключение к PostgreSQL: engine и сессии SQLAlchemy.

Engine создаётся лениво: приложение запускается, даже если БД недоступна
или DATABASE_URL не задан, — тогда /health вернёт db: error.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL не задан")
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": max(1, int(settings.health_timeout))},
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: сессия БД на время запроса."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
