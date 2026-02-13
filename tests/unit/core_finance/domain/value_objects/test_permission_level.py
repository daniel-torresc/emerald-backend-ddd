from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel


class TestPermissionLevelValues:
    def test_viewer_value(self) -> None:
        assert PermissionLevel.VIEWER.value == "VIEWER"

    def test_editor_value(self) -> None:
        assert PermissionLevel.EDITOR.value == "EDITOR"

    def test_owner_value(self) -> None:
        assert PermissionLevel.OWNER.value == "OWNER"


class TestPermissionLevelProperty:
    def test_viewer_level(self) -> None:
        assert PermissionLevel.VIEWER.level == 1

    def test_editor_level(self) -> None:
        assert PermissionLevel.EDITOR.level == 2

    def test_owner_level(self) -> None:
        assert PermissionLevel.OWNER.level == 3


class TestHasAtLeast:
    def test_owner_has_at_least_viewer(self) -> None:
        assert PermissionLevel.OWNER.has_at_least(PermissionLevel.VIEWER) is True

    def test_owner_has_at_least_editor(self) -> None:
        assert PermissionLevel.OWNER.has_at_least(PermissionLevel.EDITOR) is True

    def test_owner_has_at_least_owner(self) -> None:
        assert PermissionLevel.OWNER.has_at_least(PermissionLevel.OWNER) is True

    def test_editor_has_at_least_viewer(self) -> None:
        assert PermissionLevel.EDITOR.has_at_least(PermissionLevel.VIEWER) is True

    def test_editor_has_at_least_editor(self) -> None:
        assert PermissionLevel.EDITOR.has_at_least(PermissionLevel.EDITOR) is True

    def test_editor_has_at_least_owner(self) -> None:
        assert PermissionLevel.EDITOR.has_at_least(PermissionLevel.OWNER) is False

    def test_viewer_has_at_least_viewer(self) -> None:
        assert PermissionLevel.VIEWER.has_at_least(PermissionLevel.VIEWER) is True

    def test_viewer_has_at_least_editor(self) -> None:
        assert PermissionLevel.VIEWER.has_at_least(PermissionLevel.EDITOR) is False

    def test_viewer_has_at_least_owner(self) -> None:
        assert PermissionLevel.VIEWER.has_at_least(PermissionLevel.OWNER) is False


class TestCanGrant:
    def test_owner_can_grant_viewer(self) -> None:
        assert PermissionLevel.OWNER.can_grant(PermissionLevel.VIEWER) is True

    def test_owner_can_grant_editor(self) -> None:
        assert PermissionLevel.OWNER.can_grant(PermissionLevel.EDITOR) is True

    def test_owner_can_grant_owner(self) -> None:
        assert PermissionLevel.OWNER.can_grant(PermissionLevel.OWNER) is True

    def test_editor_cannot_grant_viewer(self) -> None:
        assert PermissionLevel.EDITOR.can_grant(PermissionLevel.VIEWER) is False

    def test_editor_cannot_grant_editor(self) -> None:
        assert PermissionLevel.EDITOR.can_grant(PermissionLevel.EDITOR) is False

    def test_viewer_cannot_grant_viewer(self) -> None:
        assert PermissionLevel.VIEWER.can_grant(PermissionLevel.VIEWER) is False

    def test_viewer_cannot_grant_editor(self) -> None:
        assert PermissionLevel.VIEWER.can_grant(PermissionLevel.EDITOR) is False
