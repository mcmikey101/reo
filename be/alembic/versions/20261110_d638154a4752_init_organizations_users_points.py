"""Минимальная схема E0: organizations, users, points и расширение pgvector

Revision ID: d638154a4752
Revises:
Create Date: 2026-11-10 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d638154a4752"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _organization_id(table: str) -> list:
    return [
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=f"fk_{table}_organization_id_organizations",
            ondelete="CASCADE",
        ),
    ]


def upgrade() -> None:
    # Векторы для эмбеддингов (E6). Образ pgvector/pgvector:pg16 уже содержит расширение
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "organizations",
        _id(),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("industry", sa.String(length=120), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )

    op.create_table(
        "users",
        _id(),
        *_organization_id("users"),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "points",
        _id(),
        *_organization_id("points"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("address", sa.String(length=250), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_points"),
    )
    op.create_index("ix_points_organization_id", "points", ["organization_id"])


def downgrade() -> None:
    op.drop_table("points")
    op.drop_table("users")
    op.drop_table("organizations")
    # Расширение vector не удаляем: оно не принадлежит этой миграции целиком
    # и может использоваться другими объектами БД
