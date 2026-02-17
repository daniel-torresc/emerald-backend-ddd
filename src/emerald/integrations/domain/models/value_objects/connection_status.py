from enum import StrEnum


class ConnectionStatus(StrEnum):
    """Lifecycle states for a bank connection."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    NEEDS_REAUTH = "NEEDS_REAUTH"
    ERROR = "ERROR"
    DISCONNECTED = "DISCONNECTED"
