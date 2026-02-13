from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    AccountNotActiveError,
    AlreadyOwnerError,
    AlreadySharedError,
    CannotGrantOwnerError,
    CannotLeaveAsOwnerError,
    CannotModifyOwnerShareError,
    CannotRevokeOwnerError,
    CannotShareWithSelfError,
    InsufficientPermissionError,
    MaxSharesReachedError,
    ShareAlreadyRevokedError,
    ShareNotFoundError,
)
from emerald.shared_kernel.domain.exceptions import (
    AuthorizationError,
    ConflictError,
    InvariantViolationError,
    NotFoundError,
)


class TestInsufficientPermissionError:
    def test_default_message(self) -> None:
        err = InsufficientPermissionError()
        assert err.message == "Insufficient permission"

    def test_default_code(self) -> None:
        assert InsufficientPermissionError().code == "INSUFFICIENT_PERMISSION"

    def test_extends_authorization_error(self) -> None:
        assert isinstance(InsufficientPermissionError(), AuthorizationError)

    def test_custom_message(self) -> None:
        err = InsufficientPermissionError("Custom msg")
        assert err.message == "Custom msg"


class TestCannotGrantOwnerError:
    def test_default_code(self) -> None:
        assert CannotGrantOwnerError().code == "CANNOT_GRANT_OWNER"

    def test_extends_invariant_violation(self) -> None:
        assert isinstance(CannotGrantOwnerError(), InvariantViolationError)


class TestCannotShareWithSelfError:
    def test_default_code(self) -> None:
        assert CannotShareWithSelfError().code == "CANNOT_SHARE_WITH_SELF"

    def test_extends_invariant_violation(self) -> None:
        assert isinstance(CannotShareWithSelfError(), InvariantViolationError)


class TestAlreadySharedError:
    def test_default_code(self) -> None:
        assert AlreadySharedError().code == "ALREADY_SHARED"

    def test_extends_conflict_error(self) -> None:
        assert isinstance(AlreadySharedError(), ConflictError)


class TestShareNotFoundError:
    def test_default_code(self) -> None:
        assert ShareNotFoundError().code == "SHARE_NOT_FOUND"

    def test_extends_not_found_error(self) -> None:
        assert isinstance(ShareNotFoundError(), NotFoundError)


class TestCannotRevokeOwnerError:
    def test_default_code(self) -> None:
        assert CannotRevokeOwnerError().code == "CANNOT_REVOKE_OWNER"

    def test_extends_invariant_violation(self) -> None:
        assert isinstance(CannotRevokeOwnerError(), InvariantViolationError)


class TestCannotModifyOwnerShareError:
    def test_default_code(self) -> None:
        assert CannotModifyOwnerShareError().code == "CANNOT_MODIFY_OWNER_SHARE"

    def test_extends_invariant_violation(self) -> None:
        assert isinstance(CannotModifyOwnerShareError(), InvariantViolationError)


class TestAlreadyOwnerError:
    def test_default_code(self) -> None:
        assert AlreadyOwnerError().code == "ALREADY_OWNER"

    def test_extends_invariant_violation(self) -> None:
        assert isinstance(AlreadyOwnerError(), InvariantViolationError)


class TestAccountNotActiveError:
    def test_default_code(self) -> None:
        assert AccountNotActiveError().code == "ACCOUNT_NOT_ACTIVE"

    def test_extends_invariant_violation(self) -> None:
        assert isinstance(AccountNotActiveError(), InvariantViolationError)


class TestMaxSharesReachedError:
    def test_default_code(self) -> None:
        assert MaxSharesReachedError().code == "MAX_SHARES_REACHED"

    def test_extends_invariant_violation(self) -> None:
        assert isinstance(MaxSharesReachedError(), InvariantViolationError)


class TestCannotLeaveAsOwnerError:
    def test_default_code(self) -> None:
        assert CannotLeaveAsOwnerError().code == "CANNOT_LEAVE_AS_OWNER"

    def test_extends_invariant_violation(self) -> None:
        assert isinstance(CannotLeaveAsOwnerError(), InvariantViolationError)


class TestShareAlreadyRevokedError:
    def test_default_code(self) -> None:
        assert ShareAlreadyRevokedError().code == "SHARE_ALREADY_REVOKED"

    def test_extends_conflict_error(self) -> None:
        assert isinstance(ShareAlreadyRevokedError(), ConflictError)
