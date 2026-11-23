"""Модели SQLAlchemy — таблицы БД (см. docs/db-schema.md).

Каждую новую модель импортируем здесь: Alembic видит только таблицы из Base.metadata.
"""

from app.models.base import Base
from app.models.organization import Organization
from app.models.point import Point
from app.models.review import Review
from app.models.review_import import ReviewImport
from app.models.review_sentiment import ReviewSentiment
from app.models.source import Source
from app.models.user import User

__all__ = [
    "Base",
    "Organization",
    "Point",
    "Review",
    "ReviewImport",
    "ReviewSentiment",
    "Source",
    "User",
]
