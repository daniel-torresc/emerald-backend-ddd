"""Integration tests for SqlAlchemyUserRepository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from emerald.iam.adapters.outbound.persistence.user_repository import (
    SqlAlchemyUserRepository,
)
from emerald.iam.domain.models.value_objects.admin_permission import (
    AdminPermission,
    AdminPermissionType,
)
from emerald.iam.domain.models.value_objects.auth_provider import AuthProvider, ProviderType
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.user_preferences import UserPreferences
from emerald.iam.domain.models.value_objects.user_status import UserStatus
from emerald.iam.domain.models.value_objects.username import Username
from emerald.shared_kernel.domain.models import Currency

from .conftest import make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestUserRepositoryAdd:
    async def test_add_and_find_by_id(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user()
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert found.id == user.id
        assert found.email.value == user.email.value
        assert found.username is not None
        assert found.username.value == user.username.value  # type: ignore[union-attr]
        assert found.status == UserStatus.ACTIVE

    async def test_add_user_with_no_password(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        now = datetime.now(UTC)
        user = make_user(
            password=None,
            auth_providers={AuthProvider(ProviderType.GOOGLE, "google-123", now)},
        )
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert found.password is None

    async def test_add_user_with_no_username(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user(username=None)
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert found.username is None

    async def test_upsert_existing_user(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user()
        await user_repo.add(user)
        await session.flush()

        # Mutate and re-add (upsert)
        user.full_name = "Updated Name"
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert found.full_name == "Updated Name"


class TestUserRepositoryRoundTrip:
    async def test_full_round_trip(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        """Verify all fields survive persist → reload."""
        now = datetime.now(UTC)
        user = make_user(
            full_name="Jane Doe",
            system_role=SystemRole.ADMIN,
            admin_permissions=frozenset(
                {
                    AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN),
                    AdminPermission(AdminPermissionType.USER_SUPPORT_ADMIN),
                }
            ),
            password_history=["old-hash-1", "old-hash-2"],
            preferences=UserPreferences(
                timezone="America/New_York",
                locale="es-MX",
                display_currency=Currency.EUR,
            ),
            last_login_at=now,
        )
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert found.full_name == "Jane Doe"
        assert found.system_role == SystemRole.ADMIN
        assert found.admin_permissions is not None
        assert len(found.admin_permissions) == 2
        assert AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN) in found.admin_permissions
        assert found.password_history == ["old-hash-1", "old-hash-2"]
        assert found.preferences.timezone == "America/New_York"
        assert found.preferences.locale == "es-MX"
        assert found.preferences.display_currency == Currency.EUR
        assert found.last_login_at is not None
        assert found.version == user.version
        assert found.created_by == user.created_by
        assert found.email_verified is True

    async def test_empty_admin_permissions_round_trip(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user(admin_permissions=None)
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert found.admin_permissions is None

    async def test_empty_password_history_round_trip(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user(password_history=[])
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert found.password_history == []


class TestUserRepositoryAuthProviderSync:
    async def test_auth_providers_persisted(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        now = datetime.now(UTC)
        user = make_user(
            auth_providers={
                AuthProvider(ProviderType.PASSWORD, None, now),
                AuthProvider(ProviderType.GOOGLE, "google-ext-id", now),
            }
        )
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert len(found.auth_providers) == 2
        provider_types = {p.provider_type for p in found.auth_providers}
        assert ProviderType.PASSWORD in provider_types
        assert ProviderType.GOOGLE in provider_types

    async def test_add_new_provider_on_update(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        now = datetime.now(UTC)
        user = make_user(auth_providers={AuthProvider(ProviderType.PASSWORD, None, now)})
        await user_repo.add(user)
        await session.flush()

        # Add Google provider
        user.auth_providers.add(AuthProvider(ProviderType.GOOGLE, "g-123", now))
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert len(found.auth_providers) == 2

    async def test_remove_provider_on_update(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        now = datetime.now(UTC)
        user = make_user(
            auth_providers={
                AuthProvider(ProviderType.PASSWORD, None, now),
                AuthProvider(ProviderType.GOOGLE, "g-123", now),
            }
        )
        await user_repo.add(user)
        await session.flush()

        # Remove Google
        user.auth_providers = {AuthProvider(ProviderType.PASSWORD, None, now)}
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert len(found.auth_providers) == 1
        assert list(found.auth_providers)[0].provider_type == ProviderType.PASSWORD

    async def test_empty_auth_providers(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user(auth_providers=set())
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_id(user.id)
        assert found is not None
        assert len(found.auth_providers) == 0


class TestUserRepositoryFinders:
    async def test_find_by_email_case_insensitive(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user(email=EmailAddress(value="test@example.com"))
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_email(EmailAddress(value="TEST@EXAMPLE.COM"))
        assert found is not None
        assert found.id == user.id

    async def test_find_by_email_not_found(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        found = await user_repo.find_by_email(EmailAddress(value="missing@example.com"))
        assert found is None

    async def test_find_by_username_case_insensitive(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user(username=Username(value="johndoe"))
        await user_repo.add(user)
        await session.flush()

        found = await user_repo.find_by_username(Username(value="JohnDoe"))
        assert found is not None
        assert found.id == user.id

    async def test_find_by_username_not_found(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        found = await user_repo.find_by_username(Username(value="nobody123"))
        assert found is None

    async def test_find_by_id_not_found(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        found = await user_repo.find_by_id(uuid.uuid4())
        assert found is None


class TestUserRepositoryExists:
    async def test_exists_by_email(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user(email=EmailAddress(value="exists@example.com"))
        await user_repo.add(user)
        await session.flush()

        assert await user_repo.exists_by_email(EmailAddress(value="EXISTS@EXAMPLE.COM")) is True
        assert await user_repo.exists_by_email(EmailAddress(value="nope@example.com")) is False

    async def test_exists_by_username_includes_deleted(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        now = datetime.now(UTC)
        user = make_user(username=Username(value="deleteduser"))
        user.deleted_at = now
        user.deleted_by = user.id
        await user_repo.add(user)
        await session.flush()

        # With include_recently_deleted=True (default)
        assert await user_repo.exists_by_username(Username(value="DeletedUser")) is True

    async def test_exists_by_username_excludes_deleted(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        now = datetime.now(UTC)
        user = make_user(username=Username(value="gonegone"))
        user.deleted_at = now
        user.deleted_by = user.id
        await user_repo.add(user)
        await session.flush()

        assert (
            await user_repo.exists_by_username(
                Username(value="GoneGone"), include_recently_deleted=False
            )
            is False
        )

    async def test_exists_by_role(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user = make_user(system_role=SystemRole.ADMIN)
        await user_repo.add(user)
        await session.flush()

        assert await user_repo.exists_by_role(SystemRole.ADMIN) is True
        assert await user_repo.exists_by_role(SystemRole.SUPERADMIN) is False


class TestUserRepositoryConstraints:
    async def test_unique_email_constraint(
        self, user_repo: SqlAlchemyUserRepository, session: AsyncSession
    ) -> None:
        user1 = make_user(email=EmailAddress(value="unique@example.com"))
        user2 = make_user(email=EmailAddress(value="unique@example.com"))
        await user_repo.add(user1)
        await session.flush()
        await user_repo.add(user2)

        with pytest.raises(IntegrityError):
            await session.flush()
