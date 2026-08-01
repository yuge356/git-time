"""Create daily plans, plan items and session-to-item links.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def create_owner_policies(table: str) -> None:
    """Enable forced RLS and add owner-only CRUD policies."""

    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_owner_select ON {table} "
        "FOR SELECT USING (owner_id = app_current_user_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_owner_insert ON {table} "
        "FOR INSERT WITH CHECK (owner_id = app_current_user_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_owner_update ON {table} "
        "FOR UPDATE USING (owner_id = app_current_user_id()) "
        "WITH CHECK (owner_id = app_current_user_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_owner_delete ON {table} "
        "FOR DELETE USING (owner_id = app_current_user_id())"
    )


def upgrade() -> None:
    """Create daily planning and enforce cross-table ownership."""

    item_status = postgresql.ENUM(
        "TODO",
        "IN_PROGRESS",
        "PAUSED",
        "DONE",
        name="daily_plan_item_status",
        create_type=False,
    )
    item_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "daily_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_date", sa.Date(), nullable=False),
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
        sa.UniqueConstraint("id", "owner_id", name="uq_daily_plans_id_owner"),
        sa.UniqueConstraint("owner_id", "plan_date", name="uq_daily_plans_owner_date"),
    )
    op.create_index(
        "ix_daily_plans_owner_date",
        "daily_plans",
        ["owner_id", "plan_date"],
    )

    op.create_table(
        "daily_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", item_status, nullable=False, server_default="TODO"),
        sa.Column("estimated_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["daily_plan_id", "owner_id"],
            ["daily_plans.id", "daily_plans.owner_id"],
            name="fk_daily_plan_items_plan_same_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "estimated_seconds >= 0",
            name="ck_daily_plan_items_estimated_seconds",
        ),
    )
    op.create_index(
        "ix_daily_plan_items_plan_sort",
        "daily_plan_items",
        ["daily_plan_id", "sort_order"],
    )
    op.create_index(
        "ix_daily_plan_items_owner_updated",
        "daily_plan_items",
        ["owner_id", "updated_at"],
    )

    op.add_column(
        "sessions",
        sa.Column("daily_plan_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sessions_daily_plan_item",
        "sessions",
        "daily_plan_items",
        ["daily_plan_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_sessions_daily_item_started",
        "sessions",
        ["daily_plan_item_id", "started_at"],
    )
    op.create_check_constraint(
        "ck_sessions_has_subject",
        "sessions",
        "task_id IS NOT NULL OR daily_plan_item_id IS NOT NULL",
    )

    op.execute(
        """
        CREATE FUNCTION validate_daily_item_task_owner()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.task_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM tasks
            WHERE id = NEW.task_id AND owner_id = NEW.owner_id
          ) THEN
            RAISE EXCEPTION 'daily item task must belong to the same owner'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER daily_items_validate_task_owner
        BEFORE INSERT OR UPDATE OF task_id, owner_id ON daily_plan_items
        FOR EACH ROW EXECUTE FUNCTION validate_daily_item_task_owner()
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_session_daily_item_owner()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE linked_task uuid;
        BEGIN
          IF NEW.daily_plan_item_id IS NOT NULL THEN
            SELECT task_id INTO linked_task
            FROM daily_plan_items
            WHERE id = NEW.daily_plan_item_id
              AND owner_id = NEW.owner_id
              AND deleted_at IS NULL;
            IF NOT FOUND THEN
              RAISE EXCEPTION 'session daily item must belong to the same owner'
                USING ERRCODE = '23514';
            END IF;
            IF linked_task IS DISTINCT FROM NEW.task_id THEN
              RAISE EXCEPTION 'session task must match daily item task'
                USING ERRCODE = '23514';
            END IF;
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER sessions_validate_daily_item_owner
        BEFORE INSERT OR UPDATE OF daily_plan_item_id, task_id, owner_id ON sessions
        FOR EACH ROW EXECUTE FUNCTION validate_session_daily_item_owner()
        """
    )
    create_owner_policies("daily_plans")
    create_owner_policies("daily_plan_items")


def downgrade() -> None:
    """Remove daily planning objects in reverse dependency order."""

    for table in ("daily_plan_items", "daily_plans"):
        for operation in ("delete", "update", "insert", "select"):
            op.execute(f"DROP POLICY IF EXISTS {table}_owner_{operation} ON {table}")
    op.execute(
        "DROP TRIGGER IF EXISTS sessions_validate_daily_item_owner ON sessions"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_session_daily_item_owner")
    op.execute(
        "DROP TRIGGER IF EXISTS daily_items_validate_task_owner ON daily_plan_items"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_daily_item_task_owner")
    op.drop_constraint("ck_sessions_has_subject", "sessions", type_="check")
    op.drop_index("ix_sessions_daily_item_started", table_name="sessions")
    op.drop_constraint(
        "fk_sessions_daily_plan_item",
        "sessions",
        type_="foreignkey",
    )
    op.drop_column("sessions", "daily_plan_item_id")
    op.drop_index("ix_daily_plan_items_owner_updated", table_name="daily_plan_items")
    op.drop_index("ix_daily_plan_items_plan_sort", table_name="daily_plan_items")
    op.drop_table("daily_plan_items")
    op.drop_index("ix_daily_plans_owner_date", table_name="daily_plans")
    op.drop_table("daily_plans")
    postgresql.ENUM(name="daily_plan_item_status").drop(
        op.get_bind(),
        checkfirst=True,
    )
