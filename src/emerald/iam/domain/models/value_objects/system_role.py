from __future__ import annotations

from enum import Enum

_ROLE_LEVELS: dict[str, int] = {
    "USER": 1,
    "ADMIN": 2,
    "SUPERADMIN": 3,
}


class SystemRole(Enum):
    """System-level role determining portal access and coarse-grained authorization."""

    USER = "USER"
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"

    @property
    def level(self) -> int:
        """Integer level for hierarchy comparison."""
        return _ROLE_LEVELS[self.value]

    def has_at_least(self, required: SystemRole) -> bool:
        """Whether this role meets or exceeds the required level."""
        return self.level >= required.level

    def is_admin_or_above(self) -> bool:
        """Shorthand for has_at_least(ADMIN)."""
        return self.has_at_least(SystemRole.ADMIN)

    def can_access_admin_portal(self) -> bool:
        """Whether this role can access the admin portal."""
        return self.is_admin_or_above()
