from emerald.shared_kernel.domain.exceptions import (
    AlreadyExistsError,
    ConflictError,
    InvalidValueError,
    InvariantViolationError,
    NotFoundError,
    ValidationError,
)


class InvalidEmailError(InvalidValueError):
    """Invalid email address format."""

    def __init__(self, message: str = "Invalid email address", code: str = "INVALID_EMAIL") -> None:
        super().__init__(message, code)


class InvalidUsernameError(InvalidValueError):
    """Invalid username format."""

    def __init__(self, message: str = "Invalid username", code: str = "INVALID_USERNAME") -> None:
        super().__init__(message, code)


class PasswordTooWeakError(InvalidValueError):
    """Password does not meet strength requirements."""

    def __init__(self, message: str = "Password too weak", code: str = "PASSWORD_TOO_WEAK") -> None:
        super().__init__(message, code)


class InvalidStateTransitionError(InvariantViolationError):
    """Invalid lifecycle state transition."""

    def __init__(
        self,
        message: str = "Invalid state transition",
        code: str = "INVALID_STATE_TRANSITION",
    ) -> None:
        super().__init__(message, code)


class EmailAlreadyExistsError(AlreadyExistsError):
    """Email address already in use."""

    def __init__(
        self, message: str = "Email already exists", code: str = "EMAIL_ALREADY_EXISTS"
    ) -> None:
        super().__init__(message, code)


class UsernameAlreadyExistsError(AlreadyExistsError):
    """Username already in use."""

    def __init__(
        self,
        message: str = "Username already exists",
        code: str = "USERNAME_ALREADY_EXISTS",
    ) -> None:
        super().__init__(message, code)


class ProviderAlreadyLinkedError(ConflictError):
    """Auth provider type already linked to user."""

    def __init__(
        self,
        message: str = "Provider already linked",
        code: str = "PROVIDER_ALREADY_LINKED",
    ) -> None:
        super().__init__(message, code)


class PasswordAlreadySetError(ConflictError):
    """Password already set for this user."""

    def __init__(
        self,
        message: str = "Password already set",
        code: str = "PASSWORD_ALREADY_SET",
    ) -> None:
        super().__init__(message, code)


class ProviderNotLinkedError(NotFoundError):
    """Auth provider type not linked to user."""

    def __init__(
        self, message: str = "Provider not linked", code: str = "PROVIDER_NOT_LINKED"
    ) -> None:
        super().__init__(message, code)


class PasswordReusedError(ValidationError):
    """Password matches a recent password in history."""

    def __init__(
        self, message: str = "Password was recently used", code: str = "PASSWORD_REUSED"
    ) -> None:
        super().__init__(message, code)


class CannotUnlinkLastProviderError(InvariantViolationError):
    """Cannot unlink the last remaining auth provider."""

    def __init__(
        self,
        message: str = "Cannot unlink last provider",
        code: str = "CANNOT_UNLINK_LAST_PROVIDER",
    ) -> None:
        super().__init__(message, code)
