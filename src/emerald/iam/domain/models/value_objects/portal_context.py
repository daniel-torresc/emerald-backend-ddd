from datetime import timedelta
from enum import Enum


class PortalContext(Enum):
    """Identifies which portal a login session targets. Determines refresh token TTL."""

    REGULAR = "REGULAR"
    ADMIN = "ADMIN"

    @property
    def refresh_ttl(self) -> timedelta:
        """Return the refresh token TTL for this portal context."""
        if self is PortalContext.REGULAR:
            return timedelta(days=7)
        return timedelta(hours=4)
