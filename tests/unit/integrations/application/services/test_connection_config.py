"""Unit tests for BankConnectionService.update_sync_frequency."""

from __future__ import annotations

import uuid

import pytest

from emerald.integrations.application.dtos.commands.connection_commands import UpdateSyncFrequency
from emerald.integrations.application.services.bank_connection import BankConnectionService
from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidConnectionStateError,
    InvalidSyncFrequencyError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
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


def _create_connection(
    uow: FakeIntegrationsUnitOfWork,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
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


class TestUpdateSyncFrequency:
    async def test_updates_frequency_hours(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_connection(uow, user_id, account_id)
        cmd = UpdateSyncFrequency(connection_id=conn.id, hours=12, updated_by=user_id)

        await service.update_sync_frequency(cmd)

        updated = uow.bank_connections.find_by_id(conn.id)
        assert updated is not None
        assert updated.sync_frequency_hours == 12
        assert uow.committed is True

    async def test_raises_if_user_does_not_own_connection(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_connection(uow, user_id, account_id)
        other_user = uuid.uuid4()
        cmd = UpdateSyncFrequency(connection_id=conn.id, hours=12, updated_by=other_user)

        with pytest.raises(InvalidConnectionStateError):
            await service.update_sync_frequency(cmd)

    async def test_raises_invalid_sync_frequency_for_out_of_range(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_connection(uow, user_id, account_id)

        cmd_too_low = UpdateSyncFrequency(connection_id=conn.id, hours=0, updated_by=user_id)
        with pytest.raises(InvalidSyncFrequencyError):
            await service.update_sync_frequency(cmd_too_low)

        cmd_too_high = UpdateSyncFrequency(connection_id=conn.id, hours=25, updated_by=user_id)
        with pytest.raises(InvalidSyncFrequencyError):
            await service.update_sync_frequency(cmd_too_high)
