"""Модели SQLAlchemy — таблицы БД (см. docs/db-schema.md).

Каждую новую модель импортируем здесь: Alembic видит только таблицы из Base.metadata.
"""

from app.models.base import Base
from app.models.organization import Organization
from app.models.point import Point
from app.models.user import User

__all__ = ["Base", "Organization", "Point", "User"]
