"""Idempotent session synchronization and study-history endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.session import Session, SessionStatus
from app.schemas.session import SessionResponse, SessionStateUpsert
from app.services.sessions import apply_session_snapshot

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    db: DatabaseSession,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Session]:
    """Return the owner's most recent independent study sessions."""

    result = await db.scalars(
        select(Session)
        .where(Session.owner_id == current_user.id, Session.deleted_at.is_(None))
        .order_by(Session.started_at.desc(), Session.id)
        .limit(limit)
    )
    return list(result.all())


@router.get("/active", response_model=SessionResponse | None)
async def read_active_session(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Session | None:
    """Return the single running or paused session, if one exists."""

    return await db.scalar(
        select(Session).where(
            Session.owner_id == current_user.id,
            Session.status.in_([SessionStatus.RUNNING, SessionStatus.PAUSED]),
            Session.deleted_at.is_(None),
        )
    )


@router.put("/{session_id}", response_model=SessionResponse)
async def upsert_session_state(
    session_id: UUID,
    payload: SessionStateUpsert,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Session:
    """Persist the newest client snapshot, safely retrying offline writes."""

    session = await apply_session_snapshot(db, current_user.id, session_id, payload)
    try:
        await db.flush()
        await db.refresh(session)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another active timer already exists or the session id is unavailable",
        ) from exc
    return session

