from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AdminPermissionType(Enum):
    """Granular admin capability types within the admin portal."""

    MASTER_DATA_ADMIN = "MASTER_DATA_ADMIN"
    USER_SUPPORT_ADMIN = "USER_SUPPORT_ADMIN"
    COMPLIANCE_ADMIN = "COMPLIANCE_ADMIN"
    FULL_ADMIN = "FULL_ADMIN"


@dataclass(frozen=True)
class AdminPermission:
    """Granular capability within the admin portal.

    FULL_ADMIN acts as a superset — it includes all other permissions.
    """

    value: AdminPermissionType

    def __post_init__(self) -> None:
        if not isinstance(self.value, AdminPermissionType):
            msg = f"Expected AdminPermissionType, got {type(self.value).__name__}"
            raise TypeError(msg)

    def includes(self, other: AdminPermission) -> bool:
        """Whether this permission covers another.

        FULL_ADMIN.includes(X) is True for all X.
        Individual permissions only include themselves.
        """
        if self.value == AdminPermissionType.FULL_ADMIN:
            return True
        return self.value == other.value
