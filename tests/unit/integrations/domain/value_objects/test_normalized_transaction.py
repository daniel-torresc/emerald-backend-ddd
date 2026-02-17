"""Tests for NormalizedTransaction value object."""

from datetime import date
from decimal import Decimal

import pytest

from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidNormalizedTransactionError,
)
from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)


def _valid_kwargs() -> dict:
    """Return valid defaults for NormalizedTransaction."""
    return {
        "transaction_date": date(2025, 6, 15),
        "amount": Decimal("-50.00"),
        "currency_code": "USD",
        "description": "Coffee Shop Purchase",
        "external_id": "ext-001",
    }


class TestNormalizedTransactionValid:
    """Valid NormalizedTransaction creation scenarios."""

    def test_valid_with_required_fields(self) -> None:
        txn = NormalizedTransaction(**_valid_kwargs())
        assert txn.transaction_date == date(2025, 6, 15)
        assert txn.amount == Decimal("-50.00")
        assert txn.currency_code == "USD"
        assert txn.description == "Coffee Shop Purchase"
        assert txn.external_id == "ext-001"
        assert txn.value_date is None
        assert txn.merchant is None

    def test_valid_with_all_fields(self) -> None:
        txn = NormalizedTransaction(
            **_valid_kwargs(),
            value_date=date(2025, 6, 16),
            merchant="Starbucks",
        )
        assert txn.value_date == date(2025, 6, 16)
        assert txn.merchant == "Starbucks"

    def test_valid_positive_amount(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["amount"] = Decimal("100.00")
        txn = NormalizedTransaction(**kwargs)
        assert txn.amount == Decimal("100.00")

    def test_description_trimmed(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["description"] = "  Coffee  "
        txn = NormalizedTransaction(**kwargs)
        assert txn.description == "Coffee"

    def test_external_id_trimmed(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["external_id"] = "  ext-002  "
        txn = NormalizedTransaction(**kwargs)
        assert txn.external_id == "ext-002"

    def test_merchant_trimmed(self) -> None:
        txn = NormalizedTransaction(**_valid_kwargs(), merchant="  Starbucks  ")
        assert txn.merchant == "Starbucks"

    def test_blank_merchant_becomes_none(self) -> None:
        txn = NormalizedTransaction(**_valid_kwargs(), merchant="   ")
        assert txn.merchant is None

    def test_description_exactly_max_length(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["description"] = "a" * 500
        txn = NormalizedTransaction(**kwargs)
        assert len(txn.description) == 500

    def test_merchant_exactly_max_length(self) -> None:
        txn = NormalizedTransaction(**_valid_kwargs(), merchant="m" * 200)
        assert len(txn.merchant) == 200  # type: ignore[arg-type]


class TestNormalizedTransactionInvalidAmount:
    """Invalid amount scenarios."""

    def test_zero_amount_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["amount"] = Decimal("0")
        with pytest.raises(InvalidNormalizedTransactionError, match="non-zero"):
            NormalizedTransaction(**kwargs)

    def test_zero_decimal_amount_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["amount"] = Decimal("0.00")
        with pytest.raises(InvalidNormalizedTransactionError, match="non-zero"):
            NormalizedTransaction(**kwargs)


class TestNormalizedTransactionInvalidCurrency:
    """Invalid currency code scenarios."""

    def test_lowercase_currency_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["currency_code"] = "usd"
        with pytest.raises(InvalidNormalizedTransactionError, match="ISO 4217"):
            NormalizedTransaction(**kwargs)

    def test_two_char_currency_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["currency_code"] = "US"
        with pytest.raises(InvalidNormalizedTransactionError, match="ISO 4217"):
            NormalizedTransaction(**kwargs)

    def test_four_char_currency_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["currency_code"] = "USDD"
        with pytest.raises(InvalidNormalizedTransactionError, match="ISO 4217"):
            NormalizedTransaction(**kwargs)

    def test_empty_currency_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["currency_code"] = ""
        with pytest.raises(InvalidNormalizedTransactionError, match="ISO 4217"):
            NormalizedTransaction(**kwargs)

    def test_mixed_case_currency_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["currency_code"] = "Usd"
        with pytest.raises(InvalidNormalizedTransactionError, match="ISO 4217"):
            NormalizedTransaction(**kwargs)


class TestNormalizedTransactionInvalidDescription:
    """Invalid description scenarios."""

    def test_empty_description_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["description"] = ""
        with pytest.raises(InvalidNormalizedTransactionError, match="Description is required"):
            NormalizedTransaction(**kwargs)

    def test_blank_description_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["description"] = "   "
        with pytest.raises(InvalidNormalizedTransactionError, match="Description is required"):
            NormalizedTransaction(**kwargs)

    def test_description_too_long_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["description"] = "a" * 501
        with pytest.raises(InvalidNormalizedTransactionError, match="500"):
            NormalizedTransaction(**kwargs)


class TestNormalizedTransactionInvalidExternalId:
    """Invalid external_id scenarios."""

    def test_empty_external_id_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["external_id"] = ""
        with pytest.raises(InvalidNormalizedTransactionError, match="External ID is required"):
            NormalizedTransaction(**kwargs)

    def test_blank_external_id_raises_error(self) -> None:
        kwargs = _valid_kwargs()
        kwargs["external_id"] = "   "
        with pytest.raises(InvalidNormalizedTransactionError, match="External ID is required"):
            NormalizedTransaction(**kwargs)


class TestNormalizedTransactionInvalidMerchant:
    """Invalid merchant scenarios."""

    def test_merchant_too_long_raises_error(self) -> None:
        with pytest.raises(InvalidNormalizedTransactionError, match="200"):
            NormalizedTransaction(**_valid_kwargs(), merchant="m" * 201)


class TestNormalizedTransactionFrozen:
    """NormalizedTransaction is immutable."""

    def test_cannot_set_amount(self) -> None:
        txn = NormalizedTransaction(**_valid_kwargs())
        with pytest.raises(AttributeError):
            txn.amount = Decimal("1")  # type: ignore[misc]

    def test_cannot_set_description(self) -> None:
        txn = NormalizedTransaction(**_valid_kwargs())
        with pytest.raises(AttributeError):
            txn.description = "other"  # type: ignore[misc]
