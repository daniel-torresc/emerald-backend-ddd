import uuid
from dataclasses import dataclass
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class UserRegisteredViaSocialProvider(DomainEvent):
    """Emitted when a new user registers via a social provider."""

    email: str = ""
    provider_type: str = ""
    full_name: str | None = None
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class SocialLoginCompleted(DomainEvent):
    """Emitted when a user successfully logs in via a social provider."""

    user_id: uuid.UUID | None = None
    provider_type: str = ""
    aggregate_type: ClassVar[str] = "User"
