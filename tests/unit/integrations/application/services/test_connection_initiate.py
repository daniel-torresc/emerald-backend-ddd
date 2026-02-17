"""Unit tests for BankConnectionService.initiate_connection."""

from __future__ import annotations

import uuid

import pytest

from emerald.integrations.application.dtos.commands.connection_commands import (
    InitiateBankConnection,
)
from emerald.integrations.application.services.bank_connection import BankConnectionService
from emerald.integrations.domain.exceptions.connection_exceptions import DuplicateConnectionError
from emerald.integrations.domain.models.value_objects.connection_status import ConnectionStatus
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


def _make_cmd(
    user_id: uuid.UUID, account_id: uuid.UUID, provider_name: str = "plaid"
) -> InitiateBankConnection:
    return InitiateBankConnection(
        user_id=user_id,
        account_id=account_id,
        provider_name=provider_name,
        institution_id="ins_123",
        external_account_id="ext_acc_123",
    )


class TestInitiateConnection:
    def test_creates_pending_connection_and_commits(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        cmd = _make_cmd(user_id, account_id)

        connection = service.initiate_connection(cmd)

        assert connection.status == ConnectionStatus.PENDING
        assert uow.committed is True
        stored = uow.bank_connections.find_by_id(connection.id)
        assert stored is not None

    def test_returns_connection_with_correct_attributes(
        self,
        service: BankConnectionService,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        cmd = _make_cmd(user_id, account_id, provider_name="plaid")

        connection = service.initiate_connection(cmd)

        assert connection.user_id == user_id
        assert connection.account_id == account_id
        assert connection.provider_name == ProviderName("plaid")
        assert connection.institution_id == "ins_123"
        assert connection.external_account_id == "ext_acc_123"
        assert connection.status == ConnectionStatus.PENDING

    def test_raises_duplicate_connection_error_if_same_account_and_provider(
        self,
        service: BankConnectionService,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        cmd = _make_cmd(user_id, account_id, provider_name="plaid")
        service.initiate_connection(cmd)

        with pytest.raises(DuplicateConnectionError):
            service.initiate_connection(cmd)
