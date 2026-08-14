"""Allow the Supabase connection owner to enter the runtime database role.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Permit explicit SET ROLE without inheriting runtime privileges by default."""

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    role_exists = connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dayflow_app')")
    )
    if role_exists:
        op.execute(
            "GRANT dayflow_app TO postgres WITH INHERIT FALSE, SET TRUE"
        )


def downgrade() -> None:
    """Remove the explicit role-switch permission while retaining membership metadata."""

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    role_exists = connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dayflow_app')")
    )
    if role_exists:
        op.execute(
            "GRANT dayflow_app TO postgres WITH INHERIT FALSE, SET FALSE"
        )
