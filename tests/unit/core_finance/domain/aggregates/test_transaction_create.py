from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    EmptyDescriptionError,
    InvalidCommentsError,
    InvalidMerchantError,
)
from emerald.core_finance.domain.models.aggregates.transaction import Transaction
from emerald.core_finance.domain.models.value_objects.import_source import (
    ImportSource,
)
from emerald.core_finance.domain.models.value_objects.import_source_type import (
    ImportSourceType,
)
from emerald.core_finance.domain.models.value_objects.review_status import (
    ReviewStatus,
)
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money


def _make_transaction(**overrides: Any) -> Transaction:
    defaults: dict[str, Any] = {
        "account_id": uuid.uuid4(),
        "transaction_date": date(2024, 1, 15),
        "amount": Money(Decimal("100.00"), Currency.USD),
        "original_description": "Test Transaction",
        "created_by": uuid.uuid4(),
        "import_source": ImportSource(
            source_type=ImportSourceType.MANUAL,
            source_id=None,
            imported_at=datetime.now(UTC),
        ),
    }
    defaults.update(overrides)
    return Transaction.create(**defaults)


class TestTransactionCreateValid:
    def test_creates_with_defaults(self) -> None:
        tx = _make_transaction()
        assert tx.original_description == "Test Transaction"
        assert tx.review_status == ReviewStatus.TO_REVIEW

    def test_creates_with_all_optional_fields(self) -> None:
        card = uuid.uuid4()
        parent = uuid.uuid4()
        tx = _make_transaction(
            value_date=date(2024, 1, 16),
            merchant="Coffee Shop",
            comments="Morning coffee",
            external_id="ext-001",
            parent_transaction_id=parent,
            card_id=card,
        )
        assert tx.value_date == date(2024, 1, 16)
        assert tx.merchant == "Coffee Shop"
        assert tx.comments == "Morning coffee"
        assert tx.external_id == "ext-001"
        assert tx.parent_transaction_id == parent
        assert tx.card_id == card

    def test_review_status_always_to_review(self) -> None:
        tx = _make_transaction()
        assert tx.review_status == ReviewStatus.TO_REVIEW

    def test_user_description_starts_none(self) -> None:
        tx = _make_transaction()
        assert tx.user_description is None

    def test_import_source_correctly_set(self) -> None:
        source = ImportSource(
            source_type=ImportSourceType.BANK_IMPORT,
            source_id="conn-123",
            imported_at=datetime.now(UTC),
        )
        tx = _make_transaction(import_source=source)
        assert tx.import_source == source
        assert tx.import_source.source_type == ImportSourceType.BANK_IMPORT

    def test_created_by_correctly_set(self) -> None:
        actor = uuid.uuid4()
        tx = _make_transaction(created_by=actor)
        assert tx.created_by == actor

    def test_timestamps_set(self) -> None:
        tx = _make_transaction()
        assert tx.created_at is not None
        assert tx.updated_at is not None

    def test_id_is_uuid(self) -> None:
        tx = _make_transaction()
        assert isinstance(tx.id, uuid.UUID)

    def test_id_is_not_none(self) -> None:
        tx = _make_transaction()
        assert tx.id is not None

    def test_account_id_correctly_set(self) -> None:
        aid = uuid.uuid4()
        tx = _make_transaction(account_id=aid)
        assert tx.account_id == aid

    def test_transaction_date_correctly_set(self) -> None:
        tx = _make_transaction(transaction_date=date(2024, 6, 1))
        assert tx.transaction_date == date(2024, 6, 1)

    def test_amount_correctly_set(self) -> None:
        amount = Money(Decimal("-42.50"), Currency.EUR)
        tx = _make_transaction(amount=amount)
        assert tx.amount == amount

    def test_external_id_set_correctly(self) -> None:
        tx = _make_transaction(external_id="bank-tx-99")
        assert tx.external_id == "bank-tx-99"

    def test_external_id_default_none(self) -> None:
        tx = _make_transaction()
        assert tx.external_id is None

    def test_card_id_set_correctly(self) -> None:
        cid = uuid.uuid4()
        tx = _make_transaction(card_id=cid)
        assert tx.card_id == cid

    def test_card_id_default_none(self) -> None:
        tx = _make_transaction()
        assert tx.card_id is None

    def test_parent_transaction_id_set_correctly(self) -> None:
        pid = uuid.uuid4()
        tx = _make_transaction(parent_transaction_id=pid)
        assert tx.parent_transaction_id == pid

    def test_parent_transaction_id_default_none(self) -> None:
        tx = _make_transaction()
        assert tx.parent_transaction_id is None

    def test_value_date_default_none(self) -> None:
        tx = _make_transaction()
        assert tx.value_date is None


class TestTransactionCreateDescriptionValidation:
    def test_empty_raises_empty_description_error(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            _make_transaction(original_description="")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            _make_transaction(original_description="   ")

    def test_too_long_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            _make_transaction(original_description="A" * 501)

    def test_exactly_500_chars_allowed(self) -> None:
        tx = _make_transaction(original_description="A" * 500)
        assert len(tx.original_description) == 500

    def test_trimming_works(self) -> None:
        tx = _make_transaction(original_description="  Hello World  ")
        assert tx.original_description == "Hello World"


class TestTransactionCreateMerchantValidation:
    def test_empty_string_raises_invalid_merchant(self) -> None:
        with pytest.raises(InvalidMerchantError):
            _make_transaction(merchant="")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(InvalidMerchantError):
            _make_transaction(merchant="   ")

    def test_too_long_raises(self) -> None:
        with pytest.raises(InvalidMerchantError):
            _make_transaction(merchant="A" * 201)

    def test_exactly_200_chars_allowed(self) -> None:
        tx = _make_transaction(merchant="A" * 200)
        assert len(tx.merchant) == 200  # type: ignore[arg-type]

    def test_none_is_valid(self) -> None:
        tx = _make_transaction(merchant=None)
        assert tx.merchant is None

    def test_merchant_trimmed(self) -> None:
        tx = _make_transaction(merchant="  Starbucks  ")
        assert tx.merchant == "Starbucks"


class TestTransactionCreateCommentsValidation:
    def test_empty_string_raises_invalid_comments(self) -> None:
        with pytest.raises(InvalidCommentsError):
            _make_transaction(comments="")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(InvalidCommentsError):
            _make_transaction(comments="   ")

    def test_too_long_raises(self) -> None:
        with pytest.raises(InvalidCommentsError):
            _make_transaction(comments="A" * 1001)

    def test_exactly_1000_chars_allowed(self) -> None:
        tx = _make_transaction(comments="A" * 1000)
        assert len(tx.comments) == 1000  # type: ignore[arg-type]

    def test_none_is_valid(self) -> None:
        tx = _make_transaction(comments=None)
        assert tx.comments is None

    def test_comments_trimmed(self) -> None:
        tx = _make_transaction(comments="  My note  ")
        assert tx.comments == "My note"
