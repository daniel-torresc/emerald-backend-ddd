from emerald.shared_kernel.domain.exceptions import (
    AlreadyExistsError,
    ConflictError,
    DomainError,
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


# -- Authentication Exceptions (Spec 003) ------------------------------------


class AuthenticationFailedError(DomainError):
    """Authentication failed — intentionally vague to prevent information leakage."""

    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "AUTHENTICATION_FAILED",
    ) -> None:
        super().__init__(message, code)


class EmailNotVerifiedError(DomainError):
    """User email has not been verified."""

    def __init__(
        self,
        message: str = "Email not verified",
        code: str = "EMAIL_NOT_VERIFIED",
    ) -> None:
        super().__init__(message, code)


class AccountSuspendedError(DomainError):
    """User account is suspended."""

    def __init__(
        self,
        message: str = "Account suspended",
        code: str = "ACCOUNT_SUSPENDED",
    ) -> None:
        super().__init__(message, code)


class InvalidTokenError(InvalidValueError):
    """Token is structurally invalid or unrecognized."""

    def __init__(
        self,
        message: str = "Invalid token",
        code: str = "INVALID_TOKEN",
    ) -> None:
        super().__init__(message, code)


class TokenExpiredError(DomainError):
    """Token has expired."""

    def __init__(
        self,
        message: str = "Token expired",
        code: str = "TOKEN_EXPIRED",
    ) -> None:
        super().__init__(message, code)


class TokenAlreadyRevokedError(ConflictError):
    """Attempting to revoke an already-revoked token."""

    def __init__(
        self,
        message: str = "Token already revoked",
        code: str = "TOKEN_ALREADY_REVOKED",
    ) -> None:
        super().__init__(message, code)


class TokenAlreadyUsedError(ConflictError):
    """Attempting to use an already-consumed reset token."""

    def __init__(
        self,
        message: str = "Token already used",
        code: str = "TOKEN_ALREADY_USED",
    ) -> None:
        super().__init__(message, code)


# -- Role & Permission Exceptions (Spec 004) ---------------------------------


class InvalidRoleTransitionError(InvariantViolationError):
    """Invalid role transition (e.g., promoting non-USER or forbidden path)."""

    def __init__(
        self,
        message: str = "Invalid role transition",
        code: str = "INVALID_ROLE_TRANSITION",
    ) -> None:
        super().__init__(message, code)


class CannotDemoteSuperadminError(InvariantViolationError):
    """Attempting to demote SUPERADMIN."""

    def __init__(
        self,
        message: str = "Cannot demote SUPERADMIN",
        code: str = "CANNOT_DEMOTE_SUPERADMIN",
    ) -> None:
        super().__init__(message, code)


class CannotDeleteSuperadminError(InvariantViolationError):
    """Attempting to soft-delete SUPERADMIN."""

    def __init__(
        self,
        message: str = "Cannot delete SUPERADMIN",
        code: str = "CANNOT_DELETE_SUPERADMIN",
    ) -> None:
        super().__init__(message, code)


class CannotSuspendSuperadminError(InvariantViolationError):
    """Attempting to suspend SUPERADMIN."""

    def __init__(
        self,
        message: str = "Cannot suspend SUPERADMIN",
        code: str = "CANNOT_SUSPEND_SUPERADMIN",
    ) -> None:
        super().__init__(message, code)


class EmptyAdminPermissionsError(InvalidValueError):
    """Promoting with empty permissions set."""

    def __init__(
        self,
        message: str = "Admin permissions must not be empty",
        code: str = "EMPTY_ADMIN_PERMISSIONS",
    ) -> None:
        super().__init__(message, code)


class InsufficientPermissionsError(DomainError):
    """Insufficient permissions for the requested operation."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        code: str = "INSUFFICIENT_PERMISSIONS",
    ) -> None:
        super().__init__(message, code)


class NotAdminError(InvariantViolationError):
    """Target user is not an ADMIN — cannot grant/revoke permissions."""

    def __init__(
        self,
        message: str = "User is not an admin",
        code: str = "NOT_ADMIN",
    ) -> None:
        super().__init__(message, code)


class CannotGrantUnownedPermissionError(DomainError):
    """ADMIN trying to grant a permission they don't have."""

    def __init__(
        self,
        message: str = "Cannot grant a permission you do not have",
        code: str = "CANNOT_GRANT_UNOWNED_PERMISSION",
    ) -> None:
        super().__init__(message, code)


class LastAdminPermissionError(InvariantViolationError):
    """Revoking would leave ADMIN with zero permissions."""

    def __init__(
        self,
        message: str = "Cannot revoke last admin permission",
        code: str = "LAST_ADMIN_PERMISSION",
    ) -> None:
        super().__init__(message, code)


class SuperadminAlreadyExistsError(AlreadyExistsError):
    """SUPERADMIN already provisioned."""

    def __init__(
        self,
        message: str = "SUPERADMIN already exists",
        code: str = "SUPERADMIN_ALREADY_EXISTS",
    ) -> None:
        super().__init__(message, code)


# -- Federated Authentication Exceptions (Spec 005) --------------------------


class ProviderEmailNotVerifiedError(DomainError):
    """Provider reports the email as unverified."""

    def __init__(
        self,
        message: str = "Your email must be verified with the provider first",
        code: str = "PROVIDER_EMAIL_NOT_VERIFIED",
    ) -> None:
        super().__init__(message, code)


class ProviderEmailMismatchError(DomainError):
    """Provider email does not match the user's account email."""

    def __init__(
        self,
        message: str = "Provider email must match your account email",
        code: str = "PROVIDER_EMAIL_MISMATCH",
    ) -> None:
        super().__init__(message, code)


class ProviderExternalIdMismatchError(ConflictError):
    """Same provider type linked but with a different external user identity."""

    def __init__(
        self,
        message: str = "This provider is already linked to a different identity",
        code: str = "PROVIDER_EXTERNAL_ID_MISMATCH",
    ) -> None:
        super().__init__(message, code)


class OAuthStateInvalidError(DomainError):
    """OAuth state parameter mismatch or expired."""

    def __init__(
        self,
        message: str = "Authentication session expired, please try again",
        code: str = "OAUTH_STATE_INVALID",
    ) -> None:
        super().__init__(message, code)


class OAuthCodeExchangeError(DomainError):
    """Code exchange with the provider failed."""

    def __init__(
        self,
        message: str = "Authentication failed, please try again",
        code: str = "OAUTH_CODE_EXCHANGE_FAILED",
    ) -> None:
        super().__init__(message, code)
