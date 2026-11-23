"""Заглушка текущего пользователя, seed и изоляция организаций (REO-27).

Тесты проверки изоляции через API точек идут на PostgreSQL (TEST_DATABASE_URL,
см. conftest.py). Каждый тест работает внутри транзакции, которая откатывается.
"""

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
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
    response = api.get("/points")

    assert response.status_code == 200
    assert {uuid.UUID(point["id"]) for point in response.json()["items"]} == DEMO_POINT_IDS


def test_get_own_point(api: TestClient) -> None:
    response = api.get(f"/points/{DEMO_POINT_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(DEMO_POINT_ID)


def test_get_other_org_point_is_404(api: TestClient) -> None:
    response = api.get(f"/points/{OTHER_POINT_ID}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_get_missing_point_is_same_404(api: TestClient) -> None:
    response = api.get(f"/points/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_patch_other_org_point_is_404_and_unchanged(api: TestClient, db: Session) -> None:
    name_before = point_name(db, OTHER_POINT_ID)

    response = api.patch(f"/points/{OTHER_POINT_ID}", json={"name": "Чужое имя"})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert point_name(db, OTHER_POINT_ID) == name_before


def test_delete_other_org_point_is_404_and_kept(api: TestClient, db: Session) -> None:
    response = api.delete(f"/points/{OTHER_POINT_ID}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert point_name(db, OTHER_POINT_ID) is not None


def test_own_point_can_be_changed(api: TestClient, db: Session) -> None:
    response = api.patch(f"/points/{DEMO_POINT_ID}", json={"name": "Новое имя"})

    assert response.status_code == 200
    assert point_name(db, DEMO_POINT_ID) == "Новое имя"


def test_other_user_sees_only_own_organization(app, db: Session) -> None:
    # В E10 меняется только get_current_user — фильтр следует за пользователем
    app.dependency_overrides[get_current_user] = lambda: db.get(User, OTHER_USER_ID)
    api = TestClient(app)

    listed = {uuid.UUID(point["id"]) for point in api.get("/points").json()["items"]}

    assert listed == OTHER_POINT_IDS
    assert api.get(f"/points/{OTHER_POINT_ID}").status_code == 200
    assert api.get(f"/points/{DEMO_POINT_ID}").status_code == 404


def test_create_and_patch_point(api: TestClient) -> None:
    response = api.post(
        "/points", json={"name": "  Кофейня  ", "address": " Адрес ", "category": " кафе "}
    )
    assert response.status_code == 201
    point = response.json()
    assert (point["name"], point["address"], point["category"]) == ("Кофейня", "Адрес", "кафе")
    assert "organization_id" not in point
    assert point["created_at"].endswith("Z") and point["updated_at"].endswith("Z")
    assert (point["sources_count"], point["data_status"]) == (0, "no_sources")

    url = f"/points/{point['id']}"
    assert api.patch(url, json={}).json() == point
    response = api.patch(url, json={"address": "Новый адрес", "category": None})
    assert response.status_code == 200
    assert response.json()["category"] is None
    assert response.json()["address"] == "Новый адрес"
    assert response.json()["name"] == point["name"]
    assert api.get(url).json() == response.json()


def test_possible_duplicate_can_be_confirmed_on_create_and_patch(api: TestClient) -> None:
    existing = api.post("/points", json={"name": "Точка  в центре", "address": "Улица  1"}).json()
    request = {"name": "  тОЧКА в центре ", "address": "улица 1"}
    response = api.post("/points", json=request)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "possible_duplicate"
    assert error["details"]["existing_point"] == {
        field: existing[field] for field in ("id", "name", "address")
    }
    assert api.post("/points?allow_duplicate=true", json=request).status_code == 201

    distinct = api.post("/points", json={"name": request["name"], "address": "Улица 2"}).json()
    url = f"/points/{distinct['id']}"
    assert api.patch(url, json={"address": "Улица 2"}).status_code == 200
    assert api.patch(url, json={"address": request["address"]}).status_code == 409
    assert api.get(url).json()["address"] == "Улица 2"
    assert api.patch(f"{url}?allow_duplicate=true", json={"address": "улица 1"}).status_code == 200


def test_search_pagination_and_stable_sort(api: TestClient) -> None:
    points = [
        api.post("/points", json={"name": "Стойка", "address": address}).json()
        for address in ("Проспект 100%", "Квартал 100%", "Квартал 1000")
    ]
    params = {"q": "КВАРТАЛ 100", "sort": "-name", "limit": 1}
    ids = sorted(point["id"] for point in points[1:])
    for offset, expected_id in enumerate(ids):
        page = api.get("/points", params={**params, "offset": offset}).json()
        assert (page["limit"], page["offset"], page["total"]) == (1, offset, 2)
        assert [point["id"] for point in page["items"]] == [expected_id]
    assert api.get("/points", params={**params, "offset": 10}).json() == {
        "items": [],
        "total": 2,
        "limit": 1,
        "offset": 10,
    }
    assert api.get("/points", params={"q": "100%"}).json()["total"] == 2
    assert api.get("/points", params={"q": "СТОЙКА"}).json()["total"] == 3


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
