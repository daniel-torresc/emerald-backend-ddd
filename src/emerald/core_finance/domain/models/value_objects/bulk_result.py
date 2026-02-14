import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class BulkSuccess:
    """A single successful item in a bulk operation."""

    index: int
    entity_id: uuid.UUID


@dataclass(frozen=True)
class BulkFailure:
    """A single failed item in a bulk operation."""

    index: int
    entity_id: uuid.UUID | None
    error_code: str
    error_message: str


@dataclass(frozen=True)
class BulkResult:
    """Result of a bulk operation with per-item success/failure reporting."""

    success_count: int
    failure_count: int
    total_count: int
    successes: tuple[BulkSuccess, ...] = ()
    failures: tuple[BulkFailure, ...] = ()

    def __post_init__(self) -> None:
        if self.success_count < 0:
            raise ValueError("success_count must be non-negative")
        if self.failure_count < 0:
            raise ValueError("failure_count must be non-negative")
        if self.total_count != self.success_count + self.failure_count:
            raise ValueError("total_count must equal success_count + failure_count")
        if len(self.successes) != self.success_count:
            raise ValueError("len(successes) must equal success_count")
        if len(self.failures) != self.failure_count:
            raise ValueError("len(failures) must equal failure_count")

    @property
    def is_complete_success(self) -> bool:
        return self.failure_count == 0

    @property
    def is_complete_failure(self) -> bool:
        return self.success_count == 0

    @property
    def has_failures(self) -> bool:
        return self.failure_count > 0
