from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from emerald.integrations.domain.exceptions.connection_exceptions import (
    SyncAlreadyCompletedError,
)
from emerald.integrations.domain.models.value_objects.sync_result import SyncResult
from emerald.integrations.domain.models.value_objects.sync_status import SyncStatus
from emerald.shared_kernel.domain.models.base.entity import Entity
from emerald.shared_kernel.domain.models.base.timestamped import TimestampedMixin


class SyncHistory(TimestampedMixin, Entity):
    """Record of a single sync execution attempt. Immutable after completion."""

    def __init__(
        self,
        *,
        connection_id: uuid.UUID,
        status: SyncStatus,
        started_at: datetime,
        completed_at: datetime | None = None,
        transactions_found: int = 0,
        transactions_imported: int = 0,
        transactions_duplicate: int = 0,
        transactions_staged: int = 0,
        error_message: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._connection_id = connection_id
        self.status = status
        self._started_at = started_at
        self.completed_at = completed_at
        self.transactions_found = transactions_found
        self.transactions_imported = transactions_imported
        self.transactions_duplicate = transactions_duplicate
        self.transactions_staged = transactions_staged
        self.error_message = error_message

    @property
    def connection_id(self) -> uuid.UUID:
        return self._connection_id

    @property
    def started_at(self) -> datetime:
        return self._started_at

    @classmethod
    def create(cls, connection_id: uuid.UUID) -> SyncHistory:
        """Create a new in-progress sync history record."""
        now = datetime.now(UTC)
        return cls(
            connection_id=connection_id,
            status=SyncStatus.IN_PROGRESS,
            started_at=now,
            created_at=now,
        )

    def complete(self, result: SyncResult) -> None:
        """Mark sync as completed with result counts."""
        if self.status != SyncStatus.IN_PROGRESS:
            raise SyncAlreadyCompletedError()
        self.status = SyncStatus.PARTIAL if result.transactions_staged > 0 else SyncStatus.SUCCESS
        self.completed_at = datetime.now(UTC)
        self.transactions_found = result.transactions_found
        self.transactions_imported = result.transactions_imported
        self.transactions_duplicate = result.transactions_duplicate
        self.transactions_staged = result.transactions_staged

    def fail(self, error_message: str) -> None:
        """Mark sync as failed."""
        if self.status != SyncStatus.IN_PROGRESS:
            raise SyncAlreadyCompletedError()
        self.status = SyncStatus.FAILED
        self.completed_at = datetime.now(UTC)
        self.error_message = error_message
