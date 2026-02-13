from enum import StrEnum


class ReviewStatus(StrEnum):
    """Transaction review workflow status."""

    TO_REVIEW = "TO_REVIEW"
    REVIEWED = "REVIEWED"
