from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from emerald.integrations.application.dtos.transaction_match import TransactionMatch
from emerald.integrations.application.ports.outbound.unit_of_work import (
    AbstractIntegrationsUnitOfWork,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.entities.pending_transaction import PendingTransaction
from emerald.integrations.domain.models.entities.sync_history import SyncHistory
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName
from emerald.integrations.domain.models.value_objects.sync_status import SyncStatus


class FakeBankConnectionRepository:
    """In-memory bank connection repository for tests."""

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, BankConnection] = {}
        self.seen: set[BankConnection] = set()

    def save(self, connection: BankConnection) -> None:
        self._connections[connection.id] = connection
        self.seen.add(connection)

    def find_by_id(
        self, connection_id: uuid.UUID, include_deleted: bool = False
    ) -> BankConnection | None:
        conn = self._connections.get(connection_id)
        if conn is None:
            return None
        self.seen.add(conn)
        if not include_deleted and conn.is_deleted():
            return None
        return conn

    def find_by_user(
        self, user_id: uuid.UUID, include_deleted: bool = False
    ) -> list[BankConnection]:
        results: list[BankConnection] = []
        for conn in self._connections.values():
            if conn.user_id != user_id:
                continue
            if not include_deleted and conn.is_deleted():
                continue
            self.seen.add(conn)
            results.append(conn)
        return results

    def find_by_account(self, account_id: uuid.UUID) -> list[BankConnection]:
        results: list[BankConnection] = []
        for conn in self._connections.values():
            if conn.account_id == account_id and not conn.is_deleted():
                self.seen.add(conn)
                results.append(conn)
        return results

    def find_by_account_and_provider(
        self, account_id: uuid.UUID, provider_name: ProviderName
    ) -> BankConnection | None:
        for conn in self._connections.values():
            if (
                conn.account_id == account_id
                and conn.provider_name == provider_name
                and not conn.is_deleted()
            ):
                self.seen.add(conn)
                return conn
        return None

    def find_due_for_sync(self, as_of: datetime) -> list[BankConnection]:
        results: list[BankConnection] = []
        for conn in self._connections.values():
            if (
                conn.is_syncable()
                and conn.next_sync_scheduled_at is not None
                and conn.next_sync_scheduled_at <= as_of
            ):
                self.seen.add(conn)
                results.append(conn)
        return results


class FakeSyncHistoryRepository:
    """In-memory sync history repository for tests."""

    def __init__(self) -> None:
        self._histories: dict[uuid.UUID, SyncHistory] = {}

    def save(self, history: SyncHistory) -> None:
        self._histories[history.id] = history

    def find_by_id(self, sync_id: uuid.UUID) -> SyncHistory | None:
        return self._histories.get(sync_id)

    def find_by_connection(self, connection_id: uuid.UUID, limit: int = 10) -> list[SyncHistory]:
        matching = [h for h in self._histories.values() if h.connection_id == connection_id]
        matching.sort(key=lambda h: h.started_at, reverse=True)
        return matching[:limit]

    def find_latest_by_connection(self, connection_id: uuid.UUID) -> SyncHistory | None:
        results = self.find_by_connection(connection_id, limit=1)
        return results[0] if results else None

    def find_in_progress_by_connection(self, connection_id: uuid.UUID) -> SyncHistory | None:
        for h in self._histories.values():
            if h.connection_id == connection_id and h.status == SyncStatus.IN_PROGRESS:
                return h
        return None


class FakePendingTransactionRepository:
    """In-memory pending transaction repository for tests."""

    def __init__(self) -> None:
        self._pendings: dict[uuid.UUID, PendingTransaction] = {}

    def save(self, pending: PendingTransaction) -> None:
        self._pendings[pending.id] = pending

    def save_many(self, pendings: list[PendingTransaction]) -> None:
        for p in pendings:
            self.save(p)

    def find_by_id(self, pending_id: uuid.UUID) -> PendingTransaction | None:
        return self._pendings.get(pending_id)

    def find_by_connection(self, connection_id: uuid.UUID) -> list[PendingTransaction]:
        return [p for p in self._pendings.values() if p.connection_id == connection_id]

    def find_needs_review(self, connection_id: uuid.UUID) -> list[PendingTransaction]:
        return [
            p
            for p in self._pendings.values()
            if p.connection_id == connection_id and p.match_status == MatchStatus.NEEDS_REVIEW
        ]

    def find_by_sync(self, sync_id: uuid.UUID) -> list[PendingTransaction]:
        return [p for p in self._pendings.values() if p.sync_id == sync_id]

    def delete_by_connection(self, connection_id: uuid.UUID) -> int:
        to_remove = [pid for pid, p in self._pendings.items() if p.connection_id == connection_id]
        for pid in to_remove:
            del self._pendings[pid]
        return len(to_remove)


class FakeIntegrationsUnitOfWork(AbstractIntegrationsUnitOfWork):
    """In-memory Unit of Work for Integrations tests."""

    bank_connections: FakeBankConnectionRepository
    sync_history: FakeSyncHistoryRepository
    pending_transactions: FakePendingTransactionRepository

    def __init__(self) -> None:
        self.bank_connections = FakeBankConnectionRepository()
        self.sync_history = FakeSyncHistoryRepository()
        self.pending_transactions = FakePendingTransactionRepository()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class FakeBankProviderAdapter:
    """Fake bank provider adapter for tests."""

    def __init__(self) -> None:
        self._transactions: list[str] = []
        self._auth_error: Exception | None = None
        self._provider_error: Exception | None = None
        self._credentials_valid = True

    def set_transactions(self, transactions: list[str]) -> None:
        self._transactions = transactions

    def set_auth_error(self, error: Exception) -> None:
        self._auth_error = error

    def set_provider_error(self, error: Exception) -> None:
        self._provider_error = error

    def fetch_transactions(
        self,
        credentials: ProviderCredentials,
        external_account_id: str,
        since: datetime | None = None,
    ) -> list[str]:
        if self._auth_error is not None:
            raise self._auth_error
        if self._provider_error is not None:
            raise self._provider_error
        return list(self._transactions)

    def verify_credentials(self, credentials: ProviderCredentials) -> bool:
        return self._credentials_valid

    def get_account_info(
        self,
        credentials: ProviderCredentials,
        external_account_id: str,
    ) -> dict[str, Any]:
        return {"account_id": external_account_id}


class FakeTransactionNormalizer:
    """Fake normalizer that parses JSON raw data into NormalizedTransaction."""

    def normalize(self, raw_data: str) -> NormalizedTransaction:
        data = json.loads(raw_data)
        return NormalizedTransaction(
            transaction_date=date.fromisoformat(data["transaction_date"]),
            amount=Decimal(str(data["amount"])),
            currency_code=data["currency_code"],
            description=data["description"],
            external_id=data["external_id"],
            value_date=(date.fromisoformat(data["value_date"]) if data.get("value_date") else None),
            merchant=data.get("merchant"),
        )


class FakeProviderRegistry:
    """Fake provider registry resolving fake adapter + normalizer."""

    def __init__(
        self,
        adapter: FakeBankProviderAdapter | None = None,
        normalizer: FakeTransactionNormalizer | None = None,
    ) -> None:
        self._adapter = adapter or FakeBankProviderAdapter()
        self._normalizer = normalizer or FakeTransactionNormalizer()

    def get_adapter(self, provider_name: ProviderName) -> FakeBankProviderAdapter:
        return self._adapter

    def get_normalizer(self, provider_name: ProviderName) -> FakeTransactionNormalizer:
        return self._normalizer


class FakeTransactionImportPort:
    """Fake ACL port tracking imported transactions."""

    def __init__(self) -> None:
        self._imported: list[dict[str, Any]] = []
        self._existing_external_ids: dict[tuple[uuid.UUID, str], bool] = {}
        self._matches: dict[tuple[uuid.UUID, date, str], list[TransactionMatch]] = {}

    def add_existing_external_id(self, account_id: uuid.UUID, external_id: str) -> None:
        self._existing_external_ids[(account_id, external_id)] = True

    def add_match(
        self,
        account_id: uuid.UUID,
        transaction_date: date,
        amount_key: str,
        match: TransactionMatch,
    ) -> None:
        key = (account_id, transaction_date, amount_key)
        self._matches.setdefault(key, []).append(match)

    def import_transaction(
        self,
        account_id: uuid.UUID,
        transaction_date: date,
        amount: Decimal,
        currency_code: str,
        original_description: str,
        external_id: str,
        imported_by: uuid.UUID,
        value_date: date | None = None,
        merchant: str | None = None,
    ) -> uuid.UUID:
        txn_id = uuid.uuid4()
        self._imported.append(
            {
                "transaction_id": txn_id,
                "account_id": account_id,
                "transaction_date": transaction_date,
                "amount": amount,
                "currency_code": currency_code,
                "original_description": original_description,
                "external_id": external_id,
                "imported_by": imported_by,
                "value_date": value_date,
                "merchant": merchant,
            }
        )
        self._existing_external_ids[(account_id, external_id)] = True
        return txn_id

    def find_by_external_id(self, account_id: uuid.UUID, external_id: str) -> bool:
        return self._existing_external_ids.get((account_id, external_id), False)

    def find_by_date_and_amount(
        self,
        account_id: uuid.UUID,
        transaction_date: date,
        amount: Decimal,
        description: str | None = None,
    ) -> list[TransactionMatch]:
        key = (account_id, transaction_date, str(amount))
        return self._matches.get(key, [])

    @property
    def imported(self) -> list[dict[str, Any]]:
        return list(self._imported)
