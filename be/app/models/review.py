import uuid
from datetime import date as ReviewDate

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Review(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Отзыв из CSV или с площадки; точка и организация определяются через источник."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="rating"),
        ForeignKeyConstraint(
            ["import_id", "source_id"],
            ["review_imports.id", "review_imports.source_id"],
            ondelete="CASCADE",
        ),
        # Внешний ID парсера, если получен, включается в dedup_key вместо полей.
        UniqueConstraint("source_id", "dedup_key"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    import_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    date: Mapped[ReviewDate]
    text: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float | None]
    external_id: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(Text)
    dedup_key: Mapped[str] = mapped_column(String(64))
