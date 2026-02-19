import uuid
from datetime import datetime

from emerald.shared_kernel.application.ports.outbound.retention_policy_repository import (
    RetentionPolicyRepository,
)
from emerald.shared_kernel.domain.constants import (
    COOLING_OFF_PERIODS,
    DEFAULT_RETENTION,
    REGULATORY_MINIMUMS,
)
from emerald.shared_kernel.domain.exceptions.lifecycle_exceptions import BelowPlatformDefaultError
from emerald.shared_kernel.domain.models.entities.user_retention_preference import (
    UserRetentionPreference,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.retention_period import RetentionPeriod


class RetentionPolicyService:
    """Resolves the effective retention period from the hierarchy."""

    def __init__(self, preference_repository: RetentionPolicyRepository) -> None:
        self._preference_repository = preference_repository

    async def get_effective_retention(
        self, entity_type: DeletableEntityType, user_id: uuid.UUID | None = None
    ) -> RetentionPeriod:
        """Resolve hierarchy: regulatory -> platform default -> user preference.
        Returns the longest applicable period."""
        platform_default = DEFAULT_RETENTION[entity_type]
        effective = platform_default

        regulatory = REGULATORY_MINIMUMS.get(entity_type)
        if regulatory is not None and regulatory > effective:
            effective = regulatory

        if user_id is not None:
            preference = await self._preference_repository.find_user_preference(
                entity_type, user_id
            )
            if preference is not None and preference.retention_period > effective:
                effective = preference.retention_period

        return effective

    async def calculate_hard_delete_date(
        self,
        entity_type: DeletableEntityType,
        deleted_at: datetime,
        user_id: uuid.UUID | None = None,
    ) -> datetime:
        """Returns deleted_at + get_effective_retention(entity_type, user_id)."""
        retention = await self.get_effective_retention(entity_type, user_id)
        return retention.expiration_from(deleted_at)

    async def set_user_preference(
        self,
        entity_type: DeletableEntityType,
        user_id: uuid.UUID,
        period: RetentionPeriod,
    ) -> None:
        """Set user preference. Validates period >= platform default."""
        platform_default = DEFAULT_RETENTION[entity_type]
        if period < platform_default:
            raise BelowPlatformDefaultError(
                f"Retention period {period} is below platform default "
                f"{platform_default} for {entity_type.value}"
            )
        preference = UserRetentionPreference(
            user_id=user_id,
            entity_type=entity_type,
            retention_period=period,
        )
        await self._preference_repository.save_user_preference(preference)

    def get_cooling_off_period(self, entity_type: DeletableEntityType) -> RetentionPeriod | None:
        """Returns the cooling-off period for the entity type, or None if no cooling-off."""
        return COOLING_OFF_PERIODS.get(entity_type)
