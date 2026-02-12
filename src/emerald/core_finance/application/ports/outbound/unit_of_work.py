from abc import abstractmethod

from emerald.core_finance.application.ports.outbound.account_repository import AccountRepository
from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork


class AbstractCoreFinanceUnitOfWork(AbstractUnitOfWork):
    """Unit of Work for the Core Finance bounded context."""

    accounts: AccountRepository
    # TODO(spec-008): Add shares: AccountShareRepository
    # TODO(spec-009): Add transactions: TransactionRepository
    # TODO(spec-011): Add cards: CardRepository

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
