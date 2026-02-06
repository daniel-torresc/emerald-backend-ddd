class DomainError(Exception):
    """Base exception for all domain-level errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR") -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ValidationError(DomainError):
    """Base for validation-related errors."""

    def __init__(self, message: str, code: str = "VALIDATION_ERROR") -> None:
        super().__init__(message, code)


class InvalidValueError(ValidationError):
    """Value object construction failure."""

    def __init__(self, message: str, code: str = "INVALID_VALUE") -> None:
        super().__init__(message, code)


class InvariantViolationError(ValidationError):
    """Aggregate invariant broken."""

    def __init__(self, message: str, code: str = "INVARIANT_VIOLATION") -> None:
        super().__init__(message, code)


class NotFoundError(DomainError):
    """Entity not found."""

    def __init__(self, message: str, code: str = "NOT_FOUND") -> None:
        super().__init__(message, code)


class ConflictError(DomainError):
    """Uniqueness or state conflict."""

    def __init__(self, message: str, code: str = "CONFLICT") -> None:
        super().__init__(message, code)


class AlreadyExistsError(ConflictError):
    """Duplicate entity."""

    def __init__(self, message: str, code: str = "ALREADY_EXISTS") -> None:
        super().__init__(message, code)


class AlreadyDeletedError(ConflictError):
    """Operation on deleted entity."""

    def __init__(self, message: str, code: str = "ALREADY_DELETED") -> None:
        super().__init__(message, code)


class NotDeletedError(DomainError):
    """Recovery on non-deleted entity."""

    def __init__(self, message: str, code: str = "NOT_DELETED") -> None:
        super().__init__(message, code)


class AuthorizationError(DomainError):
    """Domain-level permission denied."""

    def __init__(self, message: str, code: str = "AUTHORIZATION_ERROR") -> None:
        super().__init__(message, code)


class CurrencyMismatchError(DomainError):
    """Cross-currency operation attempted."""

    def __init__(self, message: str, code: str = "CURRENCY_MISMATCH") -> None:
        super().__init__(message, code)
