"""Create hierarchical learning tasks and task-level RLS.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tasks, hierarchy constraints, cycle protection and ownership policies."""

    task_status = postgresql.ENUM(
        "TODO",
        "IN_PROGRESS",
        "PAUSED",
        "DONE",
        name="task_status",
        create_type=False,
    )
    task_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            task_status,
            nullable=False,
            server_default="TODO",
        ),
        sa.Column(
            "estimated_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_tasks_id_owner"),
        sa.ForeignKeyConstraint(
            ["parent_id", "owner_id"],
            ["tasks.id", "tasks.owner_id"],
            name="fk_tasks_parent_same_owner",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "estimated_seconds >= 0",
            name="ck_tasks_estimated_seconds",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_tasks_not_own_parent",
        ),
    )
    op.create_index(
        "ix_tasks_owner_parent_sort",
        "tasks",
        ["owner_id", "parent_id", "sort_order"],
    )
    op.create_index("ix_tasks_owner_status", "tasks", ["owner_id", "status"])
    op.create_index("ix_tasks_owner_updated", "tasks", ["owner_id", "updated_at"])

    op.execute(
        """
        CREATE FUNCTION prevent_task_cycle()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.parent_id IS NULL THEN
            RETURN NEW;
          END IF;

          IF NEW.parent_id = NEW.id OR EXISTS (
            WITH RECURSIVE ancestors(id, parent_id) AS (
              SELECT id, parent_id
              FROM tasks
              WHERE id = NEW.parent_id AND owner_id = NEW.owner_id
              UNION ALL
              SELECT task.id, task.parent_id
              FROM tasks AS task
              JOIN ancestors ON task.id = ancestors.parent_id
              WHERE task.owner_id = NEW.owner_id
            )
            SELECT 1 FROM ancestors WHERE id = NEW.id
          ) THEN
            RAISE EXCEPTION 'task hierarchy cannot contain a cycle'
              USING ERRCODE = '23514';
          END IF;

          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tasks_prevent_cycle
        BEFORE INSERT OR UPDATE OF parent_id, owner_id ON tasks
        FOR EACH ROW
        EXECUTE FUNCTION prevent_task_cycle()
        """
    )

    op.execute("ALTER TABLE tasks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tasks FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tasks_owner_select ON tasks
        FOR SELECT
        USING (owner_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY tasks_owner_insert ON tasks
        FOR INSERT
        WITH CHECK (owner_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY tasks_owner_update ON tasks
        FOR UPDATE
        USING (owner_id = app_current_user_id())
        WITH CHECK (owner_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY tasks_owner_delete ON tasks
        FOR DELETE
        USING (owner_id = app_current_user_id())
        """
    )


def downgrade() -> None:
    """Remove task objects in reverse dependency order."""

    op.execute("DROP POLICY IF EXISTS tasks_owner_delete ON tasks")
    op.execute("DROP POLICY IF EXISTS tasks_owner_update ON tasks")
    op.execute("DROP POLICY IF EXISTS tasks_owner_insert ON tasks")
    op.execute("DROP POLICY IF EXISTS tasks_owner_select ON tasks")
    op.execute("DROP TRIGGER IF EXISTS tasks_prevent_cycle ON tasks")
    op.execute("DROP FUNCTION IF EXISTS prevent_task_cycle")
    op.drop_index("ix_tasks_owner_updated", table_name="tasks")
    op.drop_index("ix_tasks_owner_status", table_name="tasks")
    op.drop_index("ix_tasks_owner_parent_sort", table_name="tasks")
    op.drop_table("tasks")
    postgresql.ENUM(name="task_status").drop(op.get_bind(), checkfirst=True)

