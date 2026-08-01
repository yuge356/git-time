"""Input validation tests for stable user identifiers and timezones."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest
from app.schemas.profile import ProfileUpdate
from app.schemas.session import SessionStateUpsert
from app.schemas.task import TaskUpdate


def test_registration_normalizes_email_and_username() -> None:
    payload = RegisterRequest(
        email="LEARNER@EXAMPLE.COM",
        username="Learner_01",
        display_name=" 学习者 ",
        password="strong-password",
    )

    assert payload.email == "learner@example.com"
    assert payload.username == "learner_01"
    assert payload.display_name == "学习者"


def test_username_rejects_unsupported_characters() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="learner@example.com",
            username="学习者!",
            display_name="学习者",
            password="strong-password",
        )


def test_timezone_must_be_an_iana_name() -> None:
    with pytest.raises(ValidationError):
        ProfileUpdate(timezone="Shanghai")


def test_required_task_fields_cannot_be_patched_to_null() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(title=None)
    with pytest.raises(ValidationError):
        TaskUpdate(estimated_seconds=None)


def test_running_session_requires_last_resume_time() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        SessionStateUpsert(
            task_id=uuid4(),
            client_id=uuid4(),
            status="RUNNING",
            started_at=now,
            duration_seconds=0,
            client_updated_at=now,
        )


def test_session_timestamps_require_timezone() -> None:
    from datetime import datetime
    from uuid import uuid4

    now = datetime.now()
    with pytest.raises(ValidationError):
        SessionStateUpsert(
            task_id=uuid4(),
            client_id=uuid4(),
            status="RUNNING",
            started_at=now,
            duration_seconds=0,
            last_resumed_at=now,
            client_updated_at=now,
        )
