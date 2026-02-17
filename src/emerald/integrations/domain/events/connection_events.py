import uuid
from dataclasses import dataclass

from emerald.integrations.domain.events.base import BankConnectionEvent


@dataclass(frozen=True)
class BankConnectionInitiated(BankConnectionEvent):
    """Emitted when a new bank connection is created."""

    user_id: uuid.UUID
    provider_name: str
    account_id: uuid.UUID


@dataclass(frozen=True)
class BankConnectionActivated(BankConnectionEvent):
    """Emitted when a connection is activated with credentials."""


@dataclass(frozen=True)
class BankConnectionNeedsReauth(BankConnectionEvent):
    """Emitted when a connection needs re-authentication."""

    user_id: uuid.UUID


@dataclass(frozen=True)
class BankConnectionErrored(BankConnectionEvent):
    """Emitted when a connection enters ERROR state after 3+ consecutive failures."""

    last_error: str
    consecutive_failures: int


@dataclass(frozen=True)
class BankConnectionDisconnected(BankConnectionEvent):
    """Emitted when a user disconnects a bank connection."""

    disconnected_by: uuid.UUID


@dataclass(frozen=True)
class BankConnectionReconnected(BankConnectionEvent):
    """Emitted when a connection is reconnected from NEEDS_REAUTH or ERROR."""


@dataclass(frozen=True)
class BankConnectionSoftDeleted(BankConnectionEvent):
    """Emitted when a bank connection is soft-deleted."""

    deleted_by: uuid.UUID


@dataclass(frozen=True)
class BankSyncStarted(BankConnectionEvent):
    """Emitted when a sync begins."""

    sync_id: uuid.UUID


@dataclass(frozen=True)
class BankSyncCompleted(BankConnectionEvent):
    """Emitted when a sync completes successfully."""

    sync_id: uuid.UUID
    transactions_found: int
    transactions_imported: int
    transactions_duplicate: int
    transactions_staged: int


@dataclass(frozen=True)
class BankSyncFailed(BankConnectionEvent):
    """Emitted when a sync fails."""

    sync_id: uuid.UUID
    error: str


@dataclass(frozen=True)
class TransactionsImported(BankConnectionEvent):
    """Emitted when new transactions are created via bank sync."""

    account_id: uuid.UUID
    count: int


@dataclass(frozen=True)
class PendingTransactionApproved(BankConnectionEvent):
    """Emitted when a user approves a pending transaction."""

    pending_id: uuid.UUID
    transaction_id: uuid.UUID


@dataclass(frozen=True)
class PendingTransactionRejected(BankConnectionEvent):
    """Emitted when a user rejects a pending transaction."""

    pending_id: uuid.UUID
