import uuid
from datetime import date
from decimal import Decimal

import pytest

from emerald.core_finance.domain.constants import (
    MAX_COMMENTS_LENGTH,
    MAX_MERCHANT_LENGTH,
    MAX_ORIGINAL_DESCRIPTION_LENGTH,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    EmptyDescriptionError,
    InvalidCommentsError,
    InvalidMerchantError,
)
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus
from emerald.core_finance.domain.models.value_objects.transaction_input import TransactionInput


class TestTransactionInput:
    def test_valid_construction_required_fields(self) -> None:
        ti = TransactionInput(
            transaction_date=date(2024, 1, 15),
            amount=Decimal("100.00"),
            original_description="Coffee",
        )
        assert ti.transaction_date == date(2024, 1, 15)
        assert ti.amount == Decimal("100.00")
        assert ti.original_description == "Coffee"
        assert ti.value_date is None
        assert ti.merchant is None
        assert ti.comments is None
        assert ti.review_status == ReviewStatus.TO_REVIEW
        assert ti.external_id is None
        assert ti.card_id is None

    def test_valid_construction_all_fields(self) -> None:
        card_id = uuid.uuid4()
        ti = TransactionInput(
            transaction_date=date(2024, 1, 15),
            amount=Decimal("-50.00"),
            original_description="Groceries",
            value_date=date(2024, 1, 16),
            merchant="Store",
            comments="Weekly",
            review_status=ReviewStatus.REVIEWED,
            external_id="ext-123",
            card_id=card_id,
        )
        assert ti.value_date == date(2024, 1, 16)
        assert ti.merchant == "Store"
        assert ti.comments == "Weekly"
        assert ti.review_status == ReviewStatus.REVIEWED
        assert ti.external_id == "ext-123"
        assert ti.card_id == card_id

    def test_whitespace_trimming_description(self) -> None:
        ti = TransactionInput(
            transaction_date=date(2024, 1, 1),
            amount=Decimal("10"),
            original_description="  Trimmed  ",
        )
        assert ti.original_description == "Trimmed"

    def test_whitespace_trimming_merchant(self) -> None:
        ti = TransactionInput(
            transaction_date=date(2024, 1, 1),
            amount=Decimal("10"),
            original_description="Test",
            merchant="  Store  ",
        )
        assert ti.merchant == "Store"

    def test_whitespace_trimming_comments(self) -> None:
        ti = TransactionInput(
            transaction_date=date(2024, 1, 1),
            amount=Decimal("10"),
            original_description="Test",
            comments="  Note  ",
        )
        assert ti.comments == "Note"

    def test_whitespace_trimming_external_id(self) -> None:
        ti = TransactionInput(
            transaction_date=date(2024, 1, 1),
            amount=Decimal("10"),
            original_description="Test",
            external_id="  abc  ",
        )
        assert ti.external_id == "abc"

    def test_empty_description_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            TransactionInput(
                transaction_date=date(2024, 1, 1),
                amount=Decimal("10"),
                original_description="",
            )

    def test_whitespace_only_description_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            TransactionInput(
                transaction_date=date(2024, 1, 1),
                amount=Decimal("10"),
                original_description="   ",
            )

    def test_description_too_long_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            TransactionInput(
                transaction_date=date(2024, 1, 1),
                amount=Decimal("10"),
                original_description="x" * (MAX_ORIGINAL_DESCRIPTION_LENGTH + 1),
            )

    def test_merchant_too_long_raises(self) -> None:
        with pytest.raises(InvalidMerchantError):
            TransactionInput(
                transaction_date=date(2024, 1, 1),
                amount=Decimal("10"),
                original_description="Test",
                merchant="x" * (MAX_MERCHANT_LENGTH + 1),
            )

    def test_empty_merchant_raises(self) -> None:
        with pytest.raises(InvalidMerchantError):
            TransactionInput(
                transaction_date=date(2024, 1, 1),
                amount=Decimal("10"),
                original_description="Test",
                merchant="   ",
            )

    def test_comments_too_long_raises(self) -> None:
        with pytest.raises(InvalidCommentsError):
            TransactionInput(
                transaction_date=date(2024, 1, 1),
                amount=Decimal("10"),
                original_description="Test",
                comments="x" * (MAX_COMMENTS_LENGTH + 1),
            )

    def test_empty_comments_raises(self) -> None:
        with pytest.raises(InvalidCommentsError):
            TransactionInput(
                transaction_date=date(2024, 1, 1),
                amount=Decimal("10"),
                original_description="Test",
                comments="   ",
            )

    def test_frozen(self) -> None:
        ti = TransactionInput(
            transaction_date=date(2024, 1, 1),
            amount=Decimal("10"),
            original_description="Test",
        )
        with pytest.raises(AttributeError):
            ti.amount = Decimal("20")  # type: ignore[misc]

    def test_description_at_max_length(self) -> None:
        desc = "x" * MAX_ORIGINAL_DESCRIPTION_LENGTH
        ti = TransactionInput(
            transaction_date=date(2024, 1, 1),
            amount=Decimal("10"),
            original_description=desc,
        )
        assert ti.original_description == desc
