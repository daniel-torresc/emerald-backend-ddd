from dataclasses import dataclass
from datetime import date

from emerald.shared_kernel.domain.exceptions import InvalidValueError


@dataclass(frozen=True)
class DateRange:
    """A time period between two dates. Both endpoints are inclusive."""

    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise InvalidValueError(
                f"start_date ({self.start_date}) must be <= end_date ({self.end_date})"
            )

    def contains(self, d: date) -> bool:
        """Whether date falls within range (inclusive)."""
        return self.start_date <= d <= self.end_date

    def overlaps(self, other: "DateRange") -> bool:
        """Whether two ranges share any dates."""
        return self.start_date <= other.end_date and other.start_date <= self.end_date

    def duration_days(self) -> int:
        """Number of days in range (inclusive count)."""
        return (self.end_date - self.start_date).days + 1
