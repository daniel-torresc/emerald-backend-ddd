from abc import abstractmethod

from emerald.core_finance.application.ports.outbound.account_repository import AccountRepository
from emerald.core_finance.application.ports.outbound.transaction_repository import (
    TransactionRepository,
)
from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork


class AbstractCoreFinanceUnitOfWork(AbstractUnitOfWork):
    """Unit of Work for the Core Finance bounded context."""

    accounts: AccountRepository
    transactions: TransactionRepository
    # TODO(spec-011): Add cards: CardRepository

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
