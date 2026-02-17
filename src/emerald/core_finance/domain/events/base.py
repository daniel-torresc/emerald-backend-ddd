from dataclasses import dataclass
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class AccountEvent(DomainEvent):
    """Base event for the Core Finance Account aggregate."""

    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True, kw_only=True)
class TransactionEvent(DomainEvent):
    """Base event for the Core Finance Transaction entity."""

    aggregate_type: ClassVar[str] = "transaction"
