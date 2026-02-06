from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from dateutil.relativedelta import relativedelta

from emerald.shared_kernel.exceptions import InvalidValueError


class RetentionUnit(Enum):
    """Unit for retention period duration."""

    DAYS = "DAYS"
    MONTHS = "MONTHS"
    YEARS = "YEARS"


@dataclass(frozen=True)
class RetentionPeriod:
    """A duration for data retention policies."""

    duration: int
    unit: RetentionUnit

    def __post_init__(self) -> None:
        if self.duration <= 0:
            raise InvalidValueError(
                f"RetentionPeriod duration must be positive, got {self.duration}"
            )

    def expiration_from(self, start: datetime) -> datetime:
        """Calculate calendar-accurate expiration date from a start time."""
        match self.unit:
            case RetentionUnit.DAYS:
                return start + relativedelta(days=self.duration)
            case RetentionUnit.MONTHS:
                return start + relativedelta(months=self.duration)
            case RetentionUnit.YEARS:
                return start + relativedelta(years=self.duration)

    def to_days(self) -> int:
        """Approximate total days (30 days/month, 365 days/year)."""
        match self.unit:
            case RetentionUnit.DAYS:
                return self.duration
            case RetentionUnit.MONTHS:
                return self.duration * 30
            case RetentionUnit.YEARS:
                return self.duration * 365

    def __lt__(self, other: "RetentionPeriod") -> bool:
        return self.to_days() < other.to_days()

    def __le__(self, other: "RetentionPeriod") -> bool:
        return self.to_days() <= other.to_days()

    def __gt__(self, other: "RetentionPeriod") -> bool:
        return self.to_days() > other.to_days()

    def __ge__(self, other: "RetentionPeriod") -> bool:
        return self.to_days() >= other.to_days()
