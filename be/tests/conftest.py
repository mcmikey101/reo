import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_engine, get_sessionmaker
from app.main import create_app

BE_DIR = Path(__file__).resolve().parent.parent

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


# Тесты на настоящем PostgreSQL + pgvector. Нужна отдельная БД: тесты миграций удаляют
# все таблицы. Без TEST_DATABASE_URL тесты, которым нужна БД, пропускаются.


@pytest.fixture(scope="session")
def database_url() -> str:
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL не задан")
    # Та же нормализация строки, что и у приложения: postgresql:// → postgresql+psycopg://
    return Settings(database_url=raw_url).database_url


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    config = Config(str(BE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BE_DIR / "alembic"))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    return config
