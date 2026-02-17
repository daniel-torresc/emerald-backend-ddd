"""Unit tests for BankConnectionService query methods."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from emerald.integrations.application.services.bank_connection import BankConnectionService
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.entities.pending_transaction import PendingTransaction
from emerald.integrations.domain.models.entities.sync_history import SyncHistory
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
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
    provider: str = "plaid",
) -> BankConnection:
    conn = BankConnection.create(
        user_id=user_id,
        account_id=account_id,
        provider_name=ProviderName(provider),
        institution_id="ins_123",
        external_account_id="ext_acc_123",
        created_by=user_id,
    )
    conn.collect_events()
    uow.bank_connections.save(conn)
    return conn


class TestGetConnectionsForUser:
    def test_returns_user_connections(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn1 = _create_connection(uow, user_id, account_id, provider="plaid")
        other_account = uuid.uuid4()
        conn2 = _create_connection(uow, user_id, other_account, provider="yodlee")

        # Another user's connection
        other_user = uuid.uuid4()
        _create_connection(uow, other_user, uuid.uuid4(), provider="mx")

        results = service.get_connections_for_user(user_id)

        result_ids = {c.id for c in results}
        assert result_ids == {conn1.id, conn2.id}


class TestGetConnectionsForAccount:
    def test_returns_account_connections(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_connection(uow, user_id, account_id)
        _create_connection(uow, user_id, uuid.uuid4(), provider="yodlee")

        results = service.get_connections_for_account(account_id)

        assert len(results) == 1
        assert results[0].id == conn.id


class TestGetSyncHistory:
    def test_returns_history_for_connection(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_connection(uow, user_id, account_id)
        history = SyncHistory.create(connection_id=conn.id)
        uow.sync_history.save(history)

        results = service.get_sync_history(conn.id)

        assert len(results) == 1
        assert results[0].id == history.id

    def test_returns_empty_list_for_no_history(
        self,
        service: BankConnectionService,
    ) -> None:
        results = service.get_sync_history(uuid.uuid4())

        assert results == []


class TestGetPendingForReview:
    def test_returns_needs_review_pendings(
        self,
        service: BankConnectionService,
        uow: FakeIntegrationsUnitOfWork,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> None:
        conn = _create_connection(uow, user_id, account_id)
        normalized = NormalizedTransaction(
            transaction_date=date(2024, 1, 15),
            amount=Decimal("-50.00"),
            currency_code="USD",
            description="Coffee Shop",
            external_id="ext_123",
        )
        pending_review = PendingTransaction.create(
            connection_id=conn.id,
            sync_id=uuid.uuid4(),
            account_id=account_id,
            external_id="ext_123",
            raw_data="{}",
            normalized=normalized,
            match_status=MatchStatus.NEEDS_REVIEW,
        )
        uow.pending_transactions.save(pending_review)

        # A NEW pending should not appear
        normalized_new = NormalizedTransaction(
            transaction_date=date(2024, 1, 16),
            amount=Decimal("-25.00"),
            currency_code="USD",
            description="Other",
            external_id="ext_456",
        )
        pending_new = PendingTransaction.create(
            connection_id=conn.id,
            sync_id=uuid.uuid4(),
            account_id=account_id,
            external_id="ext_456",
            raw_data="{}",
            normalized=normalized_new,
            match_status=MatchStatus.NEW,
        )
        uow.pending_transactions.save(pending_new)

        results = service.get_pending_for_review(conn.id)

        assert len(results) == 1
        assert results[0].id == pending_review.id
