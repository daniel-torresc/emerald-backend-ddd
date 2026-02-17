"""Unit tests for connection command DTOs."""

from __future__ import annotations

import dataclasses
import uuid

import pytest

from emerald.integrations.application.dtos.commands.connection_commands import (
    ActivateBankConnection,
    ApprovePendingTransaction,
    DisconnectBankConnection,
    InitiateBankConnection,
    ReconnectBankConnection,
    RejectPendingTransaction,
    SoftDeleteBankConnection,
    TriggerSync,
    UpdateSyncFrequency,
)


class TestInitiateBankConnection:
    def test_can_be_instantiated(self) -> None:
        cmd = InitiateBankConnection(
            user_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            provider_name="plaid",
            institution_id="ins_123",
            external_account_id="ext_acc_123",
        )
        assert cmd.provider_name == "plaid"
        assert cmd.institution_id == "ins_123"

    def test_is_frozen(self) -> None:
        cmd = InitiateBankConnection(
            user_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            provider_name="plaid",
            institution_id="ins_123",
            external_account_id="ext_acc_123",
        )
        assert dataclasses.is_dataclass(cmd)
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.provider_name = "other"  # type: ignore[misc]


class TestActivateBankConnection:
    def test_can_be_instantiated(self) -> None:
        cmd = ActivateBankConnection(
            connection_id=uuid.uuid4(),
            credentials_token="token-abc",
            activated_by=uuid.uuid4(),
        )
        assert cmd.credentials_token == "token-abc"

    def test_is_frozen(self) -> None:
        cmd = ActivateBankConnection(
            connection_id=uuid.uuid4(),
            credentials_token="token",
            activated_by=uuid.uuid4(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.credentials_token = "other"  # type: ignore[misc]


class TestDisconnectBankConnection:
    def test_can_be_instantiated(self) -> None:
        uid = uuid.uuid4()
        cid = uuid.uuid4()
        cmd = DisconnectBankConnection(connection_id=cid, disconnected_by=uid)
        assert cmd.connection_id == cid
        assert cmd.disconnected_by == uid

    def test_is_frozen(self) -> None:
        cmd = DisconnectBankConnection(connection_id=uuid.uuid4(), disconnected_by=uuid.uuid4())
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.disconnected_by = uuid.uuid4()  # type: ignore[misc]


class TestReconnectBankConnection:
    def test_can_be_instantiated(self) -> None:
        cmd = ReconnectBankConnection(
            connection_id=uuid.uuid4(),
            credentials_token="new-token",
            reconnected_by=uuid.uuid4(),
        )
        assert cmd.credentials_token == "new-token"

    def test_is_frozen(self) -> None:
        cmd = ReconnectBankConnection(
            connection_id=uuid.uuid4(),
            credentials_token="token",
            reconnected_by=uuid.uuid4(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.credentials_token = "x"  # type: ignore[misc]


class TestUpdateSyncFrequency:
    def test_can_be_instantiated(self) -> None:
        cmd = UpdateSyncFrequency(connection_id=uuid.uuid4(), hours=12, updated_by=uuid.uuid4())
        assert cmd.hours == 12

    def test_is_frozen(self) -> None:
        cmd = UpdateSyncFrequency(connection_id=uuid.uuid4(), hours=12, updated_by=uuid.uuid4())
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.hours = 6  # type: ignore[misc]


class TestTriggerSync:
    def test_can_be_instantiated(self) -> None:
        cid = uuid.uuid4()
        uid = uuid.uuid4()
        cmd = TriggerSync(connection_id=cid, triggered_by=uid)
        assert cmd.connection_id == cid
        assert cmd.triggered_by == uid

    def test_is_frozen(self) -> None:
        cmd = TriggerSync(connection_id=uuid.uuid4(), triggered_by=uuid.uuid4())
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.triggered_by = uuid.uuid4()  # type: ignore[misc]


class TestApprovePendingTransaction:
    def test_can_be_instantiated(self) -> None:
        pid = uuid.uuid4()
        uid = uuid.uuid4()
        cmd = ApprovePendingTransaction(pending_id=pid, approved_by=uid)
        assert cmd.pending_id == pid
        assert cmd.approved_by == uid

    def test_is_frozen(self) -> None:
        cmd = ApprovePendingTransaction(pending_id=uuid.uuid4(), approved_by=uuid.uuid4())
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.approved_by = uuid.uuid4()  # type: ignore[misc]


class TestRejectPendingTransaction:
    def test_can_be_instantiated(self) -> None:
        pid = uuid.uuid4()
        uid = uuid.uuid4()
        cmd = RejectPendingTransaction(pending_id=pid, rejected_by=uid)
        assert cmd.pending_id == pid
        assert cmd.rejected_by == uid

    def test_is_frozen(self) -> None:
        cmd = RejectPendingTransaction(pending_id=uuid.uuid4(), rejected_by=uuid.uuid4())
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.rejected_by = uuid.uuid4()  # type: ignore[misc]


class TestSoftDeleteBankConnection:
    def test_can_be_instantiated(self) -> None:
        cid = uuid.uuid4()
        uid = uuid.uuid4()
        cmd = SoftDeleteBankConnection(connection_id=cid, deleted_by=uid, reason="cleanup")
        assert cmd.connection_id == cid
        assert cmd.deleted_by == uid
        assert cmd.reason == "cleanup"

    def test_reason_defaults_to_none(self) -> None:
        cmd = SoftDeleteBankConnection(connection_id=uuid.uuid4(), deleted_by=uuid.uuid4())
        assert cmd.reason is None

    def test_is_frozen(self) -> None:
        cmd = SoftDeleteBankConnection(connection_id=uuid.uuid4(), deleted_by=uuid.uuid4())
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.reason = "new"  # type: ignore[misc]
