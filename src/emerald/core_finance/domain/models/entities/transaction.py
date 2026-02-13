from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from emerald.core_finance.domain.constants import (
    MAX_COMMENTS_LENGTH,
    MAX_MERCHANT_LENGTH,
    MAX_ORIGINAL_DESCRIPTION_LENGTH,
    MAX_USER_DESCRIPTION_LENGTH,
)
from emerald.core_finance.domain.events.transaction_events import (
    TransactionRecovered,
    TransactionReviewed,
    TransactionSoftDeleted,
    TransactionUpdated,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    EmptyDescriptionError,
    InvalidCommentsError,
    InvalidMerchantError,
)
from emerald.core_finance.domain.models.value_objects.import_source import ImportSource
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus
from emerald.shared_kernel.domain.events.domain_event import DomainEvent
from emerald.shared_kernel.domain.models.base.auditable import AuditableMixin
from emerald.shared_kernel.domain.models.base.entity import Entity
from emerald.shared_kernel.domain.models.base.soft_deletable import SoftDeletableMixin
from emerald.shared_kernel.domain.models.base.timestamped import TimestampedMixin
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.retention_period import RetentionPeriod

_SENTINEL = object()


class Transaction(SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity):
    """A single financial activity (debit or credit) recorded against an account."""

    def __init__(
        self,
        *,
        account_id: uuid.UUID,
        transaction_date: date,
        amount: Money,
        original_description: str,
        import_source: ImportSource,
        value_date: date | None = None,
        user_description: str | None = None,
        merchant: str | None = None,
        comments: str | None = None,
        review_status: ReviewStatus = ReviewStatus.TO_REVIEW,
        card_id: uuid.UUID | None = None,
        parent_transaction_id: uuid.UUID | None = None,
        external_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._account_id = account_id
        self.transaction_date = transaction_date
        self.amount = amount
        self._original_description = original_description
        self._import_source = import_source
        self.value_date = value_date
        self.user_description = user_description
        self.merchant = merchant
        self.comments = comments
        self.review_status = review_status
        self.card_id = card_id
        self._parent_transaction_id = parent_transaction_id
        self._external_id = external_id
        self._events: list[DomainEvent] = []

    # -- Immutable properties --------------------------------------------------

    @property
    def account_id(self) -> uuid.UUID:
        return self._account_id

    @property
    def original_description(self) -> str:
        return self._original_description

    @property
    def import_source(self) -> ImportSource:
        return self._import_source

    @property
    def external_id(self) -> str | None:
        return self._external_id

    @property
    def parent_transaction_id(self) -> uuid.UUID | None:
        return self._parent_transaction_id

    # -- Computed properties ---------------------------------------------------

    @property
    def effective_description(self) -> str:
        if self.user_description is not None:
            return self.user_description
        return self._original_description

    # -- Factory ---------------------------------------------------------------

    @classmethod
    def create(
        cls,
        account_id: uuid.UUID,
        transaction_date: date,
        amount: Money,
        original_description: str,
        created_by: uuid.UUID,
        import_source: ImportSource,
        value_date: date | None = None,
        merchant: str | None = None,
        comments: str | None = None,
        external_id: str | None = None,
        parent_transaction_id: uuid.UUID | None = None,
        card_id: uuid.UUID | None = None,
    ) -> Transaction:
        """Create a new Transaction with all invariants validated."""
        original_description = cls._validate_string(
            original_description,
            "original_description",
            MAX_ORIGINAL_DESCRIPTION_LENGTH,
            EmptyDescriptionError,
        )
        if merchant is not None:
            merchant = cls._validate_string(
                merchant, "merchant", MAX_MERCHANT_LENGTH, InvalidMerchantError
            )
        if comments is not None:
            comments = cls._validate_string(
                comments, "comments", MAX_COMMENTS_LENGTH, InvalidCommentsError
            )

        return cls(
            id=uuid.uuid4(),
            account_id=account_id,
            transaction_date=transaction_date,
            amount=amount,
            original_description=original_description,
            import_source=import_source,
            value_date=value_date,
            user_description=None,
            merchant=merchant,
            comments=comments,
            review_status=ReviewStatus.TO_REVIEW,
            card_id=card_id,
            parent_transaction_id=parent_transaction_id,
            external_id=external_id,
            created_by=created_by,
        )

    # -- Update methods --------------------------------------------------------

    def update_description(self, user_description: str | None, updated_by: uuid.UUID) -> None:
        """Update the user description overlay. Pass None to clear."""
        if user_description is not None:
            user_description = self._validate_string(
                user_description,
                "user_description",
                MAX_USER_DESCRIPTION_LENGTH,
                EmptyDescriptionError,
            )
        self.user_description = user_description
        self._set_updated_by(updated_by)
        self._touch()
        self._register_event(
            TransactionUpdated(
                aggregate_id=self.id,
                account_id=self._account_id,
                updated_by=updated_by,
                changed_fields=frozenset({"user_description"}),
            )
        )

    def update_merchant(self, merchant: str | None, updated_by: uuid.UUID) -> None:
        """Update the merchant name. Pass None to clear."""
        if merchant is not None:
            merchant = self._validate_string(
                merchant, "merchant", MAX_MERCHANT_LENGTH, InvalidMerchantError
            )
        self.merchant = merchant
        self._set_updated_by(updated_by)
        self._touch()
        self._register_event(
            TransactionUpdated(
                aggregate_id=self.id,
                account_id=self._account_id,
                updated_by=updated_by,
                changed_fields=frozenset({"merchant"}),
            )
        )

    def update_comments(self, comments: str | None, updated_by: uuid.UUID) -> None:
        """Update user comments. Pass None to clear."""
        if comments is not None:
            comments = self._validate_string(
                comments, "comments", MAX_COMMENTS_LENGTH, InvalidCommentsError
            )
        self.comments = comments
        self._set_updated_by(updated_by)
        self._touch()
        self._register_event(
            TransactionUpdated(
                aggregate_id=self.id,
                account_id=self._account_id,
                updated_by=updated_by,
                changed_fields=frozenset({"comments"}),
            )
        )

    def update_dates(
        self,
        updated_by: uuid.UUID,
        transaction_date: date | None = None,
        value_date: object = _SENTINEL,
    ) -> None:
        """Update transaction_date and/or value_date. Uses sentinel for value_date."""
        changed: set[str] = set()
        if transaction_date is not None and transaction_date != self.transaction_date:
            self.transaction_date = transaction_date
            changed.add("transaction_date")
        if value_date is not _SENTINEL and value_date != self.value_date:
            self.value_date = value_date
            changed.add("value_date")
        if changed:
            self._set_updated_by(updated_by)
            self._touch()
            self._register_event(
                TransactionUpdated(
                    aggregate_id=self.id,
                    account_id=self._account_id,
                    updated_by=updated_by,
                    changed_fields=frozenset(changed),
                )
            )

    def update_amount(self, amount: Money, updated_by: uuid.UUID) -> None:
        """Update the transaction amount."""
        self.amount = amount
        self._set_updated_by(updated_by)
        self._touch()
        self._register_event(
            TransactionUpdated(
                aggregate_id=self.id,
                account_id=self._account_id,
                updated_by=updated_by,
                changed_fields=frozenset({"amount"}),
            )
        )

    # -- Review methods --------------------------------------------------------

    def mark_as_reviewed(self, reviewed_by: uuid.UUID) -> None:
        """Mark transaction as reviewed. Idempotent if already REVIEWED."""
        if self.review_status == ReviewStatus.REVIEWED:
            return
        self.review_status = ReviewStatus.REVIEWED
        self._set_updated_by(reviewed_by)
        self._touch()
        self._register_event(
            TransactionReviewed(
                aggregate_id=self.id,
                account_id=self._account_id,
                reviewed_by=reviewed_by,
            )
        )

    def mark_for_review(self, updated_by: uuid.UUID) -> None:
        """Mark transaction as needing review. Idempotent if already TO_REVIEW."""
        if self.review_status == ReviewStatus.TO_REVIEW:
            return
        self.review_status = ReviewStatus.TO_REVIEW
        self._set_updated_by(updated_by)
        self._touch()

    # -- Lifecycle overrides ---------------------------------------------------

    def soft_delete(
        self,
        deleted_by: uuid.UUID,
        retention: RetentionPeriod,
        reason: str | None = None,
    ) -> None:
        """Soft-delete the transaction."""
        super().soft_delete(deleted_by=deleted_by, retention=retention, reason=reason)
        self._register_event(
            TransactionSoftDeleted(
                aggregate_id=self.id,
                account_id=self._account_id,
                deleted_by=deleted_by,
            )
        )

    def recover(self) -> None:
        """Recover a soft-deleted transaction."""
        super().recover()
        self._register_event(
            TransactionRecovered(
                aggregate_id=self.id,
                account_id=self._account_id,
            )
        )

    # -- Stub methods (Spec 010) -----------------------------------------------

    def is_split_parent(self) -> bool:
        """Stub: returns False until Spec 010 implements splitting."""
        return False

    def is_split_child(self) -> bool:
        """Whether this transaction is a split child."""
        return self._parent_transaction_id is not None

    # -- Event collection ------------------------------------------------------

    def _register_event(self, event: DomainEvent) -> None:
        """Add an event to the internal collection."""
        self._events.append(event)

    def collect_events(self) -> list[DomainEvent]:
        """Return all accumulated events and clear the internal list."""
        events = list(self._events)
        self._events.clear()
        return events

    # -- Private helpers -------------------------------------------------------

    @staticmethod
    def _validate_string(
        value: str,
        field_name: str,
        max_length: int,
        error_class: type[Exception],
    ) -> str:
        """Validate and trim a string field."""
        trimmed = value.strip()
        if not trimmed:
            raise error_class(f"{field_name} cannot be empty")
        if len(trimmed) > max_length:
            raise error_class(f"{field_name} must not exceed {max_length} characters")
        return trimmed
