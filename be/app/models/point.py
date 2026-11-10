import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class Point(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Филиал организации. Одинаковый адрес допустим (см. docs/screens.md, M1)."""

    __tablename__ = "points"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(250))
    category: Mapped[str | None] = mapped_column(String(60))

    organization: Mapped["Organization"] = relationship(back_populates="points")
