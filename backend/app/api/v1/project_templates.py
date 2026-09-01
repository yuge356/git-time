"""Reusable project-template CRUD endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.project_template import ProjectTemplate
from app.schemas.project_template import (
    ProjectTemplateCreate,
    ProjectTemplateResponse,
    ProjectTemplateUpdate,
)

router = APIRouter(prefix="/project-templates", tags=["project templates"])


async def get_owned_template(
    db: DatabaseSession,
    owner_id: UUID,
    template_id: UUID,
) -> ProjectTemplate:
    """Return one live owned template or a non-disclosing 404."""

    template = await db.scalar(
        select(ProjectTemplate).where(
            ProjectTemplate.id == template_id,
            ProjectTemplate.owner_id == owner_id,
            ProjectTemplate.deleted_at.is_(None),
        )
    )
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project template not found",
        )
    return template


def apply_template_changes(template: ProjectTemplate, changes: dict) -> None:
    """Copy validated schema values onto the row.

    ``changes`` comes from ``model_dump``, so the outline is already plain
    JSON-safe data. Assigning a fresh list also marks the JSON column dirty,
    which an in-place edit would not.
    """

    for field_name, value in changes.items():
        if field_name == "structure":
            template.structure = list(value)
        elif field_name == "default_repeat_rule":
            template.default_repeat_rule = None if value is None else str(value)
        else:
            setattr(template, field_name, value)


@router.get("", response_model=list[ProjectTemplateResponse])
async def list_project_templates(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> list[ProjectTemplate]:
    """Return the owner's saved templates in display order."""

    return list(
        (
            await db.scalars(
                select(ProjectTemplate)
                .where(
                    ProjectTemplate.owner_id == current_user.id,
                    ProjectTemplate.deleted_at.is_(None),
                )
                .order_by(ProjectTemplate.sort_order, ProjectTemplate.created_at)
            )
        ).all()
    )


@router.post(
    "",
    response_model=ProjectTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_template(
    payload: ProjectTemplateCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ProjectTemplate:
    """Save one template, treating a repeated client id as an update."""

    if payload.id is not None:
        existing = await db.scalar(
            select(ProjectTemplate).where(
                ProjectTemplate.id == payload.id,
                ProjectTemplate.owner_id == current_user.id,
            )
        )
        if existing is not None:
            apply_template_changes(existing, payload.model_dump(exclude={"id"}))
            existing.deleted_at = None
            await db.commit()
            await db.refresh(existing)
            return existing

    current_max = await db.scalar(
        select(func.max(ProjectTemplate.sort_order)).where(
            ProjectTemplate.owner_id == current_user.id,
            ProjectTemplate.deleted_at.is_(None),
        )
    )
    template = ProjectTemplate(
        **({"id": payload.id} if payload.id is not None else {}),
        owner_id=current_user.id,
        sort_order=(current_max if current_max is not None else -1) + 1,
    )
    apply_template_changes(template, payload.model_dump(exclude={"id"}))
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.patch("/{template_id}", response_model=ProjectTemplateResponse)
async def update_project_template(
    template_id: UUID,
    payload: ProjectTemplateUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ProjectTemplate:
    """Edit one owned template."""

    template = await get_owned_template(db, current_user.id, template_id)
    apply_template_changes(template, payload.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_template(
    template_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    """Soft-delete one owned template."""

    template = await get_owned_template(db, current_user.id, template_id)
    template.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
