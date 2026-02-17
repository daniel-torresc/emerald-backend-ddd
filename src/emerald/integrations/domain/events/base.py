from dataclasses import dataclass
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class BankConnectionEvent(DomainEvent):
    """Base event for the External Integrations BankConnection aggregate."""

    aggregate_type: ClassVar[str] = "bank_connection"
