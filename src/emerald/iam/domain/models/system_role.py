from enum import Enum


class SystemRole(Enum):
    """System-level role determining portal access and coarse-grained authorization."""

    USER = "USER"
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"
