from emerald.iam.domain.events.base import UserEvent
from emerald.iam.domain.events.role_events import (
    AdminPermissionGranted,
    AdminPermissionRevoked,
    SuperadminProvisioned,
    UserDemotedToUser,
    UserPromotedToAdmin,
)
from emerald.iam.domain.events.social_events import (
    UserRegisteredViaSocialProvider,
)
from emerald.iam.domain.events.user_events import (
    AuthProviderLinked,
    AuthProviderUnlinked,
    EmailVerified,
    PasswordChanged,
    UserEmailChanged,
    UserFullNameUpdated,
    UserLoggedIn,
    UserPreferencesUpdated,
    UserRecovered,
    UserRegistered,
    UserSoftDeleted,
    UserSuspended,
    UserUnsuspended,
    UserUsernameChanged,
)

__all__ = [
    "AdminPermissionGranted",
    "AdminPermissionRevoked",
    "AuthProviderLinked",
    "AuthProviderUnlinked",
    "EmailVerified",
    "PasswordChanged",
    "SuperadminProvisioned",
    "UserDemotedToUser",
    "UserEmailChanged",
    "UserEvent",
    "UserFullNameUpdated",
    "UserLoggedIn",
    "UserPreferencesUpdated",
    "UserPromotedToAdmin",
    "UserRecovered",
    "UserRegistered",
    "UserRegisteredViaSocialProvider",
    "UserSoftDeleted",
    "UserSuspended",
    "UserUnsuspended",
    "UserUsernameChanged",
]
