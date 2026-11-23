from threading import Event

import pytest
from fastapi.testclient import TestClient

from api.main import SentimentModel, app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_responds_while_model_is_loading(
    monkeypatch: pytest.MonkeyPatch, stub_sentiment_model: SentimentModel
) -> None:
    started = Event()
    release = Event()

    def load_model() -> SentimentModel:
        started.set()
        assert release.wait(timeout=5)
        return stub_sentiment_model

    monkeypatch.setattr("api.main.load_sentiment_model", load_model)
    with TestClient(app) as loading_client:
        try:
            assert started.wait(timeout=5)
            assert loading_client.get("/health").status_code == 200

            health = loading_client.get("/v1/health")
            assert health.status_code == 503
            assert health.json() == {"status": "loading", "models": {}, "mock": False}

            response = loading_client.post(
                "/v1/sentiment", json={"reviews": [{"id": "r1", "text": "Текст", "rating": None}]}
            )
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "model_not_ready"
        finally:
            release.set()


def test_unknown_route_uses_contract_error_format(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "details": None,
        }
    }


def test_method_not_allowed_uses_contract_error_format(client: TestClient) -> None:
    response = client.get("/v1/sentiment")

    assert response.status_code == 405
    assert response.json() == {
        "error": {
            "code": "method_not_allowed",
            "message": "Method Not Allowed",
            "details": None,
        }
    }
