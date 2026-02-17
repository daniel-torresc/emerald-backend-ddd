from __future__ import annotations

import uuid
from datetime import UTC, datetime

from emerald.shared_kernel.domain.models.base.entity import Entity

_NIL_UUID = uuid.UUID(int=0)


class TransactionTermAssignment(Entity):
    """Links a transaction to a taxonomy term. Immutable after creation."""

    def __init__(
        self,
        *,
        transaction_id: uuid.UUID,
        term_id: uuid.UUID,
        taxonomy_id: uuid.UUID,
        assigned_at: datetime,
        assigned_by: uuid.UUID,
        id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(id=id)
        self._validate_non_nil(transaction_id, "transaction_id")
        self._validate_non_nil(term_id, "term_id")
        self._validate_non_nil(taxonomy_id, "taxonomy_id")
        self._validate_non_nil(assigned_by, "assigned_by")
        if assigned_at.tzinfo is None:
            msg = "assigned_at must be timezone-aware"
            raise ValueError(msg)
        self._transaction_id = transaction_id
        self._term_id = term_id
        self._taxonomy_id = taxonomy_id
        self._assigned_at = assigned_at
        self._assigned_by = assigned_by

    @staticmethod
    def _validate_non_nil(value: uuid.UUID, name: str) -> None:
        if value == _NIL_UUID:
            msg = f"{name} must not be nil UUID"
            raise ValueError(msg)

    @classmethod
    def create(
        cls,
        *,
        transaction_id: uuid.UUID,
        term_id: uuid.UUID,
        taxonomy_id: uuid.UUID,
        assigned_by: uuid.UUID,
    ) -> TransactionTermAssignment:
        return cls(
            transaction_id=transaction_id,
            term_id=term_id,
            taxonomy_id=taxonomy_id,
            assigned_at=datetime.now(UTC),
            assigned_by=assigned_by,
        )

    @property
    def transaction_id(self) -> uuid.UUID:
        return self._transaction_id

    @property
    def term_id(self) -> uuid.UUID:
        return self._term_id

    @property
    def taxonomy_id(self) -> uuid.UUID:
        return self._taxonomy_id

    @property
    def assigned_at(self) -> datetime:
        return self._assigned_at

    @property
    def assigned_by(self) -> uuid.UUID:
        return self._assigned_by
