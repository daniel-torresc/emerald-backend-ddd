from dataclasses import dataclass

from emerald.iam.domain.events.base import UserEvent


@dataclass(frozen=True)
class UserRegisteredViaSocialProvider(UserEvent):
    """Emitted when a new user registers via a social provider."""

    email: str
    provider_type: str
    full_name: str | None = None
