import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from emerald.iam.application.dtos.commands.social_auth import SetOnboardingUsername
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.events.user_events import UserUsernameChanged
from emerald.iam.domain.exceptions import (
    AuthenticationFailedError,
    InvalidUsernameError,
    UsernameAlreadyExistsError,
)
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.auth_provider import AuthProvider, ProviderType
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.user_status import UserStatus
from emerald.iam.domain.models.value_objects.username import Username
from tests.unit.iam.fakes import FakeIamUnitOfWork, FakePasswordHasher, FakeTokenService


def _make_social_user(**overrides: Any) -> User:
    """Create a social-only user (no password, no username)."""
    defaults: dict[str, Any] = {
        "email": EmailAddress("social@test.com"),
        "username": None,
        "password": None,
        "auth_providers": {AuthProvider(ProviderType.GOOGLE, "google-123", datetime.now(UTC))},
        "status": UserStatus.ACTIVE,
        "email_verified": True,
        "id": uuid.uuid4(),
        "created_by": uuid.uuid4(),
    }
    defaults.update(overrides)
    return User(**defaults)


@pytest.fixture
def uow() -> FakeIamUnitOfWork:
    return FakeIamUnitOfWork()


@pytest.fixture
def service(uow: FakeIamUnitOfWork) -> AuthenticationService:
    return AuthenticationService(uow, FakePasswordHasher(), FakeTokenService())


class TestSetOnboardingUsername:
    """Tests for AuthenticationService.set_onboarding_username()."""

    async def test_set_username_success(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """Social-only user (username=None) -> set username succeeds."""
        user = _make_social_user()
        uow.users.add(user)
        user.collect_events()

        cmd = SetOnboardingUsername(user_id=str(user.id), username="mynewname")
        await service.set_onboarding_username(cmd)

        assert user.username == Username("mynewname")

        # Aggregate event: UserUsernameChanged
        agg_events = user.collect_events()
        assert any(isinstance(e, UserUsernameChanged) for e in agg_events)
        assert uow.committed is True

    async def test_username_already_taken(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """Username already exists -> UsernameAlreadyExistsError."""
        # Create an existing user with the desired username
        existing = User(
            email=EmailAddress("existing@test.com"),
            username=Username("takenname"),
            status=UserStatus.ACTIVE,
            email_verified=True,
            id=uuid.uuid4(),
            created_by=uuid.uuid4(),
        )
        uow.users.add(existing)

        user = _make_social_user()
        uow.users.add(user)

        cmd = SetOnboardingUsername(user_id=str(user.id), username="takenname")

        with pytest.raises(UsernameAlreadyExistsError):
            await service.set_onboarding_username(cmd)

    async def test_invalid_username_format(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """Too short username -> InvalidUsernameError."""
        user = _make_social_user()
        uow.users.add(user)

        cmd = SetOnboardingUsername(user_id=str(user.id), username="a")

        with pytest.raises(InvalidUsernameError):
            await service.set_onboarding_username(cmd)

    async def test_user_not_found(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """Invalid user_id -> AuthenticationFailedError."""
        cmd = SetOnboardingUsername(user_id=str(uuid.uuid4()), username="validname")

        with pytest.raises(AuthenticationFailedError):
            await service.set_onboarding_username(cmd)

    async def test_overwrite_existing_username(
        self, uow: FakeIamUnitOfWork, service: AuthenticationService
    ) -> None:
        """User with existing username -> update_username still works."""
        user = _make_social_user(username=Username("oldname"))
        uow.users.add(user)
        user.collect_events()

        cmd = SetOnboardingUsername(user_id=str(user.id), username="newname123")
        await service.set_onboarding_username(cmd)

        assert user.username == Username("newname123")

        agg_events = user.collect_events()
        changed_events = [e for e in agg_events if isinstance(e, UserUsernameChanged)]
        assert len(changed_events) == 1
        assert changed_events[0].old_username == "oldname"
        assert changed_events[0].new_username == "newname123"
        assert uow.committed is True
