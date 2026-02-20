"""Tests for PendingTransaction entity."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidPendingStateError,
)
from emerald.integrations.domain.models.entities.pending_transaction import (
    PendingTransaction,
)
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)


def _make_normalized() -> NormalizedTransaction:
    return NormalizedTransaction(
        transaction_date=date(2024, 1, 15),
        amount=Decimal("-50.00"),
        currency_code="USD",
        description="Test transaction",
        external_id="ext_123",
    )


def _make_pending(
    *,
    match_status: MatchStatus = MatchStatus.NEW,
    matched_transaction_id: uuid.UUID | None = None,
) -> PendingTransaction:
    return PendingTransaction.create(
        connection_id=uuid.uuid4(),
        sync_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        external_id="ext_123",
        normalized=_make_normalized(),
        match_status=match_status,
        matched_transaction_id=matched_transaction_id,
    )


class TestPendingTransactionCreate:
    """Tests for PendingTransaction.create() factory."""

    def test_create_with_new_status(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEW)
        assert pt.match_status == MatchStatus.NEW

    def test_create_with_duplicate_status(self) -> None:
        pt = _make_pending(match_status=MatchStatus.DUPLICATE)
        assert pt.match_status == MatchStatus.DUPLICATE

    def test_create_with_needs_review_status(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        assert pt.match_status == MatchStatus.NEEDS_REVIEW

    def test_create_with_user_approved_raises_invalid_pending_state(self) -> None:
        with pytest.raises(InvalidPendingStateError):
            _make_pending(match_status=MatchStatus.USER_APPROVED)

    def test_create_with_user_rejected_raises_invalid_pending_state(self) -> None:
        with pytest.raises(InvalidPendingStateError):
            _make_pending(match_status=MatchStatus.USER_REJECTED)

    def test_create_stores_connection_id(self) -> None:
        conn_id = uuid.uuid4()
        pt = PendingTransaction.create(
            connection_id=conn_id,
            sync_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            external_id="ext_1",
            normalized=_make_normalized(),
            match_status=MatchStatus.NEW,
        )
        assert pt.connection_id == conn_id

    def test_create_stores_normalized_transaction(self) -> None:
        norm = _make_normalized()
        pt = PendingTransaction.create(
            connection_id=uuid.uuid4(),
            sync_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            external_id="ext_1",
            normalized=norm,
            match_status=MatchStatus.NEW,
        )
        assert pt.normalized == norm

    def test_create_imported_transaction_id_defaults_to_none(self) -> None:
        pt = _make_pending()
        assert pt.imported_transaction_id is None


class TestPendingTransactionApprove:
    """Tests for PendingTransaction.approve()."""

    def test_approve_from_needs_review_transitions_to_user_approved(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        pt.approve()
        assert pt.match_status == MatchStatus.USER_APPROVED

    def test_approve_from_new_raises_invalid_pending_state(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEW)
        with pytest.raises(InvalidPendingStateError):
            pt.approve()

    def test_approve_from_duplicate_raises_invalid_pending_state(self) -> None:
        pt = _make_pending(match_status=MatchStatus.DUPLICATE)
        with pytest.raises(InvalidPendingStateError):
            pt.approve()


class TestPendingTransactionReject:
    """Tests for PendingTransaction.reject()."""

    def test_reject_from_needs_review_transitions_to_user_rejected(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        pt.reject()
        assert pt.match_status == MatchStatus.USER_REJECTED

    def test_reject_from_new_raises_invalid_pending_state(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEW)
        with pytest.raises(InvalidPendingStateError):
            pt.reject()

    def test_reject_from_duplicate_raises_invalid_pending_state(self) -> None:
        pt = _make_pending(match_status=MatchStatus.DUPLICATE)
        with pytest.raises(InvalidPendingStateError):
            pt.reject()


class TestPendingTransactionMarkImported:
    """Tests for PendingTransaction.mark_imported()."""

    def test_mark_imported_from_new_sets_transaction_id(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEW)
        txn_id = uuid.uuid4()
        pt.mark_imported(txn_id)
        assert pt.imported_transaction_id == txn_id

    def test_mark_imported_from_user_approved_sets_transaction_id(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        pt.approve()
        txn_id = uuid.uuid4()
        pt.mark_imported(txn_id)
        assert pt.imported_transaction_id == txn_id

    def test_mark_imported_from_duplicate_raises_invalid_pending_state(self) -> None:
        pt = _make_pending(match_status=MatchStatus.DUPLICATE)
        with pytest.raises(InvalidPendingStateError):
            pt.mark_imported(uuid.uuid4())

    def test_mark_imported_from_needs_review_raises_invalid_pending_state(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        with pytest.raises(InvalidPendingStateError):
            pt.mark_imported(uuid.uuid4())

    def test_mark_imported_from_user_rejected_raises_invalid_pending_state(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        pt.reject()
        with pytest.raises(InvalidPendingStateError):
            pt.mark_imported(uuid.uuid4())


class TestPendingTransactionIsImportable:
    """Tests for PendingTransaction.is_importable()."""

    def test_is_importable_true_for_new_without_imported_id(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEW)
        assert pt.is_importable() is True

    def test_is_importable_false_for_new_with_imported_id(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEW)
        pt.mark_imported(uuid.uuid4())
        assert pt.is_importable() is False

    def test_is_importable_false_for_duplicate(self) -> None:
        pt = _make_pending(match_status=MatchStatus.DUPLICATE)
        assert pt.is_importable() is False

    def test_is_importable_true_for_user_approved_without_imported_id(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        pt.approve()
        assert pt.is_importable() is True

    def test_is_importable_false_for_user_approved_with_imported_id(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        pt.approve()
        pt.mark_imported(uuid.uuid4())
        assert pt.is_importable() is False

    def test_is_importable_false_for_needs_review(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        assert pt.is_importable() is False

    def test_is_importable_false_for_user_rejected(self) -> None:
        pt = _make_pending(match_status=MatchStatus.NEEDS_REVIEW)
        pt.reject()
        assert pt.is_importable() is False
