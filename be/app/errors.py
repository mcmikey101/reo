"""Ошибки приложения и их ответы в формате контракта (docs/api-contract.md, 1.5).

Сервисы бросают AppError и его наследников, не зная про HTTP. Обработчик превращает
их в ответ {"error": {"code", "message", "details"}}.
Обработчики RequestValidationError, HTTPException и 500 добавятся вместе с API точек (E1).
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details)
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
