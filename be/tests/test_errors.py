"""Ошибки приложения отдаются в формате контракта (docs/api-contract.md, 1.5)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException

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

    @app.get("/unexpected")
    def unexpected() -> None:
        raise RuntimeError("Внутренние подробности")

    @app.get("/bad-request")
    def bad_request() -> None:
        raise HTTPException(status_code=400, detail="Внутренние подробности парсинга")

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


def test_http_error_has_contract_body() -> None:
    response = make_client().get("/bad-request")

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "validation_error", "message": "Некорректный запрос", "details": None}
    }


def test_unexpected_error_hides_internal_details() -> None:
    client = TestClient(make_client().app, raise_server_exceptions=False)
    response = client.get("/unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Что-то пошло не так. Повторите позже",
            "details": None,
        }
    }
