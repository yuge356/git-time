"""Allow task nodes directly under project or module.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow tasks to be placed directly under projects or modules."""

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_task_node_hierarchy()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE parent_type text;
        BEGIN
          IF NEW.node_type = 'PROJECT' THEN
            IF NEW.parent_id IS NOT NULL THEN
              RAISE EXCEPTION 'projects must stay at the top level'
                USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
          END IF;

          IF NEW.parent_id IS NULL THEN
            RAISE EXCEPTION 'module and task nodes require a parent'
              USING ERRCODE = '23514';
          END IF;
          SELECT node_type INTO parent_type
          FROM tasks
          WHERE id = NEW.parent_id AND owner_id = NEW.owner_id;

          IF (NEW.node_type = 'MODULE' AND parent_type IS DISTINCT FROM 'PROJECT')
             OR (NEW.node_type = 'TASK' AND parent_type NOT IN ('PROJECT', 'MODULE')) THEN
            RAISE EXCEPTION 'invalid project/module/task hierarchy'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Restore the strict PROJECT -> MODULE -> TASK hierarchy rule."""

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_task_node_hierarchy()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE parent_type text;
        BEGIN
          IF NEW.node_type = 'PROJECT' THEN
            IF NEW.parent_id IS NOT NULL THEN
              RAISE EXCEPTION 'projects must stay at the top level'
                USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
          END IF;

          IF NEW.parent_id IS NULL THEN
            RAISE EXCEPTION 'module and task nodes require a parent'
              USING ERRCODE = '23514';
          END IF;
          SELECT node_type INTO parent_type
          FROM tasks
          WHERE id = NEW.parent_id AND owner_id = NEW.owner_id;

          IF (NEW.node_type = 'MODULE' AND parent_type IS DISTINCT FROM 'PROJECT')
             OR (NEW.node_type = 'TASK' AND parent_type IS DISTINCT FROM 'MODULE') THEN
            RAISE EXCEPTION 'invalid project/module/task hierarchy'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END
        $$;
        """
    )
