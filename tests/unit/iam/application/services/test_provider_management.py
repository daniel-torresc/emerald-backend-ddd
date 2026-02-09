import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from emerald.iam.application.dtos.commands.social_auth import UnlinkAuthProvider
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.events.user_events import AuthProviderLinked, AuthProviderUnlinked
from emerald.iam.domain.exceptions import (
    AuthenticationFailedError,
    CannotUnlinkLastProviderError,
    ProviderAlreadyLinkedError,
    ProviderEmailMismatchError,
    ProviderNotLinkedError,
)
from emerald.iam.domain.models.auth_provider import AuthProvider, ProviderType
from emerald.iam.domain.models.email_address import EmailAddress
from emerald.iam.domain.models.hashed_password import HashedPassword
from emerald.iam.domain.models.oidc_claims import OidcClaims
from emerald.iam.domain.models.user import User
from emerald.iam.domain.models.user_status import UserStatus
from emerald.iam.domain.models.username import Username
from tests.unit.iam.fakes import FakeIamUnitOfWork, FakePasswordHasher, FakeTokenService


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
    return AuthenticationService(uow, FakePasswordHasher(), FakeTokenService())


class TestLinkProvider:
    """Tests for AuthenticationService.link_provider()."""

    def test_link_provider_success(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """ACTIVE user, claims email matches, new provider type -> link succeeds."""
        user = _make_user()
        uow.users.add(user)
        user.collect_events()

        claims = _make_claims()
        service.link_provider(user.id, claims)

        # Should have GOOGLE in providers now
        provider_types = {p.provider_type for p in user.auth_providers}
        assert ProviderType.GOOGLE in provider_types

        # Aggregate event: AuthProviderLinked
        agg_events = user.collect_events()
        assert any(isinstance(e, AuthProviderLinked) for e in agg_events)
        assert uow.committed is True

    def test_link_provider_email_mismatch(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """Claims email != user email -> ProviderEmailMismatchError."""
        user = _make_user()
        uow.users.add(user)

        claims = _make_claims(email="different@test.com")

        with pytest.raises(ProviderEmailMismatchError):
            service.link_provider(user.id, claims)

    def test_link_provider_already_linked(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """Provider type already linked -> ProviderAlreadyLinkedError."""
        user = _make_user(
            auth_providers={
                AuthProvider(ProviderType.PASSWORD, None, datetime.now(UTC)),
                AuthProvider(ProviderType.GOOGLE, "google-123", datetime.now(UTC)),
            },
        )
        uow.users.add(user)

        claims = _make_claims()

        with pytest.raises(ProviderAlreadyLinkedError):
            service.link_provider(user.id, claims)

    def test_link_provider_user_not_found(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """Invalid user_id -> AuthenticationFailedError."""
        claims = _make_claims()

        with pytest.raises(AuthenticationFailedError):
            service.link_provider(uuid.uuid4(), claims)


class TestUnlinkProvider:
    """Tests for AuthenticationService.unlink_provider()."""

    def test_unlink_provider_success(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User has PASSWORD + GOOGLE, unlink GOOGLE -> success."""
        user = _make_user(
            auth_providers={
                AuthProvider(ProviderType.PASSWORD, None, datetime.now(UTC)),
                AuthProvider(ProviderType.GOOGLE, "google-123", datetime.now(UTC)),
            },
        )
        uow.users.add(user)
        user.collect_events()

        cmd = UnlinkAuthProvider(user_id=str(user.id), provider_type="GOOGLE")
        service.unlink_provider(cmd)

        provider_types = {p.provider_type for p in user.auth_providers}
        assert ProviderType.GOOGLE not in provider_types

        # Aggregate event: AuthProviderUnlinked
        agg_events = user.collect_events()
        assert any(isinstance(e, AuthProviderUnlinked) for e in agg_events)
        assert uow.committed is True

    def test_unlink_last_provider(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User has only PASSWORD, unlink PASSWORD -> CannotUnlinkLastProviderError."""
        user = _make_user()  # Only PASSWORD
        uow.users.add(user)

        cmd = UnlinkAuthProvider(user_id=str(user.id), provider_type="PASSWORD")

        with pytest.raises(CannotUnlinkLastProviderError):
            service.unlink_provider(cmd)

    def test_unlink_not_linked(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """Provider type not linked -> ProviderNotLinkedError."""
        user = _make_user()  # Only PASSWORD
        uow.users.add(user)

        cmd = UnlinkAuthProvider(user_id=str(user.id), provider_type="GOOGLE")

        with pytest.raises(ProviderNotLinkedError):
            service.unlink_provider(cmd)

    def test_unlink_password_when_social_remains(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User has PASSWORD + GOOGLE, unlink PASSWORD -> success."""
        user = _make_user(
            auth_providers={
                AuthProvider(ProviderType.PASSWORD, None, datetime.now(UTC)),
                AuthProvider(ProviderType.GOOGLE, "google-123", datetime.now(UTC)),
            },
        )
        uow.users.add(user)
        user.collect_events()

        cmd = UnlinkAuthProvider(user_id=str(user.id), provider_type="PASSWORD")
        service.unlink_provider(cmd)

        provider_types = {p.provider_type for p in user.auth_providers}
        assert ProviderType.PASSWORD not in provider_types
        assert ProviderType.GOOGLE in provider_types
        # Password should be cleared when unlinking PASSWORD
        assert user.password is None

        agg_events = user.collect_events()
        assert any(isinstance(e, AuthProviderUnlinked) for e in agg_events)
        assert uow.committed is True
