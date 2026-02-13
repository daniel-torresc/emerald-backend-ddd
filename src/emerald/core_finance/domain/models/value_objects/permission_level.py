from __future__ import annotations

from enum import Enum


class PermissionLevel(Enum):
    """Hierarchical access level for account sharing."""

    VIEWER = "VIEWER"
    EDITOR = "EDITOR"
    OWNER = "OWNER"

    @property
    def level(self) -> int:
        return _PERMISSION_LEVELS[self]

    def has_at_least(self, required: PermissionLevel) -> bool:
        """Whether this level meets or exceeds the required level."""
        return self.level >= required.level

    def can_grant(self, level: PermissionLevel) -> bool:
        """Whether this level can grant the specified level (only OWNER can grant)."""
        return self == PermissionLevel.OWNER


_PERMISSION_LEVELS: dict[PermissionLevel, int] = {
    PermissionLevel.VIEWER: 1,
    PermissionLevel.EDITOR: 2,
    PermissionLevel.OWNER: 3,
}
