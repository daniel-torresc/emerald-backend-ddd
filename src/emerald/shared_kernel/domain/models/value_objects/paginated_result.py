import math
from dataclasses import dataclass

from emerald.shared_kernel.domain.exceptions import InvalidValueError


@dataclass(frozen=True)
class PaginatedResult[T]:
    """Generic paginated query result."""

    items: tuple[T, ...]
    total: int
    page: int
    page_size: int

    def __post_init__(self) -> None:
        if self.page < 1:
            raise InvalidValueError(f"Page must be >= 1, got {self.page}")
        if self.page_size < 1:
            raise InvalidValueError(f"Page size must be >= 1, got {self.page_size}")
        if self.total < 0:
            raise InvalidValueError(f"Total must be >= 0, got {self.total}")

    @property
    def total_pages(self) -> int:
        if self.total == 0:
            return 0
        return math.ceil(self.total / self.page_size)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1
