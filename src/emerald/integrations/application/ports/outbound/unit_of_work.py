from abc import abstractmethod

from emerald.integrations.application.ports.outbound.bank_connection_repository import (
    BankConnectionRepository,
)
from emerald.integrations.application.ports.outbound.pending_transaction_repository import (
    PendingTransactionRepository,
)
from emerald.integrations.application.ports.outbound.sync_history_repository import (
    SyncHistoryRepository,
)
from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork


class AbstractIntegrationsUnitOfWork(AbstractUnitOfWork):
    """Unit of Work for the External Integrations bounded context."""

    bank_connections: BankConnectionRepository
    sync_history: SyncHistoryRepository
    pending_transactions: PendingTransactionRepository

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
