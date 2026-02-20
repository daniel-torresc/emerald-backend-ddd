import uuid
from dataclasses import dataclass
from decimal import Decimal

from emerald.core_finance.domain.events.base import TransactionEvent


@dataclass(frozen=True)
class TransactionCreated(TransactionEvent):
    """Emitted when a new transaction is created."""

    account_id: uuid.UUID
    amount: Decimal
    currency_code: str
    import_source_type: str
    created_by: uuid.UUID


@dataclass(frozen=True)
class TransactionUpdated(TransactionEvent):
    """Emitted when a mutable transaction field is updated."""

    account_id: uuid.UUID
    updated_by: uuid.UUID
    changed_fields: frozenset[str]


@dataclass(frozen=True)
class TransactionReviewed(TransactionEvent):
    """Emitted when a transaction is marked as reviewed."""

    account_id: uuid.UUID
    reviewed_by: uuid.UUID


@dataclass(frozen=True)
class TransactionMarkedForReview(TransactionEvent):
    """Emitted when a transaction is marked for review (unreview)."""

    account_id: uuid.UUID
    updated_by: uuid.UUID


@dataclass(frozen=True)
class TransactionSoftDeleted(TransactionEvent):
    """Emitted when a transaction is soft-deleted."""

    account_id: uuid.UUID
    deleted_by: uuid.UUID


@dataclass(frozen=True)
class TransactionRecovered(TransactionEvent):
    """Emitted when a soft-deleted transaction is recovered."""

    account_id: uuid.UUID


@dataclass(frozen=True)
class TransactionSplit(TransactionEvent):
    """Emitted when a transaction is split into children."""

    parent_transaction_id: uuid.UUID
    account_id: uuid.UUID
    child_count: int
    child_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class TransactionSplitsJoined(TransactionEvent):
    """Emitted when split children are joined back into the parent."""

    parent_transaction_id: uuid.UUID
    account_id: uuid.UUID
    removed_child_count: int


@dataclass(frozen=True)
class TransactionCardLinked(TransactionEvent):
    """Emitted when a transaction is linked to a card."""

    transaction_id: uuid.UUID
    card_id: uuid.UUID
    account_id: uuid.UUID


@dataclass(frozen=True)
class TransactionCardUnlinked(TransactionEvent):
    """Emitted when a transaction is unlinked from a card."""

    transaction_id: uuid.UUID
    previous_card_id: uuid.UUID
    account_id: uuid.UUID
