import uuid
from datetime import UTC, datetime, timedelta

import pytest

from emerald.iam.application.dtos.commands import LoginUser, RefreshAccessToken
from emerald.iam.application.dtos.responses import LoginResult
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.exceptions import InvalidTokenError, TokenExpiredError
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.entities.refresh_token import RefreshToken
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.portal_context import PortalContext
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


async def _login(service: AuthenticationService) -> LoginResult:
    return await service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )


async def test_refresh_valid_token_returns_new_pair(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)
    login_result = await _login(service)

    refresh_result = await service.refresh(
        RefreshAccessToken(refresh_token=login_result.refresh_token)
    )

    assert isinstance(refresh_result, LoginResult)
    assert refresh_result.access_token is not None
    assert refresh_result.refresh_token is not None
    assert refresh_result.refresh_token != login_result.refresh_token


async def test_refresh_old_token_is_revoked(auth_env):
    service, uow, _, token_service = auth_env
    _create_active_user(uow)
    login_result = await _login(service)
    old_hash = token_service.hash_token(login_result.refresh_token)

    await service.refresh(RefreshAccessToken(refresh_token=login_result.refresh_token))

    old_token = uow.refresh_tokens.find_by_hash(old_hash)
    assert old_token is not None
    assert old_token.is_revoked()


async def test_refresh_new_token_in_same_family(auth_env):
    service, uow, _, token_service = auth_env
    _create_active_user(uow)
    login_result = await _login(service)
    old_hash = token_service.hash_token(login_result.refresh_token)
    old_token = uow.refresh_tokens.find_by_hash(old_hash)
    assert old_token is not None
    old_family_id = old_token.family_id

    refresh_result = await service.refresh(
        RefreshAccessToken(refresh_token=login_result.refresh_token)
    )

    new_hash = token_service.hash_token(refresh_result.refresh_token)
    new_token = uow.refresh_tokens.find_by_hash(new_hash)
    assert new_token is not None
    assert new_token.family_id == old_family_id


async def test_refresh_expired_token_raises_token_expired(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)

    expired_token = RefreshToken(
        user_id=user.id,
        token_hash="hashed:expired_raw",
        family_id=uuid.uuid4(),
        portal_context=PortalContext.REGULAR,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
        created_at=datetime.now(UTC) - timedelta(hours=2),
    )
    uow.refresh_tokens.add(expired_token)

    with pytest.raises(TokenExpiredError):
        await service.refresh(RefreshAccessToken(refresh_token="expired_raw"))


async def test_refresh_not_found_token_raises_invalid_token(auth_env):
    service, uow, _, _ = auth_env

    with pytest.raises(InvalidTokenError):
        await service.refresh(RefreshAccessToken(refresh_token="unknown_token"))


async def test_refresh_revoked_token_triggers_theft_detection(auth_env):
    service, uow, _, token_service = auth_env
    _create_active_user(uow)

    # 1. Login to get tokens
    login_result = await _login(service)

    # 2. Find the refresh token in the fake repo and revoke it
    raw_refresh = login_result.refresh_token
    token_hash = token_service.hash_token(raw_refresh)
    stored_token = uow.refresh_tokens.find_by_hash(token_hash)
    assert stored_token is not None
    stored_token.revoke()

    # 3. Try to refresh with the original raw token -> theft detected
    with pytest.raises(InvalidTokenError):
        await service.refresh(RefreshAccessToken(refresh_token=raw_refresh))
