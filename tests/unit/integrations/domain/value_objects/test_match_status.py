"""Tests for MatchStatus enum."""

from enum import StrEnum

from emerald.integrations.domain.models.value_objects.match_status import MatchStatus


class TestMatchStatusMembers:
    """Verify all expected members exist."""

    def test_new_member_exists(self) -> None:
        assert MatchStatus.NEW == "NEW"

    def test_duplicate_member_exists(self) -> None:
        assert MatchStatus.DUPLICATE == "DUPLICATE"

    def test_needs_review_member_exists(self) -> None:
        assert MatchStatus.NEEDS_REVIEW == "NEEDS_REVIEW"

    def test_user_approved_member_exists(self) -> None:
        assert MatchStatus.USER_APPROVED == "USER_APPROVED"

    def test_user_rejected_member_exists(self) -> None:
        assert MatchStatus.USER_REJECTED == "USER_REJECTED"

    def test_has_exactly_five_members(self) -> None:
        assert len(MatchStatus) == 5


class TestMatchStatusIsStrEnum:
    """Verify MatchStatus is a StrEnum."""

    def test_is_str_enum(self) -> None:
        assert issubclass(MatchStatus, StrEnum)

    def test_members_are_strings(self) -> None:
        for member in MatchStatus:
            assert isinstance(member, str)
            assert isinstance(member.value, str)

    def test_string_comparison(self) -> None:
        assert MatchStatus.NEW == "NEW"
        assert "DUPLICATE" == MatchStatus.DUPLICATE

    def test_can_create_from_value(self) -> None:
        assert MatchStatus("NEEDS_REVIEW") is MatchStatus.NEEDS_REVIEW
