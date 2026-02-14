from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

from emerald.core_finance.application.ports.outbound.unit_of_work import (
    AbstractCoreFinanceUnitOfWork,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.aggregates.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel
from emerald.shared_kernel.domain.events.domain_event import DomainEvent
from emerald.shared_kernel.domain.models.value_objects.date_range import DateRange
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.paginated_result import PaginatedResult


class FakeAccountRepository:
    """In-memory account repository for tests."""

    def __init__(self) -> None:
        self._accounts: dict[uuid.UUID, Account] = {}
        self.seen: set[Account] = set()

    def save(self, account: Account) -> None:
        self._accounts[account.id] = account
        self.seen.add(account)

    def find_by_id(self, account_id: uuid.UUID, include_deleted: bool = False) -> Account | None:
        account = self._accounts.get(account_id)
        if account is None:
            return None
        self.seen.add(account)
        if not include_deleted and account.is_deleted():
            return None
        return account

    def find_by_owner(self, user_id: uuid.UUID, include_deleted: bool = False) -> list[Account]:
        results: list[Account] = []
        for account in self._accounts.values():
            if account.created_by != user_id:
                continue
            if not include_deleted and account.is_deleted():
                continue
            self.seen.add(account)
            results.append(account)
        return results

    def exists_by_name_for_user(self, account_name: AccountName, user_id: uuid.UUID) -> bool:
        for account in self._accounts.values():
            if account.is_deleted():
                continue
            if account.created_by == user_id and account.account_name == account_name:
                return True
        return False

    def find_accessible_by_user(
        self, user_id: uuid.UUID, include_deleted: bool = False
    ) -> list[Account]:
        results: list[Account] = []
        for account in self._accounts.values():
            if not include_deleted and account.is_deleted():
                continue
            if account.has_permission(user_id, PermissionLevel.VIEWER):
                self.seen.add(account)
                results.append(account)
        return results


class FakeTransactionRepository:
    """In-memory transaction repository for tests."""

    def __init__(self) -> None:
        self._transactions: dict[uuid.UUID, Transaction] = {}
        self.seen: set[Transaction] = set()

    def save(self, transaction: Transaction) -> None:
        self._transactions[transaction.id] = transaction
        self.seen.add(transaction)

    def save_many(self, transactions: list[Transaction]) -> None:
        for txn in transactions:
            self.save(txn)

    def find_by_id(
        self,
        transaction_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> Transaction | None:
        txn = self._transactions.get(transaction_id)
        if txn is None:
            return None
        self.seen.add(txn)
        if not include_deleted and txn.is_deleted():
            return None
        return txn

    def find_by_account(
        self,
        account_id: uuid.UUID,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[Transaction]:
        all_txns = [
            t
            for t in self._transactions.values()
            if t.account_id == account_id and (include_deleted or not t.is_deleted())
        ]
        return self._paginate(all_txns, page, page_size)

    def find_by_account_in_range(
        self,
        account_id: uuid.UUID,
        date_range: DateRange,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[Transaction]:
        all_txns = [
            t
            for t in self._transactions.values()
            if t.account_id == account_id
            and (include_deleted or not t.is_deleted())
            and date_range.contains(t.transaction_date)
        ]
        return self._paginate(all_txns, page, page_size)

    def find_by_external_id(
        self,
        account_id: uuid.UUID,
        external_id: str,
    ) -> Transaction | None:
        for txn in self._transactions.values():
            if txn.account_id == account_id and txn.external_id == external_id:
                self.seen.add(txn)
                return txn
        return None

    def count_by_account(
        self,
        account_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> int:
        return sum(
            1
            for t in self._transactions.values()
            if t.account_id == account_id and (include_deleted or not t.is_deleted())
        )

    def sum_amounts(
        self,
        account_id: uuid.UUID,
        exclude_split_parents: bool = True,
    ) -> Money:
        matching = [
            t
            for t in self._transactions.values()
            if t.account_id == account_id
            and not t.is_deleted()
            and not (exclude_split_parents and t.is_split_parent)
        ]
        if not matching:
            from emerald.shared_kernel.domain.models.value_objects.currency import Currency

            return Money(Decimal("0"), Currency.USD)
        total = Decimal("0")
        currency = matching[0].amount.currency
        for txn in matching:
            total += txn.amount.amount
        return Money(total, currency)

    def find_children(
        self,
        parent_transaction_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> list[Transaction]:
        return [
            t
            for t in self._transactions.values()
            if t.parent_transaction_id == parent_transaction_id
            and (include_deleted or not t.is_deleted())
        ]

    def hard_delete_children(self, parent_transaction_id: uuid.UUID) -> int:
        to_remove = [
            tid
            for tid, t in self._transactions.items()
            if t.parent_transaction_id == parent_transaction_id
        ]
        for tid in to_remove:
            del self._transactions[tid]
        return len(to_remove)

    @staticmethod
    def _paginate(
        items: list[Transaction], page: int, page_size: int
    ) -> PaginatedResult[Transaction]:
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]
        return PaginatedResult(
            items=tuple(page_items),
            total=total,
            page=page,
            page_size=page_size,
        )


class FakeCoreFinanceUnitOfWork(AbstractCoreFinanceUnitOfWork):
    """In-memory Unit of Work for Core Finance tests."""

    accounts: FakeAccountRepository
    transactions: FakeTransactionRepository

    def __init__(self) -> None:
        self.accounts = FakeAccountRepository()
        self.transactions = FakeTransactionRepository()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def collect_new_events(self) -> Iterator[DomainEvent]:
        for aggregate in self.accounts.seen:
            yield from aggregate.collect_events()
        for txn in self.transactions.seen:
            yield from txn.collect_events()
