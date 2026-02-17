"""Tests for BankConnection lifecycle state transitions."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from emerald.integrations.domain.events.connection_events import (
    BankConnectionActivated,
    BankConnectionDisconnected,
    BankConnectionNeedsReauth,
    BankConnectionReconnected,
    BankConnectionSoftDeleted,
)
from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidConnectionStateError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.value_objects.connection_status import ConnectionStatus
from emerald.integrations.domain.models.value_objects.provider_credentials import (
    ProviderCredentials,
)
from emerald.integrations.domain.models.value_objects.provider_name import ProviderName
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)


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


def _retention() -> RetentionPeriod:
    return RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)


# ---------------------------------------------------------------------------
# activate()
# ---------------------------------------------------------------------------


class TestActivate:
    """Tests for BankConnection.activate()."""

    def test_activate_from_pending_transitions_to_active(self) -> None:
        conn = _make_connection()
        conn.collect_events()

        conn.activate(ProviderCredentials("access-token"))

        assert conn.status == ConnectionStatus.ACTIVE
        assert conn.credentials == ProviderCredentials("access-token")
        assert conn.consecutive_failures == 0
        assert conn.next_sync_scheduled_at is not None

    def test_activate_emits_bank_connection_activated(self) -> None:
        conn = _make_connection()
        conn.collect_events()

        conn.activate(ProviderCredentials("access-token"))
        events = conn.collect_events()

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, BankConnectionActivated)
        assert event.aggregate_id == conn.id

    def test_activate_from_needs_reauth_transitions_to_active(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.mark_needs_reauth()
        conn.collect_events()

        conn.activate(ProviderCredentials("new-token"))

        assert conn.status == ConnectionStatus.ACTIVE
        assert conn.credentials == ProviderCredentials("new-token")

    def test_activate_from_active_raises_invalid_connection_state(self) -> None:
        conn = _activate_connection(_make_connection())

        with pytest.raises(InvalidConnectionStateError):
            conn.activate(ProviderCredentials("token"))

    def test_activate_from_error_raises_invalid_connection_state(self) -> None:
        conn = _activate_connection(_make_connection())
        # Drive to ERROR via 3 failures
        conn.record_sync_failure("fail1")
        conn.record_sync_failure("fail2")
        conn.record_sync_failure("fail3")
        assert conn.status == ConnectionStatus.ERROR
        conn.collect_events()

        with pytest.raises(InvalidConnectionStateError):
            conn.activate(ProviderCredentials("token"))

    def test_activate_from_disconnected_raises_invalid_connection_state(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.disconnect(uuid.uuid4())
        conn.collect_events()

        with pytest.raises(InvalidConnectionStateError):
            conn.activate(ProviderCredentials("token"))


# ---------------------------------------------------------------------------
# mark_needs_reauth()
# ---------------------------------------------------------------------------


class TestMarkNeedsReauth:
    """Tests for BankConnection.mark_needs_reauth()."""

    def test_mark_needs_reauth_transitions_to_needs_reauth(self) -> None:
        conn = _activate_connection(_make_connection())

        conn.mark_needs_reauth()

        assert conn.status == ConnectionStatus.NEEDS_REAUTH
        assert conn.credentials is None
        assert conn.next_sync_scheduled_at is None

    def test_mark_needs_reauth_emits_event_with_user_id(self) -> None:
        user_id = uuid.uuid4()
        conn = _activate_connection(_make_connection(user_id=user_id))

        conn.mark_needs_reauth()
        events = conn.collect_events()

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, BankConnectionNeedsReauth)
        assert event.aggregate_id == conn.id
        assert event.user_id == user_id

    def test_mark_needs_reauth_from_non_active_raises_error(self) -> None:
        conn = _make_connection()  # PENDING
        with pytest.raises(InvalidConnectionStateError):
            conn.mark_needs_reauth()


# ---------------------------------------------------------------------------
# disconnect()
# ---------------------------------------------------------------------------


class TestDisconnect:
    """Tests for BankConnection.disconnect()."""

    def test_disconnect_from_active_transitions_to_disconnected(self) -> None:
        conn = _activate_connection(_make_connection())
        disconnected_by = uuid.uuid4()

        conn.disconnect(disconnected_by)

        assert conn.status == ConnectionStatus.DISCONNECTED
        assert conn.credentials is None
        assert conn.next_sync_scheduled_at is None

    def test_disconnect_emits_event_with_disconnected_by(self) -> None:
        conn = _activate_connection(_make_connection())
        disconnected_by = uuid.uuid4()

        conn.disconnect(disconnected_by)
        events = conn.collect_events()

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, BankConnectionDisconnected)
        assert event.aggregate_id == conn.id
        assert event.disconnected_by == disconnected_by

    def test_disconnect_from_pending(self) -> None:
        conn = _make_connection()
        conn.collect_events()
        disconnected_by = uuid.uuid4()

        conn.disconnect(disconnected_by)

        assert conn.status == ConnectionStatus.DISCONNECTED

    def test_disconnect_from_needs_reauth(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.mark_needs_reauth()
        conn.collect_events()
        disconnected_by = uuid.uuid4()

        conn.disconnect(disconnected_by)

        assert conn.status == ConnectionStatus.DISCONNECTED

    def test_disconnect_from_error(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.record_sync_failure("fail1")
        conn.record_sync_failure("fail2")
        conn.record_sync_failure("fail3")
        conn.collect_events()
        disconnected_by = uuid.uuid4()

        conn.disconnect(disconnected_by)

        assert conn.status == ConnectionStatus.DISCONNECTED

    def test_disconnect_from_disconnected_raises_error(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.disconnect(uuid.uuid4())
        conn.collect_events()

        with pytest.raises(InvalidConnectionStateError):
            conn.disconnect(uuid.uuid4())


# ---------------------------------------------------------------------------
# reconnect()
# ---------------------------------------------------------------------------


class TestReconnect:
    """Tests for BankConnection.reconnect()."""

    def test_reconnect_from_needs_reauth_transitions_to_active(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.mark_needs_reauth()
        conn.collect_events()

        conn.reconnect(ProviderCredentials("new-token"))

        assert conn.status == ConnectionStatus.ACTIVE
        assert conn.credentials == ProviderCredentials("new-token")
        assert conn.consecutive_failures == 0
        assert conn.next_sync_scheduled_at is not None

    def test_reconnect_from_error_transitions_to_active(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.record_sync_failure("fail1")
        conn.record_sync_failure("fail2")
        conn.record_sync_failure("fail3")
        assert conn.status == ConnectionStatus.ERROR
        conn.collect_events()

        conn.reconnect(ProviderCredentials("new-token"))

        assert conn.status == ConnectionStatus.ACTIVE
        assert conn.consecutive_failures == 0

    def test_reconnect_emits_bank_connection_reconnected(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.mark_needs_reauth()
        conn.collect_events()

        conn.reconnect(ProviderCredentials("new-token"))
        events = conn.collect_events()

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, BankConnectionReconnected)
        assert event.aggregate_id == conn.id

    def test_reconnect_from_disconnected_raises_error(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.disconnect(uuid.uuid4())
        conn.collect_events()

        with pytest.raises(InvalidConnectionStateError):
            conn.reconnect(ProviderCredentials("token"))

    def test_reconnect_from_pending_raises_error(self) -> None:
        conn = _make_connection()
        conn.collect_events()

        with pytest.raises(InvalidConnectionStateError):
            conn.reconnect(ProviderCredentials("token"))


# ---------------------------------------------------------------------------
# soft_delete()
# ---------------------------------------------------------------------------


class TestSoftDelete:
    """Tests for BankConnection.soft_delete()."""

    def test_soft_delete_disconnects_first_then_soft_deletes(self) -> None:
        conn = _activate_connection(_make_connection())
        deleted_by = uuid.uuid4()

        conn.soft_delete(deleted_by=deleted_by, retention=_retention())

        assert conn.status == ConnectionStatus.DISCONNECTED
        assert conn.credentials is None
        assert conn.next_sync_scheduled_at is None
        assert conn.is_deleted()

    def test_soft_delete_emits_bank_connection_soft_deleted(self) -> None:
        conn = _activate_connection(_make_connection())
        deleted_by = uuid.uuid4()

        conn.soft_delete(deleted_by=deleted_by, retention=_retention())
        events = conn.collect_events()

        soft_deleted_events = [e for e in events if isinstance(e, BankConnectionSoftDeleted)]
        assert len(soft_deleted_events) == 1
        assert soft_deleted_events[0].aggregate_id == conn.id
        assert soft_deleted_events[0].deleted_by == deleted_by

    def test_soft_delete_from_already_disconnected_still_soft_deletes(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.disconnect(uuid.uuid4())
        conn.collect_events()
        deleted_by = uuid.uuid4()

        conn.soft_delete(deleted_by=deleted_by, retention=_retention())

        assert conn.is_deleted()
        assert conn.status == ConnectionStatus.DISCONNECTED


# ---------------------------------------------------------------------------
# is_syncable()
# ---------------------------------------------------------------------------


class TestIsSyncable:
    """Tests for BankConnection.is_syncable()."""

    def test_is_syncable_true_for_active_not_deleted(self) -> None:
        conn = _activate_connection(_make_connection())

        assert conn.is_syncable() is True

    @pytest.mark.parametrize(
        "status_name",
        ["PENDING", "NEEDS_REAUTH", "ERROR", "DISCONNECTED"],
    )
    def test_is_syncable_false_for_non_active_statuses(self, status_name: str) -> None:
        conn = _activate_connection(_make_connection())

        if status_name == "PENDING":
            # Cannot go back to PENDING, so create fresh
            conn = _make_connection()
        elif status_name == "NEEDS_REAUTH":
            conn.mark_needs_reauth()
        elif status_name == "ERROR":
            conn.record_sync_failure("fail1")
            conn.record_sync_failure("fail2")
            conn.record_sync_failure("fail3")
        elif status_name == "DISCONNECTED":
            conn.disconnect(uuid.uuid4())

        assert conn.is_syncable() is False

    def test_is_syncable_false_when_deleted(self) -> None:
        conn = _activate_connection(_make_connection())
        conn.soft_delete(deleted_by=uuid.uuid4(), retention=_retention())

        assert conn.is_syncable() is False
