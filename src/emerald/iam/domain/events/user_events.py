import uuid
from dataclasses import dataclass

from emerald.iam.domain.events.base import UserEvent


@dataclass(frozen=True)
class UserRegistered(UserEvent):
    """Emitted when a new user registers."""

    email: str
    username: str


@dataclass(frozen=True)
class EmailVerified(UserEvent):
    """Emitted when a user verifies their email."""


@dataclass(frozen=True)
class UserEmailChanged(UserEvent):
    """Emitted when a user changes their email."""

    old_email: str
    new_email: str


@dataclass(frozen=True)
class UserUsernameChanged(UserEvent):
    """Emitted when a user changes their username."""

    old_username: str
    new_username: str


@dataclass(frozen=True)
class PasswordChanged(UserEvent):
    """Emitted when a user changes their password. Never contains password data."""


@dataclass(frozen=True)
class AuthProviderLinked(UserEvent):
    """Emitted when an auth provider is linked to a user."""

    provider_type: str


@dataclass(frozen=True)
class AuthProviderUnlinked(UserEvent):
    """Emitted when an auth provider is unlinked from a user."""

    provider_type: str


@dataclass(frozen=True)
class UserSuspended(UserEvent):
    """Emitted when a user is suspended."""

    reason: str | None = None


@dataclass(frozen=True)
class UserUnsuspended(UserEvent):
    """Emitted when a user is unsuspended."""


@dataclass(frozen=True)
class UserSoftDeleted(UserEvent):
    """Emitted when a user is soft deleted."""

    deleted_by: uuid.UUID | None = None


@dataclass(frozen=True)
class UserRecovered(UserEvent):
    """Emitted when a soft-deleted user is recovered."""


@dataclass(frozen=True)
class UserLoggedIn(UserEvent):
    """Emitted when a user logs in."""
