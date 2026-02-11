from datetime import UTC, datetime

import pytest

from emerald.iam.application.dtos.commands import RequestPasswordReset
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.constants import PASSWORD_RESET_TOKEN_TTL
from emerald.iam.domain.events.auth_events import PasswordResetRequested
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.username import Username
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)
from tests.unit.iam.fakes import FakeIamUnitOfWork, FakePasswordHasher, FakeTokenService


def _create_active_user(uow: FakeIamUnitOfWork) -> User:
    user = User.register(
        EmailAddress("test@example.com"),
        Username("testuser"),
        HashedPassword("hashed:Password123!"),
    )
    user.verify_email()
    user.collect_events()
    uow.users.add(user)
    return user


@pytest.fixture
def auth_env():
    uow = FakeIamUnitOfWork()
    hasher = FakePasswordHasher()
    token_service = FakeTokenService()
    service = AuthenticationService(uow, hasher, token_service)
    return service, uow, hasher, token_service


def test_request_existing_user_returns_raw_token(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)

    raw_token = service.request_password_reset(RequestPasswordReset(email="test@example.com"))

    assert raw_token is not None
    assert isinstance(raw_token, str)
    assert len(raw_token) > 0


def test_request_nonexistent_email_returns_none(auth_env):
    service, uow, _, _ = auth_env

    result = service.request_password_reset(RequestPasswordReset(email="nobody@example.com"))

    assert result is None


def test_request_deleted_user_returns_none(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)
    user.soft_delete(
        deleted_by=user.id,
        retention=RetentionPeriod(duration=90, unit=RetentionUnit.DAYS),
    )
    user.collect_events()

    result = service.request_password_reset(RequestPasswordReset(email="test@example.com"))

    assert result is None


def test_request_invalidates_previous_tokens(auth_env):
    service, uow, _, token_service = auth_env
    _create_active_user(uow)

    # Request first token
    raw_token_1 = service.request_password_reset(RequestPasswordReset(email="test@example.com"))
    assert raw_token_1 is not None

    # Request second token
    raw_token_2 = service.request_password_reset(RequestPasswordReset(email="test@example.com"))
    assert raw_token_2 is not None

    # First token should be invalidated (used_at set)
    hash_1 = token_service.hash_token(raw_token_1)
    token_1 = uow.password_reset_tokens.find_by_hash(hash_1)
    assert token_1 is not None
    assert token_1.is_used()

    # Second token should still be valid
    hash_2 = token_service.hash_token(raw_token_2)
    token_2 = uow.password_reset_tokens.find_by_hash(hash_2)
    assert token_2 is not None
    assert not token_2.is_used()


def test_request_emits_password_reset_requested(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)
    service.collect_events()  # Clear any previous events

    service.request_password_reset(RequestPasswordReset(email="test@example.com"))

    events = service.collect_events()
    assert any(isinstance(e, PasswordResetRequested) for e in events)


def test_request_reset_token_expires_in_one_hour(auth_env):
    service, uow, _, token_service = auth_env
    _create_active_user(uow)

    before = datetime.now(UTC)
    raw_token = service.request_password_reset(RequestPasswordReset(email="test@example.com"))
    after = datetime.now(UTC)

    assert raw_token is not None
    token_hash = token_service.hash_token(raw_token)
    reset_token = uow.password_reset_tokens.find_by_hash(token_hash)
    assert reset_token is not None

    # The token's expires_at should be approximately created_at + 1 hour
    expected_lower = before + PASSWORD_RESET_TOKEN_TTL
    expected_upper = after + PASSWORD_RESET_TOKEN_TTL
    assert expected_lower <= reset_token.expires_at <= expected_upper
