"""Add task recurrence and daily reminder settings.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist recurrence and optional daily reminder time on tasks."""

    op.add_column(
        "tasks",
        sa.Column(
            "repeat_rule",
            sa.String(length=16),
            nullable=False,
            server_default="NONE",
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("daily_reminder_time", sa.Time(), nullable=True),
    )


def downgrade() -> None:
    """Remove task recurrence settings."""

    op.drop_column("tasks", "daily_reminder_time")
    op.drop_column("tasks", "repeat_rule")
