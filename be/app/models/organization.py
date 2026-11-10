from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.point import Point
    from app.models.user import User


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Бизнес-клиент: сеть кафе, магазинов, клиник. Данные организации не видны другим."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(120))
    industry: Mapped[str | None] = mapped_column(String(120))

    users: Mapped[list["User"]] = relationship(back_populates="organization", passive_deletes=True)
    points: Mapped[list["Point"]] = relationship(
        back_populates="organization", passive_deletes=True
    )
