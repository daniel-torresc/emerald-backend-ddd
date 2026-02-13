from emerald.shared_kernel.domain.exceptions import (
    AuthorizationError,
    ConflictError,
    InvariantViolationError,
    NotFoundError,
)


class InsufficientPermissionError(AuthorizationError):
    """User lacks required permission level for operation."""

    def __init__(
        self,
        message: str = "Insufficient permission",
        code: str = "INSUFFICIENT_PERMISSION",
    ) -> None:
        super().__init__(message, code)


class CannotGrantOwnerError(InvariantViolationError):
    """Attempted to grant OWNER via share_with() or update."""

    def __init__(
        self,
        message: str = "Cannot grant OWNER permission",
        code: str = "CANNOT_GRANT_OWNER",
    ) -> None:
        super().__init__(message, code)


class CannotShareWithSelfError(InvariantViolationError):
    """Owner attempted to share with themselves."""

    def __init__(
        self,
        message: str = "Cannot share account with yourself",
        code: str = "CANNOT_SHARE_WITH_SELF",
    ) -> None:
        super().__init__(message, code)


class AlreadySharedError(ConflictError):
    """User already has an active share on this account."""

    def __init__(
        self,
        message: str = "User already has an active share on this account",
        code: str = "ALREADY_SHARED",
    ) -> None:
        super().__init__(message, code)


class ShareNotFoundError(NotFoundError):
    """No active share exists for the specified user."""

    def __init__(
        self,
        message: str = "Share not found",
        code: str = "SHARE_NOT_FOUND",
    ) -> None:
        super().__init__(message, code)


class CannotRevokeOwnerError(InvariantViolationError):
    """Attempted to revoke the owner's share."""

    def __init__(
        self,
        message: str = "Cannot revoke owner's share",
        code: str = "CANNOT_REVOKE_OWNER",
    ) -> None:
        super().__init__(message, code)


class CannotModifyOwnerShareError(InvariantViolationError):
    """Attempted to change the owner's permission level."""

    def __init__(
        self,
        message: str = "Cannot modify owner's share permission",
        code: str = "CANNOT_MODIFY_OWNER_SHARE",
    ) -> None:
        super().__init__(message, code)


class AlreadyOwnerError(InvariantViolationError):
    """Attempted to transfer ownership to the current owner."""

    def __init__(
        self,
        message: str = "User is already the owner",
        code: str = "ALREADY_OWNER",
    ) -> None:
        super().__init__(message, code)


class AccountNotActiveError(InvariantViolationError):
    """Share operation attempted on a soft-deleted account."""

    def __init__(
        self,
        message: str = "Account is not active",
        code: str = "ACCOUNT_NOT_ACTIVE",
    ) -> None:
        super().__init__(message, code)


class MaxSharesReachedError(InvariantViolationError):
    """Account has reached maximum active shares."""

    def __init__(
        self,
        message: str = "Maximum shares per account reached",
        code: str = "MAX_SHARES_REACHED",
    ) -> None:
        super().__init__(message, code)


class CannotLeaveAsOwnerError(InvariantViolationError):
    """Owner attempted to leave; must transfer ownership first."""

    def __init__(
        self,
        message: str = "Owner cannot leave account; transfer ownership first",
        code: str = "CANNOT_LEAVE_AS_OWNER",
    ) -> None:
        super().__init__(message, code)


class ShareAlreadyRevokedError(ConflictError):
    """Attempted to revoke an already-revoked share."""

    def __init__(
        self,
        message: str = "Share is already revoked",
        code: str = "SHARE_ALREADY_REVOKED",
    ) -> None:
        super().__init__(message, code)
