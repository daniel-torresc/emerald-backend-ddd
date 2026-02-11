import uuid
from datetime import UTC, datetime

import pytest

from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.hard_delete_confirmation import (
    HardDeleteConfirmation,
)


class TestHardDeleteConfirmationConstruction:
    def test_valid_construction(self) -> None:
        entity_id = uuid.uuid4()
        confirmed_by = uuid.uuid4()
        now = datetime.now(UTC)

        confirmation = HardDeleteConfirmation(
            entity_id=entity_id,
            entity_type=DeletableEntityType.TAXONOMY,
            confirmed_by=confirmed_by,
            acknowledged_cascade_count=3,
            confirmed_at=now,
        )

        assert confirmation.entity_id == entity_id
        assert confirmation.entity_type == DeletableEntityType.TAXONOMY
        assert confirmation.confirmed_by == confirmed_by
        assert confirmation.acknowledged_cascade_count == 3
        assert confirmation.confirmed_at == now

    def test_minimum_acknowledged_cascade_count(self) -> None:
        confirmation = HardDeleteConfirmation(
            entity_id=uuid.uuid4(),
            entity_type=DeletableEntityType.CARD,
            confirmed_by=uuid.uuid4(),
            acknowledged_cascade_count=1,
            confirmed_at=datetime.now(UTC),
        )
        assert confirmation.acknowledged_cascade_count == 1


class TestHardDeleteConfirmationValidation:
    def test_zero_acknowledged_cascade_count_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            HardDeleteConfirmation(
                entity_id=uuid.uuid4(),
                entity_type=DeletableEntityType.USER,
                confirmed_by=uuid.uuid4(),
                acknowledged_cascade_count=0,
                confirmed_at=datetime.now(UTC),
            )

    def test_negative_acknowledged_cascade_count_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            HardDeleteConfirmation(
                entity_id=uuid.uuid4(),
                entity_type=DeletableEntityType.USER,
                confirmed_by=uuid.uuid4(),
                acknowledged_cascade_count=-1,
                confirmed_at=datetime.now(UTC),
            )


class TestHardDeleteConfirmationImmutability:
    def test_frozen(self) -> None:
        confirmation = HardDeleteConfirmation(
            entity_id=uuid.uuid4(),
            entity_type=DeletableEntityType.BANK_CONNECTION,
            confirmed_by=uuid.uuid4(),
            acknowledged_cascade_count=1,
            confirmed_at=datetime.now(UTC),
        )
        with pytest.raises(AttributeError):
            confirmation.acknowledged_cascade_count = 5  # type: ignore[misc]
