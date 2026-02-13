from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    EmptyDescriptionError,
    InvalidCommentsError,
    InvalidMerchantError,
)
from emerald.core_finance.domain.models.value_objects.split_request import SplitRequest
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money

_USD_50 = Money(Decimal("50.00"), Currency.USD)


class TestSplitRequestCreation:
    def test_valid_with_all_fields(self) -> None:
        sr = SplitRequest(
            amount=_USD_50,
            description="Food items",
            merchant="Grocery Store",
            comments="Weekly groceries",
        )
        assert sr.amount == _USD_50
        assert sr.description == "Food items"
        assert sr.merchant == "Grocery Store"
        assert sr.comments == "Weekly groceries"

    def test_valid_with_optional_none(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="Food")
        assert sr.merchant is None
        assert sr.comments is None

    def test_trims_description(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="  Food  ")
        assert sr.description == "Food"

    def test_trims_merchant(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="Food", merchant="  Store  ")
        assert sr.merchant == "Store"

    def test_trims_comments(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="Food", comments="  Note  ")
        assert sr.comments == "Note"

    def test_whitespace_only_merchant_becomes_none(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="Food", merchant="   ")
        assert sr.merchant is None

    def test_whitespace_only_comments_becomes_none(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="Food", comments="   ")
        assert sr.comments is None

    def test_frozen(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="Food")
        with pytest.raises(dataclasses.FrozenInstanceError):
            sr.description = "Other"  # type: ignore[misc]


class TestSplitRequestValidation:
    def test_empty_description_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            SplitRequest(amount=_USD_50, description="")

    def test_whitespace_only_description_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            SplitRequest(amount=_USD_50, description="   ")

    def test_description_exceeding_max_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            SplitRequest(amount=_USD_50, description="x" * 501)

    def test_description_at_max_is_valid(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="x" * 500)
        assert len(sr.description) == 500

    def test_merchant_exceeding_max_raises(self) -> None:
        with pytest.raises(InvalidMerchantError):
            SplitRequest(amount=_USD_50, description="Food", merchant="x" * 201)

    def test_merchant_at_max_is_valid(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="Food", merchant="x" * 200)
        assert len(sr.merchant) == 200  # type: ignore[arg-type]

    def test_comments_exceeding_max_raises(self) -> None:
        with pytest.raises(InvalidCommentsError):
            SplitRequest(amount=_USD_50, description="Food", comments="x" * 1001)

    def test_comments_at_max_is_valid(self) -> None:
        sr = SplitRequest(amount=_USD_50, description="Food", comments="x" * 1000)
        assert len(sr.comments) == 1000  # type: ignore[arg-type]
