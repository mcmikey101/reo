"""Заглушка текущего пользователя, seed и изоляция организаций (REO-27).

Тесты с БД идут на настоящем PostgreSQL (TEST_DATABASE_URL, см. conftest.py), каждый — внутри
транзакции, которая откатывается: после тестов БД остаётся как была.
Эндпоинтов с данными ещё нет, поэтому изоляцию проверяем тестовым роутером /_test/points
на настоящих зависимостях get_current_user и get_scope.
"""

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import Scope, get_current_user
from app.errors import NotFoundError
from app.main import create_app
from app.models import Organization, Point, User
from app.scope import OrgScope
from app.seed import DEMO_ORG_ID, DEMO_USER_ID, OTHER_ORG_ID, OTHER_USER_ID, POINTS, seed

DEMO_POINT_IDS = {row["id"] for row in POINTS if row["organization_id"] == DEMO_ORG_ID}
OTHER_POINT_IDS = {row["id"] for row in POINTS if row["organization_id"] == OTHER_ORG_ID}
DEMO_POINT_ID = min(DEMO_POINT_IDS)
OTHER_POINT_ID = min(OTHER_POINT_IDS)

NOT_FOUND = {"error": {"code": "not_found", "message": "Точка не найдена", "details": None}}


# --- Тестовый роутер: так будут устроены настоящие эндпоинты точек ---

points_router = APIRouter(prefix="/_test/points")


class RenameBody(BaseModel):
    name: str


@points_router.get("")
def list_points(scope: Scope) -> list[uuid.UUID]:
    return [point.id for point in scope.db.scalars(scope.select(Point))]


@points_router.get("/{point_id}")
def read_point(point_id: uuid.UUID, scope: Scope) -> dict[str, str]:
    point = scope.get(Point, point_id, message="Точка не найдена")
    return {"id": str(point.id), "name": point.name}


@points_router.patch("/{point_id}")
def rename_point(point_id: uuid.UUID, body: RenameBody, scope: Scope) -> dict[str, str]:
    point = scope.get(Point, point_id, message="Точка не найдена")
    point.name = body.name
    scope.db.commit()
    return {"id": str(point.id), "name": point.name}


@points_router.delete("/{point_id}", status_code=204)
def delete_point(point_id: uuid.UUID, scope: Scope) -> None:
    point = scope.get(Point, point_id, message="Точка не найдена")
    scope.db.delete(point)
    scope.db.commit()


# --- Фикстуры ---


@pytest.fixture(scope="module")
def engine(database_url: str, alembic_config: Config) -> Iterator[Engine]:
    command.upgrade(alembic_config, "head")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Сессия с seed-данными внутри внешней транзакции; commit в коде — это savepoint."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    seed(session)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def app(env, db: Session):
    app = create_app()
    app.include_router(points_router)
    app.dependency_overrides[get_db] = lambda: db
    return app


@pytest.fixture
def api(app) -> TestClient:
    return TestClient(app)


def point_name(db: Session, point_id: uuid.UUID) -> str | None:
    """Имя точки прямо из БД, мимо identity map сессии."""
    db.expire_all()
    return db.scalar(select(Point.name).where(Point.id == point_id))


# --- Заглушка текущего пользователя ---


def test_current_user_is_demo_user(db: Session) -> None:
    user = get_current_user(db)

    assert user.id == DEMO_USER_ID
    assert user.organization_id == DEMO_ORG_ID
    assert user.organization.name == "Кофейня «Зерно»"


def test_current_user_without_seed_fails_loudly() -> None:
    class EmptySession:
        def get(self, *_):
            return None

    with pytest.raises(RuntimeError, match="python -m app.seed"):
        get_current_user(EmptySession())  # type: ignore[arg-type]


# --- Seed ---


def test_seed_has_two_organizations_with_points(db: Session) -> None:
    for org_id in (DEMO_ORG_ID, OTHER_ORG_ID):
        assert db.get(Organization, org_id) is not None
        points = db.scalar(select(func.count()).where(Point.organization_id == org_id))
        users = db.scalar(select(func.count()).where(User.organization_id == org_id))
        assert points >= 1
        assert users >= 1


def test_seed_is_idempotent(db: Session) -> None:
    def counts() -> tuple[int, int, int]:
        return tuple(
            db.scalar(select(func.count()).select_from(m)) for m in (Organization, User, Point)
        )

    before = counts()

    assert seed(db) == {"organizations": 0, "users": 0, "points": 0}
    assert counts() == before


# --- Изоляция через API ---


def test_list_shows_only_own_points(api: TestClient) -> None:
    response = api.get("/_test/points")

    assert response.status_code == 200
    assert {uuid.UUID(point_id) for point_id in response.json()} == DEMO_POINT_IDS


def test_get_own_point(api: TestClient) -> None:
    response = api.get(f"/_test/points/{DEMO_POINT_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(DEMO_POINT_ID)


def test_get_other_org_point_is_404(api: TestClient) -> None:
    response = api.get(f"/_test/points/{OTHER_POINT_ID}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_get_missing_point_is_same_404(api: TestClient) -> None:
    response = api.get(f"/_test/points/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_patch_other_org_point_is_404_and_unchanged(api: TestClient, db: Session) -> None:
    name_before = point_name(db, OTHER_POINT_ID)

    response = api.patch(f"/_test/points/{OTHER_POINT_ID}", json={"name": "Взлом"})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert point_name(db, OTHER_POINT_ID) == name_before


def test_delete_other_org_point_is_404_and_kept(api: TestClient, db: Session) -> None:
    response = api.delete(f"/_test/points/{OTHER_POINT_ID}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert point_name(db, OTHER_POINT_ID) is not None


def test_own_point_can_be_changed(api: TestClient, db: Session) -> None:
    response = api.patch(f"/_test/points/{DEMO_POINT_ID}", json={"name": "Новое имя"})

    assert response.status_code == 200
    assert point_name(db, DEMO_POINT_ID) == "Новое имя"


def test_other_user_sees_only_own_organization(app, db: Session) -> None:
    # В E10 меняется только get_current_user — фильтр следует за пользователем
    app.dependency_overrides[get_current_user] = lambda: db.get(User, OTHER_USER_ID)
    api = TestClient(app)

    listed = {uuid.UUID(point_id) for point_id in api.get("/_test/points").json()}

    assert listed == OTHER_POINT_IDS
    assert api.get(f"/_test/points/{OTHER_POINT_ID}").status_code == 200
    assert api.get(f"/_test/points/{DEMO_POINT_ID}").status_code == 404


# --- OrgScope напрямую ---


def test_scope_get_ignores_identity_map(db: Session) -> None:
    # Чужая точка уже загружена в сессию, но scope её всё равно не отдаёт
    assert db.get(Point, OTHER_POINT_ID) is not None

    with pytest.raises(NotFoundError):
        OrgScope(db, DEMO_ORG_ID).get(Point, OTHER_POINT_ID)


def test_scope_add_sets_organization(db: Session) -> None:
    scope = OrgScope(db, DEMO_ORG_ID)

    point = scope.add(Point(name="Новая", address="Москва, ул. Новая, 1"))
    db.flush()

    own = {p.id for p in db.scalars(scope.select(Point))}
    other = {p.id for p in db.scalars(OrgScope(db, OTHER_ORG_ID).select(Point))}
    assert point.organization_id == DEMO_ORG_ID
    assert point.id in own
    assert point.id not in other


def test_scope_rejects_model_without_organization_id() -> None:
    with pytest.raises(TypeError, match="organization_id"):
        OrgScope(None, DEMO_ORG_ID).select(Organization)  # type: ignore[arg-type]
