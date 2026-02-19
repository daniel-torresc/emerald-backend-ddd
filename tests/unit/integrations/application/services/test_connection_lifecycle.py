"""Unit tests for BankConnectionService lifecycle operations."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from emerald.integrations.application.dtos.commands.connection_commands import (
    ActivateBankConnection,
    DisconnectBankConnection,
    ReconnectBankConnection,
    SoftDeleteBankConnection,
)
from emerald.integrations.application.services.bank_connection import BankConnectionService
from emerald.integrations.domain.exceptions.connection_exceptions import (
    BankConnectionNotFoundError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.entities.pending_transaction import PendingTransaction
from emerald.integrations.domain.models.value_objects.connection_status import ConnectionStatus
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName
from emerald.shared_kernel.domain.services.retention_policy_service import RetentionPolicyService
from tests.unit.integrations.fakes import FakeIntegrationsUnitOfWork
from tests.unit.shared_kernel.fakes import FakeRetentionPolicyRepository


@pytest.fixture()
def uow() -> FakeIntegrationsUnitOfWork:
    return FakeIntegrationsUnitOfWork()


@pytest.fixture()
def retention() -> RetentionPolicyService:
    return RetentionPolicyService(preference_repository=FakeRetentionPolicyRepository())


@pytest.fixture()
def service(
    uow: FakeIntegrationsUnitOfWork, retention: RetentionPolicyService
) -> BankConnectionService:
    return BankConnectionService(uow, retention)


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def account_id() -> uuid.UUID:
    return uuid.uuid4()


async def _create_connection(
    uow: FakeIntegrationsUnitOfWork,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    activate: bool = False,
) -> BankConnection:
    conn = BankConnection.create(
        user_id=user_id,
        account_id=account_id,
        provider_name=ProviderName("plaid"),
        institution_id="ins_123",
        external_account_id="ext_acc_123",
        created_by=user_id,
    )
    if activate:
        conn.activate(ProviderCredentials("test-token"))
    conn.collect_events()
    await uow.bank_connections.save(conn)
    return conn


def _make_pending(connection_id: uuid.UUID, account_id: uuid.UUID) -> PendingTransaction:
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


class TestActivateConnection:
    async def test_activates_with_credentials(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = await _create_connection(uow, user_id, account_id)
        cmd = ActivateBankConnection(
            connection_id=conn.id,
            credentials_token="new-token",
            activated_by=user_id,
        )

        await service.activate_connection(cmd)

        updated = await uow.bank_connections.find_by_id(conn.id)
        assert updated is not None
        assert updated.status == ConnectionStatus.ACTIVE
        assert updated.credentials == ProviderCredentials("new-token")
        assert uow.committed is True

    async def test_raises_not_found_for_missing_connection(
        self,
        service: BankConnectionService,
    ) -> None:
        cmd = ActivateBankConnection(
            connection_id=uuid.uuid4(),
            credentials_token="token",
            activated_by=uuid.uuid4(),
        )

        with pytest.raises(BankConnectionNotFoundError):
            await service.activate_connection(cmd)


class TestDisconnectConnection:
    async def test_disconnects_and_deletes_pending(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = await _create_connection(uow, user_id, account_id, activate=True)
        pending = _make_pending(conn.id, account_id)
        await uow.pending_transactions.save(pending)
        assert len(await uow.pending_transactions.find_by_connection(conn.id)) == 1

        cmd = DisconnectBankConnection(connection_id=conn.id, disconnected_by=user_id)

        await service.disconnect_connection(cmd)

        updated = await uow.bank_connections.find_by_id(conn.id)
        assert updated is not None
        assert updated.status == ConnectionStatus.DISCONNECTED
        assert len(await uow.pending_transactions.find_by_connection(conn.id)) == 0
        assert uow.committed is True

    async def test_raises_not_found_for_missing_connection(
        self,
        service: BankConnectionService,
    ) -> None:
        cmd = DisconnectBankConnection(connection_id=uuid.uuid4(), disconnected_by=uuid.uuid4())

        with pytest.raises(BankConnectionNotFoundError):
            await service.disconnect_connection(cmd)


class TestReconnectConnection:
    async def test_reconnects_with_new_credentials(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = await _create_connection(uow, user_id, account_id, activate=True)
        conn.mark_needs_reauth()
        conn.collect_events()
        assert conn.status == ConnectionStatus.NEEDS_REAUTH

        cmd = ReconnectBankConnection(
            connection_id=conn.id,
            credentials_token="fresh-token",
            reconnected_by=user_id,
        )

        await service.reconnect_connection(cmd)

        updated = await uow.bank_connections.find_by_id(conn.id)
        assert updated is not None
        assert updated.status == ConnectionStatus.ACTIVE
        assert updated.credentials == ProviderCredentials("fresh-token")
        assert uow.committed is True


class TestSoftDeleteConnection:
    async def test_soft_deletes_and_removes_pending(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = await _create_connection(uow, user_id, account_id, activate=True)
        pending = _make_pending(conn.id, account_id)
        await uow.pending_transactions.save(pending)

        cmd = SoftDeleteBankConnection(
            connection_id=conn.id, deleted_by=user_id, reason="no longer needed"
        )

        await service.soft_delete_connection(cmd)

        # Connection is soft-deleted (not visible without include_deleted)
        assert await uow.bank_connections.find_by_id(conn.id) is None
        deleted = await uow.bank_connections.find_by_id(conn.id, include_deleted=True)
        assert deleted is not None
        assert deleted.is_deleted()
        assert len(await uow.pending_transactions.find_by_connection(conn.id)) == 0
        assert uow.committed is True
