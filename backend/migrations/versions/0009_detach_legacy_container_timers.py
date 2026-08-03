"""Detach legacy daily timers from project and module containers.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Preserve old daily entries as ad-hoc snapshots after tree normalization."""

    connection = op.get_bind()
    legacy_container_ids = "SELECT id FROM tasks WHERE node_type <> 'TASK'"
    connection.execute(
        sa.text(
            "UPDATE sessions SET task_id = NULL "
            "WHERE daily_plan_item_id IS NOT NULL "
            f"AND task_id IN ({legacy_container_ids})"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE daily_plan_items SET task_id = NULL "
            f"WHERE task_id IN ({legacy_container_ids})"
        )
    )


def downgrade() -> None:
    """Detached snapshot links cannot be reconstructed unambiguously."""

