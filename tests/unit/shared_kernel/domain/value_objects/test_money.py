from decimal import Decimal

import pytest

from emerald.shared_kernel.domain.exceptions import CurrencyMismatchError, InvalidValueError
from emerald.shared_kernel.domain.models import Currency, Money


class TestMoneyConstruction:
    def test_valid_construction(self) -> None:
        m = Money(Decimal("10.00"), Currency.USD)
        assert m.amount == Decimal("10.00")
        assert m.currency == Currency.USD

    def test_negative_amount_allowed(self) -> None:
        m = Money(Decimal("-5.00"), Currency.USD)
        assert m.amount == Decimal("-5.00")

    def test_nan_raises_invalid_value(self) -> None:
        with pytest.raises(InvalidValueError):
            Money(Decimal("NaN"), Currency.USD)

    def test_infinity_raises_invalid_value(self) -> None:
        with pytest.raises(InvalidValueError):
            Money(Decimal("Infinity"), Currency.USD)

    def test_neg_infinity_raises_invalid_value(self) -> None:
        with pytest.raises(InvalidValueError):
            Money(Decimal("-Infinity"), Currency.USD)

    def test_float_raises_invalid_value(self) -> None:
        with pytest.raises(InvalidValueError):
            Money(10.00, Currency.USD)  # type: ignore[arg-type]

    def test_zero_factory(self) -> None:
        m = Money.zero(Currency.USD)
        assert m.amount == Decimal("0")
        assert m.currency == Currency.USD
        assert m.is_zero()


class TestMoneyArithmetic:
    def test_addition_same_currency(self) -> None:
        result = Money(Decimal("10.00"), Currency.USD) + Money(Decimal("5.00"), Currency.USD)
        assert result == Money(Decimal("15.00"), Currency.USD)

    def test_addition_different_currency_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money(Decimal("10.00"), Currency.USD) + Money(Decimal("5.00"), Currency.EUR)

    def test_subtraction_same_currency(self) -> None:
        result = Money(Decimal("10.00"), Currency.USD) - Money(Decimal("3.00"), Currency.USD)
        assert result == Money(Decimal("7.00"), Currency.USD)

    def test_subtraction_different_currency_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money(Decimal("10.00"), Currency.USD) - Money(Decimal("3.00"), Currency.EUR)

    def test_negation(self) -> None:
        result = -Money(Decimal("10.00"), Currency.USD)
        assert result == Money(Decimal("-10.00"), Currency.USD)


class TestMoneyComparison:
    def test_lt_same_currency(self) -> None:
        assert Money(Decimal("5.00"), Currency.USD) < Money(Decimal("10.00"), Currency.USD)

    def test_le_same_currency(self) -> None:
        assert Money(Decimal("5.00"), Currency.USD) <= Money(Decimal("5.00"), Currency.USD)

    def test_gt_same_currency(self) -> None:
        assert Money(Decimal("10.00"), Currency.USD) > Money(Decimal("5.00"), Currency.USD)

    def test_ge_same_currency(self) -> None:
        assert Money(Decimal("10.00"), Currency.USD) >= Money(Decimal("10.00"), Currency.USD)

    def test_lt_different_currency_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money(Decimal("10.00"), Currency.USD) < Money(Decimal("20.00"), Currency.EUR)

    def test_le_different_currency_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money(Decimal("10.00"), Currency.USD) <= Money(Decimal("20.00"), Currency.EUR)

    def test_gt_different_currency_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money(Decimal("10.00"), Currency.USD) > Money(Decimal("5.00"), Currency.EUR)

    def test_ge_different_currency_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money(Decimal("10.00"), Currency.USD) >= Money(Decimal("5.00"), Currency.EUR)


class TestMoneyPredicates:
    def test_is_zero(self) -> None:
        assert Money.zero(Currency.USD).is_zero()

    def test_is_not_zero(self) -> None:
        assert not Money(Decimal("1.00"), Currency.USD).is_zero()

    def test_is_positive(self) -> None:
        assert Money(Decimal("10.00"), Currency.USD).is_positive()

    def test_is_not_positive_for_zero(self) -> None:
        assert not Money.zero(Currency.USD).is_positive()

    def test_is_negative(self) -> None:
        assert Money(Decimal("-5.00"), Currency.USD).is_negative()

    def test_is_not_negative_for_zero(self) -> None:
        assert not Money.zero(Currency.USD).is_negative()


class TestMoneyRounding:
    def test_bankers_rounding_005_rounds_down(self) -> None:
        # 10.005 -> 10.00 (Banker's: .005 rounds to even, 0 is even)
        result = Money(Decimal("10.005"), Currency.USD).round_to_currency()
        assert result == Money(Decimal("10.00"), Currency.USD)

    def test_bankers_rounding_015_rounds_up(self) -> None:
        # 10.015 -> 10.02 (Banker's: .015 rounds to even, 2 is even)
        result = Money(Decimal("10.015"), Currency.USD).round_to_currency()
        assert result == Money(Decimal("10.02"), Currency.USD)

    def test_jpy_zero_decimal_places(self) -> None:
        result = Money(Decimal("100"), Currency.JPY).round_to_currency()
        assert result == Money(Decimal("100"), Currency.JPY)

    def test_jpy_rounding(self) -> None:
        result = Money(Decimal("100.5"), Currency.JPY).round_to_currency()
        assert result == Money(Decimal("100"), Currency.JPY)


class TestMoneyEqualityAndHash:
    def test_equal_money(self) -> None:
        a = Money(Decimal("10.00"), Currency.USD)
        b = Money(Decimal("10.00"), Currency.USD)
        assert a == b

    def test_different_amount_not_equal(self) -> None:
        a = Money(Decimal("10.00"), Currency.USD)
        b = Money(Decimal("20.00"), Currency.USD)
        assert a != b

    def test_different_currency_not_equal(self) -> None:
        a = Money(Decimal("10.00"), Currency.USD)
        b = Money(Decimal("10.00"), Currency.EUR)
        assert a != b

    def test_same_hash_for_equal(self) -> None:
        a = Money(Decimal("10.00"), Currency.USD)
        b = Money(Decimal("10.00"), Currency.USD)
        assert hash(a) == hash(b)

    def test_immutability(self) -> None:
        m = Money(Decimal("10.00"), Currency.USD)
        with pytest.raises(AttributeError):
            m.amount = Decimal("20.00")  # type: ignore[misc]
