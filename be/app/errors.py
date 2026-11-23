"""Ошибки приложения и их ответы в формате контракта (docs/api-contract.md, 1.5).

Сервисы бросают AppError и его наследников, не зная про HTTP. Обработчик превращает
их в ответ {"error": {"code", "message", "details"}}.
Ошибки параметров FastAPI тоже приводятся к формату контракта.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class AppError(Exception):
    """Ожидаемая ошибка: у неё есть HTTP-код и машинный код из контракта."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "Что-то пошло не так. Повторите позже"

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None):
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    """Записи нет или она принадлежит другой организации: для API это одно и то же."""

    status_code = 404
    code = "not_found"
    message = "Запись не найдена"


class PossibleDuplicateError(AppError):
    status_code = 409
    code = "possible_duplicate"
    message = "Точка с таким названием и адресом уже есть"


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details)
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)


async def handle_http_error(_: Request, exc: HTTPException) -> JSONResponse:
    code, message = {
        400: ("validation_error", "Некорректный запрос"),
        404: ("not_found", "Запись не найдена"),
        405: ("method_not_allowed", "Метод не поддерживается"),
    }.get(exc.status_code, ("request_error", "Не удалось выполнить запрос"))
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, message),
        headers=exc.headers,
    )


async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content=error_body(AppError.code, AppError.message))


async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = []
    for error in exc.errors():
        kind = error["type"]
        field = ".".join(str(part) for part in error["loc"][1:])
        if kind == "missing":
            code, message = "required", "Обязательное поле"
        elif kind == "blank":
            code, message = kind, error["msg"]
        elif kind == "extra_forbidden":
            code, message = "unknown_field", "Неизвестное поле"
        elif kind in {"string_too_long", "too_long"}:
            code, message = "too_long", "Превышен лимит длины"
        elif kind.endswith(("_parsing", "_type")) or kind == "value_error":
            code, message = "invalid_type", "Неверный тип значения"
        else:
            code, message = "invalid_value", "Недопустимое значение"
        fields.append({"field": field, "code": code, "message": message})
    return JSONResponse(
        status_code=422,
        content=error_body("validation_error", "Проверьте поля формы", {"fields": fields}),
    )
