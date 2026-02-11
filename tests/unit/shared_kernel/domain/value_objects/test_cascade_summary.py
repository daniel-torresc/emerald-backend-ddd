import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from emerald.shared_kernel.domain.exceptions import InvalidValueError
from emerald.shared_kernel.domain.models.value_objects.cascade_summary import CascadeSummary
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.trash_item import TrashItem


def _make_trash_item(**overrides: Any) -> TrashItem:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "entity_id": uuid.uuid4(),
        "entity_type": DeletableEntityType.TRANSACTION,
        "display_name": "Child Entity",
        "deleted_at": now,
        "deleted_by": uuid.uuid4(),
        "deletion_reason": None,
        "hard_delete_scheduled_at": now + timedelta(days=30),
        "child_count": 0,
    }
    defaults.update(overrides)
    return TrashItem(**defaults)


class TestCascadeSummaryConstruction:
    def test_construction_with_no_children(self) -> None:
        target_id = uuid.uuid4()
        summary = CascadeSummary(
            target_entity_id=target_id,
            target_entity_type=DeletableEntityType.USER,
            affected_children=(),
            total_affected_count=1,
        )
        assert summary.target_entity_id == target_id
        assert summary.target_entity_type == DeletableEntityType.USER
        assert summary.affected_children == ()
        assert summary.total_affected_count == 1

    def test_construction_with_children(self) -> None:
        child_1 = _make_trash_item(display_name="Transaction 1")
        child_2 = _make_trash_item(display_name="Transaction 2")

        summary = CascadeSummary(
            target_entity_id=uuid.uuid4(),
            target_entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
            affected_children=(child_1, child_2),
            total_affected_count=3,
        )
        assert len(summary.affected_children) == 2
        assert summary.total_affected_count == 3


class TestCascadeSummaryValidation:
    def test_total_affected_count_zero_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            CascadeSummary(
                target_entity_id=uuid.uuid4(),
                target_entity_type=DeletableEntityType.USER,
                affected_children=(),
                total_affected_count=0,
            )

    def test_total_affected_count_negative_raises(self) -> None:
        with pytest.raises(InvalidValueError):
            CascadeSummary(
                target_entity_id=uuid.uuid4(),
                target_entity_type=DeletableEntityType.USER,
                affected_children=(),
                total_affected_count=-1,
            )


class TestCascadeSummaryImmutability:
    def test_affected_children_is_tuple(self) -> None:
        summary = CascadeSummary(
            target_entity_id=uuid.uuid4(),
            target_entity_type=DeletableEntityType.USER,
            affected_children=(),
            total_affected_count=1,
        )
        assert isinstance(summary.affected_children, tuple)
