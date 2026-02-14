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


@dataclass(frozen=True)
class TransactionSplit(DomainEvent):
    """Emitted when a transaction is split into children."""

    parent_transaction_id: uuid.UUID = uuid.UUID(int=0)
    account_id: uuid.UUID = uuid.UUID(int=0)
    child_count: int = 0
    child_ids: tuple[uuid.UUID, ...] = ()
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionSplitsJoined(DomainEvent):
    """Emitted when split children are joined back into the parent."""

    parent_transaction_id: uuid.UUID = uuid.UUID(int=0)
    account_id: uuid.UUID = uuid.UUID(int=0)
    removed_child_count: int = 0
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionCardLinked(DomainEvent):
    """Emitted when a transaction is linked to a card."""

    transaction_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    account_id: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionCardUnlinked(DomainEvent):
    """Emitted when a transaction is unlinked from a card."""

    transaction_id: uuid.UUID = uuid.UUID(int=0)
    previous_card_id: uuid.UUID = uuid.UUID(int=0)
    account_id: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"


# -- Bulk aggregate events (Spec 012) ------------------------------------------


@dataclass(frozen=True)
class TransactionsBulkCreated(DomainEvent):
    """Emitted once per bulk create operation with summary counts."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    success_count: int = 0
    failure_count: int = 0
    import_source_type: str = ""
    created_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionsBulkUpdated(DomainEvent):
    """Emitted once per bulk update operation with summary counts."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    success_count: int = 0
    failure_count: int = 0
    updated_fields: frozenset[str] = frozenset()
    updated_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionsBulkDeleted(DomainEvent):
    """Emitted once per bulk delete operation with summary counts."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    success_count: int = 0
    failure_count: int = 0
    deleted_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"


@dataclass(frozen=True)
class TransactionsBulkRecovered(DomainEvent):
    """Emitted once per bulk recover operation with summary counts."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    success_count: int = 0
    failure_count: int = 0
    recovered_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "transaction"
