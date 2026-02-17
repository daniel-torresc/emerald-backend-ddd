"""Tests for BankConnection sync recording and retry logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from emerald.integrations.domain.events.connection_events import BankConnectionErrored
from emerald.integrations.domain.exceptions.connection_exceptions import (
    ConnectionNotActiveError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.value_objects.connection_status import ConnectionStatus
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName


def _make_connection(**overrides: Any) -> BankConnection:
    defaults: dict[str, Any] = {
        "user_id": uuid.uuid4(),
        "account_id": uuid.uuid4(),
        "provider_name": ProviderName("plaid"),
        "institution_id": "ins_123",
        "external_account_id": "ext_acc_123",
        "created_by": uuid.uuid4(),
    }
    defaults.update(overrides)
    created_by = defaults.pop("created_by")
    return BankConnection.create(**defaults, created_by=created_by)


def _activate_connection(conn: BankConnection) -> BankConnection:
    conn.collect_events()  # clear creation events
    conn.activate(ProviderCredentials("test-token"))
    conn.collect_events()  # clear activation events
    return conn


# ---------------------------------------------------------------------------
# record_sync_success()
# ---------------------------------------------------------------------------


class TestRecordSyncSuccess:
    """Tests for BankConnection.record_sync_success()."""

    def test_sets_last_sync_and_schedules_next(self) -> None:
        conn = _activate_connection(_make_connection())
        synced_at = datetime.now(UTC)

        conn.record_sync_success(synced_at)

        assert conn.last_sync_at == synced_at
        assert conn.last_sync_error is None
        assert conn.consecutive_failures == 0
        expected_next = synced_at + timedelta(hours=conn.sync_frequency_hours)
        assert conn.next_sync_scheduled_at == expected_next

    def test_clears_previous_error_and_resets_failures(self) -> None:
        conn = _activate_connection(_make_connection())
        # Build up some failure state
        conn.record_sync_failure("transient error")
        assert conn.consecutive_failures == 1
        assert conn.last_sync_error == "transient error"

        synced_at = datetime.now(UTC)
        conn.record_sync_success(synced_at)

        assert conn.last_sync_error is None
        assert conn.consecutive_failures == 0

    def test_from_non_active_raises_connection_not_active(self) -> None:
        conn = _make_connection()  # PENDING

        with pytest.raises(ConnectionNotActiveError):
            conn.record_sync_success(datetime.now(UTC))


# ---------------------------------------------------------------------------
# record_sync_failure()
# ---------------------------------------------------------------------------


class TestRecordSyncFailure:
    """Tests for BankConnection.record_sync_failure()."""

    def test_increments_consecutive_failures(self) -> None:
        conn = _activate_connection(_make_connection())

        conn.record_sync_failure("error 1")

        assert conn.consecutive_failures == 1
        assert conn.last_sync_error == "error 1"

    def test_at_one_failure_schedules_retry_stays_active(self) -> None:
        conn = _activate_connection(_make_connection())

        conn.record_sync_failure("error 1")

        assert conn.status == ConnectionStatus.ACTIVE
        assert conn.next_sync_scheduled_at is not None

    def test_at_two_failures_schedules_retry_stays_active(self) -> None:
        conn = _activate_connection(_make_connection())

        conn.record_sync_failure("error 1")
        conn.record_sync_failure("error 2")

        assert conn.status == ConnectionStatus.ACTIVE
        assert conn.consecutive_failures == 2
        assert conn.next_sync_scheduled_at is not None

    def test_at_three_failures_transitions_to_error(self) -> None:
        conn = _activate_connection(_make_connection())

        conn.record_sync_failure("error 1")
        conn.record_sync_failure("error 2")
        conn.record_sync_failure("error 3")

        assert conn.status == ConnectionStatus.ERROR
        assert conn.consecutive_failures == 3
        assert conn.next_sync_scheduled_at is None

    def test_at_three_failures_emits_bank_connection_errored(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.record_sync_failure("error 1")
        conn.record_sync_failure("error 2")
        conn.collect_events()

        conn.record_sync_failure("fatal error")
        events = conn.collect_events()

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, BankConnectionErrored)
        assert event.aggregate_id == conn.id
        assert event.last_error == "fatal error"
        assert event.consecutive_failures == 3

    def test_from_non_active_raises_connection_not_active(self) -> None:
        conn = _make_connection()  # PENDING

        with pytest.raises(ConnectionNotActiveError):
            conn.record_sync_failure("error")


# ---------------------------------------------------------------------------
# calculate_next_retry() - exponential backoff
# ---------------------------------------------------------------------------


class TestCalculateNextRetry:
    """Tests for BankConnection.calculate_next_retry() static method."""

    def test_first_failure_15_minutes(self) -> None:
        before = datetime.now(UTC)
        result = BankConnection.calculate_next_retry(1)
        after = datetime.now(UTC)

        # 15 minutes backoff for first failure (15 * 2^0 = 15)
        expected_min = before + timedelta(minutes=15)
        expected_max = after + timedelta(minutes=15)
        assert expected_min <= result <= expected_max

    def test_second_failure_30_minutes(self) -> None:
        before = datetime.now(UTC)
        result = BankConnection.calculate_next_retry(2)
        after = datetime.now(UTC)

        # 30 minutes backoff for second failure (15 * 2^1 = 30)
        expected_min = before + timedelta(minutes=30)
        expected_max = after + timedelta(minutes=30)
        assert expected_min <= result <= expected_max

    def test_third_failure_60_minutes(self) -> None:
        before = datetime.now(UTC)
        result = BankConnection.calculate_next_retry(3)
        after = datetime.now(UTC)

        # 60 minutes backoff for third failure (15 * 2^2 = 60)
        expected_min = before + timedelta(minutes=60)
        expected_max = after + timedelta(minutes=60)
        assert expected_min <= result <= expected_max

    def test_fourth_failure_capped_at_60_minutes(self) -> None:
        before = datetime.now(UTC)
        result = BankConnection.calculate_next_retry(4)
        after = datetime.now(UTC)

        # Capped at 60 minutes (15 * 2^3 = 120, but max is 60)
        expected_min = before + timedelta(minutes=60)
        expected_max = after + timedelta(minutes=60)
        assert expected_min <= result <= expected_max
