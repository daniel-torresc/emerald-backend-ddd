from dataclasses import dataclass
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class UserEvent(DomainEvent):
    """Base event for the IAM User aggregate."""

    aggregate_type: ClassVar[str] = "user"
