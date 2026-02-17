"""Tests for BankConnection.create() factory method."""

from __future__ import annotations

import uuid
from typing import Any

from emerald.integrations.domain.events.connection_events import BankConnectionInitiated
from emerald.integrations.domain.models.aggregates.bank_connection import BankConnection
from emerald.integrations.domain.models.value_objects.connection_status import ConnectionStatus
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


class TestBankConnectionCreate:
    """Tests for the BankConnection.create() factory."""

    def test_create_returns_pending_status_with_no_credentials(self) -> None:
        conn = _make_connection()

        assert conn.status == ConnectionStatus.PENDING
        assert conn.credentials is None

    def test_create_has_correct_identity_fields(self) -> None:
        user_id = uuid.uuid4()
        account_id = uuid.uuid4()
        provider = ProviderName("plaid")
        institution_id = "ins_456"
        external_account_id = "ext_789"

        conn = _make_connection(
            user_id=user_id,
            account_id=account_id,
            provider_name=provider,
            institution_id=institution_id,
            external_account_id=external_account_id,
        )

        assert conn.user_id == user_id
        assert conn.account_id == account_id
        assert conn.provider_name == provider
        assert conn.institution_id == institution_id
        assert conn.external_account_id == external_account_id

    def test_create_emits_bank_connection_initiated_event(self) -> None:
        user_id = uuid.uuid4()
        account_id = uuid.uuid4()
        provider = ProviderName("plaid")

        conn = _make_connection(
            user_id=user_id,
            account_id=account_id,
            provider_name=provider,
        )
        events = conn.collect_events()

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, BankConnectionInitiated)
        assert event.aggregate_id == conn.id
        assert event.user_id == user_id
        assert event.provider_name == "plaid"
        assert event.account_id == account_id

    def test_create_sets_version_to_one(self) -> None:
        conn = _make_connection()

        assert conn.version == 1

    def test_create_sets_default_sync_frequency_hours(self) -> None:
        conn = _make_connection()

        assert conn.sync_frequency_hours == 6
