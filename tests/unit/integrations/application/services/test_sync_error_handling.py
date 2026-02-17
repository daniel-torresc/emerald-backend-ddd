"""Unit tests for BankSyncService error handling during execute_sync."""

from __future__ import annotations

import uuid

import pytest

from emerald.integrations.application.dtos.commands.connection_commands import TriggerSync
from emerald.integrations.application.services.bank_sync import BankSyncService
from emerald.integrations.domain.exceptions.connection_exceptions import (
    ProviderAuthError,
    ProviderError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.value_objects.connection_status import ConnectionStatus
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


class TestAuthErrorHandling:
    def test_auth_error_marks_needs_reauth_and_fails_history(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        adapter: FakeBankProviderAdapter,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_active_connection(uow, user_id, account_id)
        adapter.set_auth_error(ProviderAuthError("Token expired"))
        cmd = TriggerSync(connection_id=conn.id, triggered_by=user_id)

        history = service.execute_sync(cmd)

        assert history.status == SyncStatus.FAILED
        assert history.error_message == "Token expired"
        updated = uow.bank_connections.find_by_id(conn.id)
        assert updated is not None
        assert updated.status == ConnectionStatus.NEEDS_REAUTH
        assert updated.credentials is None
        assert uow.committed is True


class TestProviderErrorHandling:
    def test_provider_error_records_failure_and_fails_history(
        self,
        service: BankSyncService,
        uow: FakeIntegrationsUnitOfWork,
        adapter: FakeBankProviderAdapter,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_active_connection(uow, user_id, account_id)
        adapter.set_provider_error(ProviderError("Service unavailable"))
        cmd = TriggerSync(connection_id=conn.id, triggered_by=user_id)

        history = service.execute_sync(cmd)

        assert history.status == SyncStatus.FAILED
        assert history.error_message == "Service unavailable"
        updated = uow.bank_connections.find_by_id(conn.id)
        assert updated is not None
        # First failure does not transition to ERROR (needs MAX_CONSECUTIVE_FAILURES)
        assert updated.status == ConnectionStatus.ACTIVE
        assert updated.consecutive_failures == 1
        assert updated.last_sync_error == "Service unavailable"
        assert uow.committed is True
