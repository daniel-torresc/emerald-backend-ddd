import uuid
from typing import Protocol

from emerald.shared_kernel.domain.models.entities.user_retention_preference import (
    UserRetentionPreference,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


class RetentionPolicyRepository(Protocol):
    """Port for persisting and retrieving user retention preferences."""

    def find_user_preference(
        self, entity_type: DeletableEntityType, user_id: uuid.UUID
    ) -> UserRetentionPreference | None: ...

    def save_user_preference(self, preference: UserRetentionPreference) -> None: ...

    def delete_user_preference(
        self, entity_type: DeletableEntityType, user_id: uuid.UUID
    ) -> None: ...
