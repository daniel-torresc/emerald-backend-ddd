from emerald.iam.application.dto import RegisterUser
from emerald.iam.application.ports import AbstractIamUnitOfWork, UserRepository
from emerald.iam.application.services import UserRegistrationService
from emerald.iam.domain.events import (
    AuthProviderLinked,
    AuthProviderUnlinked,
    EmailVerified,
    PasswordChanged,
    UserEmailChanged,
    UserLoggedIn,
    UserRecovered,
    UserRegistered,
    UserSoftDeleted,
    UserSuspended,
    UserUnsuspended,
    UserUsernameChanged,
)
from emerald.iam.domain.exceptions import (
    CannotUnlinkLastProviderError,
    EmailAlreadyExistsError,
    InvalidEmailError,
    InvalidStateTransitionError,
    InvalidUsernameError,
    PasswordAlreadySetError,
    PasswordReusedError,
    PasswordTooWeakError,
    ProviderAlreadyLinkedError,
    ProviderNotLinkedError,
    UsernameAlreadyExistsError,
)
from emerald.iam.domain.models import (
    AuthProvider,
    EmailAddress,
    HashedPassword,
    ProviderType,
    User,
    Username,
    UserPreferences,
    UserStatus,
)
from emerald.iam.domain.ports import PasswordHasher
from emerald.iam.domain.services import validate_not_in_history, validate_password_strength

__all__ = [
    # Entity
    "User",
    # Value Objects
    "AuthProvider",
    "EmailAddress",
    "HashedPassword",
    "ProviderType",
    "UserPreferences",
    "UserStatus",
    "Username",
    # Domain Services
    "validate_not_in_history",
    "validate_password_strength",
    # Events
    "AuthProviderLinked",
    "AuthProviderUnlinked",
    "EmailVerified",
    "PasswordChanged",
    "UserEmailChanged",
    "UserLoggedIn",
    "UserRecovered",
    "UserRegistered",
    "UserSoftDeleted",
    "UserSuspended",
    "UserUnsuspended",
    "UserUsernameChanged",
    # Exceptions
    "CannotUnlinkLastProviderError",
    "EmailAlreadyExistsError",
    "InvalidEmailError",
    "InvalidStateTransitionError",
    "InvalidUsernameError",
    "PasswordAlreadySetError",
    "PasswordReusedError",
    "PasswordTooWeakError",
    "ProviderAlreadyLinkedError",
    "ProviderNotLinkedError",
    "UsernameAlreadyExistsError",
    # Commands
    "RegisterUser",
    # Ports
    "AbstractIamUnitOfWork",
    "PasswordHasher",
    "UserRepository",
    # Services
    "UserRegistrationService",
]
