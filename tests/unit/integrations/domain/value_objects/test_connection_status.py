"""Tests for ConnectionStatus enum."""

from enum import StrEnum

from emerald.integrations.domain.models.value_objects.connection_status import ConnectionStatus


class TestConnectionStatusMembers:
    """Verify all expected members exist."""

    def test_pending_member_exists(self) -> None:
        assert ConnectionStatus.PENDING == "PENDING"

    def test_active_member_exists(self) -> None:
        assert ConnectionStatus.ACTIVE == "ACTIVE"

    def test_needs_reauth_member_exists(self) -> None:
        assert ConnectionStatus.NEEDS_REAUTH == "NEEDS_REAUTH"

    def test_error_member_exists(self) -> None:
        assert ConnectionStatus.ERROR == "ERROR"

    def test_disconnected_member_exists(self) -> None:
        assert ConnectionStatus.DISCONNECTED == "DISCONNECTED"

    def test_has_exactly_five_members(self) -> None:
        assert len(ConnectionStatus) == 5


class TestConnectionStatusIsStrEnum:
    """Verify ConnectionStatus is a StrEnum."""

    def test_is_str_enum(self) -> None:
        assert issubclass(ConnectionStatus, StrEnum)

    def test_members_are_strings(self) -> None:
        for member in ConnectionStatus:
            assert isinstance(member, str)
            assert isinstance(member.value, str)

    def test_string_comparison(self) -> None:
        assert ConnectionStatus.ACTIVE == "ACTIVE"
        assert "PENDING" == ConnectionStatus.PENDING

    def test_can_create_from_value(self) -> None:
        assert ConnectionStatus("ACTIVE") is ConnectionStatus.ACTIVE
