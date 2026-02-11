import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.trash_item import TrashItem


def _make_trash_item(**overrides: Any) -> TrashItem:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "entity_id": uuid.uuid4(),
        "entity_type": DeletableEntityType.USER,
        "display_name": "Test Entity",
        "deleted_at": now,
        "deleted_by": uuid.uuid4(),
        "deletion_reason": "No longer needed",
        "hard_delete_scheduled_at": now + timedelta(days=30),
        "child_count": 0,
    }
    defaults.update(overrides)
    return TrashItem(**defaults)


class TestTrashItemConstruction:
    def test_valid_construction(self) -> None:
        entity_id = uuid.uuid4()
        deleted_by = uuid.uuid4()
        now = datetime.now(UTC)
        scheduled = now + timedelta(days=30)

        item = TrashItem(
            entity_id=entity_id,
            entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
            display_name="My Savings Account",
            deleted_at=now,
            deleted_by=deleted_by,
            deletion_reason="Closed account",
            hard_delete_scheduled_at=scheduled,
            child_count=5,
        )

        assert item.entity_id == entity_id
        assert item.entity_type == DeletableEntityType.FINANCIAL_ACCOUNT
        assert item.display_name == "My Savings Account"
        assert item.deleted_at == now
        assert item.deleted_by == deleted_by
        assert item.deletion_reason == "Closed account"
        assert item.hard_delete_scheduled_at == scheduled
        assert item.child_count == 5

    def test_optional_deletion_reason_none(self) -> None:
        item = _make_trash_item(deletion_reason=None)
        assert item.deletion_reason is None


class TestTrashItemTimeRemaining:
    def test_positive_time_remaining_when_future(self) -> None:
        scheduled = datetime.now(UTC) + timedelta(days=10)
        item = _make_trash_item(hard_delete_scheduled_at=scheduled)
        remaining = item.time_remaining
        assert remaining.total_seconds() > 0

    def test_negative_time_remaining_when_overdue(self) -> None:
        scheduled = datetime.now(UTC) - timedelta(days=5)
        item = _make_trash_item(hard_delete_scheduled_at=scheduled)
        remaining = item.time_remaining
        assert remaining.total_seconds() < 0


class TestTrashItemValidation:
    def test_negative_child_count_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            _make_trash_item(child_count=-1)

    def test_empty_display_name_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            _make_trash_item(display_name="")

    def test_blank_display_name_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            _make_trash_item(display_name="   ")

    def test_zero_child_count_allowed(self) -> None:
        item = _make_trash_item(child_count=0)
        assert item.child_count == 0
