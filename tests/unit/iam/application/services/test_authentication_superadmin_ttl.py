import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from emerald.iam.application.dtos.commands import LoginUser, RefreshAccessToken
from emerald.iam.application.services.authentication import AuthenticationService
from emerald.iam.domain.constants import REFRESH_TOKEN_TTL_SUPERADMIN
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.admin_permission import (
    AdminPermission,
    AdminPermissionType,
)
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.portal_context import PortalContext
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.user_status import UserStatus
from emerald.iam.domain.models.value_objects.username import Username
from tests.unit.iam.fakes import FakeIamUnitOfWork, FakePasswordHasherPort, FakeTokenPort

MASTER_DATA = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)


def _make_user(**overrides: Any) -> User:
    defaults: dict[str, Any] = {
        "email": EmailAddress(f"user{uuid.uuid4().hex[:6]}@example.com"),
        "username": Username(f"user{uuid.uuid4().hex[:6]}"),
        "password": HashedPassword("hashed:Password1!"),
        "status": UserStatus.ACTIVE,
        "email_verified": True,
        "id": uuid.uuid4(),
        "created_by": uuid.uuid4(),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_superadmin(**overrides: Any) -> User:
    user = _make_user(**overrides)
    user.system_role = SystemRole.SUPERADMIN
    return user


def _make_admin(permissions: frozenset[AdminPermission] | None = None, **overrides: Any) -> User:
    user = _make_user(**overrides)
    user.system_role = SystemRole.ADMIN
    user.admin_permissions = permissions or frozenset({MASTER_DATA})
    return user


def _setup_auth_service() -> tuple[
    FakeIamUnitOfWork, FakePasswordHasherPort, FakeTokenPort, AuthenticationService
]:
    uow = FakeIamUnitOfWork()
    hasher = FakePasswordHasherPort()
    token_service = FakeTokenPort()
    svc = AuthenticationService(uow, hasher, token_service)
    return uow, hasher, token_service, svc


def _find_latest_refresh_token(uow: FakeIamUnitOfWork, user_id: uuid.UUID):
    """Find the most recently created refresh token for a given user."""
    tokens = [t for t in uow.refresh_tokens._tokens.values() if t.user_id == user_id]
    if not tokens:
        return None
    return max(tokens, key=lambda t: t.created_at)


# ---------------------------------------------------------------------------
# Login - SUPERADMIN TTL override
# ---------------------------------------------------------------------------


async def test_superadmin_login_gets_15_minute_refresh_ttl_regular_portal():
    uow, _, _, svc = _setup_auth_service()
    superadmin = _make_superadmin(
        email=EmailAddress("sa@example.com"),
        username=Username("superadmin"),
        password=HashedPassword("hashed:Password1!"),
    )
    await uow.users.add(superadmin)

    await svc.login(
        LoginUser(email="sa@example.com", password="Password1!", portal_context="REGULAR")
    )

    token = _find_latest_refresh_token(uow, superadmin.id)
    assert token is not None
    expected_max = datetime.now(UTC) + REFRESH_TOKEN_TTL_SUPERADMIN + timedelta(seconds=5)
    expected_min = datetime.now(UTC) + REFRESH_TOKEN_TTL_SUPERADMIN - timedelta(seconds=5)
    assert expected_min <= token.expires_at <= expected_max


async def test_superadmin_login_gets_15_minute_refresh_ttl_admin_portal():
    uow, _, _, svc = _setup_auth_service()
    superadmin = _make_superadmin(
        email=EmailAddress("sa@example.com"),
        username=Username("superadmin"),
        password=HashedPassword("hashed:Password1!"),
    )
    await uow.users.add(superadmin)

    await svc.login(
        LoginUser(email="sa@example.com", password="Password1!", portal_context="ADMIN")
    )

    token = _find_latest_refresh_token(uow, superadmin.id)
    assert token is not None
    expected_max = datetime.now(UTC) + REFRESH_TOKEN_TTL_SUPERADMIN + timedelta(seconds=5)
    expected_min = datetime.now(UTC) + REFRESH_TOKEN_TTL_SUPERADMIN - timedelta(seconds=5)
    assert expected_min <= token.expires_at <= expected_max


async def test_regular_user_login_gets_portal_context_ttl_regular():
    uow, _, _, svc = _setup_auth_service()
    user = _make_user(
        email=EmailAddress("user@example.com"),
        username=Username("regularuser"),
        password=HashedPassword("hashed:Password1!"),
    )
    await uow.users.add(user)

    await svc.login(
        LoginUser(email="user@example.com", password="Password1!", portal_context="REGULAR")
    )

    token = _find_latest_refresh_token(uow, user.id)
    assert token is not None
    regular_ttl = PortalContext.REGULAR.refresh_ttl  # 7 days
    expected_max = datetime.now(UTC) + regular_ttl + timedelta(seconds=5)
    expected_min = datetime.now(UTC) + regular_ttl - timedelta(seconds=5)
    assert expected_min <= token.expires_at <= expected_max


async def test_admin_login_on_admin_portal_gets_4_hour_ttl():
    uow, _, _, svc = _setup_auth_service()
    admin = _make_admin(
        permissions=frozenset({MASTER_DATA}),
        email=EmailAddress("admin@example.com"),
        username=Username("adminuser"),
        password=HashedPassword("hashed:Password1!"),
    )
    await uow.users.add(admin)

    await svc.login(
        LoginUser(email="admin@example.com", password="Password1!", portal_context="ADMIN")
    )

    token = _find_latest_refresh_token(uow, admin.id)
    assert token is not None
    admin_ttl = PortalContext.ADMIN.refresh_ttl  # 4 hours
    expected_max = datetime.now(UTC) + admin_ttl + timedelta(seconds=5)
    expected_min = datetime.now(UTC) + admin_ttl - timedelta(seconds=5)
    assert expected_min <= token.expires_at <= expected_max


async def test_admin_login_on_regular_portal_gets_7_day_ttl():
    uow, _, _, svc = _setup_auth_service()
    admin = _make_admin(
        permissions=frozenset({MASTER_DATA}),
        email=EmailAddress("admin@example.com"),
        username=Username("adminuser"),
        password=HashedPassword("hashed:Password1!"),
    )
    await uow.users.add(admin)

    await svc.login(
        LoginUser(email="admin@example.com", password="Password1!", portal_context="REGULAR")
    )

    token = _find_latest_refresh_token(uow, admin.id)
    assert token is not None
    regular_ttl = PortalContext.REGULAR.refresh_ttl  # 7 days
    expected_max = datetime.now(UTC) + regular_ttl + timedelta(seconds=5)
    expected_min = datetime.now(UTC) + regular_ttl - timedelta(seconds=5)
    assert expected_min <= token.expires_at <= expected_max


# ---------------------------------------------------------------------------
# Refresh - SUPERADMIN TTL override
# ---------------------------------------------------------------------------


async def test_superadmin_refresh_gets_15_minute_refresh_ttl():
    uow, _, token_service, svc = _setup_auth_service()
    superadmin = _make_superadmin(
        email=EmailAddress("sa@example.com"),
        username=Username("superadmin"),
        password=HashedPassword("hashed:Password1!"),
    )
    await uow.users.add(superadmin)

    login_result = await svc.login(
        LoginUser(email="sa@example.com", password="Password1!", portal_context="REGULAR")
    )

    refresh_result = await svc.refresh(RefreshAccessToken(refresh_token=login_result.refresh_token))

    # Find the new (non-revoked) refresh token
    new_hash = await token_service.hash_token(refresh_result.refresh_token)
    new_token = await uow.refresh_tokens.find_by_hash(new_hash)
    assert new_token is not None
    expected_max = datetime.now(UTC) + REFRESH_TOKEN_TTL_SUPERADMIN + timedelta(seconds=5)
    expected_min = datetime.now(UTC) + REFRESH_TOKEN_TTL_SUPERADMIN - timedelta(seconds=5)
    assert expected_min <= new_token.expires_at <= expected_max


async def test_regular_user_refresh_keeps_portal_context_ttl():
    uow, _, token_service, svc = _setup_auth_service()
    user = _make_user(
        email=EmailAddress("user@example.com"),
        username=Username("regularuser"),
        password=HashedPassword("hashed:Password1!"),
    )
    await uow.users.add(user)

    login_result = await svc.login(
        LoginUser(email="user@example.com", password="Password1!", portal_context="REGULAR")
    )

    refresh_result = await svc.refresh(RefreshAccessToken(refresh_token=login_result.refresh_token))

    new_hash = await token_service.hash_token(refresh_result.refresh_token)
    new_token = await uow.refresh_tokens.find_by_hash(new_hash)
    assert new_token is not None
    regular_ttl = PortalContext.REGULAR.refresh_ttl  # 7 days
    expected_max = datetime.now(UTC) + regular_ttl + timedelta(seconds=5)
    expected_min = datetime.now(UTC) + regular_ttl - timedelta(seconds=5)
    assert expected_min <= new_token.expires_at <= expected_max


async def test_superadmin_refresh_on_admin_portal_still_gets_15_minute_ttl():
    uow, _, token_service, svc = _setup_auth_service()
    superadmin = _make_superadmin(
        email=EmailAddress("sa@example.com"),
        username=Username("superadmin"),
        password=HashedPassword("hashed:Password1!"),
    )
    await uow.users.add(superadmin)

    login_result = await svc.login(
        LoginUser(email="sa@example.com", password="Password1!", portal_context="ADMIN")
    )

    refresh_result = await svc.refresh(RefreshAccessToken(refresh_token=login_result.refresh_token))

    new_hash = await token_service.hash_token(refresh_result.refresh_token)
    new_token = await uow.refresh_tokens.find_by_hash(new_hash)
    assert new_token is not None
    expected_max = datetime.now(UTC) + REFRESH_TOKEN_TTL_SUPERADMIN + timedelta(seconds=5)
    expected_min = datetime.now(UTC) + REFRESH_TOKEN_TTL_SUPERADMIN - timedelta(seconds=5)
    assert expected_min <= new_token.expires_at <= expected_max


async def test_admin_refresh_on_admin_portal_gets_4_hour_ttl():
    uow, _, token_service, svc = _setup_auth_service()
    admin = _make_admin(
        permissions=frozenset({MASTER_DATA}),
        email=EmailAddress("admin@example.com"),
        username=Username("adminuser"),
        password=HashedPassword("hashed:Password1!"),
    )
    await uow.users.add(admin)

    login_result = await svc.login(
        LoginUser(email="admin@example.com", password="Password1!", portal_context="ADMIN")
    )

    refresh_result = await svc.refresh(RefreshAccessToken(refresh_token=login_result.refresh_token))

    new_hash = await token_service.hash_token(refresh_result.refresh_token)
    new_token = await uow.refresh_tokens.find_by_hash(new_hash)
    assert new_token is not None
    admin_ttl = PortalContext.ADMIN.refresh_ttl  # 4 hours
    expected_max = datetime.now(UTC) + admin_ttl + timedelta(seconds=5)
    expected_min = datetime.now(UTC) + admin_ttl - timedelta(seconds=5)
    assert expected_min <= new_token.expires_at <= expected_max
