"""Supabase identity normalization tests."""

from app.core.supabase_auth import identity_contacts_from_payload


def test_phone_password_alias_becomes_e164_phone() -> None:
    email, phone = identity_contacts_from_payload(
        {"email": "phone.8613800138000@phone.dayflow.invalid", "phone": None}
    )

    assert email is None
    assert phone == "+8613800138000"


def test_regular_email_stays_an_email() -> None:
    email, phone = identity_contacts_from_payload(
        {"email": "Person@Example.com", "phone": None}
    )

    assert email == "person@example.com"
    assert phone is None


def test_native_phone_claim_remains_supported() -> None:
    email, phone = identity_contacts_from_payload(
        {"email": None, "phone": "+8613800138000"}
    )

    assert email is None
    assert phone == "+8613800138000"
