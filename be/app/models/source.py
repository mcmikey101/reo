import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Подключение точки: общий источник для CSV и будущего парсера."""

    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("kind IN ('csv', 'parser')", name="kind"),
        CheckConstraint(
            "status IN ('checking', 'collecting', 'ok', 'error', 'paused')", name="status"
        ),
        Index(
            "uq_sources_csv_point", "point_id", unique=True, postgresql_where=text("kind = 'csv'")
        ),
    )

    point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("points.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    platform: Mapped[str | None] = mapped_column(String(60))
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="ok")
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
