import uuid
from datetime import UTC, datetime
from typing import Any

from emerald.shared_kernel.domain.exceptions import AlreadyDeletedError, NotDeletedError
from emerald.shared_kernel.domain.models.value_objects.retention_period import RetentionPeriod


class SoftDeletableMixin:
    """Mixin providing soft-delete lifecycle with retention scheduling."""

    def __init__(self, **kwargs: Any) -> None:
        self.deleted_at: datetime | None = None
        self.deleted_by: uuid.UUID | None = None
        self.deletion_reason: str | None = None
        self.hard_delete_scheduled_at: datetime | None = None
        super().__init__(**kwargs)

    def soft_delete(
        self,
        deleted_by: uuid.UUID,
        retention: RetentionPeriod,
        reason: str | None = None,
    ) -> None:
        """Mark as soft deleted and schedule hard deletion."""
        if self.is_deleted():
            raise AlreadyDeletedError("Entity is already soft deleted")
        self.deleted_at = datetime.now(UTC)
        self.deleted_by = deleted_by
        self.deletion_reason = reason
        self.hard_delete_scheduled_at = retention.expiration_from(self.deleted_at)

    def recover(self) -> None:
        """Restore from soft-deleted state."""
        if not self.is_deleted():
            raise NotDeletedError("Entity is not soft deleted")
        self.deleted_at = None
        self.deleted_by = None
        self.deletion_reason = None
        self.hard_delete_scheduled_at = None

    def is_deleted(self) -> bool:
        """Whether entity is currently soft deleted."""
        return self.deleted_at is not None

    def is_active(self) -> bool:
        """Whether entity is active (not deleted)."""
        return not self.is_deleted()
