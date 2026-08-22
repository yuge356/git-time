"""Read-only date-range learning analytics endpoint."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.analytics import AnalyticsDashboard, AnalyticsSummary, HourlyFocusResponse
from app.services.analytics import (
    build_analytics_summary,
    build_dashboard_summaries,
    build_hourly_focus,
)
from app.services.daily_plans import build_check_in

router = APIRouter(prefix="/analytics", tags=["analytics"])


def validate_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to cannot precede date_from")
    if (date_to - date_from).days > 365:
        raise HTTPException(status_code=422, detail="Analytics range cannot exceed 366 days")


@router.get("/dashboard", response_model=AnalyticsDashboard)
async def read_analytics_dashboard(
    db: DatabaseSession,
    current_user: CurrentUser,
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    today: Annotated[date, Query()],
) -> AnalyticsDashboard:
    """Return all analytics-page data through one auth and HTTP round trip."""
    validate_range(date_from, date_to)
    timezone = current_user.profile.timezone
    range_summary, today_summary = await build_dashboard_summaries(
        db,
        current_user.id,
        timezone,
        date_from,
        date_to,
        today,
    )
    today_check_in = await build_check_in(db, current_user.id, today, timezone)
    return AnalyticsDashboard(
        range_summary=range_summary,
        today_summary=today_summary,
        today_check_in=today_check_in,
    )


@router.get("/summary", response_model=AnalyticsSummary)
async def read_analytics_summary(
    db: DatabaseSession,
    current_user: CurrentUser,
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
) -> AnalyticsSummary:
    """Return at most one year of learning, completion and budget figures."""

    validate_range(date_from, date_to)
    return await build_analytics_summary(
        db,
        current_user.id,
        current_user.profile.timezone,
        date_from,
        date_to,
    )


@router.get("/hourly-focus", response_model=HourlyFocusResponse)
async def read_hourly_focus(
    db: DatabaseSession,
    current_user: CurrentUser,
    day: Annotated[date, Query()],
) -> HourlyFocusResponse:
    """Return the hour-by-hour focus distribution for one local date."""

    return await build_hourly_focus(
        db,
        current_user.id,
        current_user.profile.timezone,
        day,
    )
