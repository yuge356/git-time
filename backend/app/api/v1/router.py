"""Top-level API v1 router."""

from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    auth,
    daily_plans,
    notifications,
    partnerships,
    profiles,
    sessions,
    sharing,
    tasks,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(tasks.router)
api_router.include_router(sessions.router)
api_router.include_router(daily_plans.router)
api_router.include_router(analytics.router)
api_router.include_router(partnerships.router)
api_router.include_router(sharing.router)
api_router.include_router(notifications.router)
