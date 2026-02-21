"""IAM integration test fixtures and factory helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from emerald.iam.adapters.outbound.persistence.password_reset_token_repository import (
    SqlAlchemyPasswordResetTokenRepository,
)
from emerald.iam.adapters.outbound.persistence.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from emerald.iam.adapters.outbound.persistence.unit_of_work import (
    SqlAlchemyIamUnitOfWork,
)
from emerald.iam.adapters.outbound.persistence.user_repository import (
    SqlAlchemyUserRepository,
)
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.entities.password_reset_token import PasswordResetToken
from emerald.iam.domain.models.entities.refresh_token import RefreshToken
from emerald.iam.domain.models.value_objects.auth_provider import AuthProvider, ProviderType
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.portal_context import PortalContext
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.user_preferences import UserPreferences
from emerald.iam.domain.models.value_objects.user_status import UserStatus
from emerald.iam.domain.models.value_objects.username import Username
from emerald.shared_kernel.domain.models import Currency


@pytest.fixture
def user_repo(session: AsyncSession) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


@pytest.fixture
def refresh_token_repo(session: AsyncSession) -> SqlAlchemyRefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


@pytest.fixture
def password_reset_token_repo(session: AsyncSession) -> SqlAlchemyPasswordResetTokenRepository:
    return SqlAlchemyPasswordResetTokenRepository(session)


@pytest.fixture
def iam_uow(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyIamUnitOfWork:
    return SqlAlchemyIamUnitOfWork(session_factory)


def make_user(**overrides: Any) -> User:
    """Create a User domain entity with sensible defaults."""
    user_id = overrides.pop("id", uuid.uuid4())
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "email": EmailAddress(value=f"user-{user_id}@example.com"),
        "username": Username(value=f"user{str(user_id)[:8]}"),
        "password": HashedPassword(hashed_value="hashed:testpass123"),
        "password_history": [],
        "auth_providers": {AuthProvider(ProviderType.PASSWORD, None, now)},
        "status": UserStatus.ACTIVE,
        "email_verified": True,
        "preferences": UserPreferences(
            timezone="UTC", locale="en-US", display_currency=Currency.USD
        ),
        "full_name": "Test User",
        "last_login_at": None,
        "suspension_reason": None,
        "system_role": SystemRole.USER,
        "admin_permissions": None,
        "created_by": user_id,
        "version": 1,
        "created_at": now,
    }
    defaults.update(overrides)
    user = User(id=user_id, **defaults)
    # Clear construction events
    user.collect_events()
    return user


def make_refresh_token(user_id: uuid.UUID, **overrides: Any) -> RefreshToken:
    """Create a RefreshToken with sensible defaults."""
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "token_hash": f"hash-{uuid.uuid4()}",
        "family_id": uuid.uuid4(),
        "portal_context": PortalContext.REGULAR,
        "expires_at": now + timedelta(days=7),
        "created_at": now,
        "revoked_at": None,
    }
    defaults.update(overrides)
    return RefreshToken(**defaults)


def make_password_reset_token(user_id: uuid.UUID, **overrides: Any) -> PasswordResetToken:
    """Create a PasswordResetToken with sensible defaults."""
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "token_hash": f"reset-hash-{uuid.uuid4()}",
        "expires_at": now + timedelta(hours=1),
        "created_at": now,
        "used_at": None,
    }
    defaults.update(overrides)
    return PasswordResetToken(**defaults)
