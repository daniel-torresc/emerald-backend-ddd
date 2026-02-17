"""Tests for bank connection domain events."""

import uuid
from datetime import UTC, datetime

from emerald.integrations.domain.events.base import BankConnectionEvent
from emerald.integrations.domain.events.connection_events import (
    BankConnectionActivated,
    BankConnectionDisconnected,
    BankConnectionErrored,
    BankConnectionInitiated,
    BankConnectionNeedsReauth,
    BankConnectionReconnected,
    BankConnectionSoftDeleted,
    BankSyncCompleted,
    BankSyncFailed,
    BankSyncStarted,
    PendingTransactionApproved,
    PendingTransactionRejected,
    TransactionsImported,
)
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


class TestBankConnectionEventBase:
    """Tests for BankConnectionEvent base class."""

    def test_aggregate_type_is_bank_connection(self) -> None:
        assert BankConnectionEvent.aggregate_type == "bank_connection"

    def test_extends_domain_event(self) -> None:
        assert issubclass(BankConnectionEvent, DomainEvent)

    def test_can_instantiate_with_aggregate_id(self) -> None:
        agg_id = uuid.uuid4()
        event = BankConnectionActivated(aggregate_id=agg_id)
        assert event.aggregate_id == agg_id

    def test_event_id_is_auto_generated(self) -> None:
        event = BankConnectionActivated(aggregate_id=uuid.uuid4())
        assert isinstance(event.event_id, uuid.UUID)

    def test_occurred_at_is_set_automatically(self) -> None:
        before = datetime.now(UTC)
        event = BankConnectionActivated(aggregate_id=uuid.uuid4())
        after = datetime.now(UTC)
        assert before <= event.occurred_at <= after


class TestBankConnectionInitiated:
    """Tests for BankConnectionInitiated event."""

    def test_has_correct_aggregate_type(self) -> None:
        assert BankConnectionInitiated.aggregate_type == "bank_connection"

    def test_stores_all_fields(self) -> None:
        agg_id = uuid.uuid4()
        user_id = uuid.uuid4()
        account_id = uuid.uuid4()
        event = BankConnectionInitiated(
            aggregate_id=agg_id,
            user_id=user_id,
            provider_name="plaid",
            account_id=account_id,
        )
        assert event.aggregate_id == agg_id
        assert event.user_id == user_id
        assert event.provider_name == "plaid"
        assert event.account_id == account_id

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankConnectionInitiated, BankConnectionEvent)


class TestBankConnectionActivated:
    """Tests for BankConnectionActivated event."""

    def test_has_correct_aggregate_type(self) -> None:
        assert BankConnectionActivated.aggregate_type == "bank_connection"

    def test_can_instantiate_with_aggregate_id_only(self) -> None:
        agg_id = uuid.uuid4()
        event = BankConnectionActivated(aggregate_id=agg_id)
        assert event.aggregate_id == agg_id

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankConnectionActivated, BankConnectionEvent)


class TestBankConnectionNeedsReauth:
    """Tests for BankConnectionNeedsReauth event."""

    def test_stores_user_id(self) -> None:
        user_id = uuid.uuid4()
        event = BankConnectionNeedsReauth(
            aggregate_id=uuid.uuid4(),
            user_id=user_id,
        )
        assert event.user_id == user_id

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankConnectionNeedsReauth, BankConnectionEvent)


class TestBankConnectionErrored:
    """Tests for BankConnectionErrored event."""

    def test_stores_error_details(self) -> None:
        event = BankConnectionErrored(
            aggregate_id=uuid.uuid4(),
            last_error="connection timeout",
            consecutive_failures=3,
        )
        assert event.last_error == "connection timeout"
        assert event.consecutive_failures == 3

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankConnectionErrored, BankConnectionEvent)


class TestBankConnectionDisconnected:
    """Tests for BankConnectionDisconnected event."""

    def test_stores_disconnected_by(self) -> None:
        user_id = uuid.uuid4()
        event = BankConnectionDisconnected(
            aggregate_id=uuid.uuid4(),
            disconnected_by=user_id,
        )
        assert event.disconnected_by == user_id

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankConnectionDisconnected, BankConnectionEvent)


class TestBankConnectionReconnected:
    """Tests for BankConnectionReconnected event."""

    def test_can_instantiate(self) -> None:
        agg_id = uuid.uuid4()
        event = BankConnectionReconnected(aggregate_id=agg_id)
        assert event.aggregate_id == agg_id

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankConnectionReconnected, BankConnectionEvent)


class TestBankConnectionSoftDeleted:
    """Tests for BankConnectionSoftDeleted event."""

    def test_stores_deleted_by(self) -> None:
        user_id = uuid.uuid4()
        event = BankConnectionSoftDeleted(
            aggregate_id=uuid.uuid4(),
            deleted_by=user_id,
        )
        assert event.deleted_by == user_id

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankConnectionSoftDeleted, BankConnectionEvent)


class TestBankSyncStarted:
    """Tests for BankSyncStarted event."""

    def test_stores_sync_id(self) -> None:
        sync_id = uuid.uuid4()
        event = BankSyncStarted(
            aggregate_id=uuid.uuid4(),
            sync_id=sync_id,
        )
        assert event.sync_id == sync_id

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankSyncStarted, BankConnectionEvent)


class TestBankSyncCompleted:
    """Tests for BankSyncCompleted event."""

    def test_stores_all_count_fields(self) -> None:
        sync_id = uuid.uuid4()
        event = BankSyncCompleted(
            aggregate_id=uuid.uuid4(),
            sync_id=sync_id,
            transactions_found=10,
            transactions_imported=7,
            transactions_duplicate=2,
            transactions_staged=1,
        )
        assert event.sync_id == sync_id
        assert event.transactions_found == 10
        assert event.transactions_imported == 7
        assert event.transactions_duplicate == 2
        assert event.transactions_staged == 1

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankSyncCompleted, BankConnectionEvent)


class TestBankSyncFailed:
    """Tests for BankSyncFailed event."""

    def test_stores_sync_id_and_error(self) -> None:
        sync_id = uuid.uuid4()
        event = BankSyncFailed(
            aggregate_id=uuid.uuid4(),
            sync_id=sync_id,
            error="provider unreachable",
        )
        assert event.sync_id == sync_id
        assert event.error == "provider unreachable"

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(BankSyncFailed, BankConnectionEvent)


class TestTransactionsImported:
    """Tests for TransactionsImported event."""

    def test_stores_account_and_count(self) -> None:
        account_id = uuid.uuid4()
        event = TransactionsImported(
            aggregate_id=uuid.uuid4(),
            account_id=account_id,
            count=15,
        )
        assert event.account_id == account_id
        assert event.count == 15

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(TransactionsImported, BankConnectionEvent)


class TestPendingTransactionApproved:
    """Tests for PendingTransactionApproved event."""

    def test_stores_pending_and_transaction_ids(self) -> None:
        pending_id = uuid.uuid4()
        txn_id = uuid.uuid4()
        event = PendingTransactionApproved(
            aggregate_id=uuid.uuid4(),
            pending_id=pending_id,
            transaction_id=txn_id,
        )
        assert event.pending_id == pending_id
        assert event.transaction_id == txn_id

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(PendingTransactionApproved, BankConnectionEvent)


class TestPendingTransactionRejected:
    """Tests for PendingTransactionRejected event."""

    def test_stores_pending_id(self) -> None:
        pending_id = uuid.uuid4()
        event = PendingTransactionRejected(
            aggregate_id=uuid.uuid4(),
            pending_id=pending_id,
        )
        assert event.pending_id == pending_id

    def test_extends_bank_connection_event(self) -> None:
        assert issubclass(PendingTransactionRejected, BankConnectionEvent)


class TestAllEventsAreFrozen:
    """Verify all events are immutable frozen dataclasses."""

    ALL_EVENT_CLASSES = [
        BankConnectionInitiated,
        BankConnectionActivated,
        BankConnectionNeedsReauth,
        BankConnectionErrored,
        BankConnectionDisconnected,
        BankConnectionReconnected,
        BankConnectionSoftDeleted,
        BankSyncStarted,
        BankSyncCompleted,
        BankSyncFailed,
        TransactionsImported,
        PendingTransactionApproved,
        PendingTransactionRejected,
    ]

    def test_exactly_13_event_classes(self) -> None:
        assert len(self.ALL_EVENT_CLASSES) == 13

    def test_all_extend_bank_connection_event(self) -> None:
        for cls in self.ALL_EVENT_CLASSES:
            assert issubclass(cls, BankConnectionEvent), (
                f"{cls.__name__} must extend BankConnectionEvent"
            )

    def test_all_have_bank_connection_aggregate_type(self) -> None:
        for cls in self.ALL_EVENT_CLASSES:
            assert cls.aggregate_type == "bank_connection", (
                f"{cls.__name__}.aggregate_type should be 'bank_connection'"
            )
