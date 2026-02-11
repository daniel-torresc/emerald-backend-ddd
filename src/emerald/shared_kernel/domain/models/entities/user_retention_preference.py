import uuid

from emerald.shared_kernel.domain.constants import DEFAULT_RETENTION
from emerald.shared_kernel.domain.exceptions.lifecycle_exceptions import BelowPlatformDefaultError
from emerald.shared_kernel.domain.models.base.entity import Entity
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.retention_period import RetentionPeriod


class UserRetentionPreference(Entity):
    """Per-user retention preference for a specific entity type."""

    def __init__(
        self,
        user_id: uuid.UUID,
        entity_type: DeletableEntityType,
        retention_period: RetentionPeriod,
        id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(id=id)
        platform_default = DEFAULT_RETENTION[entity_type]
        if retention_period < platform_default:
            raise BelowPlatformDefaultError(
                f"Retention period {retention_period} is below platform default "
                f"{platform_default} for {entity_type.value}"
            )
        self._user_id = user_id
        self._entity_type = entity_type
        self._retention_period = retention_period

    @property
    def user_id(self) -> uuid.UUID:
        return self._user_id

    @property
    def entity_type(self) -> DeletableEntityType:
        return self._entity_type

    @property
    def retention_period(self) -> RetentionPeriod:
        return self._retention_period
