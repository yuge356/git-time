"""Create reliable, offline-synchronizable study sessions.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create session state, integrity triggers, indexes and ownership RLS."""

    session_status = postgresql.ENUM(
        "RUNNING",
        "PAUSED",
        "COMPLETED",
        name="session_status",
        create_type=False,
    )
    session_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", session_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "duration_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "duration_seconds >= 0",
            name="ck_sessions_duration_seconds",
        ),
        sa.CheckConstraint(
            """
            (status = 'RUNNING' AND last_resumed_at IS NOT NULL AND ended_at IS NULL)
            OR (status = 'PAUSED' AND last_resumed_at IS NULL AND ended_at IS NULL)
            OR (status = 'COMPLETED' AND last_resumed_at IS NULL AND ended_at IS NOT NULL)
            """,
            name="ck_sessions_state_timestamps",
        ),
    )
    op.create_index(
        "ix_sessions_owner_started",
        "sessions",
        ["owner_id", "started_at"],
    )
    op.create_index(
        "ix_sessions_task_started",
        "sessions",
        ["task_id", "started_at"],
    )
    op.create_index(
        "ix_sessions_owner_updated",
        "sessions",
        ["owner_id", "updated_at"],
    )
    op.create_index(
        "uq_sessions_one_active_owner",
        "sessions",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('RUNNING', 'PAUSED') AND deleted_at IS NULL"
        ),
    )

    op.execute(
        """
        CREATE FUNCTION validate_session_task_owner()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.task_id IS NOT NULL AND NOT EXISTS (
            SELECT 1
            FROM tasks
            WHERE id = NEW.task_id
              AND owner_id = NEW.owner_id
          ) THEN
            RAISE EXCEPTION 'session task must belong to the same owner'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER sessions_validate_task_owner
        BEFORE INSERT OR UPDATE OF task_id, owner_id ON sessions
        FOR EACH ROW
        EXECUTE FUNCTION validate_session_task_owner()
        """
    )

    op.execute("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sessions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY sessions_owner_select ON sessions
        FOR SELECT
        USING (owner_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY sessions_owner_insert ON sessions
        FOR INSERT
        WITH CHECK (owner_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY sessions_owner_update ON sessions
        FOR UPDATE
        USING (owner_id = app_current_user_id())
        WITH CHECK (owner_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY sessions_owner_delete ON sessions
        FOR DELETE
        USING (owner_id = app_current_user_id())
        """
    )


def downgrade() -> None:
    """Remove session objects in reverse dependency order."""

    op.execute("DROP POLICY IF EXISTS sessions_owner_delete ON sessions")
    op.execute("DROP POLICY IF EXISTS sessions_owner_update ON sessions")
    op.execute("DROP POLICY IF EXISTS sessions_owner_insert ON sessions")
    op.execute("DROP POLICY IF EXISTS sessions_owner_select ON sessions")
    op.execute("DROP TRIGGER IF EXISTS sessions_validate_task_owner ON sessions")
    op.execute("DROP FUNCTION IF EXISTS validate_session_task_owner")
    op.drop_index("uq_sessions_one_active_owner", table_name="sessions")
    op.drop_index("ix_sessions_owner_updated", table_name="sessions")
    op.drop_index("ix_sessions_task_started", table_name="sessions")
    op.drop_index("ix_sessions_owner_started", table_name="sessions")
    op.drop_table("sessions")
    postgresql.ENUM(name="session_status").drop(op.get_bind(), checkfirst=True)

