"""Загрузка через API, реальные ограничения PostgreSQL и выборка по import_id."""

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.errors import NotFoundError
from app.main import create_app
from app.models import Organization, Point, Review, ReviewImport, Source, User
from app.scope import OrgScope
from app.seed import DEMO_ORG_ID, OTHER_ORG_ID, OTHER_USER_ID, POINTS, seed
from app.services.csv_parser import MAX_CSV_BYTES
from app.services.imports import get_import_reviews, import_csv

OWN_POINTS = [p["id"] for p in POINTS if p["organization_id"] == DEMO_ORG_ID]
OWN_POINT = OWN_POINTS[0]
OTHER_POINT = next(p["id"] for p in POINTS if p["organization_id"] == OTHER_ORG_ID)
VALID_CSV = "date,text,rating\n2026-11-20,Вкусный кофе,5\n2026-11-21,Без оценки,\n".encode()


@pytest.fixture(scope="module")
def engine(database_url: str, alembic_config: Config) -> Iterator[Engine]:
    command.upgrade(alembic_config, "head")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            autoflush=False,
            expire_on_commit=False,
        ) as session:
            seed(session)
            yield session
        transaction.rollback()


@pytest.fixture
def app(env, db: Session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return app


@pytest.fixture
def api(app) -> TestClient:
    return TestClient(app)


def upload(api: TestClient, content: bytes = VALID_CSV, point_id=OWN_POINT):
    return api.post(
        "/imports/csv",
        data={"point_id": str(point_id)},
        files={"file": ("reviews.csv", content, "text/csv")},
    )


def counts(db: Session) -> tuple[int, ...]:
    return tuple(
        db.scalar(select(func.count()).select_from(model))
        for model in (Source, ReviewImport, Review)
    )


def test_partial_import_and_saved_report(api: TestClient, db: Session) -> None:
    response = upload(api, VALID_CSV + "2026-11-22,Текст есть,6\n".encode())

    assert response.status_code == 201
    body = response.json()
    assert (body["total"], body["imported"], body["duplicates"], body["rejected"]) == (3, 2, 0, 1)
    assert body["errors"] == [
        {
            "row": 4,
            "field": "rating",
            "code": "invalid_rating",
            "message": "Оценка должна быть числом от 1 до 5 или пустой",
        }
    ]
    report = db.get(ReviewImport, uuid.UUID(body["import_id"]))
    assert report.errors == body["errors"]
    assert (report.total, report.imported, report.duplicates, report.rejected) == (3, 2, 0, 1)
    source = db.get(Source, uuid.UUID(body["source_id"]))
    assert (source.point_id, source.kind, source.name) == (OWN_POINT, "csv", "Импорт CSV")
    assert source.last_collected_at is not None
    reviews = get_import_reviews(OrgScope(db, DEMO_ORG_ID), report.id)
    assert [(r.text, r.rating, r.date) for r in reviews] == [
        ("Вкусный кофе", 5.0, date(2026, 11, 20)),
        ("Без оценки", None, date(2026, 11, 21)),
    ]
    assert all(r.source_id == report.source_id for r in reviews)


def test_repeat_upload_keeps_original_import_membership(api: TestClient, db: Session) -> None:
    first = upload(api).json()
    second = upload(api).json()

    assert first["source_id"] == second["source_id"]
    assert first["import_id"] != second["import_id"]
    assert (second["imported"], second["duplicates"]) == (0, 2)
    assert counts(db) == (1, 2, 2)
    scope = OrgScope(db, DEMO_ORG_ID)
    assert len(get_import_reviews(scope, uuid.UUID(first["import_id"]))) == 2
    assert get_import_reviews(scope, uuid.UUID(second["import_id"])) == []


def test_dedup_inside_file_and_between_files(api: TestClient, db: Session) -> None:
    response = upload(api, VALID_CSV + " 2026-11-20 , Вкусный кофе ,5.0\n".encode())
    assert (response.json()["imported"], response.json()["duplicates"]) == (2, 1)

    changed_name = api.post(
        "/imports/csv",
        data={"point_id": str(OWN_POINT)},
        files={"file": ("another-name.txt", VALID_CSV, "application/octet-stream")},
    )
    assert changed_name.status_code == 201
    assert changed_name.json()["duplicates"] == 2
    assert counts(db) == (1, 2, 2)


def test_new_import_selects_only_its_new_reviews(api: TestClient, db: Session) -> None:
    upload(api)
    body = upload(api, VALID_CSV + "2026-11-22,Новый отзыв,4.5\n".encode()).json()

    assert (body["imported"], body["duplicates"]) == (1, 2)
    reviews = get_import_reviews(OrgScope(db, DEMO_ORG_ID), uuid.UUID(body["import_id"]))
    assert [(r.text, r.rating) for r in reviews] == [("Новый отзыв", 4.5)]


def test_same_file_is_allowed_in_different_points(api: TestClient, db: Session) -> None:
    first = upload(api).json()
    second = upload(api, point_id=OWN_POINTS[1]).json()

    assert second["imported"] == 2
    assert first["source_id"] != second["source_id"]
    assert counts(db) == (2, 2, 4)


@pytest.mark.parametrize("point_id", [OTHER_POINT, uuid.uuid4()])
def test_unknown_and_other_org_points_are_same_404(api: TestClient, db: Session, point_id):
    response = upload(api, point_id=point_id)

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Точка не найдена", "details": None}
    }
    assert counts(db) == (0, 0, 0)


def test_scope_follows_current_user_and_hides_imports(app, db: Session) -> None:
    api = TestClient(app)
    own = upload(api).json()
    # Даже уже загруженный в identity map импорт другой организации недоступен.
    assert db.get(ReviewImport, uuid.UUID(own["import_id"])) is not None
    with pytest.raises(NotFoundError, match="Импорт не найден"):
        get_import_reviews(OrgScope(db, OTHER_ORG_ID), uuid.UUID(own["import_id"]))
    with pytest.raises(NotFoundError, match="Импорт не найден"):
        get_import_reviews(OrgScope(db, OTHER_ORG_ID), uuid.uuid4())

    app.dependency_overrides[get_current_user] = lambda: db.get(User, OTHER_USER_ID)
    assert upload(api).status_code == 404
    other = upload(api, point_id=OTHER_POINT)
    assert other.status_code == 201
    assert other.json()["imported"] == 2
    assert (
        len(get_import_reviews(OrgScope(db, OTHER_ORG_ID), uuid.UUID(other.json()["import_id"])))
        == 2
    )


@pytest.mark.parametrize(
    "content",
    [b"", b"date;text;rating\n", b"date,text,rating\n\xff", VALID_CSV + b'2026-11-22,"oops,5'],
)
def test_invalid_file_does_not_save_anything(api: TestClient, db: Session, content: bytes):
    response = upload(api, content)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_csv"
    assert "row" in response.json()["error"]["details"]
    assert counts(db) == (0, 0, 0)


@pytest.mark.parametrize("content", [b"date,text,rating\n", b"date,text,rating\n,,\n"])
def test_empty_and_fully_rejected_imports_have_saved_reports(api, db, content):
    response = upload(api, content)

    assert response.status_code == 201
    body = response.json()
    assert body["imported"] == body["duplicates"] == 0
    assert body["total"] == body["rejected"] == len(body["errors"])
    assert get_import_reviews(OrgScope(db, DEMO_ORG_ID), uuid.UUID(body["import_id"])) == []
    assert counts(db) == (1, 1, 0)


def test_oversized_file(api: TestClient, db: Session) -> None:
    response = upload(api, b"a" * (MAX_CSV_BYTES + 1))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert response.json()["error"]["details"] == {"max_bytes": MAX_CSV_BYTES}
    assert counts(db) == (0, 0, 0)


def test_malformed_multipart_uses_contract_error(api: TestClient, db: Session) -> None:
    response = api.post(
        "/imports/csv", content=b"invalid", headers={"Content-Type": "multipart/form-data"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert counts(db) == (0, 0, 0)


@pytest.mark.parametrize(
    ("data", "files", "field", "code"),
    [
        ({}, {"file": ("r.csv", VALID_CSV)}, "point_id", "required"),
        ({"point_id": str(OWN_POINT)}, {}, "file", "required"),
        ({"point_id": "not-uuid"}, {"file": ("r.csv", VALID_CSV)}, "point_id", "invalid_type"),
        ({"point_id": str(OWN_POINT), "file": "text"}, {}, "file", "invalid_type"),
    ],
)
def test_form_errors_follow_api_contract(api, db, data, files, field, code):
    response = api.post("/imports/csv", data=data, files=files)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert (error["details"]["fields"][0]["field"], error["details"]["fields"][0]["code"]) == (
        field,
        code,
    )
    assert counts(db) == (0, 0, 0)


def test_large_import_deduplicates_across_insert_batches(api: TestClient, db: Session) -> None:
    rows = [f"2026-11-20,Отзыв {i},5" for i in range(501)]
    content = ("date,text,rating\n" + "\n".join(rows + rows)).encode()
    body = upload(api, content).json()

    assert (body["total"], body["imported"], body["duplicates"]) == (1002, 501, 501)
    assert len(get_import_reviews(OrgScope(db, DEMO_ORG_ID), uuid.UUID(body["import_id"]))) == 501


def test_save_failure_rolls_back_entire_import(db: Session, monkeypatch) -> None:
    def fail_commit():
        # Отзывы уже вставлены в транзакцию: ошибка не должна оставить их или отчёт.
        assert counts(db) == (1, 1, 2)
        raise RuntimeError("Тестовая ошибка сохранения")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="Тестовая ошибка"):
        import_csv(OrgScope(db, DEMO_ORG_ID), OWN_POINT, VALID_CSV)

    assert counts(db) == (0, 0, 0)


def test_point_deletion_cascades_to_source_import_and_reviews(api, db):
    upload(api)
    db.execute(delete(Point).where(Point.id == OWN_POINT))
    db.flush()

    assert counts(db) == (0, 0, 0)


def test_parser_reviews_share_schema_and_allow_no_text(api, db):
    body = upload(api).json()
    source = Source(point_id=OWN_POINT, kind="parser", name="Площадка", platform="example")
    db.add(source)
    db.flush()
    db.add(Review(source_id=source.id, date=date(2026, 11, 22), rating=3, dedup_key="a" * 64))
    db.flush()

    assert counts(db) == (2, 1, 3)
    assert len(get_import_reviews(OrgScope(db, DEMO_ORG_ID), uuid.UUID(body["import_id"]))) == 2


def test_database_rejects_import_from_another_source(api, db):
    body = upload(api).json()
    source = Source(point_id=OTHER_POINT, kind="csv", name="Импорт CSV")
    db.add(source)
    db.flush()
    db.add(
        Review(
            source_id=source.id,
            import_id=uuid.UUID(body["import_id"]),
            date=date(2026, 11, 22),
            text="Чужой источник",
            dedup_key="b" * 64,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_concurrent_imports_create_one_source_and_no_duplicates(engine: Engine) -> None:
    # Отдельные соединения требуют зафиксированной точки вне транзакционной фикстуры db.
    with Session(engine, expire_on_commit=False) as session:
        organization = Organization(name="Проверка параллельного импорта")
        session.add(organization)
        session.flush()
        point = Point(organization_id=organization.id, name="Точка", address="Адрес")
        session.add(point)
        session.commit()

    barrier = Barrier(2)

    def load():
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            barrier.wait(timeout=10)
            return import_csv(OrgScope(session, organization.id), point.id, VALID_CSV)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: load(), range(2)))
        assert len({r.source_id for r in results}) == 1
        assert sorted((r.imported, r.duplicates) for r in results) == [(0, 2), (2, 0)]
        with Session(engine) as session:
            assert (
                len(get_import_reviews(OrgScope(session, organization.id), results[0].import_id))
                == results[0].imported
            )
            assert (
                len(get_import_reviews(OrgScope(session, organization.id), results[1].import_id))
                == results[1].imported
            )
    finally:
        with Session(engine) as session:
            session.execute(delete(Organization).where(Organization.id == organization.id))
            session.commit()
