from enum import StrEnum


class MatchStatus(StrEnum):
    """Deduplication match result for a pending transaction."""

    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    USER_APPROVED = "USER_APPROVED"
    USER_REJECTED = "USER_REJECTED"
