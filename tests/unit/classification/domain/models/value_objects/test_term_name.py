import pytest

from emerald.classification.domain.constants import MAX_TERM_NAME_LENGTH
from emerald.classification.domain.exceptions import InvalidTermNameError
from emerald.classification.domain.models.value_objects import TermName


class TestTermName:
    def test_valid_name(self) -> None:
        name = TermName("Food")
        assert name.value == "Food"

    def test_trims_whitespace(self) -> None:
        name = TermName("  Restaurants  ")
        assert name.value == "Restaurants"

    def test_empty_raises(self) -> None:
        with pytest.raises(InvalidTermNameError):
            TermName("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(InvalidTermNameError):
            TermName("   ")

    def test_exceeds_max_length_raises(self) -> None:
        with pytest.raises(InvalidTermNameError):
            TermName("x" * (MAX_TERM_NAME_LENGTH + 1))

    def test_at_max_length_succeeds(self) -> None:
        name = TermName("x" * MAX_TERM_NAME_LENGTH)
        assert len(name.value) == MAX_TERM_NAME_LENGTH

    def test_case_insensitive_equality(self) -> None:
        assert TermName("Food") == TermName("food")
        assert TermName("Food") == TermName("FOOD")

    def test_case_insensitive_hash(self) -> None:
        assert hash(TermName("Food")) == hash(TermName("food"))

    def test_not_equal_different_value(self) -> None:
        assert TermName("Food") != TermName("Transport")

    def test_normalized(self) -> None:
        name = TermName("Italian Food")
        assert name.normalized() == "italian food"

    def test_not_equal_to_non_term_name(self) -> None:
        name = TermName("Food")
        assert name.__eq__("Food") is NotImplemented
