"""Let an invitation recipient read the requester's profile.

``profiles_discovery_select`` only exposed searchable profiles and profiles
already joined by an ACCEPTED partnership. A user who switched discovery off
after sending an invitation therefore became unreadable to the person they
invited, and the whole partnership list failed with "User not found" -- the
recipient could never see, accept or decline the request. Pending
invitations now grant the same narrow read the acceptance already does.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PARTICIPANT_DISCOVERY_POLICY = """
CREATE POLICY profiles_discovery_select ON profiles
FOR SELECT USING (
  (
    is_searchable
    OR EXISTS (
      SELECT 1
      FROM partnerships
      WHERE status IN ('ACCEPTED', 'PENDING')
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

ACCEPTED_ONLY_DISCOVERY_POLICY = """
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


def upgrade() -> None:
    """Include pending invitations in the profile discovery policy."""

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    op.execute("DROP POLICY IF EXISTS profiles_discovery_select ON profiles")
    op.execute(PARTICIPANT_DISCOVERY_POLICY)


def downgrade() -> None:
    """Restrict profile discovery back to accepted partnerships."""

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    op.execute("DROP POLICY IF EXISTS profiles_discovery_select ON profiles")
    op.execute(ACCEPTED_ONLY_DISCOVERY_POLICY)
