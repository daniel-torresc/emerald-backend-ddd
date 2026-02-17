from __future__ import annotations

import uuid
from datetime import UTC, datetime

from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidPendingStateError,
)
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)
from emerald.shared_kernel.domain.models.base.entity import Entity

_CREATION_STATUSES = frozenset({MatchStatus.NEW, MatchStatus.DUPLICATE, MatchStatus.NEEDS_REVIEW})


class PendingTransaction(Entity):
    """Ephemeral staging entity for imported transactions awaiting dedup or user review."""

    def __init__(
        self,
        *,
        connection_id: uuid.UUID,
        sync_id: uuid.UUID,
        account_id: uuid.UUID,
        external_id: str,
        raw_data: str,
        normalized: NormalizedTransaction,
        match_status: MatchStatus,
        matched_transaction_id: uuid.UUID | None = None,
        imported_transaction_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
        id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(id=id)
        self._connection_id = connection_id
        self._sync_id = sync_id
        self._account_id = account_id
        self._external_id = external_id
        self._raw_data = raw_data
        self._normalized = normalized
        self.match_status = match_status
        self.matched_transaction_id = matched_transaction_id
        self.imported_transaction_id = imported_transaction_id
        self._created_at = created_at if created_at is not None else datetime.now(UTC)

    @property
    def connection_id(self) -> uuid.UUID:
        return self._connection_id

    @property
    def sync_id(self) -> uuid.UUID:
        return self._sync_id

    @property
    def account_id(self) -> uuid.UUID:
        return self._account_id

    @property
    def external_id(self) -> str:
        return self._external_id

    @property
    def raw_data(self) -> str:
        return self._raw_data

    @property
    def normalized(self) -> NormalizedTransaction:
        return self._normalized

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @classmethod
    def create(
        cls,
        *,
        connection_id: uuid.UUID,
        sync_id: uuid.UUID,
        account_id: uuid.UUID,
        external_id: str,
        raw_data: str,
        normalized: NormalizedTransaction,
        match_status: MatchStatus,
        matched_transaction_id: uuid.UUID | None = None,
    ) -> PendingTransaction:
        """Create a new pending transaction with validated initial match status."""
        if match_status not in _CREATION_STATUSES:
            raise InvalidPendingStateError(
                f"Initial match_status must be NEW, DUPLICATE, or NEEDS_REVIEW, got {match_status}"
            )
        return cls(
            connection_id=connection_id,
            sync_id=sync_id,
            account_id=account_id,
            external_id=external_id,
            raw_data=raw_data,
            normalized=normalized,
            match_status=match_status,
            matched_transaction_id=matched_transaction_id,
        )

    def approve(self) -> None:
        """Approve a NEEDS_REVIEW pending transaction."""
        if self.match_status != MatchStatus.NEEDS_REVIEW:
            raise InvalidPendingStateError(
                f"Can only approve NEEDS_REVIEW items, got {self.match_status}"
            )
        self.match_status = MatchStatus.USER_APPROVED

    def reject(self) -> None:
        """Reject a NEEDS_REVIEW pending transaction."""
        if self.match_status != MatchStatus.NEEDS_REVIEW:
            raise InvalidPendingStateError(
                f"Can only reject NEEDS_REVIEW items, got {self.match_status}"
            )
        self.match_status = MatchStatus.USER_REJECTED

    def mark_imported(self, transaction_id: uuid.UUID) -> None:
        """Mark as imported with the created transaction ID."""
        if self.match_status not in (MatchStatus.NEW, MatchStatus.USER_APPROVED):
            raise InvalidPendingStateError(
                f"Can only mark NEW or USER_APPROVED as imported, got {self.match_status}"
            )
        self.imported_transaction_id = transaction_id

    def is_importable(self) -> bool:
        """Whether this pending transaction can be imported."""
        return (
            self.match_status in (MatchStatus.NEW, MatchStatus.USER_APPROVED)
            and self.imported_transaction_id is None
        )
