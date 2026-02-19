import uuid

from emerald.shared_kernel.domain.models.entities.user_retention_preference import (
    UserRetentionPreference,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


class FakeRetentionPolicyRepository:
    """In-memory fake for RetentionPolicyRepository protocol."""

    def __init__(self) -> None:
        self._preferences: dict[tuple[DeletableEntityType, uuid.UUID], UserRetentionPreference] = {}

    async def find_user_preference(
        self, entity_type: DeletableEntityType, user_id: uuid.UUID
    ) -> UserRetentionPreference | None:
        return self._preferences.get((entity_type, user_id))

    async def save_user_preference(self, preference: UserRetentionPreference) -> None:
        self._preferences[(preference.entity_type, preference.user_id)] = preference

    async def delete_user_preference(
        self, entity_type: DeletableEntityType, user_id: uuid.UUID
    ) -> None:
        self._preferences.pop((entity_type, user_id), None)
