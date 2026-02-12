import pytest

from emerald.core_finance.domain.exceptions import InvalidIBANError
from emerald.core_finance.domain.models.value_objects.iban import IBAN


class TestIBANCreation:
    def test_valid_gb_iban(self) -> None:
        iban = IBAN("GB29 NWBK 6016 1331 9268 19")
        assert iban.value == "GB29NWBK60161331926819"

    def test_valid_de_iban(self) -> None:
        iban = IBAN("DE89 3704 0044 0532 0130 00")
        assert iban.value == "DE89370400440532013000"

    def test_normalizes_lowercase(self) -> None:
        iban = IBAN("gb29 nwbk 6016 1331 9268 19")
        assert iban.value == "GB29NWBK60161331926819"

    def test_strips_spaces(self) -> None:
        iban = IBAN("  GB29 NWBK 6016 1331 9268 19  ")
        assert iban.value == "GB29NWBK60161331926819"

    def test_frozen(self) -> None:
        iban = IBAN("GB29NWBK60161331926819")
        with pytest.raises(AttributeError):
            iban.value = "XX"  # type: ignore[misc]


class TestIBANValidation:
    def test_rejects_too_short(self) -> None:
        with pytest.raises(InvalidIBANError, match="at least 15"):
            IBAN("GB29NWBK601613")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidIBANError, match="at most 34"):
            IBAN("GB29NWBK60161331926819" + "A" * 13)

    def test_rejects_invalid_country_code(self) -> None:
        with pytest.raises(InvalidIBANError, match="country code"):
            IBAN("12345678901234567")

    def test_rejects_non_digit_check_digits(self) -> None:
        with pytest.raises(InvalidIBANError, match="check digits"):
            IBAN("GBXX NWBK 6016 1331 9268 19")

    def test_rejects_non_alphanumeric_body(self) -> None:
        with pytest.raises(InvalidIBANError, match="alphanumeric"):
            IBAN("GB29NW!K60161331926819")

    def test_rejects_bad_checksum(self) -> None:
        with pytest.raises(InvalidIBANError, match="checksum"):
            IBAN("GB00 NWBK 6016 1331 9268 19")

    def test_rejects_another_bad_checksum(self) -> None:
        with pytest.raises(InvalidIBANError, match="checksum"):
            IBAN("DE00370400440532013000")


class TestIBANLastFour:
    def test_gb_last_four(self) -> None:
        iban = IBAN("GB29NWBK60161331926819")
        assert iban.last_four == "6819"

    def test_de_last_four(self) -> None:
        iban = IBAN("DE89370400440532013000")
        assert iban.last_four == "3000"


class TestIBANMasked:
    def test_masked_gb(self) -> None:
        iban = IBAN("GB29NWBK60161331926819")
        assert iban.masked() == "****6819"

    def test_masked_de(self) -> None:
        iban = IBAN("DE89370400440532013000")
        assert iban.masked() == "****3000"


class TestIBANEquality:
    def test_equal_ibans(self) -> None:
        assert IBAN("GB29NWBK60161331926819") == IBAN("GB29 NWBK 6016 1331 9268 19")

    def test_different_ibans(self) -> None:
        assert IBAN("GB29NWBK60161331926819") != IBAN("DE89370400440532013000")
