import uuid
from typing import Any

import pytest

from emerald.iam.domain.events.role_events import (
    AdminPermissionGranted,
    AdminPermissionRevoked,
    UserDemotedToUser,
    UserPromotedToAdmin,
)
from emerald.iam.domain.exceptions import (
    CannotDeleteSuperadminError,
    CannotDemoteSuperadminError,
    CannotGrantUnownedPermissionError,
    CannotSuspendSuperadminError,
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
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)

MASTER_DATA = AdminPermission(AdminPermissionType.MASTER_DATA_ADMIN)
USER_SUPPORT = AdminPermission(AdminPermissionType.USER_SUPPORT_ADMIN)
COMPLIANCE = AdminPermission(AdminPermissionType.COMPLIANCE_ADMIN)
FULL = AdminPermission(AdminPermissionType.FULL_ADMIN)


def _make_user(**overrides: Any) -> User:
    defaults: dict[str, Any] = {
        "email": EmailAddress("user@example.com"),
        "username": Username("testuser"),
        "password": HashedPassword("hashed:pw"),
        "status": UserStatus.ACTIVE,
        "email_verified": True,
        "id": uuid.uuid4(),
        "created_by": uuid.uuid4(),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_admin(**overrides: Any) -> User:
    user = _make_user(**overrides)
    user.system_role = SystemRole.ADMIN
    user.admin_permissions = frozenset({MASTER_DATA})
    return user


def _make_superadmin(**overrides: Any) -> User:
    user = _make_user(**overrides)
    user.system_role = SystemRole.SUPERADMIN
    return user


# -- promote_to_admin (AC-03) --------------------------------------------------


class TestPromoteToAdmin:
    def test_happy_path_superadmin_promotes_user(self):
        user = _make_user()
        promoter_id = uuid.uuid4()
        user.promote_to_admin(
            permissions={MASTER_DATA, USER_SUPPORT},
            promoted_by_role=SystemRole.SUPERADMIN,
            promoted_by_id=promoter_id,
        )
        assert user.system_role == SystemRole.ADMIN

    def test_system_role_becomes_admin(self):
        user = _make_user()
        user.promote_to_admin(
            permissions={MASTER_DATA},
            promoted_by_role=SystemRole.SUPERADMIN,
            promoted_by_id=uuid.uuid4(),
        )
        assert user.system_role == SystemRole.ADMIN

    def test_admin_permissions_set_correctly(self):
        user = _make_user()
        user.promote_to_admin(
            permissions={MASTER_DATA, COMPLIANCE},
            promoted_by_role=SystemRole.SUPERADMIN,
            promoted_by_id=uuid.uuid4(),
        )
        assert user.admin_permissions == frozenset({MASTER_DATA, COMPLIANCE})

    def test_emits_user_promoted_to_admin_event(self):
        user = _make_user()
        promoter_id = uuid.uuid4()
        user.promote_to_admin(
            permissions={MASTER_DATA},
            promoted_by_role=SystemRole.SUPERADMIN,
            promoted_by_id=promoter_id,
        )
        events = user.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, UserPromotedToAdmin)
        assert event.aggregate_id == user.id
        assert event.promoted_by_id == promoter_id
        assert event.permissions == frozenset({"MASTER_DATA_ADMIN"})

    def test_event_permissions_as_frozenset_of_strings(self):
        user = _make_user()
        user.promote_to_admin(
            permissions={MASTER_DATA, USER_SUPPORT},
            promoted_by_role=SystemRole.SUPERADMIN,
            promoted_by_id=uuid.uuid4(),
        )
        events = user.collect_events()
        event = events[0]
        assert isinstance(event, UserPromotedToAdmin)
        assert event.permissions == frozenset({"MASTER_DATA_ADMIN", "USER_SUPPORT_ADMIN"})

    def test_empty_permissions_raises_empty_admin_permissions_error(self):
        user = _make_user()
        with pytest.raises(EmptyAdminPermissionsError):
            user.promote_to_admin(
                permissions=set(),
                promoted_by_role=SystemRole.SUPERADMIN,
                promoted_by_id=uuid.uuid4(),
            )

    def test_promote_admin_raises_invalid_role_transition(self):
        admin = _make_admin()
        with pytest.raises(InvalidRoleTransitionError, match="must be USER"):
            admin.promote_to_admin(
                permissions={USER_SUPPORT},
                promoted_by_role=SystemRole.SUPERADMIN,
                promoted_by_id=uuid.uuid4(),
            )

    def test_promote_superadmin_raises_invalid_role_transition(self):
        superadmin = _make_superadmin()
        with pytest.raises(InvalidRoleTransitionError, match="must be USER"):
            superadmin.promote_to_admin(
                permissions={MASTER_DATA},
                promoted_by_role=SystemRole.SUPERADMIN,
                promoted_by_id=uuid.uuid4(),
            )

    def test_non_superadmin_promoting_raises_insufficient_permissions(self):
        user = _make_user()
        with pytest.raises(InsufficientPermissionsError, match="Only SUPERADMIN"):
            user.promote_to_admin(
                permissions={MASTER_DATA},
                promoted_by_role=SystemRole.ADMIN,
                promoted_by_id=uuid.uuid4(),
            )

    def test_user_role_promoting_raises_insufficient_permissions(self):
        user = _make_user()
        with pytest.raises(InsufficientPermissionsError, match="Only SUPERADMIN"):
            user.promote_to_admin(
                permissions={MASTER_DATA},
                promoted_by_role=SystemRole.USER,
                promoted_by_id=uuid.uuid4(),
            )


# -- demote_to_user (AC-04) ---------------------------------------------------


class TestDemoteToUser:
    def test_happy_path_superadmin_demotes_admin(self):
        admin = _make_admin()
        demoter_id = uuid.uuid4()
        admin.demote_to_user(
            demoted_by_role=SystemRole.SUPERADMIN,
            demoted_by_id=demoter_id,
        )
        assert admin.system_role == SystemRole.USER
        assert admin.admin_permissions is None

    def test_system_role_becomes_user(self):
        admin = _make_admin()
        admin.demote_to_user(
            demoted_by_role=SystemRole.SUPERADMIN,
            demoted_by_id=uuid.uuid4(),
        )
        assert admin.system_role == SystemRole.USER

    def test_admin_permissions_cleared(self):
        admin = _make_admin()
        admin.demote_to_user(
            demoted_by_role=SystemRole.SUPERADMIN,
            demoted_by_id=uuid.uuid4(),
        )
        assert admin.admin_permissions is None

    def test_emits_user_demoted_to_user_event(self):
        admin = _make_admin()
        demoter_id = uuid.uuid4()
        admin.demote_to_user(
            demoted_by_role=SystemRole.SUPERADMIN,
            demoted_by_id=demoter_id,
        )
        events = admin.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, UserDemotedToUser)
        assert event.aggregate_id == admin.id
        assert event.demoted_by_id == demoter_id

    def test_demote_superadmin_raises_cannot_demote(self):
        superadmin = _make_superadmin()
        with pytest.raises(CannotDemoteSuperadminError):
            superadmin.demote_to_user(
                demoted_by_role=SystemRole.SUPERADMIN,
                demoted_by_id=uuid.uuid4(),
            )

    def test_demote_user_raises_invalid_role_transition(self):
        user = _make_user()
        with pytest.raises(InvalidRoleTransitionError, match="must be ADMIN"):
            user.demote_to_user(
                demoted_by_role=SystemRole.SUPERADMIN,
                demoted_by_id=uuid.uuid4(),
            )

    def test_non_superadmin_demoting_raises_insufficient_permissions(self):
        admin = _make_admin()
        with pytest.raises(InsufficientPermissionsError, match="Only SUPERADMIN"):
            admin.demote_to_user(
                demoted_by_role=SystemRole.ADMIN,
                demoted_by_id=uuid.uuid4(),
            )


# -- grant_admin_permission (AC-05) -------------------------------------------


class TestGrantAdminPermission:
    def test_happy_path_grant_new_permission(self):
        admin = _make_admin()  # has MASTER_DATA
        granter_id = uuid.uuid4()
        admin.grant_admin_permission(
            permission=USER_SUPPORT,
            granted_by_role=SystemRole.SUPERADMIN,
            granted_by_id=granter_id,
            granted_by_has_permission=True,
        )
        assert admin.admin_permissions is not None
        assert USER_SUPPORT in admin.admin_permissions
        assert MASTER_DATA in admin.admin_permissions

    def test_emits_admin_permission_granted_event(self):
        admin = _make_admin()
        granter_id = uuid.uuid4()
        admin.grant_admin_permission(
            permission=USER_SUPPORT,
            granted_by_role=SystemRole.SUPERADMIN,
            granted_by_id=granter_id,
            granted_by_has_permission=True,
        )
        events = admin.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AdminPermissionGranted)
        assert event.permission == "USER_SUPPORT_ADMIN"
        assert event.granted_by_id == granter_id

    def test_granting_already_held_permission_is_idempotent(self):
        admin = _make_admin()  # has MASTER_DATA
        admin.grant_admin_permission(
            permission=MASTER_DATA,
            granted_by_role=SystemRole.SUPERADMIN,
            granted_by_id=uuid.uuid4(),
            granted_by_has_permission=True,
        )
        # No error, no event
        events = admin.collect_events()
        assert len(events) == 0

    def test_grant_to_non_admin_raises_not_admin_error(self):
        user = _make_user()
        with pytest.raises(NotAdminError):
            user.grant_admin_permission(
                permission=MASTER_DATA,
                granted_by_role=SystemRole.SUPERADMIN,
                granted_by_id=uuid.uuid4(),
                granted_by_has_permission=True,
            )

    def test_admin_without_permission_raises_cannot_grant_unowned(self):
        admin = _make_admin()
        with pytest.raises(CannotGrantUnownedPermissionError):
            admin.grant_admin_permission(
                permission=USER_SUPPORT,
                granted_by_role=SystemRole.ADMIN,
                granted_by_id=uuid.uuid4(),
                granted_by_has_permission=False,
            )

    def test_non_admin_granting_raises_insufficient_permissions(self):
        admin = _make_admin()
        with pytest.raises(InsufficientPermissionsError, match="Only ADMIN or SUPERADMIN"):
            admin.grant_admin_permission(
                permission=USER_SUPPORT,
                granted_by_role=SystemRole.USER,
                granted_by_id=uuid.uuid4(),
                granted_by_has_permission=False,
            )

    def test_admin_with_full_admin_can_grant_any_permission(self):
        admin = _make_admin()
        admin.admin_permissions = frozenset({FULL})
        admin_other = _make_admin()
        admin_other.grant_admin_permission(
            permission=COMPLIANCE,
            granted_by_role=SystemRole.ADMIN,
            granted_by_id=admin.id,
            granted_by_has_permission=True,
        )
        assert admin_other.admin_permissions is not None
        assert COMPLIANCE in admin_other.admin_permissions

    def test_superadmin_can_grant_permission(self):
        admin = _make_admin()
        admin.grant_admin_permission(
            permission=COMPLIANCE,
            granted_by_role=SystemRole.SUPERADMIN,
            granted_by_id=uuid.uuid4(),
            granted_by_has_permission=True,
        )
        assert admin.admin_permissions is not None
        assert COMPLIANCE in admin.admin_permissions


# -- revoke_admin_permission (AC-06) ------------------------------------------


class TestRevokeAdminPermission:
    def test_happy_path_revoke_permission(self):
        admin = _make_admin()
        admin.admin_permissions = frozenset({MASTER_DATA, USER_SUPPORT})
        revoker_id = uuid.uuid4()
        admin.revoke_admin_permission(
            permission=USER_SUPPORT,
            revoked_by_role=SystemRole.SUPERADMIN,
            revoked_by_id=revoker_id,
        )
        assert admin.admin_permissions is not None
        assert USER_SUPPORT not in admin.admin_permissions
        assert MASTER_DATA in admin.admin_permissions

    def test_emits_admin_permission_revoked_event(self):
        admin = _make_admin()
        admin.admin_permissions = frozenset({MASTER_DATA, COMPLIANCE})
        revoker_id = uuid.uuid4()
        admin.revoke_admin_permission(
            permission=COMPLIANCE,
            revoked_by_role=SystemRole.SUPERADMIN,
            revoked_by_id=revoker_id,
        )
        events = admin.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AdminPermissionRevoked)
        assert event.permission == "COMPLIANCE_ADMIN"
        assert event.revoked_by_id == revoker_id

    def test_revoke_last_permission_raises_last_admin_permission_error(self):
        admin = _make_admin()  # has only MASTER_DATA
        with pytest.raises(LastAdminPermissionError):
            admin.revoke_admin_permission(
                permission=MASTER_DATA,
                revoked_by_role=SystemRole.SUPERADMIN,
                revoked_by_id=uuid.uuid4(),
            )

    def test_non_superadmin_revoking_raises_insufficient_permissions(self):
        admin = _make_admin()
        admin.admin_permissions = frozenset({MASTER_DATA, USER_SUPPORT})
        with pytest.raises(InsufficientPermissionsError, match="Only SUPERADMIN"):
            admin.revoke_admin_permission(
                permission=USER_SUPPORT,
                revoked_by_role=SystemRole.ADMIN,
                revoked_by_id=uuid.uuid4(),
            )

    def test_revoke_from_non_admin_raises_not_admin_error(self):
        user = _make_user()
        with pytest.raises(NotAdminError):
            user.revoke_admin_permission(
                permission=MASTER_DATA,
                revoked_by_role=SystemRole.SUPERADMIN,
                revoked_by_id=uuid.uuid4(),
            )

    def test_revoke_non_held_permission_is_idempotent(self):
        admin = _make_admin()  # has MASTER_DATA
        admin.revoke_admin_permission(
            permission=COMPLIANCE,
            revoked_by_role=SystemRole.SUPERADMIN,
            revoked_by_id=uuid.uuid4(),
        )
        # No error, no event
        events = admin.collect_events()
        assert len(events) == 0

    def test_revoke_from_user_role_raises_insufficient_permissions(self):
        admin = _make_admin()
        admin.admin_permissions = frozenset({MASTER_DATA, USER_SUPPORT})
        with pytest.raises(InsufficientPermissionsError):
            admin.revoke_admin_permission(
                permission=USER_SUPPORT,
                revoked_by_role=SystemRole.USER,
                revoked_by_id=uuid.uuid4(),
            )


# -- has_admin_permission (AC-07) ----------------------------------------------


class TestHasAdminPermission:
    def test_superadmin_returns_true_for_any_permission(self):
        superadmin = _make_superadmin()
        assert superadmin.has_admin_permission(MASTER_DATA) is True
        assert superadmin.has_admin_permission(USER_SUPPORT) is True
        assert superadmin.has_admin_permission(COMPLIANCE) is True
        assert superadmin.has_admin_permission(FULL) is True

    def test_admin_with_matching_permission_returns_true(self):
        admin = _make_admin()  # has MASTER_DATA
        assert admin.has_admin_permission(MASTER_DATA) is True

    def test_admin_with_full_admin_returns_true_for_any(self):
        admin = _make_admin()
        admin.admin_permissions = frozenset({FULL})
        assert admin.has_admin_permission(MASTER_DATA) is True
        assert admin.has_admin_permission(USER_SUPPORT) is True
        assert admin.has_admin_permission(COMPLIANCE) is True
        assert admin.has_admin_permission(FULL) is True

    def test_admin_without_permission_returns_false(self):
        admin = _make_admin()  # has MASTER_DATA
        assert admin.has_admin_permission(USER_SUPPORT) is False
        assert admin.has_admin_permission(COMPLIANCE) is False

    def test_user_returns_false(self):
        user = _make_user()
        assert user.has_admin_permission(MASTER_DATA) is False
        assert user.has_admin_permission(FULL) is False


# -- can_access_admin_portal (AC-07) -------------------------------------------


class TestCanAccessAdminPortal:
    def test_admin_can_access(self):
        admin = _make_admin()
        assert admin.can_access_admin_portal() is True

    def test_superadmin_can_access(self):
        superadmin = _make_superadmin()
        assert superadmin.can_access_admin_portal() is True

    def test_user_cannot_access(self):
        user = _make_user()
        assert user.can_access_admin_portal() is False


# -- SUPERADMIN guards (AC-08) ------------------------------------------------


class TestSuperadminGuards:
    def test_soft_delete_superadmin_raises_cannot_delete(self):
        superadmin = _make_superadmin()
        with pytest.raises(CannotDeleteSuperadminError):
            superadmin.soft_delete(
                deleted_by=uuid.uuid4(),
                retention=RetentionPeriod(90, RetentionUnit.DAYS),
            )

    def test_suspend_superadmin_raises_cannot_suspend(self):
        superadmin = _make_superadmin()
        with pytest.raises(CannotSuspendSuperadminError):
            superadmin.suspend("reason")


# -- admin_permissions attribute -----------------------------------------------


class TestAdminPermissionsAttribute:
    def test_default_is_none(self):
        user = _make_user()
        assert user.admin_permissions is None

    def test_none_when_user_role(self):
        user = _make_user()
        assert user.system_role == SystemRole.USER
        assert user.admin_permissions is None

    def test_none_when_superadmin(self):
        superadmin = _make_superadmin()
        assert superadmin.admin_permissions is None

    def test_non_empty_frozenset_when_admin(self):
        admin = _make_admin()
        assert admin.admin_permissions is not None
        assert isinstance(admin.admin_permissions, frozenset)
        assert len(admin.admin_permissions) > 0
