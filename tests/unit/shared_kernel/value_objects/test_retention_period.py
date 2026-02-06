from datetime import UTC, datetime

import pytest

from emerald.shared_kernel.exceptions import InvalidValueError
from emerald.shared_kernel.value_objects import RetentionPeriod, RetentionUnit


class TestRetentionPeriodConstruction:
    def test_valid_construction(self) -> None:
        rp = RetentionPeriod(30, RetentionUnit.DAYS)
        assert rp.duration == 30
        assert rp.unit == RetentionUnit.DAYS

    def test_zero_duration_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            RetentionPeriod(0, RetentionUnit.DAYS)

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            RetentionPeriod(-1, RetentionUnit.DAYS)


class TestRetentionPeriodToDays:
    def test_days(self) -> None:
        assert RetentionPeriod(30, RetentionUnit.DAYS).to_days() == 30

    def test_months(self) -> None:
        assert RetentionPeriod(6, RetentionUnit.MONTHS).to_days() == 180

    def test_years(self) -> None:
        assert RetentionPeriod(1, RetentionUnit.YEARS).to_days() == 365


class TestRetentionPeriodExpirationFrom:
    def test_days_expiration(self) -> None:
        start = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = RetentionPeriod(30, RetentionUnit.DAYS).expiration_from(start)
        assert result == datetime(2025, 1, 31, 12, 0, 0, tzinfo=UTC)

    def test_months_expiration_month_end_boundary(self) -> None:
        # 1 month from Jan 31 = Feb 28 (non-leap year)
        start = datetime(2025, 1, 31, 0, 0, 0, tzinfo=UTC)
        result = RetentionPeriod(1, RetentionUnit.MONTHS).expiration_from(start)
        assert result == datetime(2025, 2, 28, 0, 0, 0, tzinfo=UTC)

    def test_months_expiration_leap_year(self) -> None:
        # 1 month from Jan 31 2024 = Feb 29 2024 (leap year)
        start = datetime(2024, 1, 31, 0, 0, 0, tzinfo=UTC)
        result = RetentionPeriod(1, RetentionUnit.MONTHS).expiration_from(start)
        assert result == datetime(2024, 2, 29, 0, 0, 0, tzinfo=UTC)

    def test_years_expiration_leap_year_boundary(self) -> None:
        # 1 year from Feb 29 2024 = Feb 28 2025 (no Feb 29 in 2025)
        start = datetime(2024, 2, 29, 0, 0, 0, tzinfo=UTC)
        result = RetentionPeriod(1, RetentionUnit.YEARS).expiration_from(start)
        assert result == datetime(2025, 2, 28, 0, 0, 0, tzinfo=UTC)

    def test_expiration_preserves_timezone(self) -> None:
        start = datetime(2025, 6, 1, 15, 30, 0, tzinfo=UTC)
        result = RetentionPeriod(3, RetentionUnit.MONTHS).expiration_from(start)
        assert result.tzinfo is not None


class TestRetentionPeriodComparison:
    def test_days_less_than_months(self) -> None:
        assert RetentionPeriod(30, RetentionUnit.DAYS) < RetentionPeriod(6, RetentionUnit.MONTHS)

    def test_months_less_than_years(self) -> None:
        assert RetentionPeriod(6, RetentionUnit.MONTHS) < RetentionPeriod(1, RetentionUnit.YEARS)

    def test_equal_periods(self) -> None:
        a = RetentionPeriod(30, RetentionUnit.DAYS)
        b = RetentionPeriod(30, RetentionUnit.DAYS)
        assert a == b
        assert a <= b
        assert a >= b

    def test_greater_than(self) -> None:
        assert RetentionPeriod(1, RetentionUnit.YEARS) > RetentionPeriod(30, RetentionUnit.DAYS)


class TestRetentionPeriodEqualityAndHash:
    def test_equal_periods_same_hash(self) -> None:
        a = RetentionPeriod(30, RetentionUnit.DAYS)
        b = RetentionPeriod(30, RetentionUnit.DAYS)
        assert hash(a) == hash(b)

    def test_hashable_in_set(self) -> None:
        s = {RetentionPeriod(30, RetentionUnit.DAYS), RetentionPeriod(30, RetentionUnit.DAYS)}
        assert len(s) == 1
