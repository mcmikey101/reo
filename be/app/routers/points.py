from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from app.deps import Scope
from app.schemas.points import PointCreate, PointList, PointListParams, PointOut, PointUpdate
from app.services import points


class ErrorContent(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None


class ErrorResponse(BaseModel):
    error: ErrorContent


NOT_FOUND = {"model": ErrorResponse, "description": "Точка не найдена"}
DUPLICATE = {"model": ErrorResponse, "description": "Возможный дубль точки"}

router = APIRouter(
    prefix="/points",
    tags=["points"],
    responses={422: {"model": ErrorResponse, "description": "Ошибка валидации"}},
)


@router.get("")
def list_points(scope: Scope, params: Annotated[PointListParams, Query()]) -> PointList:
    """Список точек организации с поиском и пагинацией."""
    return points.list_points(scope, params)


@router.get("/{id}", responses={404: NOT_FOUND})
def get_point(id: UUID, scope: Scope) -> PointOut:
    """Получить точку по идентификатору."""
    return points.get_point(scope, id)


@router.post("", status_code=201, responses={409: DUPLICATE})
def create_point(data: PointCreate, scope: Scope, allow_duplicate: bool = False) -> PointOut:
    """Создать точку организации."""
    return points.create_point(scope, data, allow_duplicate=allow_duplicate)


@router.patch("/{id}", responses={404: NOT_FOUND, 409: DUPLICATE})
def update_point(
    id: UUID, data: PointUpdate, scope: Scope, allow_duplicate: bool = False
) -> PointOut:
    """Изменить переданные поля точки."""
    return points.update_point(scope, id, data, allow_duplicate=allow_duplicate)


@router.delete("/{id}", status_code=204, response_class=Response, responses={404: NOT_FOUND})
def delete_point(id: UUID, scope: Scope) -> None:
    """Удалить точку, её источники и отзывы."""
    points.delete_point(scope, id)
