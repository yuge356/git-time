"""Security helper unit tests."""

from uuid import uuid4

import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verifiable() -> None:
    password = "correct horse battery staple"
    encoded = hash_password(password)

    assert encoded != password
    assert verify_password(password, encoded)
    assert not verify_password("wrong password", encoded)


def test_access_token_round_trip() -> None:
    user_id = uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_invalid_access_token_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-jwt")

