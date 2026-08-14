"""Support phone and password accounts without an SMS provider.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_alias_aware_trigger() -> None:
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
          identity_email text;
          identity_phone text;
          phone_digits text;
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

          phone_digits := substring(
            lower(COALESCE(NEW.email, ''))
            from '^phone\\.([1-9][0-9]{7,14})@phone\\.dayflow\\.invalid$'
          );
          IF NEW.phone IS NULL AND phone_digits IS NOT NULL THEN
            identity_email := NULL;
            identity_phone := '+' || phone_digits;
          ELSE
            identity_email := NEW.email;
            identity_phone := NEW.phone;
          END IF;

          INSERT INTO public.users (id, email, phone, password_hash, is_active)
          VALUES (NEW.id, identity_email, identity_phone, NULL, true)
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
        "REVOKE EXECUTE ON FUNCTION public.handle_dayflow_auth_user() "
        "FROM PUBLIC, anon, authenticated"
    )


def upgrade() -> None:
    """Normalize internal phone aliases in the Supabase identity mirror."""

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    has_supabase_auth = connection.scalar(
        sa.text("SELECT to_regclass('auth.users') IS NOT NULL")
    )
    if has_supabase_auth:
        _create_alias_aware_trigger()


def downgrade() -> None:
    """Keep existing identity rows; restoring the old trigger is unnecessary."""

