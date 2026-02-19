import uuid
from datetime import UTC, datetime, timedelta

import pytest

from emerald.iam.application.dtos.commands import LoginUser
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.exceptions import InvalidTokenError
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.access_token_claims import AccessTokenClaims
from emerald.iam.domain.models.value_objects.authenticated_identity import AuthenticatedIdentity
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.username import Username
from tests.unit.iam.fakes import FakeIamUnitOfWork, FakePasswordHasher, FakeTokenService


async def _create_active_user(uow: FakeIamUnitOfWork) -> User:
    user = User.register(
        EmailAddress("test@example.com"),
        Username("testuser"),
        HashedPassword("hashed:Password123!"),
    )
    user.verify_email()
    user.collect_events()
    await uow.users.add(user)
    return user


@pytest.fixture
def auth_env():
    uow = FakeIamUnitOfWork()
    hasher = FakePasswordHasher()
    token_service = FakeTokenService()
    service = AuthenticationService(uow, hasher, token_service)
    return service, uow, hasher, token_service


async def test_verify_valid_token_returns_authenticated_identity(auth_env):
    service, uow, _, _ = auth_env
    await _create_active_user(uow)

    login_result = await service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )

    identity = await service.verify_access_token(login_result.access_token)

    assert isinstance(identity, AuthenticatedIdentity)
    assert identity.email == EmailAddress("test@example.com")
    assert identity.system_role == SystemRole.USER


async def test_verify_invalid_token_raises_error(auth_env):
    service, uow, _, _ = auth_env

    with pytest.raises(InvalidTokenError):
        await service.verify_access_token("garbage_token")


async def test_verify_user_not_found_raises_invalid_token(auth_env):
    service, uow, _, token_service = auth_env

    # Sign a token with claims for a non-existent user
    non_existent_user_id = uuid.uuid4()
    now = datetime.now(UTC)
    claims = AccessTokenClaims(
        sub=non_existent_user_id,
        email="ghost@example.com",
        system_role=SystemRole.USER,
        iat=now,
        exp=now + timedelta(minutes=15),
        jti=uuid.uuid4(),
    )
    fake_token = await token_service.sign_access_token(claims)

    with pytest.raises(InvalidTokenError):
        await service.verify_access_token(fake_token)


async def test_verify_display_name_uses_full_name(auth_env):
    service, uow, _, _ = auth_env
    user = await _create_active_user(uow)
    user.update_full_name("John Doe")
    user.collect_events()

    login_result = await service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )

    identity = await service.verify_access_token(login_result.access_token)

    assert identity.display_name == "John Doe"


async def test_verify_display_name_falls_back_to_username(auth_env):
    service, uow, _, _ = auth_env
    await _create_active_user(uow)
    # full_name is None by default after register

    login_result = await service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )

    identity = await service.verify_access_token(login_result.access_token)

    assert identity.display_name == "testuser"
