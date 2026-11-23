"""Состояние фонового анализа CSV-импорта (REO-37).

Revision ID: c4cba5dd6e6b
Revises: ace28cb13ea4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4cba5dd6e6b"
down_revision: str | Sequence[str] | None = "ace28cb13ea4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review_imports", sa.Column("analysis_run_id", sa.Uuid()))
    op.add_column("review_imports", sa.Column("analysis_lease_until", sa.DateTime(timezone=True)))
    op.add_column(
        "review_imports",
        sa.Column("analysis_failed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("review_imports", "analysis_failed")
    op.drop_column("review_imports", "analysis_lease_until")
    op.drop_column("review_imports", "analysis_run_id")
