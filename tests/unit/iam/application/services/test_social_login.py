import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from emerald.iam.application.dtos.responses import LoginResult
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.constants import MAX_CONCURRENT_SESSIONS
from emerald.iam.domain.events.social_events import UserRegisteredViaSocialProvider
from emerald.iam.domain.events.user_events import AuthProviderLinked, EmailVerified
from emerald.iam.domain.exceptions import (
    AccountSuspendedError,
    AuthenticationFailedError,
    ProviderExternalIdMismatchError,
)
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.entities.refresh_token import RefreshToken
from emerald.iam.domain.models.value_objects.auth_provider import AuthProvider, ProviderType
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.oidc_claims import OidcClaims
from emerald.iam.domain.models.value_objects.portal_context import PortalContext
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.user_status import UserStatus
from emerald.iam.domain.models.value_objects.username import Username
from tests.unit.iam.fakes import (
    FakeIamUnitOfWork,
    FakePasswordHasherPort,
    FakeTokenPort,
)


def _make_user(**overrides: Any) -> User:
    defaults: dict[str, Any] = {
        "email": EmailAddress("user@test.com"),
        "username": Username("testuser"),
        "password": HashedPassword("hashed:S3cureP@ss1"),
        "auth_providers": {AuthProvider(ProviderType.PASSWORD, None, datetime.now(UTC))},
        "status": UserStatus.ACTIVE,
        "email_verified": True,
        "id": uuid.uuid4(),
        "created_by": uuid.uuid4(),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_claims(**overrides: Any) -> OidcClaims:
    defaults: dict[str, Any] = {
        "provider_type": ProviderType.GOOGLE,
        "external_id": "google-123",
        "email": "user@test.com",
        "email_verified": True,
        "full_name": "Test User",
    }
    defaults.update(overrides)
    return OidcClaims(**defaults)


@pytest.fixture
def uow() -> FakeIamUnitOfWork:
    return FakeIamUnitOfWork()


@pytest.fixture
def service(uow: FakeIamUnitOfWork) -> AuthenticationService:
    return AuthenticationService(uow, FakePasswordHasherPort(), FakeTokenPort())


class TestLoginWithProvider:
    """Tests for AuthenticationService.login_with_provider()."""

    async def test_existing_user_provider_already_linked(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User has GOOGLE linked with same external_id -> login succeeds."""
        user = _make_user(
            auth_providers={
                AuthProvider(ProviderType.PASSWORD, None, datetime.now(UTC)),
                AuthProvider(ProviderType.GOOGLE, "google-123", datetime.now(UTC)),
            },
        )
        await uow.users.add(user)
        user.collect_events()  # Clear prior events

        claims = _make_claims()
        result = await service.login_with_provider(claims)

        assert isinstance(result, LoginResult)
        assert result.is_new_registration is False
        assert user.last_login_at is not None

    async def test_existing_active_user_auto_link(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User exists ACTIVE, no GOOGLE linked -> auto-link."""
        user = _make_user()  # Only PASSWORD provider
        await uow.users.add(user)
        user.collect_events()

        claims = _make_claims()
        result = await service.login_with_provider(claims)

        assert isinstance(result, LoginResult)
        assert result.is_new_registration is False

        # Aggregate events: AuthProviderLinked + UserLoggedIn
        agg_events = user.collect_events()
        assert any(isinstance(e, AuthProviderLinked) for e in agg_events)

    async def test_pending_verification_user_upgrade(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User is PENDING_VERIFICATION -> link, verify, become ACTIVE."""
        user = _make_user(
            status=UserStatus.PENDING_VERIFICATION,
            email_verified=False,
        )
        await uow.users.add(user)
        user.collect_events()

        claims = _make_claims()
        result = await service.login_with_provider(claims)

        assert isinstance(result, LoginResult)
        assert user.status == UserStatus.ACTIVE
        assert user.email_verified is True

        # Aggregate events: AuthProviderLinked, EmailVerified, UserLoggedIn
        agg_events = user.collect_events()
        assert any(isinstance(e, AuthProviderLinked) for e in agg_events)
        assert any(isinstance(e, EmailVerified) for e in agg_events)

    async def test_deleted_user_raises_auth_failed(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User is DELETED -> AuthenticationFailedError."""
        user = _make_user(status=UserStatus.DELETED)
        await uow.users.add(user)

        claims = _make_claims()

        with pytest.raises(AuthenticationFailedError):
            await service.login_with_provider(claims)

    async def test_suspended_user_raises_account_suspended(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User is SUSPENDED -> AccountSuspendedError."""
        user = _make_user(status=UserStatus.SUSPENDED)
        await uow.users.add(user)

        claims = _make_claims()

        with pytest.raises(AccountSuspendedError):
            await service.login_with_provider(claims)

    async def test_external_id_mismatch_raises(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User has GOOGLE with google-123 but claims have google-999."""
        user = _make_user(
            auth_providers={
                AuthProvider(ProviderType.PASSWORD, None, datetime.now(UTC)),
                AuthProvider(ProviderType.GOOGLE, "google-123", datetime.now(UTC)),
            },
        )
        await uow.users.add(user)

        claims = _make_claims(external_id="google-999")

        with pytest.raises(ProviderExternalIdMismatchError):
            await service.login_with_provider(claims)

    async def test_new_user_social_registration(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """No user exists -> creates new user with is_new_registration=True."""
        claims = _make_claims(email="newuser@test.com")

        result = await service.login_with_provider(claims)

        assert isinstance(result, LoginResult)
        assert result.is_new_registration is True

        # New user should exist in repo
        new_user = await uow.users.find_by_email(EmailAddress("newuser@test.com"))
        assert new_user is not None
        assert new_user.status == UserStatus.ACTIVE
        assert new_user.password is None
        assert new_user.username is None

        # Aggregate event: UserRegisteredViaSocialProvider
        agg_events = new_user.collect_events()
        assert any(isinstance(e, UserRegisteredViaSocialProvider) for e in agg_events)

    async def test_new_user_social_registration_no_full_name(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """full_name=None in claims -> still registers, user.full_name is None."""
        claims = _make_claims(email="nofullname@test.com", full_name=None)

        result = await service.login_with_provider(claims)

        assert result.is_new_registration is True
        new_user = await uow.users.find_by_email(EmailAddress("nofullname@test.com"))
        assert new_user is not None
        assert new_user.full_name is None

    async def test_superadmin_social_login_short_ttl(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """Existing SUPERADMIN with GOOGLE linked -> login succeeds."""
        user = _make_user(
            system_role=SystemRole.SUPERADMIN,
            auth_providers={
                AuthProvider(ProviderType.PASSWORD, None, datetime.now(UTC)),
                AuthProvider(ProviderType.GOOGLE, "google-123", datetime.now(UTC)),
            },
        )
        await uow.users.add(user)
        user.collect_events()

        claims = _make_claims()
        result = await service.login_with_provider(claims)

        assert isinstance(result, LoginResult)
        assert result.is_new_registration is False

    async def test_session_limit_enforced(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """At MAX_CONCURRENT_SESSIONS, oldest family is revoked."""
        user = _make_user(
            auth_providers={
                AuthProvider(ProviderType.PASSWORD, None, datetime.now(UTC)),
                AuthProvider(ProviderType.GOOGLE, "google-123", datetime.now(UTC)),
            },
        )
        await uow.users.add(user)
        user.collect_events()

        # Create MAX_CONCURRENT_SESSIONS active families
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
                created_at=now + timedelta(seconds=i),
            )
            await uow.refresh_tokens.add(token)

        claims = _make_claims()
        result = await service.login_with_provider(claims)

        assert result is not None

        # Oldest family should have been revoked
        active_families = await uow.refresh_tokens.find_active_families_by_user(user.id)
        assert family_ids[0] not in active_families
        assert len(active_families) == MAX_CONCURRENT_SESSIONS
