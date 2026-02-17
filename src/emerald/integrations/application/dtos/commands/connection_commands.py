import uuid
from dataclasses import dataclass

from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class InitiateBankConnection(Command):
    """Command to initiate a new bank connection."""

    user_id: uuid.UUID
    account_id: uuid.UUID
    provider_name: str
    institution_id: str
    external_account_id: str


@dataclass(frozen=True)
class ActivateBankConnection(Command):
    """Command to activate a bank connection with credentials."""

    connection_id: uuid.UUID
    credentials_token: str
    activated_by: uuid.UUID


@dataclass(frozen=True)
class DisconnectBankConnection(Command):
    """Command to disconnect a bank connection."""

    connection_id: uuid.UUID
    disconnected_by: uuid.UUID


@dataclass(frozen=True)
class ReconnectBankConnection(Command):
    """Command to reconnect a bank connection."""

    connection_id: uuid.UUID
    credentials_token: str
    reconnected_by: uuid.UUID


@dataclass(frozen=True)
class UpdateSyncFrequency(Command):
    """Command to update the sync frequency of a connection."""

    connection_id: uuid.UUID
    hours: int
    updated_by: uuid.UUID


@dataclass(frozen=True)
class TriggerSync(Command):
    """Command to trigger a sync for a connection."""

    connection_id: uuid.UUID
    triggered_by: uuid.UUID


@dataclass(frozen=True)
class ApprovePendingTransaction(Command):
    """Command to approve a pending transaction for import."""

    pending_id: uuid.UUID
    approved_by: uuid.UUID


@dataclass(frozen=True)
class RejectPendingTransaction(Command):
    """Command to reject a pending transaction."""

    pending_id: uuid.UUID
    rejected_by: uuid.UUID


@dataclass(frozen=True)
class SoftDeleteBankConnection(Command):
    """Command to soft-delete a bank connection."""

    connection_id: uuid.UUID
    deleted_by: uuid.UUID
    reason: str | None = None
