import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from emerald.shared_kernel.application.dtos.commands import Command
from emerald.shared_kernel.application.dtos.lifecycle_commands import (
    CancelHardDelete,
    ConfirmHardDelete,
    RecoverEntity,
    RequestHardDelete,
    SetUserRetentionPreference,
    SoftDeleteEntity,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.hard_delete_confirmation import (
    HardDeleteConfirmation,
)
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)


class TestSoftDeleteEntity:
    def test_instantiation_with_reason(self) -> None:
        entity_id = uuid.uuid4()
        deleted_by = uuid.uuid4()
        cmd = SoftDeleteEntity(
            entity_id=entity_id,
            entity_type=DeletableEntityType.USER,
            deleted_by=deleted_by,
            reason="No longer needed",
        )
        assert cmd.entity_id == entity_id
        assert cmd.entity_type == DeletableEntityType.USER
        assert cmd.deleted_by == deleted_by
        assert cmd.reason == "No longer needed"

    def test_reason_defaults_to_none(self) -> None:
        cmd = SoftDeleteEntity(
            entity_id=uuid.uuid4(),
            entity_type=DeletableEntityType.TRANSACTION,
            deleted_by=uuid.uuid4(),
        )
        assert cmd.reason is None

    def test_extends_command(self) -> None:
        cmd = SoftDeleteEntity(
            entity_id=uuid.uuid4(),
            entity_type=DeletableEntityType.USER,
            deleted_by=uuid.uuid4(),
        )
        assert isinstance(cmd, Command)

    def test_is_frozen(self) -> None:
        cmd = SoftDeleteEntity(
            entity_id=uuid.uuid4(),
            entity_type=DeletableEntityType.USER,
            deleted_by=uuid.uuid4(),
        )
        with pytest.raises(FrozenInstanceError):
            cmd.reason = "changed"  # type: ignore[misc]


class TestRecoverEntity:
    def test_instantiation(self) -> None:
        entity_id = uuid.uuid4()
        recovered_by = uuid.uuid4()
        cmd = RecoverEntity(
            entity_id=entity_id,
            entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
            recovered_by=recovered_by,
        )
        assert cmd.entity_id == entity_id
        assert cmd.entity_type == DeletableEntityType.FINANCIAL_ACCOUNT
        assert cmd.recovered_by == recovered_by

    def test_extends_command(self) -> None:
        assert issubclass(RecoverEntity, Command)

    def test_is_frozen(self) -> None:
        cmd = RecoverEntity(
            entity_id=uuid.uuid4(),
            entity_type=DeletableEntityType.CARD,
            recovered_by=uuid.uuid4(),
        )
        with pytest.raises(FrozenInstanceError):
            cmd.entity_id = uuid.uuid4()  # type: ignore[misc]


class TestRequestHardDelete:
    def test_instantiation(self) -> None:
        entity_id = uuid.uuid4()
        requested_by = uuid.uuid4()
        cmd = RequestHardDelete(
            entity_id=entity_id,
            entity_type=DeletableEntityType.TAXONOMY,
            requested_by=requested_by,
        )
        assert cmd.entity_id == entity_id
        assert cmd.entity_type == DeletableEntityType.TAXONOMY
        assert cmd.requested_by == requested_by

    def test_extends_command(self) -> None:
        assert issubclass(RequestHardDelete, Command)


class TestConfirmHardDelete:
    def test_instantiation(self) -> None:
        entity_id = uuid.uuid4()
        confirmation = HardDeleteConfirmation(
            entity_id=entity_id,
            entity_type=DeletableEntityType.USER,
            confirmed_by=uuid.uuid4(),
            acknowledged_cascade_count=5,
            confirmed_at=datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
        )
        cmd = ConfirmHardDelete(
            entity_id=entity_id,
            entity_type=DeletableEntityType.USER,
            confirmation=confirmation,
        )
        assert cmd.entity_id == entity_id
        assert cmd.entity_type == DeletableEntityType.USER
        assert cmd.confirmation == confirmation

    def test_extends_command(self) -> None:
        assert issubclass(ConfirmHardDelete, Command)


class TestCancelHardDelete:
    def test_instantiation(self) -> None:
        entity_id = uuid.uuid4()
        cancelled_by = uuid.uuid4()
        cmd = CancelHardDelete(
            entity_id=entity_id,
            entity_type=DeletableEntityType.BANK_CONNECTION,
            cancelled_by=cancelled_by,
        )
        assert cmd.entity_id == entity_id
        assert cmd.entity_type == DeletableEntityType.BANK_CONNECTION
        assert cmd.cancelled_by == cancelled_by

    def test_extends_command(self) -> None:
        assert issubclass(CancelHardDelete, Command)


class TestSetUserRetentionPreference:
    def test_instantiation(self) -> None:
        user_id = uuid.uuid4()
        period = RetentionPeriod(duration=90, unit=RetentionUnit.DAYS)
        cmd = SetUserRetentionPreference(
            user_id=user_id,
            entity_type=DeletableEntityType.CARD,
            retention_period=period,
        )
        assert cmd.user_id == user_id
        assert cmd.entity_type == DeletableEntityType.CARD
        assert cmd.retention_period == period

    def test_extends_command(self) -> None:
        assert issubclass(SetUserRetentionPreference, Command)

    def test_is_frozen(self) -> None:
        cmd = SetUserRetentionPreference(
            user_id=uuid.uuid4(),
            entity_type=DeletableEntityType.CARD,
            retention_period=RetentionPeriod(duration=90, unit=RetentionUnit.DAYS),
        )
        with pytest.raises(FrozenInstanceError):
            cmd.user_id = uuid.uuid4()  # type: ignore[misc]
