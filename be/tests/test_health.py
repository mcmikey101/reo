import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.services import health as health_service

FRONTEND_ORIGIN = "http://localhost:5173"


async def _ml_ok() -> str:
    return "ok"


def test_health_all_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_service, "check_db", lambda: "ok")
    monkeypatch.setattr(health_service, "check_ml", _ml_ok)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "ml": "ok"}


def test_health_ml_unreachable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_service, "check_db", lambda: "ok")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "ml": "error"}


def test_health_db_unreachable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_service, "check_ml", _ml_ok)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "error", "ml": "ok"}


def test_health_without_database_url(env, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import create_app

    env(DATABASE_URL=None)
    monkeypatch.setattr(health_service, "check_ml", _ml_ok)

    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json()["db"] == "error"


def test_health_everything_down(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "error", "ml": "error"}


def test_cors_allows_frontend(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={"Origin": FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN


def test_cors_rejects_other_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_swagger_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert "/health" in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@db:5432/reo", "postgresql+psycopg://u:p@db:5432/reo"),
        ("postgres://u:p@db:5432/reo", "postgresql+psycopg://u:p@db:5432/reo"),
        ("postgresql+psycopg://u:p@db:5432/reo", "postgresql+psycopg://u:p@db:5432/reo"),
    ],
)
def test_database_url_uses_psycopg(raw: str, expected: str) -> None:
    assert Settings(database_url=raw).database_url == expected
