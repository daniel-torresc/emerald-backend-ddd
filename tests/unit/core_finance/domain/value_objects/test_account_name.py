import pytest

from emerald.core_finance.domain.exceptions import InvalidAccountNameError
from emerald.core_finance.domain.models.value_objects.account_name import AccountName


class TestAccountNameCreation:
    def test_valid_name(self) -> None:
        name = AccountName("My Checking")
        assert name.value == "My Checking"

    def test_trims_whitespace(self) -> None:
        name = AccountName("  My Checking  ")
        assert name.value == "My Checking"

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(InvalidAccountNameError):
            AccountName("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(InvalidAccountNameError):
            AccountName("   ")

    def test_rejects_over_100_characters(self) -> None:
        with pytest.raises(InvalidAccountNameError):
            AccountName("A" * 101)

    def test_accepts_exactly_100_characters(self) -> None:
        name = AccountName("A" * 100)
        assert len(name.value) == 100

    def test_frozen(self) -> None:
        name = AccountName("Checking")
        with pytest.raises(AttributeError):
            name.value = "Savings"  # type: ignore[misc]


class TestAccountNameEquality:
    def test_case_insensitive_equality(self) -> None:
        assert AccountName("My Account") == AccountName("my account")

    def test_case_insensitive_equality_mixed(self) -> None:
        assert AccountName("My Account") == AccountName("MY ACCOUNT")

    def test_same_case_equality(self) -> None:
        assert AccountName("Checking") == AccountName("Checking")

    def test_different_names_not_equal(self) -> None:
        assert AccountName("Checking") != AccountName("Savings")

    def test_same_hash_for_different_case(self) -> None:
        assert hash(AccountName("My Account")) == hash(AccountName("my account"))

    def test_different_hash_for_different_names(self) -> None:
        assert hash(AccountName("Checking")) != hash(AccountName("Savings"))

    def test_not_equal_to_non_account_name(self) -> None:
        assert AccountName("Checking") != "Checking"


class TestAccountNameNormalized:
    def test_normalized_lowercase(self) -> None:
        assert AccountName("My Account").normalized() == "my account"

    def test_normalized_already_lowercase(self) -> None:
        assert AccountName("checking").normalized() == "checking"

    def test_normalized_trimmed(self) -> None:
        assert AccountName("  My Account  ").normalized() == "my account"
