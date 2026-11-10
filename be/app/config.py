"""Настройки приложения из переменных окружения (см. docs/conventions.md)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DRIVER_SCHEME = "postgresql+psycopg://"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Строка подключения к PostgreSQL. Принимается postgresql://… или postgresql+psycopg://…
    database_url: str | None = None
    # Адрес ML-сервиса
    ml_url: str = "http://ml:8001"
    # Разрешённые источники запросов (фронтенд)
    cors_origins: list[str] = ["http://localhost:5173"]
    # Таймаут проверок /health, секунды
    health_timeout: float = 2.0

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str | None) -> str | None:
        """Приводит обычную строку PostgreSQL к драйверу psycopg 3."""
        if not value:
            return None
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return DRIVER_SCHEME + value[len(prefix) :]
        return value

    @field_validator("ml_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
