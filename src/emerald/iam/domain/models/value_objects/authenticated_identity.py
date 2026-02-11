import uuid
from dataclasses import dataclass

from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.system_role import SystemRole


@dataclass(frozen=True, eq=False)
class AuthenticatedIdentity:
    """Integration contract for downstream bounded contexts.

    Downstream contexts (Core Finance, Classification) consume this — never IAM internals.
    Equality is based solely on user_id.
    """

    user_id: uuid.UUID
    email: EmailAddress
    display_name: str
    system_role: SystemRole

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AuthenticatedIdentity):
            return NotImplemented
        return self.user_id == other.user_id

    def __hash__(self) -> int:
        return hash(self.user_id)
