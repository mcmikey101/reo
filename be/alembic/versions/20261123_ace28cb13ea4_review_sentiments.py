"""Результаты анализа тональности отзывов (REO-36).

Revision ID: ace28cb13ea4
Revises: b34c5f981e20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ace28cb13ea4"
down_revision: str | Sequence[str] | None = "b34c5f981e20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_sentiments",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(40)),
        sa.Column("method", sa.String(20)),
        sa.Column("label", sa.String(20)),
        sa.Column("p_pos", sa.Float()),
        sa.Column("p_neu", sa.Float()),
        sa.Column("p_neg", sa.Float()),
        sa.Column("score", sa.Float()),
        sa.Column("model_version", sa.Text()),
        sa.Column("analyzed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('done', 'skipped', 'error')", name=op.f("ck_review_sentiments_status")
        ),
        sa.CheckConstraint("score BETWEEN -1 AND 1", name=op.f("ck_review_sentiments_score")),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name=op.f("fk_review_sentiments_review_id_reviews"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("review_id", name=op.f("pk_review_sentiments")),
    )


def downgrade() -> None:
    op.drop_table("review_sentiments")
