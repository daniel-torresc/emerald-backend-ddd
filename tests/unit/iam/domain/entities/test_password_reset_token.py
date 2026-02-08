import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from emerald.iam.domain.constants import PASSWORD_RESET_TOKEN_TTL
from emerald.iam.domain.exceptions import TokenAlreadyUsedError
from emerald.iam.domain.models.password_reset_token import PasswordResetToken


def _make_reset_token(**overrides: Any) -> PasswordResetToken:
    """Build a valid, non-expired PasswordResetToken with sensible defaults."""
    defaults: dict[str, Any] = {
        "user_id": uuid.uuid4(),
        "token_hash": "hashed:reset_token_value",
    }
    defaults.update(overrides)
    return PasswordResetToken(**defaults)


class TestPasswordResetTokenConstruction:
    def test_has_uuid_id_from_entity(self):
        token = _make_reset_token()
        assert isinstance(token.id, uuid.UUID)

    def test_created_at_defaults_to_utc_now(self):
        before = datetime.now(UTC)
        token = _make_reset_token()
        after = datetime.now(UTC)
        assert token.created_at is not None
        assert before <= token.created_at <= after

    def test_used_at_defaults_to_none(self):
        token = _make_reset_token()
        assert token.used_at is None

    def test_default_expiration_one_hour_from_creation(self):
        token = _make_reset_token()
        expected = token.created_at + PASSWORD_RESET_TOKEN_TTL
        assert token.expires_at == expected

    def test_custom_id_accepted(self):
        custom_id = uuid.uuid4()
        token = _make_reset_token(id=custom_id)
        assert token.id == custom_id


class TestPasswordResetTokenMarkUsed:
    def test_mark_used_sets_used_at(self):
        token = _make_reset_token()
        before = datetime.now(UTC)
        token.mark_used()
        after = datetime.now(UTC)
        assert token.used_at is not None
        assert before <= token.used_at <= after
        assert token.used_at.tzinfo is not None

    def test_mark_used_already_used_raises(self):
        token = _make_reset_token()
        token.mark_used()
        with pytest.raises(TokenAlreadyUsedError):
            token.mark_used()


class TestPasswordResetTokenIsValid:
    def test_valid_when_not_used_and_not_expired(self):
        token = _make_reset_token()
        assert token.is_valid() is True

    def test_not_valid_when_used(self):
        token = _make_reset_token()
        token.mark_used()
        assert token.is_valid() is False

    def test_not_valid_when_expired(self):
        token = _make_reset_token(
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert token.is_valid() is False


class TestPasswordResetTokenIsExpired:
    def test_not_expired_when_future(self):
        token = _make_reset_token()
        assert token.is_expired() is False

    def test_expired_when_past(self):
        token = _make_reset_token(
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert token.is_expired() is True


class TestPasswordResetTokenIsUsed:
    def test_not_used_initially(self):
        token = _make_reset_token()
        assert token.is_used() is False

    def test_used_after_mark_used(self):
        token = _make_reset_token()
        token.mark_used()
        assert token.is_used() is True


class TestPasswordResetTokenDatetimeAwareness:
    def test_created_at_is_timezone_aware(self):
        token = _make_reset_token()
        assert token.created_at.tzinfo is not None

    def test_expires_at_is_timezone_aware(self):
        token = _make_reset_token()
        assert token.expires_at.tzinfo is not None

    def test_used_at_is_timezone_aware_after_mark_used(self):
        token = _make_reset_token()
        token.mark_used()
        assert token.used_at is not None
        assert token.used_at.tzinfo is not None
