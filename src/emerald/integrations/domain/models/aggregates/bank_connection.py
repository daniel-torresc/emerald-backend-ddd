from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from emerald.integrations.domain.constants import (
    DEFAULT_SYNC_FREQUENCY_HOURS,
    MAX_CONSECUTIVE_FAILURES,
    MAX_SYNC_FREQUENCY_HOURS,
    MIN_SYNC_FREQUENCY_HOURS,
    RETRY_BASE_MINUTES,
    RETRY_MAX_MINUTES,
)
from emerald.integrations.domain.events.connection_events import (
    BankConnectionActivated,
    BankConnectionDisconnected,
    BankConnectionErrored,
    BankConnectionInitiated,
    BankConnectionNeedsReauth,
    BankConnectionReconnected,
    BankConnectionSoftDeleted,
)
from emerald.integrations.domain.exceptions.connection_exceptions import (
    ConnectionNotActiveError,
    InvalidConnectionStateError,
    InvalidSyncFrequencyError,
)
from emerald.integrations.domain.models.value_objects.connection_status import ConnectionStatus
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName
from emerald.shared_kernel.domain.models.base.aggregate_root import AggregateRoot
from emerald.shared_kernel.domain.models.base.auditable import AuditableMixin
from emerald.shared_kernel.domain.models.base.soft_deletable import SoftDeletableMixin
from emerald.shared_kernel.domain.models.value_objects.retention_period import RetentionPeriod


class BankConnection(SoftDeletableMixin, AuditableMixin, AggregateRoot):
    """Aggregate root for bank connection lifecycle and sync scheduling."""

    def __init__(
        self,
        *,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        provider_name: ProviderName,
        external_account_id: str,
        institution_id: str,
        status: ConnectionStatus = ConnectionStatus.PENDING,
        credentials: ProviderCredentials | None = None,
        last_sync_at: datetime | None = None,
        last_sync_error: str | None = None,
        next_sync_scheduled_at: datetime | None = None,
        sync_frequency_hours: int = DEFAULT_SYNC_FREQUENCY_HOURS,
        consecutive_failures: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._user_id = user_id
        self._account_id = account_id
        self._provider_name = provider_name
        self._external_account_id = external_account_id
        self._institution_id = institution_id
        self.status = status
        self.credentials = credentials
        self.last_sync_at = last_sync_at
        self.last_sync_error = last_sync_error
        self.next_sync_scheduled_at = next_sync_scheduled_at
        self.sync_frequency_hours = sync_frequency_hours
        self.consecutive_failures = consecutive_failures

    # -- Immutable properties --------------------------------------------------

    @property
    def user_id(self) -> uuid.UUID:
        return self._user_id

    @property
    def account_id(self) -> uuid.UUID:
        return self._account_id

    @property
    def provider_name(self) -> ProviderName:
        return self._provider_name

    @property
    def external_account_id(self) -> str:
        return self._external_account_id

    @property
    def institution_id(self) -> str:
        return self._institution_id

    # -- Factory ---------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        provider_name: ProviderName,
        institution_id: str,
        external_account_id: str,
        created_by: uuid.UUID,
    ) -> BankConnection:
        """Create a new bank connection in PENDING status."""
        connection_id = uuid.uuid4()
        connection = cls(
            user_id=user_id,
            account_id=account_id,
            provider_name=provider_name,
            institution_id=institution_id,
            external_account_id=external_account_id,
            status=ConnectionStatus.PENDING,
            id=connection_id,
            created_by=created_by,
            version=1,
        )
        connection._register_event(
            BankConnectionInitiated(
                aggregate_id=connection_id,
                user_id=user_id,
                provider_name=provider_name.value,
                account_id=account_id,
            )
        )
        return connection

    # -- Activation ------------------------------------------------------------

    def activate(self, credentials: ProviderCredentials) -> None:
        """Activate the connection with provider credentials."""
        if self.status not in (ConnectionStatus.PENDING, ConnectionStatus.NEEDS_REAUTH):
            raise InvalidConnectionStateError(
                f"Cannot activate from {self.status} — expected PENDING or NEEDS_REAUTH"
            )
        self.status = ConnectionStatus.ACTIVE
        self.credentials = credentials
        self.consecutive_failures = 0
        self.next_sync_scheduled_at = datetime.now(UTC)
        self._touch()
        self._register_event(BankConnectionActivated(aggregate_id=self.id))

    # -- Sync lifecycle --------------------------------------------------------

    def record_sync_success(self, synced_at: datetime) -> None:
        """Record a successful sync."""
        if self.status != ConnectionStatus.ACTIVE:
            raise ConnectionNotActiveError()
        self.last_sync_at = synced_at
        self.last_sync_error = None
        self.consecutive_failures = 0
        self.next_sync_scheduled_at = synced_at + timedelta(hours=self.sync_frequency_hours)
        self._touch()

    def record_sync_failure(self, error: str) -> None:
        """Record a failed sync, potentially transitioning to ERROR."""
        if self.status != ConnectionStatus.ACTIVE:
            raise ConnectionNotActiveError()
        self.last_sync_error = error
        self.consecutive_failures += 1
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            self.status = ConnectionStatus.ERROR
            self.next_sync_scheduled_at = None
            self._touch()
            self._register_event(
                BankConnectionErrored(
                    aggregate_id=self.id,
                    last_error=error,
                    consecutive_failures=self.consecutive_failures,
                )
            )
        else:
            self.next_sync_scheduled_at = self.calculate_next_retry(self.consecutive_failures)
            self._touch()

    # -- Status transitions ----------------------------------------------------

    def mark_needs_reauth(self) -> None:
        """Transition ACTIVE → NEEDS_REAUTH."""
        if self.status != ConnectionStatus.ACTIVE:
            raise InvalidConnectionStateError(
                f"Cannot mark needs_reauth from {self.status} — expected ACTIVE"
            )
        self.status = ConnectionStatus.NEEDS_REAUTH
        self.credentials = None
        self.next_sync_scheduled_at = None
        self._touch()
        self._register_event(BankConnectionNeedsReauth(aggregate_id=self.id, user_id=self._user_id))

    def disconnect(self, disconnected_by: uuid.UUID) -> None:
        """Disconnect the bank connection (terminal state)."""
        if self.status == ConnectionStatus.DISCONNECTED:
            raise InvalidConnectionStateError("Connection is already disconnected")
        if self.is_deleted():
            raise InvalidConnectionStateError("Cannot disconnect a deleted connection")
        self.status = ConnectionStatus.DISCONNECTED
        self.credentials = None
        self.next_sync_scheduled_at = None
        self._touch()
        self._set_updated_by(disconnected_by)
        self._register_event(
            BankConnectionDisconnected(aggregate_id=self.id, disconnected_by=disconnected_by)
        )

    def reconnect(self, credentials: ProviderCredentials) -> None:
        """Reconnect from NEEDS_REAUTH or ERROR."""
        if self.status not in (ConnectionStatus.NEEDS_REAUTH, ConnectionStatus.ERROR):
            raise InvalidConnectionStateError(
                f"Cannot reconnect from {self.status} — expected NEEDS_REAUTH or ERROR"
            )
        self.status = ConnectionStatus.ACTIVE
        self.credentials = credentials
        self.consecutive_failures = 0
        self.next_sync_scheduled_at = datetime.now(UTC)
        self._touch()
        self._register_event(BankConnectionReconnected(aggregate_id=self.id))

    # -- Configuration ---------------------------------------------------------

    def update_sync_frequency(self, hours: int) -> None:
        """Update sync frequency, recalculating next sync if ACTIVE."""
        if hours < MIN_SYNC_FREQUENCY_HOURS or hours > MAX_SYNC_FREQUENCY_HOURS:
            raise InvalidSyncFrequencyError(
                f"Sync frequency must be between {MIN_SYNC_FREQUENCY_HOURS} "
                f"and {MAX_SYNC_FREQUENCY_HOURS} hours, got {hours}"
            )
        self.sync_frequency_hours = hours
        if self.status == ConnectionStatus.ACTIVE and self.last_sync_at is not None:
            self.next_sync_scheduled_at = self.last_sync_at + timedelta(hours=hours)
        self._touch()

    # -- Lifecycle (soft delete) -----------------------------------------------

    def soft_delete(
        self,
        deleted_by: uuid.UUID,
        retention: RetentionPeriod,
        reason: str | None = None,
    ) -> None:
        """Disconnect first if needed, then soft delete."""
        if self.status != ConnectionStatus.DISCONNECTED:
            self.status = ConnectionStatus.DISCONNECTED
            self.credentials = None
            self.next_sync_scheduled_at = None
        super().soft_delete(deleted_by=deleted_by, retention=retention, reason=reason)
        self._touch()
        self._register_event(BankConnectionSoftDeleted(aggregate_id=self.id, deleted_by=deleted_by))

    # -- Query helpers ---------------------------------------------------------

    def is_syncable(self) -> bool:
        """Whether this connection can execute a sync."""
        return self.status == ConnectionStatus.ACTIVE and not self.is_deleted()

    @staticmethod
    def calculate_next_retry(current_failures: int) -> datetime:
        """Calculate next retry with exponential backoff."""
        backoff_minutes = min(
            RETRY_BASE_MINUTES * (2 ** (current_failures - 1)),
            RETRY_MAX_MINUTES,
        )
        return datetime.now(UTC) + timedelta(minutes=backoff_minutes)
