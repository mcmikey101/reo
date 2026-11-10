import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Сотрудник организации. Пароль появится в E10 (вход по логину и паролю)."""

    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(120))

    organization: Mapped["Organization"] = relationship(back_populates="users")


# Email уникален без учёта регистра: по нему входят в сервис
Index("uq_users_email_lower", func.lower(User.email), unique=True)
