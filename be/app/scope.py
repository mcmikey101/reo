"""Доступ к данным в пределах организации текущего пользователя.

Сервисы работают с данными организации только через OrgScope: фильтр по organization_id
задаётся здесь один раз, а не вручную в каждом запросе. Запись другой организации
для API не существует — OrgScope.get отвечает NotFoundError, как для несуществующей.

OrgScope работает с моделями, у которых есть своя колонка organization_id (points, users…).
Таблицы, связанные с организацией через родителя (отзыв → точка), фильтруются join'ом
с родителем: select = scope.select(Point).join(...) или where(Review.point_id.in_(...)).
"""

import uuid
from typing import Any, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Base

ModelT = TypeVar("ModelT", bound=Base)


class OrgScope:
    def __init__(self, db: Session, organization_id: uuid.UUID) -> None:
        self.db = db
        self.organization_id = organization_id

    def select(self, model: type[ModelT]) -> Select[tuple[ModelT]]:
        """SELECT записей модели только этой организации. Дальше — where, order_by и т. п."""
        return select(model).where(_organization_column(model) == self.organization_id)

    def get(
        self, model: type[ModelT], record_id: uuid.UUID, *, message: str | None = None
    ) -> ModelT:
        """Запись этой организации по id. Нет записи или она чужая — NotFoundError.

        Читаем запросом, а не db.get(): тот вернул бы объект из identity map без фильтра.
        """
        record = self.db.scalar(self.select(model).where(model.id == record_id))
        if record is None:
            raise NotFoundError(message)
        return record

    def add(self, record: ModelT) -> ModelT:
        """Добавляет новую запись в сессию от имени этой организации."""
        _organization_column(type(record))
        record.organization_id = self.organization_id
        self.db.add(record)
        return record


def _organization_column(model: type[Base]) -> Any:
    column = getattr(model, "organization_id", None)
    if column is None:
        raise TypeError(
            f"У модели {model.__name__} нет organization_id: фильтруйте её join'ом "
            "с родительской таблицей, у которой он есть"
        )
    return column
