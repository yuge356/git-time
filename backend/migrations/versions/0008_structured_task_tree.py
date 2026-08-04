"""Introduce explicit project, module and executable-task roles.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _new_id(dialect_name: str) -> object:
    value = uuid4()
    return value if dialect_name == "postgresql" else value.hex


def _migrate_existing_tree() -> None:
    """Map legacy roots to projects and normalize every branch to three levels."""

    connection = op.get_bind()
    dialect_name = connection.dialect.name
    rows = list(
        connection.execute(
            sa.text(
                "SELECT id, owner_id, parent_id, estimated_seconds, sort_order "
                "FROM tasks"
            )
        ).mappings()
    )
    if not rows:
        return

    by_id = {row["id"]: row for row in rows}
    children: dict[object, list[object]] = {}
    for row in rows:
        parent_id = row["parent_id"]
        if parent_id in by_id:
            children.setdefault(parent_id, []).append(row["id"])

    roots = [
        row
        for row in rows
        if row["parent_id"] is None or row["parent_id"] not in by_id
    ]
    update_node = sa.text(
        "UPDATE tasks SET parent_id = :parent_id, node_type = :node_type, "
        "budget_mode = :budget_mode, fixed_budget_seconds = :fixed_budget_seconds, "
        "estimated_seconds = :estimated_seconds, status = :status, completed_at = NULL, "
        "repeat_rule = :repeat_rule, repeat_end_date = NULL, daily_reminder_time = NULL "
        "WHERE id = :id"
    )

    for root in roots:
        root_budget = int(root["estimated_seconds"] or 0)
        connection.execute(
            update_node,
            {
                "id": root["id"],
                "parent_id": None,
                "node_type": "PROJECT",
                "budget_mode": "FIXED_CAP" if root_budget > 0 else "ROLLUP",
                "fixed_budget_seconds": root_budget if root_budget > 0 else None,
                "estimated_seconds": 0,
                "status": "TODO",
                "repeat_rule": "NONE",
            },
        )

        root_children = [by_id[child_id] for child_id in children.get(root["id"], [])]
        leaf_children = [child for child in root_children if not children.get(child["id"])]
        module_children = [child for child in root_children if children.get(child["id"])]

        if leaf_children:
            module_id = _new_id(dialect_name)
            next_sort = (
                max(
                    (int(child["sort_order"] or 0) for child in root_children),
                    default=-1,
                )
                + 1
            )
            connection.execute(
                sa.text(
                    "INSERT INTO tasks "
                    "(id, owner_id, parent_id, node_type, title, status, estimated_seconds, "
                    "budget_mode, sort_order, repeat_rule) "
                    "VALUES (:id, :owner_id, :parent_id, 'MODULE', :title, 'TODO', 0, "
                    "'ROLLUP', :sort_order, 'NONE')"
                ),
                {
                    "id": module_id,
                    "owner_id": root["owner_id"],
                    "parent_id": root["id"],
                    "title": "未分类",
                    "sort_order": next_sort,
                },
            )
            for leaf in leaf_children:
                connection.execute(
                    sa.text(
                        "UPDATE tasks SET parent_id = :parent_id, node_type = 'TASK', "
                        "budget_mode = 'ROLLUP', fixed_budget_seconds = NULL "
                        "WHERE id = :id"
                    ),
                    {"id": leaf["id"], "parent_id": module_id},
                )

        for module in module_children:
            module_budget = int(module["estimated_seconds"] or 0)
            connection.execute(
                update_node,
                {
                    "id": module["id"],
                    "parent_id": root["id"],
                    "node_type": "MODULE",
                    "budget_mode": "FIXED_CAP" if module_budget > 0 else "ROLLUP",
                    "fixed_budget_seconds": module_budget if module_budget > 0 else None,
                    "estimated_seconds": 0,
                    "status": "TODO",
                    "repeat_rule": "NONE",
                },
            )
            pending = list(children.get(module["id"], []))
            visited: set[object] = set()
            while pending:
                task_id = pending.pop()
                if task_id in visited:
                    continue
                visited.add(task_id)
                pending.extend(children.get(task_id, []))
                connection.execute(
                    sa.text(
                        "UPDATE tasks SET parent_id = :parent_id, node_type = 'TASK', "
                        "budget_mode = 'ROLLUP', fixed_budget_seconds = NULL "
                        "WHERE id = :id"
                    ),
                    {"id": task_id, "parent_id": module["id"]},
                )


def upgrade() -> None:
    """Add role/default columns, normalize legacy rows and enforce the hierarchy."""

    # ``repeat_end_date`` is consumed by both the ORM and the normalization
    # below, but legacy databases created through revision 0007 do not have it.
    # Add it here before touching existing rows so upgrades from 0007 do not
    # fail halfway through and leave the task table on the old schema.
    op.add_column("tasks", sa.Column("repeat_end_date", sa.Date(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("node_type", sa.String(length=16), nullable=False, server_default="PROJECT"),
    )
    op.add_column(
        "tasks",
        sa.Column("budget_mode", sa.String(length=16), nullable=False, server_default="ROLLUP"),
    )
    op.add_column("tasks", sa.Column("fixed_budget_seconds", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("default_estimated_seconds", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("default_repeat_rule", sa.String(length=16), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("default_daily_reminder_time", sa.Time(), nullable=True),
    )

    _migrate_existing_tree()
    op.create_index("ix_tasks_owner_node_type", "tasks", ["owner_id", "node_type"])

    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_tasks_fixed_budget_seconds",
            "tasks",
            "fixed_budget_seconds IS NULL OR fixed_budget_seconds >= 0",
        )
        op.create_check_constraint(
            "ck_tasks_default_estimated_seconds",
            "tasks",
            "default_estimated_seconds IS NULL OR default_estimated_seconds >= 0",
        )
        op.execute(
            """
            CREATE FUNCTION enforce_task_node_hierarchy()
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
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER tasks_enforce_node_hierarchy
            BEFORE INSERT OR UPDATE OF parent_id, owner_id, node_type ON tasks
            FOR EACH ROW
            EXECUTE FUNCTION enforce_task_node_hierarchy()
            """
        )

    if connection.dialect.name != "sqlite":
        op.alter_column("tasks", "node_type", server_default=None)
        op.alter_column("tasks", "budget_mode", server_default=None)


def downgrade() -> None:
    """Remove explicit roles while leaving normalized parent relationships intact."""

    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS tasks_enforce_node_hierarchy ON tasks")
        op.execute("DROP FUNCTION IF EXISTS enforce_task_node_hierarchy")
        op.drop_constraint("ck_tasks_default_estimated_seconds", "tasks", type_="check")
        op.drop_constraint("ck_tasks_fixed_budget_seconds", "tasks", type_="check")
    op.drop_index("ix_tasks_owner_node_type", table_name="tasks")
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("default_daily_reminder_time")
        batch_op.drop_column("default_repeat_rule")
        batch_op.drop_column("default_estimated_seconds")
        batch_op.drop_column("fixed_budget_seconds")
        batch_op.drop_column("budget_mode")
        batch_op.drop_column("node_type")
        batch_op.drop_column("repeat_end_date")
