import uuid
from datetime import UTC, datetime

from emerald.integrations.application.dtos.commands.connection_commands import (
    ApprovePendingTransaction,
    RejectPendingTransaction,
    TriggerSync,
)
from emerald.integrations.application.ports.outbound.provider_registry import (
    BankProviderAdapterRegistry,
)
from emerald.integrations.application.ports.outbound.transaction_import_port import (
    TransactionImportPort,
)
from emerald.integrations.application.ports.outbound.unit_of_work import (
    AbstractIntegrationsUnitOfWork,
)
from emerald.integrations.application.services.deduplication import DeduplicationService
from emerald.integrations.domain.events.connection_events import (
    BankSyncCompleted,
    BankSyncFailed,
    BankSyncStarted,
    PendingTransactionApproved,
    PendingTransactionRejected,
    TransactionsImported,
)
from emerald.integrations.domain.exceptions.connection_exceptions import (
    BankConnectionNotFoundError,
    ConnectionNotActiveError,
    InvalidConnectionStateError,
    PendingTransactionNotFoundError,
    ProviderAuthError,
    ProviderError,
    SyncAlreadyInProgressError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.entities.pending_transaction import PendingTransaction
from emerald.integrations.domain.models.entities.sync_history import SyncHistory
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.sync_result import SyncResult


class BankSyncService:
    """Application service orchestrating sync execution and pending transaction review."""

    def __init__(
        self,
        uow: AbstractIntegrationsUnitOfWork,
        transaction_import_port: TransactionImportPort,
        provider_registry: BankProviderAdapterRegistry,
    ) -> None:
        self._uow = uow
        self._import_port = transaction_import_port
        self._registry = provider_registry
        self._dedup = DeduplicationService(transaction_import_port)

    async def execute_sync(self, cmd: TriggerSync) -> SyncHistory:
        """Execute a full sync pipeline for a connection."""
        async with self._uow:
            connection = self._load_connection(cmd.connection_id)
            if not connection.is_syncable():
                raise ConnectionNotActiveError()

            # Check no sync already in progress
            in_progress = self._uow.sync_history.find_in_progress_by_connection(cmd.connection_id)
            if in_progress is not None:
                raise SyncAlreadyInProgressError()

            # Create sync history
            history = SyncHistory.create(connection_id=cmd.connection_id)
            self._uow.sync_history.save(history)

            # Register sync started event
            connection._register_event(
                BankSyncStarted(aggregate_id=connection.id, sync_id=history.id)
            )

            # Resolve adapter + normalizer
            adapter = self._registry.get_adapter(connection.provider_name)
            normalizer = self._registry.get_normalizer(connection.provider_name)

            # Fetch raw transactions
            try:
                raw_transactions = adapter.fetch_transactions(
                    connection.credentials,  # type: ignore[arg-type]
                    connection.external_account_id,
                    since=connection.last_sync_at,
                )
            except ProviderAuthError as e:
                connection.mark_needs_reauth()
                history.fail(str(e))
                connection._register_event(
                    BankSyncFailed(
                        aggregate_id=connection.id,
                        sync_id=history.id,
                        error=str(e),
                    )
                )
                await self._uow.commit()
                return history
            except ProviderError as e:
                connection.record_sync_failure(str(e))
                history.fail(str(e))
                connection._register_event(
                    BankSyncFailed(
                        aggregate_id=connection.id,
                        sync_id=history.id,
                        error=str(e),
                    )
                )
                await self._uow.commit()
                return history

            # Process each transaction
            imported_count = 0
            duplicate_count = 0
            staged_count = 0

            for raw in raw_transactions:
                normalized = normalizer.normalize(raw)
                dedup_result = self._dedup.check(normalized, connection.account_id)

                if dedup_result.match_status == MatchStatus.DUPLICATE:
                    duplicate_count += 1
                    continue

                if dedup_result.match_status == MatchStatus.NEW:
                    # Auto-import
                    pending = PendingTransaction.create(
                        connection_id=connection.id,
                        sync_id=history.id,
                        account_id=connection.account_id,
                        external_id=normalized.external_id,
                        raw_data=raw,
                        normalized=normalized,
                        match_status=MatchStatus.NEW,
                    )
                    txn_id = self._import_port.import_transaction(
                        account_id=connection.account_id,
                        transaction_date=normalized.transaction_date,
                        amount=normalized.amount,
                        currency_code=normalized.currency_code,
                        original_description=normalized.description,
                        external_id=normalized.external_id,
                        imported_by=connection.user_id,
                        value_date=normalized.value_date,
                        merchant=normalized.merchant,
                    )
                    pending.mark_imported(txn_id)
                    self._uow.pending_transactions.save(pending)
                    imported_count += 1

                elif dedup_result.match_status == MatchStatus.NEEDS_REVIEW:
                    pending = PendingTransaction.create(
                        connection_id=connection.id,
                        sync_id=history.id,
                        account_id=connection.account_id,
                        external_id=normalized.external_id,
                        raw_data=raw,
                        normalized=normalized,
                        match_status=MatchStatus.NEEDS_REVIEW,
                        matched_transaction_id=dedup_result.matched_transaction_id,
                    )
                    self._uow.pending_transactions.save(pending)
                    staged_count += 1

            # Complete sync
            result = SyncResult(
                transactions_found=len(raw_transactions),
                transactions_imported=imported_count,
                transactions_duplicate=duplicate_count,
                transactions_staged=staged_count,
            )
            history.complete(result)

            now = datetime.now(UTC)
            connection.record_sync_success(now)

            # Register completion events
            connection._register_event(
                BankSyncCompleted(
                    aggregate_id=connection.id,
                    sync_id=history.id,
                    transactions_found=result.transactions_found,
                    transactions_imported=result.transactions_imported,
                    transactions_duplicate=result.transactions_duplicate,
                    transactions_staged=result.transactions_staged,
                )
            )
            if imported_count > 0:
                connection._register_event(
                    TransactionsImported(
                        aggregate_id=connection.id,
                        account_id=connection.account_id,
                        count=imported_count,
                    )
                )

            await self._uow.commit()
            return history

    async def approve_pending(self, cmd: ApprovePendingTransaction) -> uuid.UUID:
        """Approve a pending transaction and import it."""
        async with self._uow:
            pending = self._uow.pending_transactions.find_by_id(cmd.pending_id)
            if pending is None:
                raise PendingTransactionNotFoundError()

            connection = self._load_connection(pending.connection_id)
            if connection.user_id != cmd.approved_by:
                raise InvalidConnectionStateError(
                    "Only the connection owner can approve pending transactions"
                )

            pending.approve()
            txn_id = self._import_port.import_transaction(
                account_id=pending.account_id,
                transaction_date=pending.normalized.transaction_date,
                amount=pending.normalized.amount,
                currency_code=pending.normalized.currency_code,
                original_description=pending.normalized.description,
                external_id=pending.external_id,
                imported_by=cmd.approved_by,
                value_date=pending.normalized.value_date,
                merchant=pending.normalized.merchant,
            )
            pending.mark_imported(txn_id)
            self._uow.pending_transactions.save(pending)

            connection._register_event(
                PendingTransactionApproved(
                    aggregate_id=connection.id,
                    pending_id=pending.id,
                    transaction_id=txn_id,
                )
            )
            await self._uow.commit()
            return txn_id

    async def reject_pending(self, cmd: RejectPendingTransaction) -> None:
        """Reject a pending transaction."""
        async with self._uow:
            pending = self._uow.pending_transactions.find_by_id(cmd.pending_id)
            if pending is None:
                raise PendingTransactionNotFoundError()

            connection = self._load_connection(pending.connection_id)
            if connection.user_id != cmd.rejected_by:
                raise InvalidConnectionStateError(
                    "Only the connection owner can reject pending transactions"
                )

            pending.reject()
            self._uow.pending_transactions.save(pending)

            connection._register_event(
                PendingTransactionRejected(
                    aggregate_id=connection.id,
                    pending_id=pending.id,
                )
            )
            await self._uow.commit()

    async def find_connections_due_for_sync(self, as_of: datetime) -> list[BankConnection]:
        """Find connections that are due for sync."""
        async with self._uow:
            return self._uow.bank_connections.find_due_for_sync(as_of)

    # -- Private helpers -------------------------------------------------------

    def _load_connection(self, connection_id: uuid.UUID) -> BankConnection:
        """Load a bank connection or raise BankConnectionNotFoundError."""
        connection = self._uow.bank_connections.find_by_id(connection_id)
        if connection is None:
            raise BankConnectionNotFoundError(f"Bank connection {connection_id} not found")
        return connection
