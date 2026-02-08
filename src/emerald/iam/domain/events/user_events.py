import uuid
from dataclasses import dataclass
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class UserRegistered(DomainEvent):
    """Emitted when a new user registers."""

    email: str = ""
    username: str = ""
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class EmailVerified(DomainEvent):
    """Emitted when a user verifies their email."""

    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class UserEmailChanged(DomainEvent):
    """Emitted when a user changes their email."""

    old_email: str = ""
    new_email: str = ""
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class UserUsernameChanged(DomainEvent):
    """Emitted when a user changes their username."""

    old_username: str = ""
    new_username: str = ""
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class PasswordChanged(DomainEvent):
    """Emitted when a user changes their password. Never contains password data."""

    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class AuthProviderLinked(DomainEvent):
    """Emitted when an auth provider is linked to a user."""

    provider_type: str = ""
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class AuthProviderUnlinked(DomainEvent):
    """Emitted when an auth provider is unlinked from a user."""

    provider_type: str = ""
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class UserSuspended(DomainEvent):
    """Emitted when a user is suspended."""

    reason: str | None = None
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class UserUnsuspended(DomainEvent):
    """Emitted when a user is unsuspended."""

    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class UserSoftDeleted(DomainEvent):
    """Emitted when a user is soft deleted."""

    deleted_by: uuid.UUID | None = None
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class UserRecovered(DomainEvent):
    """Emitted when a soft-deleted user is recovered."""

    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class UserLoggedIn(DomainEvent):
    """Emitted when a user logs in."""

    aggregate_type: ClassVar[str] = "User"
