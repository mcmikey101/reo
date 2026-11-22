import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Отчёт одной загрузки; id используется конвейером анализа как import_id."""

    __tablename__ = "review_imports"
    __table_args__ = (
        UniqueConstraint("id", "source_id"),
        CheckConstraint(
            "total >= 0 AND imported >= 0 AND duplicates >= 0 AND rejected >= 0 "
            "AND total = imported + duplicates + rejected",
            name="counts",
        ),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    total: Mapped[int]
    imported: Mapped[int]
    duplicates: Mapped[int]
    rejected: Mapped[int]
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
