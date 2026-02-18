"""Unit tests for BankSyncService pending transaction review (approve/reject)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from emerald.integrations.application.dtos.commands.connection_commands import (
    ApprovePendingTransaction,
    RejectPendingTransaction,
)
from emerald.integrations.application.services.bank_sync import BankSyncService
from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidConnectionStateError,
    PendingTransactionNotFoundError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.entities.pending_transaction import PendingTransaction
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName
from tests.unit.integrations.fakes import (
    FakeIntegrationsUnitOfWork,
    FakeProviderRegistry,
    FakeTransactionImportPort,
)


@pytest.fixture()
def uow() -> FakeIntegrationsUnitOfWork:
    return FakeIntegrationsUnitOfWork()


@pytest.fixture()
def import_port() -> FakeTransactionImportPort:
    return FakeTransactionImportPort()


@pytest.fixture()
def registry() -> FakeProviderRegistry:
    return FakeProviderRegistry()


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


def _create_active_connection(
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
    uow.bank_connections.save(conn)
    return conn


def _create_pending(connection_id: uuid.UUID, account_id: uuid.UUID) -> PendingTransaction:
    normalized = NormalizedTransaction(
        transaction_date=date(2024, 1, 15),
        amount=Decimal("-50.00"),
        currency_code="USD",
        description="Coffee Shop",
        external_id="ext_pending_123",
    )
    return PendingTransaction.create(
        connection_id=connection_id,
        sync_id=uuid.uuid4(),
        account_id=account_id,
        external_id="ext_pending_123",
        raw_data="{}",
        normalized=normalized,
        match_status=MatchStatus.NEEDS_REVIEW,
    )


class TestApprovePending:
    async def test_approves_imports_and_returns_transaction_id(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        import_port: FakeTransactionImportPort,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_active_connection(uow, user_id, account_id)
        pending = _create_pending(conn.id, account_id)
        uow.pending_transactions.save(pending)

        cmd = ApprovePendingTransaction(pending_id=pending.id, approved_by=user_id)

        txn_id = await service.approve_pending(cmd)

        assert txn_id is not None
        assert len(import_port.imported) == 1
        assert import_port.imported[0]["transaction_id"] == txn_id
        assert import_port.imported[0]["account_id"] == account_id
        assert import_port.imported[0]["external_id"] == "ext_pending_123"

        updated_pending = uow.pending_transactions.find_by_id(pending.id)
        assert updated_pending is not None
        assert updated_pending.match_status == MatchStatus.USER_APPROVED
        assert updated_pending.imported_transaction_id == txn_id
        assert uow.committed is True

    async def test_raises_not_found_for_missing_pending(
        self,
        service: BankSyncService,
    ) -> None:
        cmd = ApprovePendingTransaction(pending_id=uuid.uuid4(), approved_by=uuid.uuid4())

        with pytest.raises(PendingTransactionNotFoundError):
            await service.approve_pending(cmd)

    async def test_raises_invalid_state_if_user_does_not_own_connection(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_active_connection(uow, user_id, account_id)
        pending = _create_pending(conn.id, account_id)
        uow.pending_transactions.save(pending)

        other_user = uuid.uuid4()
        cmd = ApprovePendingTransaction(pending_id=pending.id, approved_by=other_user)

        with pytest.raises(InvalidConnectionStateError):
            await service.approve_pending(cmd)


class TestRejectPending:
    async def test_rejects_pending_transaction(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_active_connection(uow, user_id, account_id)
        pending = _create_pending(conn.id, account_id)
        uow.pending_transactions.save(pending)

        cmd = RejectPendingTransaction(pending_id=pending.id, rejected_by=user_id)

        await service.reject_pending(cmd)

        updated = uow.pending_transactions.find_by_id(pending.id)
        assert updated is not None
        assert updated.match_status == MatchStatus.USER_REJECTED
        assert uow.committed is True

    async def test_raises_not_found_for_missing_pending(
        self,
        service: BankSyncService,
    ) -> None:
        cmd = RejectPendingTransaction(pending_id=uuid.uuid4(), rejected_by=uuid.uuid4())

        with pytest.raises(PendingTransactionNotFoundError):
            await service.reject_pending(cmd)
