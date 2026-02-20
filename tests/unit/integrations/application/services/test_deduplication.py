"""Unit tests for DeduplicationService."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from emerald.integrations.application.dtos.transaction_match import TransactionMatch
from emerald.integrations.application.services.deduplication import DeduplicationService
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)
from tests.unit.integrations.fakes import FakeTransactionImportPort


@pytest.fixture()
def import_port() -> FakeTransactionImportPort:
    return FakeTransactionImportPort()


@pytest.fixture()
def service(import_port: FakeTransactionImportPort) -> DeduplicationService:
    return DeduplicationService(import_port)


@pytest.fixture()
def account_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_normalized(
    *,
    external_id: str = "ext_123",
    transaction_date: date = date(2024, 1, 15),
    amount: Decimal = Decimal("-50.00"),
    currency_code: str = "USD",
    description: str = "Coffee Shop",
) -> NormalizedTransaction:
    return NormalizedTransaction(
        transaction_date=transaction_date,
        amount=amount,
        currency_code=currency_code,
        description=description,
        external_id=external_id,
    )


class TestExactExternalIdMatch:
    """Tier 1: exact external_id match."""

    async def test_returns_duplicate_with_confidence_one(
        self,
        service: DeduplicationService,
        import_port: FakeTransactionImportPort,
        account_id: uuid.UUID,
    ) -> None:
        normalized = _make_normalized(external_id="ext_123")
        import_port.add_existing_external_id(account_id, "ext_123")

        result = await service.check(normalized, account_id)

        assert result.match_status == MatchStatus.DUPLICATE
        assert result.confidence == 1.0
        assert result.match_reason == "Exact external_id match"
        assert result.matched_transaction_id is None


class TestExactDateAmountDescription:
    """Tier 2: same date + amount + description."""

    async def test_returns_duplicate_with_confidence_095(
        self,
        service: DeduplicationService,
        import_port: FakeTransactionImportPort,
        account_id: uuid.UUID,
    ) -> None:
        txn_id = uuid.uuid4()
        normalized = _make_normalized(
            transaction_date=date(2024, 1, 15),
            amount=Decimal("-50.00"),
            description="Coffee Shop",
        )
        import_port.add_match(
            account_id,
            date(2024, 1, 15),
            str(Decimal("-50.00")),
            TransactionMatch(
                transaction_id=txn_id,
                transaction_date=date(2024, 1, 15),
                amount=Decimal("-50.00"),
                description="Coffee Shop",
            ),
        )

        result = await service.check(normalized, account_id)

        assert result.match_status == MatchStatus.DUPLICATE
        assert result.confidence == 0.95
        assert result.matched_transaction_id == txn_id


class TestFuzzyDateApproximateAmount:
    """Tier 3: same date + approximate amount (within tolerance)."""

    async def test_returns_needs_review_with_confidence_06(
        self,
        service: DeduplicationService,
        import_port: FakeTransactionImportPort,
        account_id: uuid.UUID,
    ) -> None:
        txn_id = uuid.uuid4()
        normalized = _make_normalized(
            transaction_date=date(2024, 1, 15),
            amount=Decimal("-50.00"),
            description="Coffee Shop",
        )
        # Match has same amount but different description (so not tier 2)
        import_port.add_match(
            account_id,
            date(2024, 1, 15),
            str(Decimal("-50.00")),
            TransactionMatch(
                transaction_id=txn_id,
                transaction_date=date(2024, 1, 15),
                amount=Decimal("-50.00"),
                description="Different Desc",
            ),
        )

        result = await service.check(normalized, account_id)

        assert result.match_status == MatchStatus.NEEDS_REVIEW
        assert result.confidence == 0.6
        assert result.matched_transaction_id == txn_id

    async def test_approximate_amount_within_tolerance(
        self,
        service: DeduplicationService,
        import_port: FakeTransactionImportPort,
        account_id: uuid.UUID,
    ) -> None:
        txn_id = uuid.uuid4()
        normalized = _make_normalized(
            transaction_date=date(2024, 1, 15),
            amount=Decimal("-50.00"),
            description="Coffee Shop",
        )
        # Amount differs by 0.01 (within tolerance), description differs
        import_port.add_match(
            account_id,
            date(2024, 1, 15),
            str(Decimal("-50.00")),
            TransactionMatch(
                transaction_id=txn_id,
                transaction_date=date(2024, 1, 15),
                amount=Decimal("-50.01"),
                description="Different Desc",
            ),
        )

        result = await service.check(normalized, account_id)

        assert result.match_status == MatchStatus.NEEDS_REVIEW
        assert result.confidence == 0.6


class TestNoMatch:
    """Tier 4: no matching transaction."""

    async def test_returns_new_with_confidence_zero(
        self,
        service: DeduplicationService,
        import_port: FakeTransactionImportPort,
        account_id: uuid.UUID,
    ) -> None:
        normalized = _make_normalized()

        result = await service.check(normalized, account_id)

        assert result.match_status == MatchStatus.NEW
        assert result.confidence == 0.0
        assert result.match_reason == "No matching transaction found"
        assert result.matched_transaction_id is None
