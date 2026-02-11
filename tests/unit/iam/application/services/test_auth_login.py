import uuid
from datetime import UTC, datetime, timedelta

import pytest

from emerald.iam.application.dtos.commands import LoginUser
from emerald.iam.application.dtos.responses import LoginResult
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.constants import ACCESS_TOKEN_TTL, MAX_CONCURRENT_SESSIONS
from emerald.iam.domain.events import UserLoggedIn
from emerald.iam.domain.events.auth_events import LoginFailed
from emerald.iam.domain.exceptions import (
    AccountSuspendedError,
    AuthenticationFailedError,
    EmailNotVerifiedError,
)
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.entities.refresh_token import RefreshToken
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.portal_context import PortalContext
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
    user.collect_events()  # Clear registration events
    uow.users.add(user)
    return user


@pytest.fixture
def auth_env():
    uow = FakeIamUnitOfWork()
    hasher = FakePasswordHasher()
    token_service = FakeTokenService()
    service = AuthenticationService(uow, hasher, token_service)
    return service, uow, hasher, token_service


def test_login_valid_credentials_returns_login_result(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)

    result = service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )

    assert isinstance(result, LoginResult)
    assert result.access_token is not None
    assert result.refresh_token is not None
    assert result.expires_in == ACCESS_TOKEN_TTL


def test_login_invalid_password_raises_authentication_failed(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)

    with pytest.raises(AuthenticationFailedError):
        service.login(
            LoginUser(email="test@example.com", password="WrongPassword!", portal_context="REGULAR")
        )


def test_login_nonexistent_email_raises_authentication_failed(auth_env):
    service, uow, _, _ = auth_env

    with pytest.raises(AuthenticationFailedError):
        service.login(
            LoginUser(email="nobody@example.com", password="Password123!", portal_context="REGULAR")
        )


def test_login_pending_verification_raises_email_not_verified(auth_env):
    service, uow, _, _ = auth_env
    user = User.register(
        EmailAddress("unverified@example.com"),
        Username("unverified"),
        HashedPassword("hashed:Password123!"),
    )
    user.collect_events()
    uow.users.add(user)

    with pytest.raises(EmailNotVerifiedError):
        service.login(
            LoginUser(
                email="unverified@example.com", password="Password123!", portal_context="REGULAR"
            )
        )


def test_login_suspended_raises_account_suspended(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)
    user.suspend("policy violation")
    user.collect_events()

    with pytest.raises(AccountSuspendedError):
        service.login(
            LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
        )


def test_login_deleted_raises_authentication_failed(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)
    user.soft_delete(
        deleted_by=user.id,
        retention=RetentionPeriod(duration=90, unit=RetentionUnit.DAYS),
    )
    user.collect_events()

    with pytest.raises(AuthenticationFailedError):
        service.login(
            LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
        )


def test_login_records_last_login_at(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)
    assert user.last_login_at is None

    service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )

    assert user.last_login_at is not None


def test_login_emits_user_logged_in(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)

    service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )

    events = user.collect_events()
    assert any(isinstance(e, UserLoggedIn) for e in events)


def test_login_emits_login_failed_on_failure(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)

    with pytest.raises(AuthenticationFailedError):
        service.login(
            LoginUser(email="test@example.com", password="WrongPass!", portal_context="REGULAR")
        )

    events = service.collect_events()
    assert len(events) >= 1
    assert any(isinstance(e, LoginFailed) for e in events)


def test_login_at_max_sessions_revokes_oldest_family(auth_env):
    service, uow, _, _ = auth_env
    user = _create_active_user(uow)

    # Create 5 active families (at the max)
    now = datetime.now(UTC)
    family_ids = []
    for i in range(MAX_CONCURRENT_SESSIONS):
        fid = uuid.uuid4()
        family_ids.append(fid)
        token = RefreshToken(
            user_id=user.id,
            token_hash=f"existing_hash_{i}",
            family_id=fid,
            portal_context=PortalContext.REGULAR,
            expires_at=now + timedelta(days=7),
            created_at=now + timedelta(seconds=i),  # incremental so ordering is deterministic
        )
        uow.refresh_tokens.add(token)

    # Login creates a 6th session, which should revoke the oldest family
    result = service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )

    assert result is not None
    # Oldest family (family_ids[0]) should have been revoked
    active_families = uow.refresh_tokens.find_active_families_by_user(user.id)
    assert family_ids[0] not in active_families
    # Should still be at MAX_CONCURRENT_SESSIONS (5 old - 1 revoked + 1 new = 5)
    assert len(active_families) == MAX_CONCURRENT_SESSIONS


def test_login_commits_uow(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)

    service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )

    assert uow.committed is True


def test_login_admin_portal_context(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)

    result = service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="ADMIN")
    )

    assert isinstance(result, LoginResult)
    assert result.expires_in == ACCESS_TOKEN_TTL


def test_login_regular_portal_context(auth_env):
    service, uow, _, _ = auth_env
    _create_active_user(uow)

    result = service.login(
        LoginUser(email="test@example.com", password="Password123!", portal_context="REGULAR")
    )

    assert isinstance(result, LoginResult)
    assert result.expires_in == ACCESS_TOKEN_TTL
