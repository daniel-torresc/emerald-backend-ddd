import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class TransactionCreated(DomainEvent):
    """Emitted when a new transaction is created."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    amount: Decimal = Decimal("0")
    currency_code: str = ""
    import_source_type: str = ""
    created_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionUpdated(DomainEvent):
    """Emitted when a mutable transaction field is updated."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    updated_by: uuid.UUID = uuid.UUID(int=0)
    changed_fields: frozenset[str] = frozenset()
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionReviewed(DomainEvent):
    """Emitted when a transaction is marked as reviewed."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    reviewed_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionSoftDeleted(DomainEvent):
    """Emitted when a transaction is soft-deleted."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    deleted_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionRecovered(DomainEvent):
    """Emitted when a soft-deleted transaction is recovered."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"
