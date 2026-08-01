"""Create partnership invitations and mutual privacy blocks.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create collaboration relationships with participant-scoped RLS."""

    partnership_status = postgresql.ENUM(
        "PENDING",
        "ACCEPTED",
        "DECLINED",
        name="partnership_status",
        create_type=False,
    )
    partnership_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "partnerships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "requester_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "addressee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pair_key", sa.String(length=73), nullable=False),
        sa.Column("status", partnership_status, nullable=False, server_default="PENDING"),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
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
            "requester_id <> addressee_id",
            name="ck_partnerships_distinct_users",
        ),
    )
    op.create_index(
        "ix_partnerships_requester_status",
        "partnerships",
        ["requester_id", "status"],
    )
    op.create_index(
        "ix_partnerships_addressee_status",
        "partnerships",
        ["addressee_id", "status"],
    )
    op.create_index(
        "uq_partnerships_active_pair",
        "partnerships",
        ["pair_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "user_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "blocker_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "blocked_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
        sa.CheckConstraint(
            "blocker_id <> blocked_id",
            name="ck_user_blocks_distinct_users",
        ),
    )
    op.create_index("ix_user_blocks_blocked", "user_blocks", ["blocked_id"])

    op.execute(
        """
        CREATE FUNCTION validate_partnership_pair_key()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.pair_key <> LEAST(NEW.requester_id::text, NEW.addressee_id::text)
             || ':' ||
             GREATEST(NEW.requester_id::text, NEW.addressee_id::text) THEN
            RAISE EXCEPTION 'invalid partnership pair key'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER partnerships_validate_pair_key
        BEFORE INSERT OR UPDATE OF requester_id, addressee_id, pair_key ON partnerships
        FOR EACH ROW EXECUTE FUNCTION validate_partnership_pair_key()
        """
    )

    op.execute("ALTER TABLE partnerships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE partnerships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY partnerships_participant_select ON partnerships
        FOR SELECT USING (
          requester_id = app_current_user_id()
          OR addressee_id = app_current_user_id()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY partnerships_requester_insert ON partnerships
        FOR INSERT WITH CHECK (requester_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY partnerships_participant_update ON partnerships
        FOR UPDATE USING (
          requester_id = app_current_user_id()
          OR addressee_id = app_current_user_id()
        )
        WITH CHECK (
          requester_id = app_current_user_id()
          OR addressee_id = app_current_user_id()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY partnerships_participant_delete ON partnerships
        FOR DELETE USING (
          requester_id = app_current_user_id()
          OR addressee_id = app_current_user_id()
        )
        """
    )

    op.execute("ALTER TABLE user_blocks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_blocks FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY user_blocks_participant_select ON user_blocks
        FOR SELECT USING (
          blocker_id = app_current_user_id()
          OR blocked_id = app_current_user_id()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY user_blocks_blocker_insert ON user_blocks
        FOR INSERT WITH CHECK (blocker_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY user_blocks_blocker_delete ON user_blocks
        FOR DELETE USING (blocker_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY profiles_discovery_select ON profiles
        FOR SELECT USING (
          (
            is_searchable
            OR EXISTS (
              SELECT 1
              FROM partnerships
              WHERE status = 'ACCEPTED'
                AND deleted_at IS NULL
                AND (
                  (requester_id = profiles.id
                   AND addressee_id = app_current_user_id())
                  OR
                  (addressee_id = profiles.id
                   AND requester_id = app_current_user_id())
                )
            )
          )
          AND NOT EXISTS (
            SELECT 1
            FROM user_blocks
            WHERE (
              blocker_id = profiles.id
              AND blocked_id = app_current_user_id()
            )
            OR (
              blocked_id = profiles.id
              AND blocker_id = app_current_user_id()
            )
          )
        )
        """
    )


def downgrade() -> None:
    """Remove partnerships, privacy blocks and enum types."""

    op.execute("DROP POLICY IF EXISTS profiles_discovery_select ON profiles")
    op.execute("DROP POLICY IF EXISTS user_blocks_blocker_delete ON user_blocks")
    op.execute("DROP POLICY IF EXISTS user_blocks_blocker_insert ON user_blocks")
    op.execute("DROP POLICY IF EXISTS user_blocks_participant_select ON user_blocks")
    op.execute(
        "DROP POLICY IF EXISTS partnerships_participant_delete ON partnerships"
    )
    op.execute(
        "DROP POLICY IF EXISTS partnerships_participant_update ON partnerships"
    )
    op.execute(
        "DROP POLICY IF EXISTS partnerships_requester_insert ON partnerships"
    )
    op.execute(
        "DROP POLICY IF EXISTS partnerships_participant_select ON partnerships"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS partnerships_validate_pair_key ON partnerships"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_partnership_pair_key")
    op.drop_index("ix_user_blocks_blocked", table_name="user_blocks")
    op.drop_table("user_blocks")
    op.drop_index("uq_partnerships_active_pair", table_name="partnerships")
    op.drop_index("ix_partnerships_addressee_status", table_name="partnerships")
    op.drop_index("ix_partnerships_requester_status", table_name="partnerships")
    op.drop_table("partnerships")
    postgresql.ENUM(name="partnership_status").drop(op.get_bind(), checkfirst=True)
