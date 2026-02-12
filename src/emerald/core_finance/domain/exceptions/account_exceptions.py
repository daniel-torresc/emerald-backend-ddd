from emerald.shared_kernel.domain.exceptions import (
    AlreadyExistsError,
    AuthorizationError,
    InvalidValueError,
    NotFoundError,
)


class InvalidAccountNameError(InvalidValueError):
    """Account name is empty or exceeds maximum length."""

    def __init__(
        self, message: str = "Invalid account name", code: str = "INVALID_ACCOUNT_NAME"
    ) -> None:
        super().__init__(message, code)


class InvalidIBANError(InvalidValueError):
    """IBAN fails format or MOD-97 checksum validation."""

    def __init__(self, message: str = "Invalid IBAN", code: str = "INVALID_IBAN") -> None:
        super().__init__(message, code)


class InvalidAccountNotesError(InvalidValueError):
    """Account notes exceed maximum length."""

    def __init__(
        self,
        message: str = "Account notes exceed 500 characters",
        code: str = "INVALID_ACCOUNT_NOTES",
    ) -> None:
        super().__init__(message, code)


class InvalidUserReferenceError(InvalidValueError):
    """UserReference has None user_id or blank display_name."""

    def __init__(
        self,
        message: str = "Invalid user reference",
        code: str = "INVALID_USER_REFERENCE",
    ) -> None:
        super().__init__(message, code)


class AccountNameAlreadyExistsError(AlreadyExistsError):
    """Duplicate account name for the same user."""

    def __init__(
        self,
        message: str = "Account name already exists for this user",
        code: str = "ACCOUNT_NAME_ALREADY_EXISTS",
    ) -> None:
        super().__init__(message, code)


class AccountNotFoundError(NotFoundError):
    """Account not found in repository."""

    def __init__(self, message: str = "Account not found", code: str = "ACCOUNT_NOT_FOUND") -> None:
        super().__init__(message, code)


class NotAccountOwnerError(AuthorizationError):
    """Non-owner attempts a mutation on an account."""

    def __init__(
        self, message: str = "Not the account owner", code: str = "NOT_ACCOUNT_OWNER"
    ) -> None:
        super().__init__(message, code)
