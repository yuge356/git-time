"""Allow one subtask level under executable task nodes.

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


HIERARCHY_FUNCTION = """
CREATE OR REPLACE FUNCTION enforce_task_node_hierarchy()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE parent_type text;
DECLARE grandparent_type text;
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
  WHERE id = NEW.parent_id AND owner_id = NEW.owner_id AND deleted_at IS NULL;

  IF NEW.node_type = 'MODULE' THEN
    IF parent_type IS DISTINCT FROM 'PROJECT' THEN
      RAISE EXCEPTION 'module nodes must be placed under project nodes'
        USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;

  -- Executable tasks may sit under a project, a module, or one extra
  -- subtask level: the parent task itself must sit directly under a
  -- project or module, and the moved node must stay a leaf.
  IF parent_type NOT IN ('PROJECT', 'MODULE', 'TASK') THEN
    RAISE EXCEPTION 'task nodes must be placed under project or module nodes'
      USING ERRCODE = '23514';
  END IF;
  IF parent_type = 'TASK' THEN
    SELECT p.node_type INTO grandparent_type
    FROM tasks p
    WHERE p.id = (
      SELECT t.parent_id FROM tasks t
      WHERE t.id = NEW.parent_id AND t.owner_id = NEW.owner_id AND t.deleted_at IS NULL
    ) AND p.owner_id = NEW.owner_id AND p.deleted_at IS NULL;
    IF grandparent_type IS NULL OR grandparent_type = 'TASK' THEN
      RAISE EXCEPTION 'subtasks cannot contain further subtasks'
        USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
      SELECT 1 FROM tasks c
      WHERE c.parent_id = NEW.id AND c.owner_id = NEW.owner_id AND c.deleted_at IS NULL
    ) THEN
      RAISE EXCEPTION 'only leaf tasks can become subtasks'
        USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END
$$;
"""


STRICT_HIERARCHY_FUNCTION = """
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


def upgrade() -> None:
    """Allow tasks to gain one level of subtasks."""

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    op.execute(HIERARCHY_FUNCTION)


def downgrade() -> None:
    """Restore the strict PROJECT -> MODULE -> TASK hierarchy rule."""

    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    op.execute(STRICT_HIERARCHY_FUNCTION)
