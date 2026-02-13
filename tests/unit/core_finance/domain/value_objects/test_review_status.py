from __future__ import annotations

from enum import StrEnum

from emerald.core_finance.domain.models.value_objects.review_status import (
    ReviewStatus,
)


class TestReviewStatusMembers:
    def test_to_review_exists(self) -> None:
        assert ReviewStatus.TO_REVIEW == "TO_REVIEW"

    def test_reviewed_exists(self) -> None:
        assert ReviewStatus.REVIEWED == "REVIEWED"

    def test_has_exactly_two_members(self) -> None:
        assert len(ReviewStatus) == 2


class TestReviewStatusIsStrEnum:
    def test_is_str_enum(self) -> None:
        assert issubclass(ReviewStatus, StrEnum)

    def test_members_are_strings(self) -> None:
        for member in ReviewStatus:
            assert isinstance(member, str)
            assert isinstance(member.value, str)
