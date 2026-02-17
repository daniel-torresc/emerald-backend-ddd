import uuid

from emerald.integrations.application.dtos.commands.connection_commands import (
    ActivateBankConnection,
    DisconnectBankConnection,
    InitiateBankConnection,
    ReconnectBankConnection,
    SoftDeleteBankConnection,
    UpdateSyncFrequency,
)
from emerald.integrations.application.ports.outbound.unit_of_work import (
    AbstractIntegrationsUnitOfWork,
)
from emerald.integrations.domain.exceptions.connection_exceptions import (
    BankConnectionNotFoundError,
    DuplicateConnectionError,
    InvalidConnectionStateError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.entities.pending_transaction import PendingTransaction
from emerald.integrations.domain.models.entities.sync_history import SyncHistory
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService


class BankConnectionService:
    """Application service orchestrating bank connection lifecycle."""

    def __init__(
        self,
        uow: AbstractIntegrationsUnitOfWork,
        retention_policy_service: RetentionPolicyService,
    ) -> None:
        self._uow = uow
        self._retention = retention_policy_service

    def initiate_connection(self, cmd: InitiateBankConnection) -> BankConnection:
        """Create a new bank connection in PENDING status."""
        with self._uow:
            provider_name = ProviderName(cmd.provider_name)
            existing = self._uow.bank_connections.find_by_account_and_provider(
                cmd.account_id, provider_name
            )
            if existing is not None:
                raise DuplicateConnectionError()

            connection = BankConnection.create(
                user_id=cmd.user_id,
                account_id=cmd.account_id,
                provider_name=provider_name,
                institution_id=cmd.institution_id,
                external_account_id=cmd.external_account_id,
                created_by=cmd.user_id,
            )
            self._uow.bank_connections.save(connection)
            self._uow.commit()
            return connection

    def activate_connection(self, cmd: ActivateBankConnection) -> None:
        """Activate a bank connection with credentials."""
        with self._uow:
            connection = self._load_connection(cmd.connection_id)
            credentials = ProviderCredentials(cmd.credentials_token)
            connection.activate(credentials)
            self._uow.commit()

    def disconnect_connection(self, cmd: DisconnectBankConnection) -> None:
        """Disconnect a bank connection and hard-delete pending transactions."""
        with self._uow:
            connection = self._load_connection(cmd.connection_id)
            connection.disconnect(cmd.disconnected_by)
            self._uow.pending_transactions.delete_by_connection(cmd.connection_id)
            self._uow.commit()

    def reconnect_connection(self, cmd: ReconnectBankConnection) -> None:
        """Reconnect a bank connection with new credentials."""
        with self._uow:
            connection = self._load_connection(cmd.connection_id)
            credentials = ProviderCredentials(cmd.credentials_token)
            connection.reconnect(credentials)
            self._uow.commit()

    def update_sync_frequency(self, cmd: UpdateSyncFrequency) -> None:
        """Update the sync frequency for a connection."""
        with self._uow:
            connection = self._load_connection(cmd.connection_id)
            if connection.user_id != cmd.updated_by:
                raise InvalidConnectionStateError(
                    "Only the connection owner can update sync frequency"
                )
            connection.update_sync_frequency(cmd.hours)
            self._uow.commit()

    def soft_delete_connection(self, cmd: SoftDeleteBankConnection) -> None:
        """Soft-delete a bank connection."""
        with self._uow:
            connection = self._load_connection(cmd.connection_id, include_deleted=True)
            retention = self._retention.get_effective_retention(
                DeletableEntityType.BANK_CONNECTION, cmd.deleted_by
            )
            connection.soft_delete(cmd.deleted_by, retention, cmd.reason)
            self._uow.pending_transactions.delete_by_connection(cmd.connection_id)
            self._uow.commit()

    def get_connections_for_user(self, user_id: uuid.UUID) -> list[BankConnection]:
        """Get all connections for a user."""
        with self._uow:
            return self._uow.bank_connections.find_by_user(user_id)

    def get_connections_for_account(self, account_id: uuid.UUID) -> list[BankConnection]:
        """Get all connections for an account."""
        with self._uow:
            return self._uow.bank_connections.find_by_account(account_id)

    def get_sync_history(self, connection_id: uuid.UUID, limit: int = 10) -> list[SyncHistory]:
        """Get sync history for a connection."""
        with self._uow:
            return self._uow.sync_history.find_by_connection(connection_id, limit=limit)

    def get_pending_for_review(self, connection_id: uuid.UUID) -> list[PendingTransaction]:
        """Get pending transactions needing review for a connection."""
        with self._uow:
            return self._uow.pending_transactions.find_needs_review(connection_id)

    # -- Private helpers -------------------------------------------------------

    def _load_connection(
        self, connection_id: uuid.UUID, include_deleted: bool = False
    ) -> BankConnection:
        """Load a bank connection or raise BankConnectionNotFoundError."""
        connection = self._uow.bank_connections.find_by_id(
            connection_id, include_deleted=include_deleted
        )
        if connection is None:
            raise BankConnectionNotFoundError(f"Bank connection {connection_id} not found")
        return connection
