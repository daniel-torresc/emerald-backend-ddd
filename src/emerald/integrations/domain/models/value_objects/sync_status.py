from enum import StrEnum


class SyncStatus(StrEnum):
    """Status of a sync execution."""

    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
