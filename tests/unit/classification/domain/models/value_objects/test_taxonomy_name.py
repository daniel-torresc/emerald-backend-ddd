import pytest

from emerald.classification.domain.constants import MAX_TAXONOMY_NAME_LENGTH
from emerald.classification.domain.exceptions import InvalidTaxonomyNameError
from emerald.classification.domain.models.value_objects import TaxonomyName


class TestTaxonomyName:
    def test_valid_name(self) -> None:
        name = TaxonomyName("Categories")
        assert name.value == "Categories"

    def test_trims_whitespace(self) -> None:
        name = TaxonomyName("  Budget  ")
        assert name.value == "Budget"

    def test_empty_raises(self) -> None:
        with pytest.raises(InvalidTaxonomyNameError):
            TaxonomyName("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(InvalidTaxonomyNameError):
            TaxonomyName("   ")

    def test_exceeds_max_length_raises(self) -> None:
        with pytest.raises(InvalidTaxonomyNameError):
            TaxonomyName("x" * (MAX_TAXONOMY_NAME_LENGTH + 1))

    def test_at_max_length_succeeds(self) -> None:
        name = TaxonomyName("x" * MAX_TAXONOMY_NAME_LENGTH)
        assert len(name.value) == MAX_TAXONOMY_NAME_LENGTH

    def test_case_insensitive_equality(self) -> None:
        assert TaxonomyName("Budget") == TaxonomyName("budget")
        assert TaxonomyName("Budget") == TaxonomyName("BUDGET")

    def test_case_insensitive_hash(self) -> None:
        assert hash(TaxonomyName("Budget")) == hash(TaxonomyName("budget"))

    def test_not_equal_different_value(self) -> None:
        assert TaxonomyName("Budget") != TaxonomyName("Spending")

    def test_normalized(self) -> None:
        name = TaxonomyName("My Categories")
        assert name.normalized() == "my categories"

    def test_not_equal_to_non_taxonomy_name(self) -> None:
        name = TaxonomyName("Budget")
        assert name.__eq__("Budget") is NotImplemented
