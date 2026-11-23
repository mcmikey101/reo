"""Источники, CSV-импорты и отзывы (REO-34)

Revision ID: b34c5f981e20
Revises: d638154a4752
Create Date: 2026-11-22 17:26:22.281884
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b34c5f981e20"
down_revision: str | Sequence[str] | None = "d638154a4752"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Родительские таблицы создаются перед зависимыми; существующие точки не меняются.
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("point_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("platform", sa.String(length=60), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="ok", nullable=False),
        sa.Column("last_collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('csv', 'parser')", name=op.f("ck_sources_kind")),
        sa.CheckConstraint(
            "status IN ('checking', 'collecting', 'ok', 'error', 'paused')",
            name=op.f("ck_sources_status"),
        ),
        sa.ForeignKeyConstraint(
            ["point_id"], ["points.id"], name=op.f("fk_sources_point_id_points"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
    )
    op.create_index(op.f("ix_sources_point_id"), "sources", ["point_id"], unique=False)
    op.create_index(
        "uq_sources_csv_point",
        "sources",
        ["point_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'csv'"),
    )
    op.create_table(
        "review_imports",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("rejected", sa.Integer(), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "total >= 0 AND imported >= 0 AND duplicates >= 0 AND rejected >= 0 "
            "AND total = imported + duplicates + rejected",
            name=op.f("ck_review_imports_counts"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_review_imports_source_id_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_imports")),
        sa.UniqueConstraint("id", "source_id", name=op.f("uq_review_imports_id_source_id")),
    )
    op.create_index(
        op.f("ix_review_imports_source_id"), "review_imports", ["source_id"], unique=False
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("rating", sa.Double(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("dedup_key", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name=op.f("ck_reviews_rating")),
        sa.ForeignKeyConstraint(
            ["import_id", "source_id"],
            ["review_imports.id", "review_imports.source_id"],
            name=op.f("fk_reviews_import_id_review_imports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_reviews_source_id_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
        sa.UniqueConstraint("source_id", "dedup_key", name=op.f("uq_reviews_source_id_dedup_key")),
    )
    op.create_index(op.f("ix_reviews_import_id"), "reviews", ["import_id"], unique=False)
    op.create_index(op.f("ix_reviews_source_id"), "reviews", ["source_id"], unique=False)


def downgrade() -> None:
    # Откат удаляет только таблицы REO-34; organizations, users и points сохраняются.
    op.drop_index(op.f("ix_reviews_source_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_import_id"), table_name="reviews")
    op.drop_table("reviews")
    op.drop_index(op.f("ix_review_imports_source_id"), table_name="review_imports")
    op.drop_table("review_imports")
    op.drop_index(
        "uq_sources_csv_point", table_name="sources", postgresql_where=sa.text("kind = 'csv'")
    )
    op.drop_index(op.f("ix_sources_point_id"), table_name="sources")
    op.drop_table("sources")
