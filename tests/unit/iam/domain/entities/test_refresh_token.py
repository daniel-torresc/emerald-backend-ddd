import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from emerald.iam.domain.exceptions import TokenAlreadyRevokedError
from emerald.iam.domain.models.entities.refresh_token import RefreshToken
from emerald.iam.domain.models.value_objects.portal_context import PortalContext


def _make_token(**overrides: Any) -> RefreshToken:
    """Build a valid, non-expired RefreshToken with sensible defaults."""
    defaults: dict[str, Any] = {
        "user_id": uuid.uuid4(),
        "token_hash": "hashed:refresh_token_value",
        "family_id": uuid.uuid4(),
        "portal_context": PortalContext.REGULAR,
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }
    defaults.update(overrides)
    return RefreshToken(**defaults)


class TestRefreshTokenConstruction:
    def test_has_uuid_id_from_entity(self):
        token = _make_token()
        assert isinstance(token.id, uuid.UUID)

    def test_created_at_defaults_to_utc_now(self):
        before = datetime.now(UTC)
        token = _make_token()
        after = datetime.now(UTC)
        assert token.created_at is not None
        assert before <= token.created_at <= after
        assert token.created_at.tzinfo is not None

    def test_revoked_at_defaults_to_none(self):
        token = _make_token()
        assert token.revoked_at is None

    def test_custom_id_accepted(self):
        custom_id = uuid.uuid4()
        token = _make_token(id=custom_id)
        assert token.id == custom_id


class TestRefreshTokenCreateFactory:
    def test_create_generates_uuid(self):
        token = RefreshToken.create(
            user_id=uuid.uuid4(),
            token_hash="hashed:value",
            family_id=uuid.uuid4(),
            portal_context=PortalContext.REGULAR,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert isinstance(token.id, uuid.UUID)

    def test_create_sets_created_at(self):
        before = datetime.now(UTC)
        token = RefreshToken.create(
            user_id=uuid.uuid4(),
            token_hash="hashed:value",
            family_id=uuid.uuid4(),
            portal_context=PortalContext.REGULAR,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        after = datetime.now(UTC)
        assert before <= token.created_at <= after

    def test_create_sets_all_fields(self):
        user_id = uuid.uuid4()
        family_id = uuid.uuid4()
        expires = datetime.now(UTC) + timedelta(hours=2)
        token = RefreshToken.create(
            user_id=user_id,
            token_hash="hashed:abc",
            family_id=family_id,
            portal_context=PortalContext.ADMIN,
            expires_at=expires,
        )
        assert token.user_id == user_id
        assert token.token_hash == "hashed:abc"
        assert token.family_id == family_id
        assert token.portal_context == PortalContext.ADMIN
        assert token.expires_at == expires
        assert token.revoked_at is None


class TestRefreshTokenRevoke:
    def test_revoke_sets_revoked_at(self):
        token = _make_token()
        before = datetime.now(UTC)
        token.revoke()
        after = datetime.now(UTC)
        assert token.revoked_at is not None
        assert before <= token.revoked_at <= after
        assert token.revoked_at.tzinfo is not None

    def test_revoke_already_revoked_raises(self):
        token = _make_token()
        token.revoke()
        with pytest.raises(TokenAlreadyRevokedError):
            token.revoke()


class TestRefreshTokenIsActive:
    def test_active_when_not_revoked_and_not_expired(self):
        token = _make_token(expires_at=datetime.now(UTC) + timedelta(hours=1))
        assert token.is_active() is True

    def test_not_active_when_revoked(self):
        token = _make_token(expires_at=datetime.now(UTC) + timedelta(hours=1))
        token.revoke()
        assert token.is_active() is False

    def test_not_active_when_expired(self):
        token = _make_token(expires_at=datetime.now(UTC) - timedelta(hours=1))
        assert token.is_active() is False


class TestRefreshTokenIsExpired:
    def test_not_expired_when_future(self):
        token = _make_token(expires_at=datetime.now(UTC) + timedelta(hours=1))
        assert token.is_expired() is False

    def test_expired_when_past(self):
        token = _make_token(expires_at=datetime.now(UTC) - timedelta(hours=1))
        assert token.is_expired() is True


class TestRefreshTokenIsRevoked:
    def test_not_revoked_initially(self):
        token = _make_token()
        assert token.is_revoked() is False

    def test_revoked_after_revoke(self):
        token = _make_token()
        token.revoke()
        assert token.is_revoked() is True


class TestRefreshTokenDatetimeAwareness:
    def test_expires_at_is_timezone_aware(self):
        token = _make_token()
        assert token.expires_at.tzinfo is not None

    def test_created_at_is_timezone_aware(self):
        token = _make_token()
        assert token.created_at.tzinfo is not None

    def test_revoked_at_is_timezone_aware_after_revoke(self):
        token = _make_token()
        token.revoke()
        assert token.revoked_at is not None
        assert token.revoked_at.tzinfo is not None
