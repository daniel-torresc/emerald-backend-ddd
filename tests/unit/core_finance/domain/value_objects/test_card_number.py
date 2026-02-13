from __future__ import annotations

import pytest

from emerald.core_finance.domain.exceptions.card_exceptions import InvalidCardNumberError
from emerald.core_finance.domain.models.value_objects.card_number import CardNumber


class TestCardNumberValid:
    def test_visa_number(self) -> None:
        cn = CardNumber("4111111111111111")
        assert cn.value == "4111111111111111"

    def test_mastercard_number(self) -> None:
        cn = CardNumber("5500000000000004")
        assert cn.value == "5500000000000004"

    def test_amex_number_15_digits(self) -> None:
        cn = CardNumber("378282246310005")
        assert cn.value == "378282246310005"

    def test_discover_number(self) -> None:
        cn = CardNumber("6011111111111117")
        assert cn.value == "6011111111111117"


class TestCardNumberNormalization:
    def test_strips_spaces(self) -> None:
        cn = CardNumber("4111 1111 1111 1111")
        assert cn.value == "4111111111111111"

    def test_strips_dashes(self) -> None:
        cn = CardNumber("4111-1111-1111-1111")
        assert cn.value == "4111111111111111"


class TestCardNumberLastFour:
    def test_last_four_derived(self) -> None:
        cn = CardNumber("4111111111111111")
        assert cn.last_four == "1111"

    def test_last_four_mastercard(self) -> None:
        cn = CardNumber("5500000000000004")
        assert cn.last_four == "0004"


class TestCardNumberMasked:
    def test_masked_visa(self) -> None:
        cn = CardNumber("4111111111111111")
        assert cn.masked() == "****1111"

    def test_masked_mastercard(self) -> None:
        cn = CardNumber("5500000000000004")
        assert cn.masked() == "****0004"


class TestCardNumberStr:
    def test_str_returns_full_number(self) -> None:
        cn = CardNumber("4111111111111111")
        assert str(cn) == "4111111111111111"


class TestCardNumberFrozen:
    def test_immutable(self) -> None:
        cn = CardNumber("4111111111111111")
        with pytest.raises(AttributeError):
            cn.value = "0000000000000000"  # type: ignore[misc]


class TestCardNumberEquality:
    def test_same_numbers_equal(self) -> None:
        cn1 = CardNumber("4111111111111111")
        cn2 = CardNumber("4111 1111 1111 1111")
        assert cn1 == cn2

    def test_different_numbers_not_equal(self) -> None:
        cn1 = CardNumber("4111111111111111")
        cn2 = CardNumber("5500000000000004")
        assert cn1 != cn2


class TestCardNumberValidation:
    def test_non_numeric_raises(self) -> None:
        with pytest.raises(InvalidCardNumberError, match="only digits"):
            CardNumber("ABCD1234567890")

    def test_too_short_raises(self) -> None:
        with pytest.raises(InvalidCardNumberError, match="at least"):
            CardNumber("411111")

    def test_too_long_raises(self) -> None:
        with pytest.raises(InvalidCardNumberError, match="at most"):
            CardNumber("41111111111111111111")

    def test_bad_luhn_checksum_raises(self) -> None:
        with pytest.raises(InvalidCardNumberError, match="Luhn"):
            CardNumber("4111111111111112")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(InvalidCardNumberError):
            CardNumber("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(InvalidCardNumberError):
            CardNumber("   ")
