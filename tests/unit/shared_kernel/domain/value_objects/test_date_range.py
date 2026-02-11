from datetime import date

import pytest

from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models import DateRange


class TestDateRangeConstruction:
    def test_valid_construction(self) -> None:
        dr = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        assert dr.start_date == date(2025, 1, 1)
        assert dr.end_date == date(2025, 1, 31)

    def test_single_day_range(self) -> None:
        dr = DateRange(date(2025, 1, 1), date(2025, 1, 1))
        assert dr.duration_days() == 1

    def test_start_after_end_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            DateRange(date(2025, 2, 1), date(2025, 1, 1))


class TestDateRangeContains:
    def test_date_within_range(self) -> None:
        dr = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        assert dr.contains(date(2025, 1, 15))

    def test_date_outside_range(self) -> None:
        dr = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        assert not dr.contains(date(2025, 2, 1))

    def test_start_date_inclusive(self) -> None:
        dr = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        assert dr.contains(date(2025, 1, 1))

    def test_end_date_inclusive(self) -> None:
        dr = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        assert dr.contains(date(2025, 1, 31))


class TestDateRangeOverlaps:
    def test_overlapping_ranges(self) -> None:
        a = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        b = DateRange(date(2025, 1, 15), date(2025, 2, 15))
        assert a.overlaps(b)
        assert b.overlaps(a)

    def test_non_overlapping_ranges(self) -> None:
        a = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        b = DateRange(date(2025, 3, 1), date(2025, 3, 31))
        assert not a.overlaps(b)
        assert not b.overlaps(a)

    def test_adjacent_ranges_share_boundary(self) -> None:
        a = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        b = DateRange(date(2025, 1, 31), date(2025, 2, 28))
        assert a.overlaps(b)

    def test_adjacent_ranges_no_shared_day(self) -> None:
        a = DateRange(date(2025, 1, 1), date(2025, 1, 30))
        b = DateRange(date(2025, 1, 31), date(2025, 2, 28))
        assert not a.overlaps(b)


class TestDateRangeDuration:
    def test_january_has_31_days(self) -> None:
        dr = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        assert dr.duration_days() == 31

    def test_single_day(self) -> None:
        dr = DateRange(date(2025, 6, 15), date(2025, 6, 15))
        assert dr.duration_days() == 1

    def test_two_days(self) -> None:
        dr = DateRange(date(2025, 1, 1), date(2025, 1, 2))
        assert dr.duration_days() == 2


class TestDateRangeEqualityAndHash:
    def test_equal_ranges(self) -> None:
        a = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        b = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        assert a == b

    def test_different_ranges(self) -> None:
        a = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        b = DateRange(date(2025, 2, 1), date(2025, 2, 28))
        assert a != b

    def test_hashable(self) -> None:
        a = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        b = DateRange(date(2025, 1, 1), date(2025, 1, 31))
        assert hash(a) == hash(b)
        assert len({a, b}) == 1
