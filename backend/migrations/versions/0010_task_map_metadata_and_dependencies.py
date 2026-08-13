"""Add task-map metadata and directed task dependencies.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store reusable priority/due-date fields and dependency edges."""

    connection = op.get_bind()
    is_postgresql = connection.dialect.name == "postgresql"

    # PostgreSQL stores ``task_status`` as a native enum. SQLite stores the
    # same values in a VARCHAR column, so running ALTER TYPE there is both
    # unnecessary and invalid SQL.
    if is_postgresql:
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'BLOCKED'")

    task_priority = sa.Enum(
        "LOW",
        "MEDIUM",
        "HIGH",
        "URGENT",
        name="task_priority",
        native_enum=False,
    )
    op.add_column(
        "tasks",
        sa.Column(
            "priority",
            task_priority,
            nullable=False,
            server_default="MEDIUM",
        ),
    )
    op.add_column("tasks", sa.Column("due_date", sa.Date(), nullable=True))

    op.create_table(
        "task_dependencies",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("task_id", "depends_on_task_id"),
        sa.ForeignKeyConstraint(
            ["task_id", "owner_id"],
            ["tasks.id", "tasks.owner_id"],
            name="fk_task_dependencies_task_same_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_task_id", "owner_id"],
            ["tasks.id", "tasks.owner_id"],
            name="fk_task_dependencies_prerequisite_same_owner",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "task_id <> depends_on_task_id",
            name="ck_task_dependencies_not_self",
        ),
    )
    op.create_index(
        "ix_task_dependencies_owner_task",
        "task_dependencies",
        ["owner_id", "task_id"],
    )
    op.create_index(
        "ix_task_dependencies_owner_prerequisite",
        "task_dependencies",
        ["owner_id", "depends_on_task_id"],
    )

    if is_postgresql:
        op.execute("ALTER TABLE task_dependencies ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE task_dependencies FORCE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY task_dependencies_owner_select ON task_dependencies
            FOR SELECT USING (owner_id = app_current_user_id())
            """
        )
        op.execute(
            """
            CREATE POLICY task_dependencies_owner_insert ON task_dependencies
            FOR INSERT WITH CHECK (owner_id = app_current_user_id())
            """
        )
        op.execute(
            """
            CREATE POLICY task_dependencies_owner_update ON task_dependencies
            FOR UPDATE USING (owner_id = app_current_user_id())
            WITH CHECK (owner_id = app_current_user_id())
            """
        )
        op.execute(
            """
            CREATE POLICY task_dependencies_owner_delete ON task_dependencies
            FOR DELETE USING (owner_id = app_current_user_id())
            """
        )


def downgrade() -> None:
    """Remove dependency edges and reusable task-map metadata."""

    connection = op.get_bind()
    is_postgresql = connection.dialect.name == "postgresql"

    if is_postgresql:
        op.execute(
            "DROP POLICY IF EXISTS task_dependencies_owner_delete ON task_dependencies"
        )
        op.execute(
            "DROP POLICY IF EXISTS task_dependencies_owner_update ON task_dependencies"
        )
        op.execute(
            "DROP POLICY IF EXISTS task_dependencies_owner_insert ON task_dependencies"
        )
        op.execute(
            "DROP POLICY IF EXISTS task_dependencies_owner_select ON task_dependencies"
        )
    op.drop_index(
        "ix_task_dependencies_owner_prerequisite",
        table_name="task_dependencies",
    )
    op.drop_index("ix_task_dependencies_owner_task", table_name="task_dependencies")
    op.drop_table("task_dependencies")
    op.drop_column("tasks", "due_date")
    op.drop_column("tasks", "priority")
    if is_postgresql:
        op.execute("UPDATE tasks SET status = 'PAUSED' WHERE status = 'BLOCKED'")
        previous_task_status = postgresql.ENUM(
            "TODO",
            "IN_PROGRESS",
            "PAUSED",
            "DONE",
            name="task_status_previous",
        )
        previous_task_status.create(connection, checkfirst=False)
        op.execute("ALTER TABLE tasks ALTER COLUMN status DROP DEFAULT")
        op.execute(
            "ALTER TABLE tasks ALTER COLUMN status TYPE task_status_previous "
            "USING status::text::task_status_previous"
        )
        op.execute("DROP TYPE task_status")
        op.execute("ALTER TYPE task_status_previous RENAME TO task_status")
        op.execute("ALTER TABLE tasks ALTER COLUMN status SET DEFAULT 'TODO'::task_status")
