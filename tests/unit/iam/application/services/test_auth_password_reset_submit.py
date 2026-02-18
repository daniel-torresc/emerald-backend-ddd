from datetime import UTC, datetime, timedelta

import pytest

from emerald.iam.application.dtos.commands import (
    LoginUser,
    RequestPasswordReset,
    SubmitPasswordReset,
)
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.exceptions import (
    InvalidTokenError,
    PasswordReusedError,
    PasswordTooWeakError,
    TokenAlreadyUsedError,
    TokenExpiredError,
)
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.entities.password_reset_token import PasswordResetToken
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.username import Username
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


async def _request_reset(service: AuthenticationService) -> str:
    raw_token = await service.request_password_reset(RequestPasswordReset(email="test@example.com"))
    assert raw_token is not None
    return raw_token


async def test_submit_valid_token_changes_password(auth_env):
    service, uow, hasher, _ = auth_env
    user = _create_active_user(uow)
    raw_token = await _request_reset(service)

    await service.submit_password_reset(
        SubmitPasswordReset(reset_token=raw_token, new_password="NewPassword123!")
    )

    assert user.password is not None
    assert user.password.hashed_value == "hashed:NewPassword123!"


async def test_submit_archives_old_hash(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)
    raw_token = await _request_reset(service)

    await service.submit_password_reset(
        SubmitPasswordReset(reset_token=raw_token, new_password="NewPassword123!")
    )

    assert "hashed:Password123!" in user.password_history


async def test_submit_marks_token_used(auth_env):
    service, uow, _, token_service = auth_env
    _create_active_user(uow)
    raw_token = await _request_reset(service)

    await service.submit_password_reset(
        SubmitPasswordReset(reset_token=raw_token, new_password="NewPassword123!")
    )

    token_hash = token_service.hash_token(raw_token)
    reset_token = uow.password_reset_tokens.find_by_hash(token_hash)
    assert reset_token is not None
    assert reset_token.used_at is not None


async def test_submit_revokes_all_refresh_tokens(auth_env):
    service, uow, _, token_service = auth_env
    _create_active_user(uow)

    # Login first to create a refresh token
    login_result = await service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )
    login_token_hash = token_service.hash_token(login_result.refresh_token)

    # Request and submit password reset
    raw_reset = await _request_reset(service)
    await service.submit_password_reset(
        SubmitPasswordReset(reset_token=raw_reset, new_password="NewPassword123!")
    )

    # Refresh token should be revoked
    refresh_token = uow.refresh_tokens.find_by_hash(login_token_hash)
    assert refresh_token is not None
    assert refresh_token.is_revoked()


async def test_submit_expired_token_raises_token_expired(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)

    # Create an expired PasswordResetToken directly
    expired_token = PasswordResetToken(
        user_id=user.id,
        token_hash="hashed:expired_reset_raw",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
        created_at=datetime.now(UTC) - timedelta(hours=2),
    )
    uow.password_reset_tokens.add(expired_token)

    with pytest.raises(TokenExpiredError):
        await service.submit_password_reset(
            SubmitPasswordReset(reset_token="expired_reset_raw", new_password="NewPassword123!")
        )


async def test_submit_used_token_raises_token_already_used(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)

    # Create a token and mark it used
    used_token = PasswordResetToken(
        user_id=user.id,
        token_hash="hashed:used_reset_raw",
    )
    used_token.mark_used()
    uow.password_reset_tokens.add(used_token)

    with pytest.raises(TokenAlreadyUsedError):
        await service.submit_password_reset(
            SubmitPasswordReset(reset_token="used_reset_raw", new_password="NewPassword123!")
        )


async def test_submit_not_found_token_raises_invalid_token(auth_env):
    service, uow, _, _ = auth_env

    with pytest.raises(InvalidTokenError):
        await service.submit_password_reset(
            SubmitPasswordReset(reset_token="unknown_token", new_password="NewPassword123!")
        )


async def test_submit_weak_password_raises_password_too_weak(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)
    raw_token = await _request_reset(service)

    with pytest.raises(PasswordTooWeakError):
        await service.submit_password_reset(
            SubmitPasswordReset(reset_token=raw_token, new_password="weak")
        )


async def test_submit_password_in_history_raises_password_reused(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)

    # First reset: change from Password123! to NewPassword123!
    raw_token_1 = await _request_reset(service)
    await service.submit_password_reset(
        SubmitPasswordReset(reset_token=raw_token_1, new_password="NewPassword123!")
    )
    # Now "hashed:Password123!" is in history

    # Second reset: try to reuse Password123!
    raw_token_2 = await _request_reset(service)
    with pytest.raises(PasswordReusedError):
        await service.submit_password_reset(
            SubmitPasswordReset(reset_token=raw_token_2, new_password="Password123!")
        )


async def test_submit_works_for_suspended_user(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)
    user.suspend("policy violation")
    user.collect_events()

    raw_token = await _request_reset(service)

    # Should not raise even though user is suspended
    await service.submit_password_reset(
        SubmitPasswordReset(reset_token=raw_token, new_password="NewPassword123!")
    )

    assert user.password is not None
    assert user.password.hashed_value == "hashed:NewPassword123!"
