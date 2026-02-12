from __future__ import annotations

import uuid
from collections.abc import Iterator

from emerald.core_finance.application.ports.outbound.unit_of_work import (
    AbstractCoreFinanceUnitOfWork,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


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


class FakeCoreFinanceUnitOfWork(AbstractCoreFinanceUnitOfWork):
    """In-memory Unit of Work for Core Finance tests."""

    accounts: FakeAccountRepository

    def __init__(self) -> None:
        self.accounts = FakeAccountRepository()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def collect_new_events(self) -> Iterator[DomainEvent]:
        for aggregate in self.accounts.seen:
            yield from aggregate.collect_events()
