"""Загрузка через API, реальные ограничения PostgreSQL и выборка по import_id."""

import json
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import date, timedelta
from threading import Barrier

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients import ml
from app.db import get_db
from app.deps import get_current_user
from app.errors import NotFoundError
from app.main import create_app
from app.models import Organization, Point, Review, ReviewImport, ReviewSentiment, Source, User
from app.scope import OrgScope
from app.seed import DEMO_ORG_ID, OTHER_ORG_ID, OTHER_USER_ID, POINTS, seed
from app.services.csv_parser import MAX_CSV_BYTES, parse_csv
from app.services.import_analysis import (
    get_import_analysis,
    run_import_analysis,
    start_import_analysis,
)
from app.services.imports import get_import_reviews, import_csv
from app.services.points import delete_point
from app.services.sentiment import ImportSentimentSummary, analyze_import

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


def sentiment_success(reviews):
    return httpx.Response(
        200,
        json={
            "model_version": "test-model@123",
            "results": [
                {
                    "id": review["id"],
                    "status": "ok",
                    "reason": None,
                    "method": "model",
                    "label": "positive",
                    "probs": {"pos": 0.8, "neu": 0.1, "neg": 0.1},
                    "score": 0.7,
                }
                for review in reversed(reviews)
            ],
        },
    )


@pytest.mark.parametrize(
    ("scores", "expected_counts", "expected_index"),
    [
        ([1, 1, 0, -1], (2, 1, 1), 62.5),
        ([-1, -1, -1], (0, 0, 3), 0),
        ([0.6, -0.5], (1, 0, 1), 52.5),
        ([], (0, 0, 0), None),
    ],
)
def test_import_analysis_index_from_saved_scores(
    api: TestClient, db: Session, scores, expected_counts, expected_index
) -> None:
    other = upload(api).json()
    csv = "date,text,rating\n" + "".join(
        f"2026-11-20,Отзыв {i},5\n" for i in range(len(scores) + 1)
    )
    selected = upload(api, csv.encode()).json()
    assert selected["source_id"] == other["source_id"]

    scope = OrgScope(db, DEMO_ORG_ID)
    reviews = get_import_reviews(scope, uuid.UUID(selected["import_id"]))
    for review, score in zip(reviews[:-1], scores, strict=True):
        label = "positive" if score > 0 else "negative" if score < 0 else "neutral"
        db.add(ReviewSentiment(review_id=review.id, status="done", label=label, score=score))
    db.add(ReviewSentiment(review_id=reviews[-1].id, status="skipped"))
    other_review = get_import_reviews(scope, uuid.UUID(other["import_id"]))[0]
    db.add(ReviewSentiment(review_id=other_review.id, status="done", label="positive", score=1))
    db.commit()

    url = f"/imports/{selected['import_id']}/analysis"
    response = api.get(url)
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["status"] == "done"
    assert analysis["error"] is None
    result = analysis["result"]
    assert result["sentiment_counts"] == dict(
        zip(("positive", "neutral", "negative"), expected_counts, strict=True)
    )
    if expected_index is None:
        assert result["satisfaction_index"] is None
    else:
        assert result["satisfaction_index"] == pytest.approx(expected_index)


def test_import_analysis_reports_partial_failure_and_retries_unsuccessful_reviews(
    api: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.import_analysis.get_sessionmaker", lambda: lambda: nullcontext(db)
    )
    monkeypatch.setattr("app.services.sentiment.SENTIMENT_BATCH_SIZE", 1)
    requests = []
    ml_available = False

    def analyze(_client, reviews):
        review = reviews[0]
        requests.append(review.text)
        if review.text == "Без оценки" and not ml_available:
            raise ml.SentimentError("ml_unavailable")
        return ml.SentimentResponse.model_validate_json(
            sentiment_success([{"id": str(review.id)}]).content
        )

    monkeypatch.setattr("app.services.sentiment.get_sentiment", analyze)
    import_id = upload(api).json()["import_id"]
    url = f"/imports/{import_id}/analysis"
    assert api.get(url).json() == {
        "import_id": import_id,
        "status": "pending",
        "result": None,
        "error": None,
    }
    db.rollback()  # GET использует транзакцию запроса, здесь переиспользуется тестовая сессия.

    response = api.post(url)
    assert response.status_code == 202
    assert response.json()["status"] == "running"
    failed = api.get(url).json()
    assert failed["status"] == "error"
    assert failed["error"]["code"] == "ml_error"
    assert failed["result"] == {
        "sentiment_counts": {"positive": 1, "neutral": 0, "negative": 0},
        "satisfaction_index": 85.0,
    }
    db.rollback()
    assert sorted(requests) == ["Без оценки", "Вкусный кофе"]

    ml_available = True
    assert api.post(url).status_code == 202
    repeated = api.post(url)
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "done"
    assert repeated.json()["result"]["sentiment_counts"]["positive"] == 2
    assert requests[2:] == ["Без оценки"]


def test_import_analysis_access_and_empty_result(api: TestClient, app) -> None:
    upload(api)
    empty_id = upload(api).json()["import_id"]
    url = f"/imports/{empty_id}/analysis"
    response = api.post(url)
    assert response.status_code == 200
    assert response.json() == {
        "import_id": empty_id,
        "status": "done",
        "result": {
            "sentiment_counts": {"positive": 0, "neutral": 0, "negative": 0},
            "satisfaction_index": None,
        },
        "error": None,
    }

    app.dependency_overrides[get_current_user] = lambda: User(organization_id=OTHER_ORG_ID)
    for request in (api.post, api.get):
        foreign = request(url)
        missing = request(f"/imports/{uuid.uuid4()}/analysis")
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json()
        assert request("/imports/invalid/analysis").status_code == 422


def test_sentiment_batches_retry_errors_only(api: TestClient, db: Session, monkeypatch) -> None:
    size = ml.SENTIMENT_BATCH_SIZE
    csv = "date,text,rating\n" + "".join(f"2026-11-20,Отзыв {i},5\n" for i in range(size + 1))
    selected = upload(api, csv.encode()).json()
    other = upload(api).json()
    assert selected["source_id"] == other["source_id"]
    import_id = uuid.UUID(selected["import_id"])
    scope = OrgScope(db, DEMO_ORG_ID)
    requests = []
    delays = []
    monkeypatch.setattr(ml, "sleep", delays.append)

    def respond(request):
        reviews = json.loads(request.content)["reviews"]
        requests.append(reviews)
        if len(requests) <= 4:
            return httpx.Response(503)
        return sentiment_success(reviews)

    with httpx.Client(
        base_url="http://ml:8001", transport=httpx.MockTransport(respond)
    ) as ml_client:
        assert analyze_import(scope, import_id, ml_client) == ImportSentimentSummary(1, 0, size)
        with db.begin():
            errors = db.scalars(
                select(ReviewSentiment).where(ReviewSentiment.status == "error")
            ).all()
            assert len(errors) == size
            assert all(row.reason == "ml_http_503" and row.model_version is None for row in errors)
            completed = db.scalars(
                select(ReviewSentiment).where(ReviewSentiment.status == "done")
            ).one()
            completed_at = completed.analyzed_at

        assert delays == [1, 4, 16]
        assert [len(batch) for batch in requests] == [size, size, size, size, 1]
        assert all(batch == requests[0] for batch in requests[:4])
        assert analyze_import(scope, import_id, ml_client) == ImportSentimentSummary(size + 1, 0, 0)
        assert requests[-1] == requests[0]
        assert analyze_import(scope, import_id, ml_client) == ImportSentimentSummary(size + 1, 0, 0)
        assert len(requests) == 6

    with db.begin():
        results = db.execute(
            select(ReviewSentiment, Review.import_id)
            .join(Review)
            .execution_options(populate_existing=True)
        ).all()
        assert len(results) == size + 1
        for row, owner_import_id in results:
            assert owner_import_id == import_id
            assert (row.status, row.method, row.label, row.reason) == (
                "done",
                "model",
                "positive",
                None,
            )
            assert (row.p_pos, row.p_neu, row.p_neg, row.score) == (0.8, 0.1, 0.1, 0.7)
            assert row.model_version == "test-model@123"
            assert row.analyzed_at is not None
            if str(row.review_id) == requests[4][0]["id"]:
                assert row.analyzed_at == completed_at

    delete_point(scope, OWN_POINT)
    assert db.scalar(select(func.count()).select_from(ReviewSentiment)) == 0


@pytest.mark.parametrize("status", [None, 413, 504], ids=["read-timeout", "http-413", "http-504"])
def test_sentiment_smaller_batches_recover_entire_import(
    api: TestClient, db: Session, monkeypatch, status: int | None
) -> None:
    csv = "date,text,rating\n" + "".join(f"2026-11-20,Отзыв {i},5\n" for i in range(33))
    import_id = uuid.UUID(upload(api, csv.encode()).json()["import_id"])
    scope = OrgScope(db, DEMO_ORG_ID)
    sizes = []
    processed_ids = []
    monkeypatch.setattr(ml, "sleep", lambda _: pytest.fail("Повтор той же пачки"))

    def respond(request):
        reviews = json.loads(request.content)["reviews"]
        sizes.append(len(reviews))
        if len(reviews) > 8:
            if status is None:
                raise httpx.ReadTimeout("ML не успел обработать пачку", request=request)
            return httpx.Response(status)
        processed_ids.extend(review["id"] for review in reviews)
        return sentiment_success(reviews)

    with httpx.Client(base_url="http://ml:8001", transport=httpx.MockTransport(respond)) as client:
        assert analyze_import(scope, import_id, client) == ImportSentimentSummary(33, 0, 0)
        assert analyze_import(scope, import_id, client) == ImportSentimentSummary(33, 0, 0)

    assert sizes == [32, 16, 8, 8, 8, 8, 1]
    assert len(processed_ids) == len(set(processed_ids)) == 33


def test_sentiment_sends_long_review_alone_and_retries_it(
    api: TestClient, db: Session, monkeypatch
) -> None:
    long_text = "Вкусный кофе. " * 800
    csv = "date,text,rating\n" + "".join(f"2026-11-20,Отзыв {i},5\n" for i in range(32))
    csv += f"2026-11-20,{long_text},5\n"
    import_id = uuid.UUID(upload(api, csv.encode()).json()["import_id"])
    scope = OrgScope(db, DEMO_ORG_ID)
    delays = []
    long_review_attempts = []
    monkeypatch.setattr(ml, "sleep", delays.append)

    def respond(request):
        reviews = json.loads(request.content)["reviews"]
        if any(review["text"].startswith("Вкусный кофе") for review in reviews):
            assert len(reviews) == 1
            assert reviews[0]["text"] == long_text[:10_000]
            assert request.extensions["timeout"]["read"] == 120
            long_review_attempts.append(reviews[0]["id"])
            if len(long_review_attempts) == 1:
                raise httpx.ReadTimeout("Медленный отзыв", request=request)
        return sentiment_success(reviews)

    with httpx.Client(base_url="http://ml:8001", transport=httpx.MockTransport(respond)) as client:
        assert analyze_import(scope, import_id, client) == ImportSentimentSummary(33, 0, 0)

    assert delays == [1]
    assert len(long_review_attempts) == 2
    assert long_review_attempts[0] == long_review_attempts[1]


def test_sentiment_empty_or_inaccessible_import_never_calls_ml(
    api: TestClient, db: Session
) -> None:
    empty = uuid.UUID(upload(api, b"date,text,rating\n").json()["import_id"])
    foreign = import_csv(OrgScope(db, OTHER_ORG_ID), OTHER_POINT, VALID_CSV).import_id
    scope = OrgScope(db, DEMO_ORG_ID)

    def fail(_):
        pytest.fail("Не должно быть вызова ML")

    with httpx.Client(base_url="http://ml:8001", transport=httpx.MockTransport(fail)) as client:
        assert analyze_import(scope, empty, client) == ImportSentimentSummary(0, 0, 0)
        for import_id in (foreign, uuid.uuid4()):
            with pytest.raises(NotFoundError, match="Импорт не найден"):
                analyze_import(scope, import_id, client)


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


def test_repeated_uploads_on_one_connection(api: TestClient, db: Session) -> None:
    # Серия загрузок использует одно соединение и запускает подготовку запросов psycopg.
    for _ in range(12):
        assert upload(api).status_code == 201

    assert counts(db) == (1, 12, 2)


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
    [
        b"",
        b"date;text;rating\n",
        b"date,text,rating\n\xff",
        VALID_CSV + b'2026-11-22,"oops,5',
        VALID_CSV + b'2026-11-22,Text with "bare quotes",5',
    ],
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
    assert upload(api).status_code == 201
    url = f"/points/{OWN_POINT}"
    point = api.get(url).json()
    assert (point["sources_count"], point["data_status"]) == (1, "ok")

    response = api.delete(url)
    assert response.status_code == 204 and not response.content
    assert counts(db) == (0, 0, 0)
    assert api.delete(url).status_code == 404


def test_point_rolls_up_source_statuses_in_list(api, db):
    assert upload(api).status_code == 201
    sources = [
        Source(point_id=OWN_POINT, kind="parser", name=status, status=status)
        for status in ("paused", "checking", "error")
    ]
    for source, expected in zip(sources, ("ok", "collecting", "error"), strict=True):
        db.add(source)
        db.flush()
        points = api.get("/points").json()["items"]
        point = next(point for point in points if point["id"] == str(OWN_POINT))
        assert point["data_status"] == expected
    assert point["sources_count"] == 4


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


@pytest.fixture
def committed_point(engine: Engine) -> Iterator[tuple[uuid.UUID, uuid.UUID]]:
    with Session(engine, expire_on_commit=False) as session:
        organization = Organization(name="Проверка параллельного импорта")
        session.add(organization)
        session.flush()
        point = Point(organization_id=organization.id, name="Точка", address="Адрес")
        session.add(point)
        session.commit()

    try:
        yield organization.id, point.id
    finally:
        with Session(engine) as session:
            session.execute(delete(Organization).where(Organization.id == organization.id))
            session.commit()


def test_import_handles_point_deleted_during_csv_parsing(
    engine: Engine, committed_point: tuple[uuid.UUID, uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    organization_id, point_id = committed_point

    def parse_and_delete(content: bytes):
        parsed = parse_csv(content)
        with Session(engine) as session:
            delete_point(OrgScope(session, organization_id), point_id)
        return parsed

    monkeypatch.setattr("app.services.imports.parse_csv", parse_and_delete)
    with Session(engine, autoflush=False) as session:
        with pytest.raises(NotFoundError, match="Точка не найдена"):
            import_csv(OrgScope(session, organization_id), point_id, VALID_CSV)


def test_late_ml_error_cannot_overwrite_a_saved_result(
    engine: Engine, committed_point: tuple[uuid.UUID, uuid.UUID]
) -> None:
    organization_id, point_id = committed_point
    with Session(engine) as session:
        report = import_csv(OrgScope(session, organization_id), point_id, VALID_CSV)
        review = session.scalars(
            select(Review).where(Review.import_id == report.import_id, Review.rating.is_(None))
        ).one()
        review.text = None
        session.commit()

    def success(request):
        results = []
        for review in reversed(json.loads(request.content)["reviews"]):
            has_text = review["text"] is not None
            results.append(
                {
                    "id": review["id"],
                    "status": "ok" if has_text else "skipped",
                    "reason": None if has_text else "no_text_no_rating",
                    "method": "model" if has_text else None,
                    "label": "positive" if has_text else None,
                    "probs": {"pos": 1, "neu": 0, "neg": 0} if has_text else None,
                    "score": 1 if has_text else None,
                }
            )
        return httpx.Response(200, json={"model_version": "test-model", "results": results})

    def late_failure(_):
        # Второй запуск успевает сохранить совпадающую пачку, пока первый ждёт ML.
        with (
            Session(engine) as session,
            httpx.Client(
                base_url="http://ml:8001", transport=httpx.MockTransport(success)
            ) as client,
        ):
            scope = OrgScope(session, organization_id)
            assert analyze_import(scope, report.import_id, client) == ImportSentimentSummary(
                1, 1, 0
            )
        return httpx.Response(422)

    with (
        Session(engine) as session,
        httpx.Client(
            base_url="http://ml:8001", transport=httpx.MockTransport(late_failure)
        ) as client,
    ):
        scope = OrgScope(session, organization_id)
        assert analyze_import(scope, report.import_id, client) == ImportSentimentSummary(1, 1, 0)
        saved = session.execute(
            select(
                Review.text, ReviewSentiment.status, ReviewSentiment.reason, ReviewSentiment.score
            )
            .join(ReviewSentiment)
            .where(Review.import_id == report.import_id)
        ).all()
        assert set(saved) == {
            ("Вкусный кофе", "done", None, 1.0),
            (None, "skipped", "no_text_no_rating", None),
        }


def test_concurrent_imports_create_one_source_and_no_duplicates(
    engine: Engine, committed_point: tuple[uuid.UUID, uuid.UUID]
) -> None:
    organization_id, point_id = committed_point
    barrier = Barrier(2)

    def load():
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            barrier.wait(timeout=10)
            return import_csv(OrgScope(session, organization_id), point_id, VALID_CSV)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: load(), range(2)))
    assert len({r.source_id for r in results}) == 1
    assert sorted((r.imported, r.duplicates) for r in results) == [(0, 2), (2, 0)]
    with Session(engine) as session:
        scope = OrgScope(session, organization_id)
        for result in results:
            assert len(get_import_reviews(scope, result.import_id)) == result.imported


def test_import_analysis_concurrent_starts_and_expired_worker(
    engine: Engine, committed_point: tuple[uuid.UUID, uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    organization_id, point_id = committed_point
    with Session(engine) as db:
        import_id = import_csv(OrgScope(db, organization_id), point_id, VALID_CSV).import_id

    barrier = Barrier(2)

    def start():
        with Session(engine) as db:
            barrier.wait(timeout=10)
            return start_import_analysis(OrgScope(db, organization_id), import_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        starts = list(executor.map(lambda _: start(), range(2)))
    assert [analysis.status for analysis, _ in starts] == ["running", "running"]
    (old_run,) = [run for _, run in starts if run is not None]

    with Session(engine) as db:
        assert get_import_analysis(OrgScope(db, organization_id), import_id).status == "running"

    monkeypatch.setattr(
        "app.services.import_analysis.get_sessionmaker", lambda: lambda: Session(engine)
    )
    replacement_run = None

    def respond_after_expiration(_client, reviews):
        nonlocal replacement_run
        with Session(engine) as db:
            scope = OrgScope(db, organization_id)
            db.execute(
                update(ReviewImport)
                .where(ReviewImport.id == import_id)
                .values(analysis_lease_until=func.clock_timestamp() - timedelta(seconds=1))
            )
            db.commit()
            expired = get_import_analysis(scope, import_id)
            assert expired.status == "error"
            assert expired.error.code == "analysis_failed"
            db.rollback()
            _, replacement_run = start_import_analysis(scope, import_id)
        return ml.SentimentResponse.model_validate_json(
            sentiment_success([{"id": str(review.id)} for review in reviews]).content
        )

    monkeypatch.setattr("app.services.sentiment.get_sentiment", respond_after_expiration)
    run_import_analysis(organization_id, import_id, old_run)
    assert replacement_run is not None and replacement_run != old_run
    with Session(engine) as db:
        assert get_import_analysis(OrgScope(db, organization_id), import_id).status == "running"
        assert db.get(ReviewImport, import_id).analysis_run_id == replacement_run
        assert (
            db.scalar(
                select(func.count())
                .select_from(ReviewSentiment)
                .join(Review)
                .where(Review.import_id == import_id)
            )
            == 0
        )
