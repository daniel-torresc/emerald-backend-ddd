"""Tests for SyncStatus enum."""

from enum import StrEnum

from emerald.integrations.domain.models.value_objects.sync_status import SyncStatus


class TestSyncStatusMembers:
    """Verify all expected members exist."""

    def test_in_progress_member_exists(self) -> None:
        assert SyncStatus.IN_PROGRESS == "IN_PROGRESS"

    def test_success_member_exists(self) -> None:
        assert SyncStatus.SUCCESS == "SUCCESS"

    def test_partial_member_exists(self) -> None:
        assert SyncStatus.PARTIAL == "PARTIAL"

    def test_failed_member_exists(self) -> None:
        assert SyncStatus.FAILED == "FAILED"

    def test_has_exactly_four_members(self) -> None:
        assert len(SyncStatus) == 4


class TestSyncStatusIsStrEnum:
    """Verify SyncStatus is a StrEnum."""

    def test_is_str_enum(self) -> None:
        assert issubclass(SyncStatus, StrEnum)

    def test_members_are_strings(self) -> None:
        for member in SyncStatus:
            assert isinstance(member, str)
            assert isinstance(member.value, str)

    def test_string_comparison(self) -> None:
        assert SyncStatus.SUCCESS == "SUCCESS"

    def test_can_create_from_value(self) -> None:
        assert SyncStatus("FAILED") is SyncStatus.FAILED
