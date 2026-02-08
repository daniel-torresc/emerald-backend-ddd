import uuid
from dataclasses import dataclass
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent

_NIL_UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class LoginFailed(DomainEvent):
    """Emitted on any failed login attempt. Uses email (not user_id) since user may not exist."""

    email: str = ""
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class TokenRefreshed(DomainEvent):
    """Emitted on successful token rotation."""

    user_id: uuid.UUID = _NIL_UUID
    family_id: uuid.UUID = _NIL_UUID
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class TokenRevoked(DomainEvent):
    """Emitted when a refresh token is revoked (logout)."""

    user_id: uuid.UUID = _NIL_UUID
    token_id: uuid.UUID = _NIL_UUID
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class TokenFamilyCompromised(DomainEvent):
    """Emitted when a revoked refresh token is reused — theft detection."""

    user_id: uuid.UUID = _NIL_UUID
    family_id: uuid.UUID = _NIL_UUID
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class AllSessionsRevoked(DomainEvent):
    """Emitted when all sessions for a user are revoked."""

    user_id: uuid.UUID = _NIL_UUID
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class PasswordResetRequested(DomainEvent):
    """Emitted when a password reset is requested. Never carries the raw token."""

    user_id: uuid.UUID = _NIL_UUID
    aggregate_type: ClassVar[str] = "User"
