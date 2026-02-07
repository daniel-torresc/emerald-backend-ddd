from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from emerald.shared_kernel.domain.exceptions import InvalidValueError


class ProviderType(Enum):
    """Authentication provider types."""

    PASSWORD = "PASSWORD"
    GOOGLE = "GOOGLE"
    MICROSOFT = "MICROSOFT"


@dataclass(frozen=True, eq=False)
class AuthProvider:
    """An authentication method linked to a user."""

    provider_type: ProviderType
    external_id: str | None
    linked_at: datetime

    def __post_init__(self) -> None:
        if self.provider_type == ProviderType.PASSWORD and self.external_id is not None:
            raise InvalidValueError("PASSWORD provider must not have an external_id")
        if self.provider_type != ProviderType.PASSWORD:
            if self.external_id is None or not self.external_id.strip():
                raise InvalidValueError(
                    f"{self.provider_type.value} provider requires a non-empty external_id"
                )
        if self.linked_at.tzinfo is None or self.linked_at.tzinfo != UTC:
            if self.linked_at.tzinfo is None:
                raise InvalidValueError("linked_at must be timezone-aware UTC")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AuthProvider):
            return NotImplemented
        return self.provider_type == other.provider_type

    def __hash__(self) -> int:
        return hash(self.provider_type)
