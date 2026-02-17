import uuid
from typing import Protocol

from emerald.integrations.domain.models.entities.sync_history import SyncHistory


class SyncHistoryRepository(Protocol):
    """Port for sync history persistence."""

    def save(self, history: SyncHistory) -> None: ...

    def find_by_id(self, sync_id: uuid.UUID) -> SyncHistory | None: ...

    def find_by_connection(
        self, connection_id: uuid.UUID, limit: int = 10
    ) -> list[SyncHistory]: ...

    def find_latest_by_connection(self, connection_id: uuid.UUID) -> SyncHistory | None: ...

    def find_in_progress_by_connection(self, connection_id: uuid.UUID) -> SyncHistory | None: ...
