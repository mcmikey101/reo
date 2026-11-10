"""Миграции Alembic на настоящем PostgreSQL + pgvector.

Нужна отдельная пустая БД: тесты откатывают схему до нуля.
Запуск: TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/reo_test pytest
Без TEST_DATABASE_URL тесты пропускаются (фикстуры database_url и alembic_config — conftest.py).
"""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.models import Base


@pytest.fixture(scope="module")
def engine(database_url: str, alembic_config: Config) -> Iterator[Engine]:
    engine = create_engine(database_url)
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    yield engine
    command.downgrade(alembic_config, "base")
    engine.dispose()


def test_vector_extension_installed(engine: Engine) -> None:
    with engine.connect() as connection:
        installed = connection.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
    assert installed == 1


def test_tables_created(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names())
    assert {"organizations", "users", "points", "alembic_version"} <= tables


def test_models_match_migrations(engine: Engine) -> None:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)
    assert diff == []


def test_delete_organization_cascades(engine: Engine) -> None:
    with engine.begin() as connection:
        org_id = connection.scalar(
            text("INSERT INTO organizations (name) VALUES ('Кофейня') RETURNING id")
        )
        connection.execute(
            text("INSERT INTO points (organization_id, name, address) VALUES (:o, 'Центр', 'ул')"),
            {"o": org_id},
        )
        connection.execute(
            text("INSERT INTO users (organization_id, email, name) VALUES (:o, 'a@b.ru', 'Аня')"),
            {"o": org_id},
        )
        connection.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        points = connection.scalar(text("SELECT count(*) FROM points"))
        users = connection.scalar(text("SELECT count(*) FROM users"))
    assert (points, users) == (0, 0)


def test_user_email_unique_ignoring_case(engine: Engine) -> None:
    with engine.connect() as connection:
        org_id = connection.scalar(
            text("INSERT INTO organizations (name) VALUES ('Сеть') RETURNING id")
        )
        insert = text("INSERT INTO users (organization_id, email, name) VALUES (:o, :e, 'Имя')")
        connection.execute(insert, {"o": org_id, "e": "user@example.com"})
        with pytest.raises(IntegrityError):
            connection.execute(insert, {"o": org_id, "e": "User@Example.com"})
        connection.rollback()


def test_downgrade_and_upgrade_again(engine: Engine, alembic_config: Config) -> None:
    command.downgrade(alembic_config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    command.upgrade(alembic_config, "head")
    assert {"organizations", "users", "points"} <= set(inspect(engine).get_table_names())
