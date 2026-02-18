import pytest

from emerald.iam.application.dtos.commands import LoginUser, LogoutAllSessions, LogoutSession
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.models.aggregates.user import User
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


async def _login(service: AuthenticationService):
    return await service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )


async def test_logout_valid_token_revokes_it(auth_env):
    service, uow, _, token_service = auth_env
    _create_active_user(uow)
    login_result = await _login(service)

    await service.logout(LogoutSession(refresh_token=login_result.refresh_token))

    token_hash = token_service.hash_token(login_result.refresh_token)
    token = uow.refresh_tokens.find_by_hash(token_hash)
    assert token is not None
    assert token.is_revoked()


async def test_logout_nonexistent_token_silently_ignored(auth_env):
    service, uow, _, _ = auth_env

    # Should not raise any exception
    await service.logout(LogoutSession(refresh_token="nonexistent_token"))


async def test_logout_all_revokes_all_tokens(auth_env):
    service, uow, _, token_service = auth_env
    user = _create_active_user(uow)

    # Create multiple sessions
    result1 = await _login(service)
    result2 = await _login(service)
    result3 = await _login(service)

    await service.logout_all(LogoutAllSessions(user_id=str(user.id)))

    # All tokens should be revoked
    for raw_token in [result1.refresh_token, result2.refresh_token, result3.refresh_token]:
        token_hash = token_service.hash_token(raw_token)
        token = uow.refresh_tokens.find_by_hash(token_hash)
        assert token is not None
        assert token.is_revoked()
