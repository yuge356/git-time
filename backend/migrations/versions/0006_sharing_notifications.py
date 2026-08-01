"""Create controlled plan sharing, encouragements and notifications.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create sharing data with participant- and recipient-scoped RLS."""

    encouragement_type = postgresql.ENUM(
        "KEEP_GOING",
        "GREAT_JOB",
        "WELL_DONE",
        "YOU_CAN_DO_IT",
        name="encouragement_type",
        create_type=False,
    )
    notification_type = postgresql.ENUM(
        "PARTNER_INVITE",
        "PARTNER_ACCEPTED",
        "PLAN_SHARED",
        "ENCOURAGEMENT",
        "TASK_COMPLETED",
        name="notification_type",
        create_type=False,
    )
    encouragement_type.create(op.get_bind(), checkfirst=True)
    notification_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "daily_plan_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "daily_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("daily_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "partner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("share_duration", sa.Boolean(), nullable=False, server_default="false"),
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
            "owner_id <> partner_id",
            name="ck_daily_plan_shares_distinct_users",
        ),
    )
    op.create_index(
        "ix_daily_plan_shares_owner",
        "daily_plan_shares",
        ["owner_id", "created_at"],
    )
    op.create_index(
        "ix_daily_plan_shares_partner",
        "daily_plan_shares",
        ["partner_id", "created_at"],
    )
    op.create_index(
        "uq_daily_plan_shares_active_recipient",
        "daily_plan_shares",
        ["daily_plan_id", "partner_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "encouragements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "share_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("daily_plan_shares.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "receiver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("encouragement_type", encouragement_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "sender_id <> receiver_id",
            name="ck_encouragements_distinct_users",
        ),
    )
    op.create_index(
        "ix_encouragements_share_created",
        "encouragements",
        ["share_id", "created_at"],
    )
    op.create_index(
        "ix_encouragements_receiver_created",
        "encouragements",
        ["receiver_id", "created_at"],
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )

    op.execute(
        """
        CREATE FUNCTION validate_plan_share_access()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM daily_plans
            WHERE id = NEW.daily_plan_id
              AND owner_id = NEW.owner_id
              AND deleted_at IS NULL
          ) THEN
            RAISE EXCEPTION 'share owner must own the daily plan'
              USING ERRCODE = '23514';
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM partnerships
            WHERE pair_key = LEAST(NEW.owner_id::text, NEW.partner_id::text)
              || ':' || GREATEST(NEW.owner_id::text, NEW.partner_id::text)
              AND status = 'ACCEPTED'
              AND deleted_at IS NULL
          ) THEN
            RAISE EXCEPTION 'active partnership required'
              USING ERRCODE = '23514';
          END IF;
          IF EXISTS (
            SELECT 1 FROM user_blocks
            WHERE (blocker_id = NEW.owner_id AND blocked_id = NEW.partner_id)
               OR (blocker_id = NEW.partner_id AND blocked_id = NEW.owner_id)
          ) THEN
            RAISE EXCEPTION 'blocked users cannot share plans'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER daily_plan_shares_validate_access
        BEFORE INSERT OR UPDATE OF daily_plan_id, owner_id, partner_id
        ON daily_plan_shares
        FOR EACH ROW EXECUTE FUNCTION validate_plan_share_access()
        """
    )

    op.execute("ALTER TABLE daily_plan_shares ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE daily_plan_shares FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY daily_plan_shares_participant_select ON daily_plan_shares
        FOR SELECT USING (
          owner_id = app_current_user_id()
          OR partner_id = app_current_user_id()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY daily_plan_shares_owner_insert ON daily_plan_shares
        FOR INSERT WITH CHECK (owner_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY daily_plan_shares_participant_update ON daily_plan_shares
        FOR UPDATE USING (
          owner_id = app_current_user_id()
          OR partner_id = app_current_user_id()
        )
        WITH CHECK (
          owner_id = app_current_user_id()
          OR partner_id = app_current_user_id()
        )
        """
    )

    op.execute("ALTER TABLE encouragements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE encouragements FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY encouragements_participant_select ON encouragements
        FOR SELECT USING (
          sender_id = app_current_user_id()
          OR receiver_id = app_current_user_id()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY encouragements_sender_insert ON encouragements
        FOR INSERT WITH CHECK (sender_id = app_current_user_id())
        """
    )

    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY notifications_owner_select ON notifications
        FOR SELECT USING (user_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY notifications_recipient_insert ON notifications
        FOR INSERT WITH CHECK (user_id = app_current_user_id() OR actor_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY notifications_owner_update ON notifications
        FOR UPDATE USING (user_id = app_current_user_id())
        WITH CHECK (user_id = app_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY daily_plans_shared_select ON daily_plans
        FOR SELECT USING (
          EXISTS (
            SELECT 1 FROM daily_plan_shares
            WHERE daily_plan_id = daily_plans.id
              AND partner_id = app_current_user_id()
              AND deleted_at IS NULL
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY daily_plan_items_shared_select ON daily_plan_items
        FOR SELECT USING (
          EXISTS (
            SELECT 1 FROM daily_plan_shares
            WHERE daily_plan_id = daily_plan_items.daily_plan_id
              AND partner_id = app_current_user_id()
              AND deleted_at IS NULL
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY sessions_shared_duration_select ON sessions
        FOR SELECT USING (
          EXISTS (
            SELECT 1
            FROM daily_plan_items
            JOIN daily_plan_shares
              ON daily_plan_shares.daily_plan_id =
                 daily_plan_items.daily_plan_id
            WHERE daily_plan_items.id = sessions.daily_plan_item_id
              AND daily_plan_shares.partner_id = app_current_user_id()
              AND daily_plan_shares.share_duration
              AND daily_plan_shares.deleted_at IS NULL
          )
        )
        """
    )


def downgrade() -> None:
    """Remove social-sharing tables and enums."""

    op.execute("DROP POLICY IF EXISTS sessions_shared_duration_select ON sessions")
    op.execute(
        "DROP POLICY IF EXISTS daily_plan_items_shared_select ON daily_plan_items"
    )
    op.execute("DROP POLICY IF EXISTS daily_plans_shared_select ON daily_plans")
    op.execute("DROP POLICY IF EXISTS notifications_owner_update ON notifications")
    op.execute(
        "DROP POLICY IF EXISTS notifications_recipient_insert ON notifications"
    )
    op.execute("DROP POLICY IF EXISTS notifications_owner_select ON notifications")
    op.execute(
        "DROP POLICY IF EXISTS encouragements_sender_insert ON encouragements"
    )
    op.execute(
        "DROP POLICY IF EXISTS encouragements_participant_select ON encouragements"
    )
    op.execute(
        "DROP POLICY IF EXISTS daily_plan_shares_participant_update ON daily_plan_shares"
    )
    op.execute(
        "DROP POLICY IF EXISTS daily_plan_shares_owner_insert ON daily_plan_shares"
    )
    op.execute(
        "DROP POLICY IF EXISTS daily_plan_shares_participant_select ON daily_plan_shares"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS daily_plan_shares_validate_access ON daily_plan_shares"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_plan_share_access")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(
        "ix_encouragements_receiver_created",
        table_name="encouragements",
    )
    op.drop_index("ix_encouragements_share_created", table_name="encouragements")
    op.drop_table("encouragements")
    op.drop_index(
        "uq_daily_plan_shares_active_recipient",
        table_name="daily_plan_shares",
    )
    op.drop_index("ix_daily_plan_shares_partner", table_name="daily_plan_shares")
    op.drop_index("ix_daily_plan_shares_owner", table_name="daily_plan_shares")
    op.drop_table("daily_plan_shares")
    postgresql.ENUM(name="notification_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="encouragement_type").drop(
        op.get_bind(),
        checkfirst=True,
    )
