"""Tests for BankConnection configuration methods."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidSyncFrequencyError,
)
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
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
# update_sync_frequency()
# ---------------------------------------------------------------------------


class TestUpdateSyncFrequency:
    """Tests for BankConnection.update_sync_frequency()."""

    @pytest.mark.parametrize("hours", [1, 6, 12, 24])
    def test_valid_range_updates_sync_frequency(self, hours: int) -> None:
        conn = _make_connection()

        conn.update_sync_frequency(hours)

        assert conn.sync_frequency_hours == hours

    def test_recalculates_next_sync_if_active_with_last_sync(self) -> None:
        conn = _activate_connection(_make_connection())
        synced_at = datetime.now(UTC)
        conn.record_sync_success(synced_at)

        conn.update_sync_frequency(12)

        expected_next = synced_at + timedelta(hours=12)
        assert conn.next_sync_scheduled_at == expected_next

    def test_does_not_recalculate_if_not_active(self) -> None:
        conn = _make_connection()  # PENDING status
        original_next = conn.next_sync_scheduled_at

        conn.update_sync_frequency(12)

        assert conn.next_sync_scheduled_at == original_next

    def test_does_not_recalculate_if_active_but_no_last_sync(self) -> None:
        conn = _activate_connection(_make_connection())
        # next_sync_scheduled_at was set by activate(), but last_sync_at is None
        next_before = conn.next_sync_scheduled_at

        conn.update_sync_frequency(12)

        # next_sync_scheduled_at should remain unchanged (set by activate, not recalculated)
        assert conn.next_sync_scheduled_at == next_before

    def test_below_minimum_raises_invalid_sync_frequency(self) -> None:
        conn = _make_connection()

        with pytest.raises(InvalidSyncFrequencyError):
            conn.update_sync_frequency(0)

    def test_above_maximum_raises_invalid_sync_frequency(self) -> None:
        conn = _make_connection()

        with pytest.raises(InvalidSyncFrequencyError):
            conn.update_sync_frequency(25)
