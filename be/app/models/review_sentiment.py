import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ReviewSentiment(TimestampMixin, Base):
    """Последний результат анализа тональности отзыва."""

    __tablename__ = "review_sentiments"
    __table_args__ = (
        CheckConstraint("status IN ('done', 'skipped', 'error')", name="status"),
        CheckConstraint("score BETWEEN -1 AND 1", name="score"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(40))
    method: Mapped[str | None] = mapped_column(String(20))
    label: Mapped[str | None] = mapped_column(String(20))
    p_pos: Mapped[float | None]
    p_neu: Mapped[float | None]
    p_neg: Mapped[float | None]
    score: Mapped[float | None]
    model_version: Mapped[str | None] = mapped_column(Text)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
