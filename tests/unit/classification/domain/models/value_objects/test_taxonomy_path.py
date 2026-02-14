import pytest

from emerald.classification.domain.models.value_objects import TaxonomyPath


class TestTaxonomyPath:
    def test_single_segment(self) -> None:
        path = TaxonomyPath(segments=("Food",))
        assert str(path) == "Food"
        assert path.depth == 0

    def test_multi_segment(self) -> None:
        path = TaxonomyPath(segments=("Food", "Restaurants", "Italian"))
        assert str(path) == "Food > Restaurants > Italian"
        assert path.depth == 2

    def test_empty_segments_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one segment"):
            TaxonomyPath(segments=())

    def test_parent_path_root_returns_none(self) -> None:
        path = TaxonomyPath(segments=("Food",))
        assert path.parent_path() is None

    def test_parent_path_child(self) -> None:
        path = TaxonomyPath(segments=("Food", "Restaurants"))
        parent = path.parent_path()
        assert parent is not None
        assert parent.segments == ("Food",)

    def test_parent_path_grandchild(self) -> None:
        path = TaxonomyPath(segments=("Food", "Restaurants", "Italian"))
        parent = path.parent_path()
        assert parent is not None
        assert parent.segments == ("Food", "Restaurants")

    def test_equality(self) -> None:
        p1 = TaxonomyPath(segments=("A", "B"))
        p2 = TaxonomyPath(segments=("A", "B"))
        assert p1 == p2

    def test_not_equal_different_segments(self) -> None:
        p1 = TaxonomyPath(segments=("A", "B"))
        p2 = TaxonomyPath(segments=("A", "C"))
        assert p1 != p2

    def test_frozen(self) -> None:
        path = TaxonomyPath(segments=("A",))
        with pytest.raises(AttributeError):
            path.segments = ("B",)  # type: ignore[misc]
