import pytest

from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models.value_objects.paginated_result import PaginatedResult


class TestPaginatedResultConstruction:
    def test_valid_construction(self) -> None:
        result = PaginatedResult(items=("a", "b", "c"), total=10, page=1, page_size=3)
        assert result.items == ("a", "b", "c")
        assert result.total == 10
        assert result.page == 1
        assert result.page_size == 3

    def test_empty_items(self) -> None:
        result = PaginatedResult(items=(), total=0, page=1, page_size=10)
        assert result.items == ()
        assert result.total == 0


class TestPaginatedResultTotalPages:
    def test_zero_items_returns_zero_pages(self) -> None:
        result = PaginatedResult(items=(), total=0, page=1, page_size=10)
        assert result.total_pages == 0

    def test_exact_fit(self) -> None:
        result = PaginatedResult(items=("a",) * 5, total=10, page=1, page_size=5)
        assert result.total_pages == 2

    def test_remainder_rounds_up(self) -> None:
        result = PaginatedResult(items=("a",) * 3, total=11, page=1, page_size=5)
        assert result.total_pages == 3

    def test_single_item_single_page(self) -> None:
        result = PaginatedResult(items=("a",), total=1, page=1, page_size=10)
        assert result.total_pages == 1


class TestPaginatedResultNavigation:
    def test_has_next_when_more_pages(self) -> None:
        result = PaginatedResult(items=("a",) * 5, total=15, page=1, page_size=5)
        assert result.has_next is True

    def test_no_next_on_last_page(self) -> None:
        result = PaginatedResult(items=("a",) * 5, total=15, page=3, page_size=5)
        assert result.has_next is False

    def test_has_previous_when_not_first_page(self) -> None:
        result = PaginatedResult(items=("a",) * 5, total=15, page=2, page_size=5)
        assert result.has_previous is True

    def test_no_previous_on_first_page(self) -> None:
        result = PaginatedResult(items=("a",) * 5, total=15, page=1, page_size=5)
        assert result.has_previous is False

    def test_no_next_and_no_previous_when_empty(self) -> None:
        result = PaginatedResult(items=(), total=0, page=1, page_size=10)
        assert result.has_next is False
        assert result.has_previous is False


class TestPaginatedResultValidation:
    def test_page_less_than_one_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            PaginatedResult(items=(), total=0, page=0, page_size=10)

    def test_page_negative_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            PaginatedResult(items=(), total=0, page=-1, page_size=10)

    def test_page_size_less_than_one_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            PaginatedResult(items=(), total=0, page=1, page_size=0)

    def test_page_size_negative_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            PaginatedResult(items=(), total=0, page=1, page_size=-5)

    def test_total_negative_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            PaginatedResult(items=(), total=-1, page=1, page_size=10)


class TestPaginatedResultGeneric:
    def test_works_with_strings(self) -> None:
        result = PaginatedResult(items=("hello", "world"), total=2, page=1, page_size=10)
        assert result.items == ("hello", "world")

    def test_works_with_integers(self) -> None:
        result = PaginatedResult(items=(1, 2, 3), total=3, page=1, page_size=10)
        assert result.items == (1, 2, 3)


class TestPaginatedResultImmutability:
    def test_frozen(self) -> None:
        result = PaginatedResult(items=("a",), total=1, page=1, page_size=10)
        with pytest.raises(AttributeError):
            result.page = 2  # type: ignore[misc]
