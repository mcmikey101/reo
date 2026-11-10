"""Ошибки приложения отдаются в формате контракта (docs/api-contract.md, 1.5)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import NotFoundError, register_error_handlers


def make_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/default")
    def default() -> None:
        raise NotFoundError()

    @app.get("/custom")
    def custom() -> None:
        raise NotFoundError("Точка не найдена")

    return TestClient(app)


def test_not_found_default_message() -> None:
    response = make_client().get("/default")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Запись не найдена", "details": None}
    }


def test_not_found_custom_message() -> None:
    response = make_client().get("/custom")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Точка не найдена"


def test_create_app_registers_handlers(client: TestClient) -> None:
    from app.errors import AppError

    assert AppError in client.app.exception_handlers
