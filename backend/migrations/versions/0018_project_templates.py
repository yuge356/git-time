"""Create reusable project templates.

Revision ID: 0018
Revises: 0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create owner-scoped project blueprints with owner-only RLS."""

    op.create_table(
        "project_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("icon", sa.String(length=8), nullable=True),
        sa.Column("preset_key", sa.String(length=40), nullable=True),
        sa.Column(
            "budget_mode",
            sa.Enum("ROLLUP", "FIXED_CAP", name="task_budget_mode", native_enum=False),
            nullable=False,
            server_default="ROLLUP",
        ),
        sa.Column("fixed_budget_seconds", sa.Integer(), nullable=True),
        sa.Column("default_estimated_seconds", sa.Integer(), nullable=True),
        sa.Column("default_repeat_rule", sa.String(length=16), nullable=True),
        sa.Column("structure", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "fixed_budget_seconds IS NULL OR fixed_budget_seconds >= 0",
            name="ck_project_templates_fixed_budget_seconds",
        ),
        sa.CheckConstraint(
            "default_estimated_seconds IS NULL OR default_estimated_seconds >= 0",
            name="ck_project_templates_default_estimated_seconds",
        ),
    )
    op.create_index(
        "ix_project_templates_owner_sort",
        "project_templates",
        ["owner_id", "sort_order"],
    )

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE project_templates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project_templates FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY project_templates_owner_all ON project_templates
        FOR ALL USING (owner_id = app_current_user_id())
        WITH CHECK (owner_id = app_current_user_id())
        """
    )

    # No default privileges exist for the least-privilege runtime role, so
    # every new table has to grant its own access explicitly. The grant is
    # written as a DO block instead of a Python-side role lookup so the same
    # migration also renders correctly in Alembic's offline --sql mode.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dayflow_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE project_templates
              TO dayflow_app;
          END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    """Drop project templates."""

    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute(
            "DROP POLICY IF EXISTS project_templates_owner_all ON project_templates"
        )
    op.drop_index("ix_project_templates_owner_sort", table_name="project_templates")
    op.drop_table("project_templates")
