from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from emerald.core_finance.domain.exceptions import InvalidUserReferenceError

if TYPE_CHECKING:
    from emerald.iam.domain.models.value_objects.authenticated_identity import (
        AuthenticatedIdentity,
    )


@dataclass(frozen=True)
class UserReference:
    """Anti-Corruption Layer: minimal IAM identity for the Core Finance domain.

    Contains only what the finance domain needs: identity and display.
    No roles, no email, no credentials.
    """

    user_id: uuid.UUID
    display_name: str

    def __post_init__(self) -> None:
        if self.user_id is None:
            raise InvalidUserReferenceError("user_id must not be None")
        if not self.display_name or not self.display_name.strip():
            raise InvalidUserReferenceError("display_name must not be blank")

    @classmethod
    def from_identity(cls, identity: AuthenticatedIdentity) -> UserReference:
        """Translate from IAM AuthenticatedIdentity, discarding email and system_role."""
        return cls(
            user_id=identity.user_id,
            display_name=identity.display_name,
        )
