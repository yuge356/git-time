"""Add executable-task planned start/end dates for Gantt scheduling.

Revision ID: 0016
Revises: 0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("planned_start_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("planned_end_date", sa.Date(), nullable=True),
    )
    op.create_check_constraint(
        "ck_tasks_planned_dates_order",
        "tasks",
        "planned_start_date IS NULL OR planned_end_date IS NULL "
        "OR planned_start_date <= planned_end_date",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tasks_planned_dates_order",
        "tasks",
        type_="check",
    )
    op.drop_column("tasks", "planned_end_date")
    op.drop_column("tasks", "planned_start_date")
