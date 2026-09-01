"""Project-template API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.task import TaskBudgetMode, TaskNodeType, TaskRepeatRule

# A template mirrors the task tree it creates: a project may hold modules and
# tasks, a module may hold tasks, and a task may hold exactly one level of
# subtasks. Three levels below the project root is therefore the deepest a
# blueprint can legally go.
MAX_TEMPLATE_DEPTH = 3
MAX_TEMPLATE_NODES = 200


class TemplateNode(BaseModel):
    """One module or task inside a template outline."""

    node_type: TaskNodeType = TaskNodeType.TASK
    title: str = Field(min_length=1, max_length=200)
    estimated_seconds: int = Field(default=0, ge=0, le=315_360_000)
    children: list["TemplateNode"] = Field(default_factory=list)

    @field_validator("node_type")
    @classmethod
    def reject_nested_projects(cls, value: TaskNodeType) -> TaskNodeType:
        """Only the applied root may be a project."""

        if value == TaskNodeType.PROJECT:
            raise ValueError("Template nodes must be modules or tasks")
        return value


TemplateNode.model_rebuild()


def _validate_outline(nodes: list[TemplateNode]) -> list[TemplateNode]:
    """Reject outlines that could not be created as a real task tree."""

    total = 0

    def walk(items: list[TemplateNode], depth: int, parent: TaskNodeType | None) -> None:
        nonlocal total
        if depth > MAX_TEMPLATE_DEPTH:
            raise ValueError("Template outline is nested too deeply")
        for item in items:
            total += 1
            if total > MAX_TEMPLATE_NODES:
                raise ValueError("Template outline contains too many nodes")
            if item.node_type == TaskNodeType.MODULE and parent is not None:
                raise ValueError("Template modules must sit directly under the project")
            walk(item.children, depth + 1, item.node_type)

    walk(nodes, 1, None)
    return nodes


class ProjectTemplateBase(BaseModel):
    """Fields shared by template creation and editing."""

    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    icon: str | None = Field(default=None, max_length=8)
    preset_key: str | None = Field(default=None, max_length=40)
    budget_mode: TaskBudgetMode = TaskBudgetMode.ROLLUP
    fixed_budget_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    default_estimated_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    default_repeat_rule: TaskRepeatRule | None = None
    structure: list[TemplateNode] = Field(default_factory=list)

    @field_validator("structure")
    @classmethod
    def validate_structure(cls, value: list[TemplateNode]) -> list[TemplateNode]:
        return _validate_outline(value)


class ProjectTemplateCreate(ProjectTemplateBase):
    """Create one owned template, optionally with a client-generated id."""

    id: UUID | None = None


class ProjectTemplateUpdate(BaseModel):
    """Partially edit an owned template."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    icon: str | None = Field(default=None, max_length=8)
    budget_mode: TaskBudgetMode | None = None
    fixed_budget_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    default_estimated_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    default_repeat_rule: TaskRepeatRule | None = None
    structure: list[TemplateNode] | None = None
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("structure")
    @classmethod
    def validate_structure(cls, value: list[TemplateNode] | None) -> list[TemplateNode] | None:
        return None if value is None else _validate_outline(value)


class ProjectTemplateResponse(ProjectTemplateBase):
    """A saved template returned to the projects page."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    sort_order: int
    created_at: datetime
    updated_at: datetime
