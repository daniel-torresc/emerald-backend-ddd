"""Unit tests for BankSyncService.execute_sync."""

from __future__ import annotations

import json
import uuid

import pytest

from emerald.integrations.application.dtos.commands.connection_commands import TriggerSync
from emerald.integrations.application.services.bank_sync import BankSyncService
from emerald.integrations.domain.exceptions.connection_exceptions import (
    ConnectionNotActiveError,
    SyncAlreadyInProgressError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.entities.sync_history import SyncHistory
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName
from emerald.integrations.domain.models.value_objects.sync_status import SyncStatus
from tests.unit.integrations.fakes import (
    FakeBankProviderAdapter,
    FakeIntegrationsUnitOfWork,
    FakeProviderRegistry,
    FakeTransactionImportPort,
)


def _raw_txn(
    *,
    external_id: str = "ext_123",
    amount: str = "-50.00",
    description: str = "Coffee Shop",
    transaction_date: str = "2024-01-15",
    currency_code: str = "USD",
) -> str:
    return json.dumps(
        {
            "transaction_date": transaction_date,
            "amount": amount,
            "currency_code": currency_code,
            "description": description,
            "external_id": external_id,
        }
    )


@pytest.fixture()
def uow() -> FakeIntegrationsUnitOfWork:
    return FakeIntegrationsUnitOfWork()


@pytest.fixture()
def import_port() -> FakeTransactionImportPort:
    return FakeTransactionImportPort()


@pytest.fixture()
def adapter() -> FakeBankProviderAdapter:
    return FakeBankProviderAdapter()


@pytest.fixture()
def registry(adapter: FakeBankProviderAdapter) -> FakeProviderRegistry:
    return FakeProviderRegistry(adapter=adapter)


@pytest.fixture()
def service(
    uow: FakeIntegrationsUnitOfWork,
    import_port: FakeTransactionImportPort,
    registry: FakeProviderRegistry,
) -> BankSyncService:
    return BankSyncService(uow, import_port, registry)


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def account_id() -> uuid.UUID:
    return uuid.uuid4()


async def _create_active_connection(
    uow: FakeIntegrationsUnitOfWork, user_id: uuid.UUID, account_id: uuid.UUID
) -> BankConnection:
    conn = BankConnection.create(
        user_id=user_id,
        account_id=account_id,
        provider_name=ProviderName("plaid"),
        institution_id="ins_123",
        external_account_id="ext_acc_123",
        created_by=user_id,
    )
    conn.activate(ProviderCredentials("test-token"))
    conn.collect_events()
    await uow.bank_connections.save(conn)
    return conn


class TestExecuteSyncWithNewTransactions:
    async def test_creates_history_imports_and_completes_success(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        import_port: FakeTransactionImportPort,
        adapter: FakeBankProviderAdapter,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = await _create_active_connection(uow, user_id, account_id)
        adapter.set_transactions([_raw_txn(external_id="ext_1"), _raw_txn(external_id="ext_2")])
        cmd = TriggerSync(connection_id=conn.id, triggered_by=user_id)

        history = await service.execute_sync(cmd)

        assert history.status == SyncStatus.SUCCESS
        assert history.transactions_found == 2
        assert history.transactions_imported == 2
        assert history.transactions_duplicate == 0
        assert history.transactions_staged == 0
        assert len(import_port.imported) == 2
        assert uow.committed is True


class TestExecuteSyncWithDuplicates:
    async def test_skips_duplicates_and_counts_them(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        import_port: FakeTransactionImportPort,
        adapter: FakeBankProviderAdapter,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = await _create_active_connection(uow, user_id, account_id)
        import_port.add_existing_external_id(account_id, "ext_dup")
        adapter.set_transactions([_raw_txn(external_id="ext_dup")])
        cmd = TriggerSync(connection_id=conn.id, triggered_by=user_id)

        history = await service.execute_sync(cmd)

        assert history.status == SyncStatus.SUCCESS
        assert history.transactions_found == 1
        assert history.transactions_duplicate == 1
        assert history.transactions_imported == 0
        assert history.transactions_staged == 0
        assert len(import_port.imported) == 0


class TestExecuteSyncWithNeedsReview:
    async def test_stages_pending_for_review(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        import_port: FakeTransactionImportPort,
        adapter: FakeBankProviderAdapter,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        from datetime import date
        from decimal import Decimal

        from emerald.integrations.application.dtos.transaction_match import TransactionMatch

        conn = await _create_active_connection(uow, user_id, account_id)
        # Set up a fuzzy match (same date+amount, different description)
        import_port.add_match(
            account_id,
            date(2024, 1, 15),
            str(Decimal("-50.00")),
            TransactionMatch(
                transaction_id=uuid.uuid4(),
                transaction_date=date(2024, 1, 15),
                amount=Decimal("-50.00"),
                description="Different Coffee Shop",
            ),
        )
        adapter.set_transactions([_raw_txn()])
        cmd = TriggerSync(connection_id=conn.id, triggered_by=user_id)

        history = await service.execute_sync(cmd)

        assert history.status == SyncStatus.PARTIAL
        assert history.transactions_found == 1
        assert history.transactions_staged == 1
        assert history.transactions_imported == 0
        assert len(import_port.imported) == 0
        pendings = await uow.pending_transactions.find_needs_review(conn.id)
        assert len(pendings) == 1
        assert pendings[0].match_status == MatchStatus.NEEDS_REVIEW


class TestExecuteSyncMixed:
    async def test_mixed_results_with_correct_counts(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        import_port: FakeTransactionImportPort,
        adapter: FakeBankProviderAdapter,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        from datetime import date
        from decimal import Decimal

        from emerald.integrations.application.dtos.transaction_match import TransactionMatch

        conn = await _create_active_connection(uow, user_id, account_id)

        # Transaction 1: duplicate (external_id match)
        import_port.add_existing_external_id(account_id, "ext_dup")

        # Transaction 2: needs review (fuzzy match)
        import_port.add_match(
            account_id,
            date(2024, 1, 20),
            str(Decimal("-75.00")),
            TransactionMatch(
                transaction_id=uuid.uuid4(),
                transaction_date=date(2024, 1, 20),
                amount=Decimal("-75.00"),
                description="Different Store",
            ),
        )

        # Transaction 3: new (no match)
        adapter.set_transactions(
            [
                _raw_txn(external_id="ext_dup"),
                _raw_txn(
                    external_id="ext_review",
                    amount="-75.00",
                    transaction_date="2024-01-20",
                    description="Store",
                ),
                _raw_txn(external_id="ext_new", amount="-100.00"),
            ]
        )
        cmd = TriggerSync(connection_id=conn.id, triggered_by=user_id)

        history = await service.execute_sync(cmd)

        assert history.transactions_found == 3
        assert history.transactions_duplicate == 1
        assert history.transactions_staged == 1
        assert history.transactions_imported == 1
        assert history.status == SyncStatus.PARTIAL


class TestExecuteSyncValidation:
    async def test_raises_connection_not_active_for_pending_connection(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = BankConnection.create(
            user_id=user_id,
            account_id=account_id,
            provider_name=ProviderName("plaid"),
            institution_id="ins_123",
            external_account_id="ext_acc_123",
            created_by=user_id,
        )
        conn.collect_events()
        await uow.bank_connections.save(conn)

        cmd = TriggerSync(connection_id=conn.id, triggered_by=user_id)

        with pytest.raises(ConnectionNotActiveError):
            await service.execute_sync(cmd)

    async def test_raises_sync_already_in_progress(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = await _create_active_connection(uow, user_id, account_id)
        existing_history = SyncHistory.create(connection_id=conn.id)
        await uow.sync_history.save(existing_history)

        cmd = TriggerSync(connection_id=conn.id, triggered_by=user_id)

        with pytest.raises(SyncAlreadyInProgressError):
            await service.execute_sync(cmd)
