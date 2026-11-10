import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.main import create_app

# Порты, на которых гарантированно никто не слушает: соединение отклоняется сразу
UNREACHABLE_DB_URL = "postgresql://user:pass@127.0.0.1:1/reo"
UNREACHABLE_ML_URL = "http://127.0.0.1:9"


def clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch):
    """Задаёт переменные окружения и сбрасывает кэш настроек и engine."""

    def set_env(**values: str | None) -> None:
        for name, value in values.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        clear_caches()

    set_env(DATABASE_URL=UNREACHABLE_DB_URL, ML_URL=UNREACHABLE_ML_URL)
    yield set_env
    clear_caches()


@pytest.fixture
def client(env) -> TestClient:
    return TestClient(create_app())
