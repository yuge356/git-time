"""Read-only date-range learning analytics endpoint."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.analytics import AnalyticsSummary
from app.services.analytics import build_analytics_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def read_analytics_summary(
    db: DatabaseSession,
    current_user: CurrentUser,
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
) -> AnalyticsSummary:
    """Return at most one year of learning, completion and budget figures."""

    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_to cannot precede date_from",
        )
    if (date_to - date_from).days > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Analytics range cannot exceed 366 days",
        )
    return await build_analytics_summary(
        db,
        current_user.id,
        current_user.profile.timezone,
        date_from,
        date_to,
    )
