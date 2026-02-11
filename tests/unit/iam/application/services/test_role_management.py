import uuid
from typing import Any

import pytest

from emerald.iam.application.dtos.commands import (
    DemoteToUser,
    GrantAdminPermission,
    PromoteToAdmin,
    RevokeAdminPermission,
)
from emerald.iam.application.services.role_management import RoleManagementService
from emerald.iam.domain.exceptions import (
    CannotDemoteSuperadminError,
    CannotGrantUnownedPermissionError,
    EmptyAdminPermissionsError,
    InsufficientPermissionsError,
    InvalidRoleTransitionError,
    LastAdminPermissionError,
    NotAdminError,
)
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.admin_permission import (
    AdminPermission,
    AdminPermissionType,
)
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.user_status import UserStatus
from emerald.iam.domain.models.value_objects.username import Username
from emerald.shared_kernel.domain.exceptions import NotFoundError
from tests.unit.iam.fakes import FakeIamUnitOfWork

MASTER_DATA = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
USER_SUPPORT = AdminPermission(AdminPermissionType.USER_SUPPORT_ADMIN)
COMPLIANCE = AdminPermission(AdminPermissionType.COMPLIANCE_ADMIN)
FULL = AdminPermission(AdminPermissionType.FULL_ADMIN)


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


def _setup() -> tuple[FakeIamUnitOfWork, RoleManagementService]:
    uow = FakeIamUnitOfWork()
    svc = RoleManagementService(uow)
    return uow, svc


# ---------------------------------------------------------------------------
# promote_to_admin
# ---------------------------------------------------------------------------


def test_promote_to_admin_happy_path():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    target = _make_user()
    uow.users.add(superadmin)
    uow.users.add(target)

    cmd = PromoteToAdmin(
        user_id=str(target.id),
        permissions=["MASTER_DATA_ADMIN"],
        promoted_by_id=str(superadmin.id),
    )
    svc.promote_to_admin(cmd)

    assert target.system_role == SystemRole.ADMIN
    assert target.admin_permissions == frozenset({MASTER_DATA})


def test_promote_to_admin_with_multiple_permissions():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    target = _make_user()
    uow.users.add(superadmin)
    uow.users.add(target)

    cmd = PromoteToAdmin(
        user_id=str(target.id),
        permissions=["MASTER_DATA_ADMIN", "COMPLIANCE_ADMIN"],
        promoted_by_id=str(superadmin.id),
    )
    svc.promote_to_admin(cmd)

    assert target.system_role == SystemRole.ADMIN
    assert target.admin_permissions == frozenset({MASTER_DATA, COMPLIANCE})


def test_promote_to_admin_self_promotion_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    uow.users.add(superadmin)

    cmd = PromoteToAdmin(
        user_id=str(superadmin.id),
        permissions=["MASTER_DATA_ADMIN"],
        promoted_by_id=str(superadmin.id),
    )

    with pytest.raises(InsufficientPermissionsError):
        svc.promote_to_admin(cmd)


def test_promote_to_admin_actor_not_found_raises():
    uow, svc = _setup()
    target = _make_user()
    uow.users.add(target)

    cmd = PromoteToAdmin(
        user_id=str(target.id),
        permissions=["MASTER_DATA_ADMIN"],
        promoted_by_id=str(uuid.uuid4()),
    )

    with pytest.raises(NotFoundError):
        svc.promote_to_admin(cmd)


def test_promote_to_admin_target_not_found_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    uow.users.add(superadmin)

    cmd = PromoteToAdmin(
        user_id=str(uuid.uuid4()),
        permissions=["MASTER_DATA_ADMIN"],
        promoted_by_id=str(superadmin.id),
    )

    with pytest.raises(NotFoundError):
        svc.promote_to_admin(cmd)


def test_promote_to_admin_non_superadmin_actor_raises():
    uow, svc = _setup()
    admin_actor = _make_admin()
    target = _make_user()
    uow.users.add(admin_actor)
    uow.users.add(target)

    cmd = PromoteToAdmin(
        user_id=str(target.id),
        permissions=["MASTER_DATA_ADMIN"],
        promoted_by_id=str(admin_actor.id),
    )

    with pytest.raises(InsufficientPermissionsError):
        svc.promote_to_admin(cmd)


def test_promote_to_admin_user_actor_raises():
    uow, svc = _setup()
    user_actor = _make_user()
    target = _make_user()
    uow.users.add(user_actor)
    uow.users.add(target)

    cmd = PromoteToAdmin(
        user_id=str(target.id),
        permissions=["MASTER_DATA_ADMIN"],
        promoted_by_id=str(user_actor.id),
    )

    with pytest.raises(InsufficientPermissionsError):
        svc.promote_to_admin(cmd)


def test_promote_to_admin_target_not_user_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    already_admin = _make_admin()
    uow.users.add(superadmin)
    uow.users.add(already_admin)

    cmd = PromoteToAdmin(
        user_id=str(already_admin.id),
        permissions=["MASTER_DATA_ADMIN"],
        promoted_by_id=str(superadmin.id),
    )

    with pytest.raises(InvalidRoleTransitionError):
        svc.promote_to_admin(cmd)


def test_promote_to_admin_empty_permissions_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    target = _make_user()
    uow.users.add(superadmin)
    uow.users.add(target)

    cmd = PromoteToAdmin(
        user_id=str(target.id),
        permissions=[],
        promoted_by_id=str(superadmin.id),
    )

    with pytest.raises(EmptyAdminPermissionsError):
        svc.promote_to_admin(cmd)


def test_promote_to_admin_commits_uow():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    target = _make_user()
    uow.users.add(superadmin)
    uow.users.add(target)

    cmd = PromoteToAdmin(
        user_id=str(target.id),
        permissions=["MASTER_DATA_ADMIN"],
        promoted_by_id=str(superadmin.id),
    )
    svc.promote_to_admin(cmd)

    assert uow.committed is True


# ---------------------------------------------------------------------------
# demote_to_user
# ---------------------------------------------------------------------------


def test_demote_to_user_happy_path():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    admin_target = _make_admin()
    uow.users.add(superadmin)
    uow.users.add(admin_target)

    cmd = DemoteToUser(
        user_id=str(admin_target.id),
        demoted_by_id=str(superadmin.id),
    )
    svc.demote_to_user(cmd)

    assert admin_target.system_role == SystemRole.USER
    assert admin_target.admin_permissions is None


def test_demote_to_user_self_demotion_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    uow.users.add(superadmin)

    cmd = DemoteToUser(
        user_id=str(superadmin.id),
        demoted_by_id=str(superadmin.id),
    )

    with pytest.raises(InsufficientPermissionsError):
        svc.demote_to_user(cmd)


def test_demote_to_user_actor_not_found_raises():
    uow, svc = _setup()
    admin_target = _make_admin()
    uow.users.add(admin_target)

    cmd = DemoteToUser(
        user_id=str(admin_target.id),
        demoted_by_id=str(uuid.uuid4()),
    )

    with pytest.raises(NotFoundError):
        svc.demote_to_user(cmd)


def test_demote_to_user_target_not_found_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    uow.users.add(superadmin)

    cmd = DemoteToUser(
        user_id=str(uuid.uuid4()),
        demoted_by_id=str(superadmin.id),
    )

    with pytest.raises(NotFoundError):
        svc.demote_to_user(cmd)


def test_demote_superadmin_raises():
    uow, svc = _setup()
    superadmin_actor = _make_superadmin()
    superadmin_target = _make_superadmin()
    uow.users.add(superadmin_actor)
    uow.users.add(superadmin_target)

    cmd = DemoteToUser(
        user_id=str(superadmin_target.id),
        demoted_by_id=str(superadmin_actor.id),
    )

    with pytest.raises(CannotDemoteSuperadminError):
        svc.demote_to_user(cmd)


def test_demote_regular_user_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    regular_user = _make_user()
    uow.users.add(superadmin)
    uow.users.add(regular_user)

    cmd = DemoteToUser(
        user_id=str(regular_user.id),
        demoted_by_id=str(superadmin.id),
    )

    with pytest.raises(InvalidRoleTransitionError):
        svc.demote_to_user(cmd)


def test_demote_non_superadmin_actor_raises():
    uow, svc = _setup()
    admin_actor = _make_admin()
    admin_target = _make_admin()
    uow.users.add(admin_actor)
    uow.users.add(admin_target)

    cmd = DemoteToUser(
        user_id=str(admin_target.id),
        demoted_by_id=str(admin_actor.id),
    )

    with pytest.raises(InsufficientPermissionsError):
        svc.demote_to_user(cmd)


def test_demote_to_user_commits_uow():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    admin_target = _make_admin()
    uow.users.add(superadmin)
    uow.users.add(admin_target)

    cmd = DemoteToUser(
        user_id=str(admin_target.id),
        demoted_by_id=str(superadmin.id),
    )
    svc.demote_to_user(cmd)

    assert uow.committed is True


# ---------------------------------------------------------------------------
# grant_admin_permission
# ---------------------------------------------------------------------------


def test_grant_permission_superadmin_grants():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA}))
    uow.users.add(superadmin)
    uow.users.add(admin_target)

    cmd = GrantAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        granted_by_id=str(superadmin.id),
    )
    svc.grant_admin_permission(cmd)

    assert admin_target.admin_permissions is not None
    assert USER_SUPPORT in admin_target.admin_permissions


def test_grant_permission_admin_with_full_admin_grants():
    uow, svc = _setup()
    full_admin_actor = _make_admin(permissions=frozenset({FULL}))
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA}))
    uow.users.add(full_admin_actor)
    uow.users.add(admin_target)

    cmd = GrantAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        granted_by_id=str(full_admin_actor.id),
    )
    svc.grant_admin_permission(cmd)

    assert admin_target.admin_permissions is not None
    assert USER_SUPPORT in admin_target.admin_permissions


def test_grant_permission_admin_with_matching_permission_grants():
    uow, svc = _setup()
    admin_actor = _make_admin(permissions=frozenset({MASTER_DATA, USER_SUPPORT}))
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA}))
    uow.users.add(admin_actor)
    uow.users.add(admin_target)

    cmd = GrantAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        granted_by_id=str(admin_actor.id),
    )
    svc.grant_admin_permission(cmd)

    assert admin_target.admin_permissions is not None
    assert USER_SUPPORT in admin_target.admin_permissions


def test_grant_permission_self_grant_raises():
    uow, svc = _setup()
    admin = _make_admin(permissions=frozenset({MASTER_DATA}))
    uow.users.add(admin)

    cmd = GrantAdminPermission(
        user_id=str(admin.id),
        permission="USER_SUPPORT_ADMIN",
        granted_by_id=str(admin.id),
    )

    with pytest.raises(InsufficientPermissionsError):
        svc.grant_admin_permission(cmd)


def test_grant_permission_actor_not_found_raises():
    uow, svc = _setup()
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA}))
    uow.users.add(admin_target)

    cmd = GrantAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        granted_by_id=str(uuid.uuid4()),
    )

    with pytest.raises(NotFoundError):
        svc.grant_admin_permission(cmd)


def test_grant_permission_target_not_found_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    uow.users.add(superadmin)

    cmd = GrantAdminPermission(
        user_id=str(uuid.uuid4()),
        permission="USER_SUPPORT_ADMIN",
        granted_by_id=str(superadmin.id),
    )

    with pytest.raises(NotFoundError):
        svc.grant_admin_permission(cmd)


def test_grant_permission_admin_without_permission_raises():
    uow, svc = _setup()
    admin_actor = _make_admin(permissions=frozenset({MASTER_DATA}))
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA}))
    uow.users.add(admin_actor)
    uow.users.add(admin_target)

    cmd = GrantAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        granted_by_id=str(admin_actor.id),
    )

    with pytest.raises(CannotGrantUnownedPermissionError):
        svc.grant_admin_permission(cmd)


def test_grant_permission_user_actor_raises():
    uow, svc = _setup()
    user_actor = _make_user()
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA}))
    uow.users.add(user_actor)
    uow.users.add(admin_target)

    cmd = GrantAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        granted_by_id=str(user_actor.id),
    )

    with pytest.raises(InsufficientPermissionsError):
        svc.grant_admin_permission(cmd)


def test_grant_permission_to_non_admin_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    regular_user = _make_user()
    uow.users.add(superadmin)
    uow.users.add(regular_user)

    cmd = GrantAdminPermission(
        user_id=str(regular_user.id),
        permission="MASTER_DATA_ADMIN",
        granted_by_id=str(superadmin.id),
    )

    with pytest.raises(NotAdminError):
        svc.grant_admin_permission(cmd)


def test_grant_permission_commits_uow():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA}))
    uow.users.add(superadmin)
    uow.users.add(admin_target)

    cmd = GrantAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        granted_by_id=str(superadmin.id),
    )
    svc.grant_admin_permission(cmd)

    assert uow.committed is True


# ---------------------------------------------------------------------------
# revoke_admin_permission
# ---------------------------------------------------------------------------


def test_revoke_permission_happy_path():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA, USER_SUPPORT}))
    uow.users.add(superadmin)
    uow.users.add(admin_target)

    cmd = RevokeAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        revoked_by_id=str(superadmin.id),
    )
    svc.revoke_admin_permission(cmd)

    assert admin_target.admin_permissions is not None
    assert USER_SUPPORT not in admin_target.admin_permissions
    assert MASTER_DATA in admin_target.admin_permissions


def test_revoke_permission_self_revoke_raises():
    uow, svc = _setup()
    admin = _make_admin(permissions=frozenset({MASTER_DATA, USER_SUPPORT}))
    uow.users.add(admin)

    cmd = RevokeAdminPermission(
        user_id=str(admin.id),
        permission="USER_SUPPORT_ADMIN",
        revoked_by_id=str(admin.id),
    )

    with pytest.raises(InsufficientPermissionsError):
        svc.revoke_admin_permission(cmd)


def test_revoke_last_permission_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA}))
    uow.users.add(superadmin)
    uow.users.add(admin_target)

    cmd = RevokeAdminPermission(
        user_id=str(admin_target.id),
        permission="MASTER_DATA_ADMIN",
        revoked_by_id=str(superadmin.id),
    )

    with pytest.raises(LastAdminPermissionError):
        svc.revoke_admin_permission(cmd)


def test_revoke_permission_non_superadmin_actor_raises():
    uow, svc = _setup()
    admin_actor = _make_admin(permissions=frozenset({MASTER_DATA, USER_SUPPORT}))
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA, USER_SUPPORT}))
    uow.users.add(admin_actor)
    uow.users.add(admin_target)

    cmd = RevokeAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        revoked_by_id=str(admin_actor.id),
    )

    with pytest.raises(InsufficientPermissionsError):
        svc.revoke_admin_permission(cmd)


def test_revoke_permission_actor_not_found_raises():
    uow, svc = _setup()
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA, USER_SUPPORT}))
    uow.users.add(admin_target)

    cmd = RevokeAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        revoked_by_id=str(uuid.uuid4()),
    )

    with pytest.raises(NotFoundError):
        svc.revoke_admin_permission(cmd)


def test_revoke_permission_target_not_found_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    uow.users.add(superadmin)

    cmd = RevokeAdminPermission(
        user_id=str(uuid.uuid4()),
        permission="USER_SUPPORT_ADMIN",
        revoked_by_id=str(superadmin.id),
    )

    with pytest.raises(NotFoundError):
        svc.revoke_admin_permission(cmd)


def test_revoke_permission_from_non_admin_raises():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    regular_user = _make_user()
    uow.users.add(superadmin)
    uow.users.add(regular_user)

    cmd = RevokeAdminPermission(
        user_id=str(regular_user.id),
        permission="MASTER_DATA_ADMIN",
        revoked_by_id=str(superadmin.id),
    )

    with pytest.raises(NotAdminError):
        svc.revoke_admin_permission(cmd)


def test_revoke_permission_commits_uow():
    uow, svc = _setup()
    superadmin = _make_superadmin()
    admin_target = _make_admin(permissions=frozenset({MASTER_DATA, USER_SUPPORT}))
    uow.users.add(superadmin)
    uow.users.add(admin_target)

    cmd = RevokeAdminPermission(
        user_id=str(admin_target.id),
        permission="USER_SUPPORT_ADMIN",
        revoked_by_id=str(superadmin.id),
    )
    svc.revoke_admin_permission(cmd)

    assert uow.committed is True
