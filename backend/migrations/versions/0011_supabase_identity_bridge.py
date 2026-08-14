"""Allow Supabase Auth identities to own DayFlow application data.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make the local user table a credential-free mirror of Supabase Auth."""

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("email", existing_type=sa.String(length=320), nullable=True)
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=True,
        )
        batch_op.add_column(sa.Column("phone", sa.String(length=32), nullable=True))
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    has_supabase_auth = connection.scalar(
        sa.text("SELECT to_regclass('auth.users') IS NOT NULL")
    )
    if not has_supabase_auth:
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.handle_dayflow_auth_user()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
          seed_username text;
          seed_display_name text;
        BEGIN
          PERFORM set_config('app.bypass_rls', 'on', true);
          seed_username := lower(COALESCE(
            NULLIF(NEW.raw_user_meta_data->>'username', ''),
            'user_' || left(replace(NEW.id::text, '-', ''), 10)
          ));
          seed_display_name := COALESCE(
            NULLIF(NEW.raw_user_meta_data->>'display_name', ''),
            seed_username
          );

          INSERT INTO public.users (id, email, phone, password_hash, is_active)
          VALUES (NEW.id, NEW.email, NEW.phone, NULL, true)
          ON CONFLICT (id) DO UPDATE
          SET email = EXCLUDED.email,
              phone = EXCLUDED.phone,
              is_active = true,
              updated_at = now();

          INSERT INTO public.profiles (id, username, display_name)
          VALUES (NEW.id, seed_username, left(seed_display_name, 80))
          ON CONFLICT (id) DO NOTHING;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS dayflow_auth_user_changed ON auth.users;
        CREATE TRIGGER dayflow_auth_user_changed
        AFTER INSERT OR UPDATE OF email, phone, raw_user_meta_data ON auth.users
        FOR EACH ROW EXECUTE FUNCTION public.handle_dayflow_auth_user()
        """
    )


def downgrade() -> None:
    """Remove the hosted-auth bridge while preserving existing profile rows."""

    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        has_supabase_auth = connection.scalar(
            sa.text("SELECT to_regclass('auth.users') IS NOT NULL")
        )
        if has_supabase_auth:
            op.execute("DROP TRIGGER IF EXISTS dayflow_auth_user_changed ON auth.users")
        op.execute("DROP FUNCTION IF EXISTS public.handle_dayflow_auth_user")
    op.drop_index("ix_users_phone", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("phone")
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column("email", existing_type=sa.String(length=320), nullable=False)
