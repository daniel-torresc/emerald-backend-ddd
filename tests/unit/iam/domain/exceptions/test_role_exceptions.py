import pytest

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
    SuperadminAlreadyExistsError,
)
from emerald.shared_kernel.domain.exceptions import (
    AlreadyExistsError,
    DomainError,
    InvalidValueError,
    InvariantViolationError,
)


class TestRoleExceptionHierarchy:
    """All role/permission exceptions extend the correct Shared Kernel parents."""

    @pytest.mark.parametrize(
        ("exception_cls", "parent_cls", "code"),
        [
            (InvalidRoleTransitionError, InvariantViolationError, "INVALID_ROLE_TRANSITION"),
            (CannotDemoteSuperadminError, InvariantViolationError, "CANNOT_DEMOTE_SUPERADMIN"),
            (CannotDeleteSuperadminError, InvariantViolationError, "CANNOT_DELETE_SUPERADMIN"),
            (CannotSuspendSuperadminError, InvariantViolationError, "CANNOT_SUSPEND_SUPERADMIN"),
            (EmptyAdminPermissionsError, InvalidValueError, "EMPTY_ADMIN_PERMISSIONS"),
            (InsufficientPermissionsError, DomainError, "INSUFFICIENT_PERMISSIONS"),
            (NotAdminError, InvariantViolationError, "NOT_ADMIN"),
            (CannotGrantUnownedPermissionError, DomainError, "CANNOT_GRANT_UNOWNED_PERMISSION"),
            (LastAdminPermissionError, InvariantViolationError, "LAST_ADMIN_PERMISSION"),
            (SuperadminAlreadyExistsError, AlreadyExistsError, "SUPERADMIN_ALREADY_EXISTS"),
        ],
    )
    def test_inherits_correct_parent(self, exception_cls, parent_cls, code):
        exc = exception_cls()
        assert isinstance(exc, parent_cls)
        assert isinstance(exc, DomainError)
        assert exc.code == code

    @pytest.mark.parametrize(
        ("exception_cls", "code"),
        [
            (InvalidRoleTransitionError, "INVALID_ROLE_TRANSITION"),
            (CannotDemoteSuperadminError, "CANNOT_DEMOTE_SUPERADMIN"),
            (CannotDeleteSuperadminError, "CANNOT_DELETE_SUPERADMIN"),
            (CannotSuspendSuperadminError, "CANNOT_SUSPEND_SUPERADMIN"),
            (EmptyAdminPermissionsError, "EMPTY_ADMIN_PERMISSIONS"),
            (InsufficientPermissionsError, "INSUFFICIENT_PERMISSIONS"),
            (NotAdminError, "NOT_ADMIN"),
            (CannotGrantUnownedPermissionError, "CANNOT_GRANT_UNOWNED_PERMISSION"),
            (LastAdminPermissionError, "LAST_ADMIN_PERMISSION"),
            (SuperadminAlreadyExistsError, "SUPERADMIN_ALREADY_EXISTS"),
        ],
    )
    def test_custom_message_with_default_code(self, exception_cls, code):
        exc = exception_cls("custom message")
        assert exc.code == code
        assert exc.message == "custom message"
        assert str(exc) == "custom message"


class TestRoleExceptionDefaultMessages:
    def test_invalid_role_transition_default_message(self):
        exc = InvalidRoleTransitionError()
        assert exc.message == "Invalid role transition"

    def test_cannot_demote_superadmin_default_message(self):
        exc = CannotDemoteSuperadminError()
        assert exc.message == "Cannot demote SUPERADMIN"

    def test_cannot_delete_superadmin_default_message(self):
        exc = CannotDeleteSuperadminError()
        assert exc.message == "Cannot delete SUPERADMIN"

    def test_cannot_suspend_superadmin_default_message(self):
        exc = CannotSuspendSuperadminError()
        assert exc.message == "Cannot suspend SUPERADMIN"

    def test_empty_admin_permissions_default_message(self):
        exc = EmptyAdminPermissionsError()
        assert exc.message == "Admin permissions must not be empty"

    def test_insufficient_permissions_default_message(self):
        exc = InsufficientPermissionsError()
        assert exc.message == "Insufficient permissions"

    def test_not_admin_default_message(self):
        exc = NotAdminError()
        assert exc.message == "User is not an admin"

    def test_cannot_grant_unowned_default_message(self):
        exc = CannotGrantUnownedPermissionError()
        assert exc.message == "Cannot grant a permission you do not have"

    def test_last_admin_permission_default_message(self):
        exc = LastAdminPermissionError()
        assert exc.message == "Cannot revoke last admin permission"

    def test_superadmin_already_exists_default_message(self):
        exc = SuperadminAlreadyExistsError()
        assert exc.message == "SUPERADMIN already exists"


class TestRoleExceptionCatchByParent:
    def test_catch_invariant_violation_from_role_transition(self):
        with pytest.raises(InvariantViolationError):
            raise InvalidRoleTransitionError("bad transition")

    def test_catch_invalid_value_from_empty_permissions(self):
        with pytest.raises(InvalidValueError):
            raise EmptyAdminPermissionsError("empty perms")

    def test_catch_domain_error_from_insufficient_permissions(self):
        with pytest.raises(DomainError):
            raise InsufficientPermissionsError("not enough")

    def test_catch_domain_error_from_cannot_grant_unowned(self):
        with pytest.raises(DomainError):
            raise CannotGrantUnownedPermissionError("cannot grant")

    def test_catch_already_exists_from_superadmin_already_exists(self):
        with pytest.raises(AlreadyExistsError):
            raise SuperadminAlreadyExistsError("exists")
