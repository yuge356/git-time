"""Create private accounts, profiles and initial RLS policies.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create module 1 tables and database-enforced ownership policies."""

    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("username", postgresql.CITEXT(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("bio", sa.String(length=300), nullable=True),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Asia/Shanghai",
        ),
        sa.Column(
            "is_searchable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
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
    )
    op.create_index("ix_profiles_username", "profiles", ["username"], unique=True)

    # Custom GUCs are transaction-local. The browser never receives database credentials;
    # only FastAPI can establish either the current-user or trusted-service context.
    op.execute(
        """
        CREATE FUNCTION app_current_user_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        AS $$
          SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_is_service()
        RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $$
          SELECT COALESCE(current_setting('app.bypass_rls', true), '') = 'on'
        $$
        """
    )

    for table in ("users", "profiles"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY users_owner_all ON users
        FOR ALL
        USING (id = app_current_user_id() OR app_is_service())
        WITH CHECK (id = app_current_user_id() OR app_is_service())
        """
    )
    op.execute(
        """
        CREATE POLICY profiles_owner_all ON profiles
        FOR ALL
        USING (id = app_current_user_id() OR app_is_service())
        WITH CHECK (id = app_current_user_id() OR app_is_service())
        """
    )


def downgrade() -> None:
    """Remove module 1 objects in reverse dependency order."""

    op.execute("DROP POLICY IF EXISTS profiles_owner_all ON profiles")
    op.execute("DROP POLICY IF EXISTS users_owner_all ON users")
    op.execute("DROP FUNCTION IF EXISTS app_is_service")
    op.execute("DROP FUNCTION IF EXISTS app_current_user_id")
    op.drop_index("ix_profiles_username", table_name="profiles")
    op.drop_table("profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
