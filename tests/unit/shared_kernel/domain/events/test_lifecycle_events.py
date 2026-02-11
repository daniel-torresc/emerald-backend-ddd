import uuid
from datetime import UTC, datetime

import pytest

from emerald.shared_kernel.domain.events import DomainEvent
from emerald.shared_kernel.domain.events.lifecycle_events import (
    EntityHardDeleted,
    EntityRecovered,
    EntitySoftDeleted,
    HardDeleteCancelled,
    HardDeleteScheduled,
    HardDeleteTrigger,
    RetentionWarningDue,
    RetentionWarningType,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


class TestHardDeleteTriggerEnum:
    def test_has_three_members(self) -> None:
        assert len(HardDeleteTrigger) == 3

    def test_values(self) -> None:
        assert HardDeleteTrigger.USER_INITIATED.value == "USER_INITIATED"
        assert HardDeleteTrigger.AUTOMATIC.value == "AUTOMATIC"
        assert HardDeleteTrigger.ADMIN_INITIATED.value == "ADMIN_INITIATED"


class TestRetentionWarningTypeEnum:
    def test_has_two_members(self) -> None:
        assert len(RetentionWarningType) == 2

    def test_values(self) -> None:
        assert RetentionWarningType.FIRST_WARNING.value == "FIRST_WARNING"
        assert RetentionWarningType.FINAL_WARNING.value == "FINAL_WARNING"


class TestEntitySoftDeleted:
    def test_instantiation(self) -> None:
        agg_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        deleted_by = uuid.uuid4()
        scheduled = datetime(2025, 7, 1, tzinfo=UTC)
        evt = EntitySoftDeleted(
            aggregate_id=agg_id,
            entity_type=DeletableEntityType.USER,
            entity_id=entity_id,
            deleted_by=deleted_by,
            reason="test reason",
            hard_delete_scheduled_at=scheduled,
        )
        assert evt.aggregate_id == agg_id
        assert evt.entity_type == DeletableEntityType.USER
        assert evt.entity_id == entity_id
        assert evt.deleted_by == deleted_by
        assert evt.reason == "test reason"
        assert evt.hard_delete_scheduled_at == scheduled

    def test_aggregate_type(self) -> None:
        evt = EntitySoftDeleted(aggregate_id=uuid.uuid4())
        assert evt.aggregate_type == "data_lifecycle"

    def test_auto_generated_fields(self) -> None:
        evt = EntitySoftDeleted(aggregate_id=uuid.uuid4())
        assert isinstance(evt.event_id, uuid.UUID)
        assert isinstance(evt.occurred_at, datetime)

    def test_extends_domain_event(self) -> None:
        assert issubclass(EntitySoftDeleted, DomainEvent)

    def test_reason_defaults_to_none(self) -> None:
        evt = EntitySoftDeleted(aggregate_id=uuid.uuid4())
        assert evt.reason is None


class TestEntityRecovered:
    def test_instantiation(self) -> None:
        agg_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        recovered_by = uuid.uuid4()
        evt = EntityRecovered(
            aggregate_id=agg_id,
            entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
            entity_id=entity_id,
            recovered_by=recovered_by,
        )
        assert evt.entity_type == DeletableEntityType.FINANCIAL_ACCOUNT
        assert evt.entity_id == entity_id
        assert evt.recovered_by == recovered_by

    def test_aggregate_type(self) -> None:
        evt = EntityRecovered(aggregate_id=uuid.uuid4())
        assert evt.aggregate_type == "data_lifecycle"


class TestHardDeleteScheduled:
    def test_instantiation(self) -> None:
        scheduled = datetime(2025, 8, 1, tzinfo=UTC)
        confirmed_by = uuid.uuid4()
        evt = HardDeleteScheduled(
            aggregate_id=uuid.uuid4(),
            entity_type=DeletableEntityType.USER,
            entity_id=uuid.uuid4(),
            scheduled_at=scheduled,
            confirmed_by=confirmed_by,
        )
        assert evt.scheduled_at == scheduled
        assert evt.confirmed_by == confirmed_by

    def test_aggregate_type(self) -> None:
        evt = HardDeleteScheduled(aggregate_id=uuid.uuid4())
        assert evt.aggregate_type == "data_lifecycle"


class TestHardDeleteCancelled:
    def test_instantiation(self) -> None:
        cancelled_by = uuid.uuid4()
        evt = HardDeleteCancelled(
            aggregate_id=uuid.uuid4(),
            entity_type=DeletableEntityType.FINANCIAL_ACCOUNT,
            entity_id=uuid.uuid4(),
            cancelled_by=cancelled_by,
        )
        assert evt.cancelled_by == cancelled_by

    def test_aggregate_type(self) -> None:
        evt = HardDeleteCancelled(aggregate_id=uuid.uuid4())
        assert evt.aggregate_type == "data_lifecycle"


class TestEntityHardDeleted:
    def test_instantiation(self) -> None:
        evt = EntityHardDeleted(
            aggregate_id=uuid.uuid4(),
            entity_type=DeletableEntityType.TRANSACTION,
            entity_id=uuid.uuid4(),
            trigger=HardDeleteTrigger.USER_INITIATED,
        )
        assert evt.trigger == HardDeleteTrigger.USER_INITIATED

    def test_aggregate_type(self) -> None:
        evt = EntityHardDeleted(aggregate_id=uuid.uuid4())
        assert evt.aggregate_type == "data_lifecycle"

    def test_default_trigger(self) -> None:
        evt = EntityHardDeleted(aggregate_id=uuid.uuid4())
        assert evt.trigger == HardDeleteTrigger.AUTOMATIC


class TestRetentionWarningDue:
    def test_instantiation(self) -> None:
        hard_delete_at = datetime(2025, 9, 1, tzinfo=UTC)
        evt = RetentionWarningDue(
            aggregate_id=uuid.uuid4(),
            entity_type=DeletableEntityType.CARD,
            entity_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            hard_delete_at=hard_delete_at,
            warning_type=RetentionWarningType.FINAL_WARNING,
        )
        assert evt.hard_delete_at == hard_delete_at
        assert evt.warning_type == RetentionWarningType.FINAL_WARNING

    def test_aggregate_type(self) -> None:
        evt = RetentionWarningDue(aggregate_id=uuid.uuid4())
        assert evt.aggregate_type == "data_lifecycle"


class TestAllEventsImmutable:
    @pytest.mark.parametrize(
        "event_cls",
        [
            EntitySoftDeleted,
            EntityRecovered,
            HardDeleteScheduled,
            HardDeleteCancelled,
            EntityHardDeleted,
            RetentionWarningDue,
        ],
    )
    def test_frozen(self, event_cls: type[DomainEvent]) -> None:
        evt = event_cls(aggregate_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            evt.aggregate_id = uuid.uuid4()  # type: ignore[misc]


class TestAllEventsUniqueIds:
    @pytest.mark.parametrize(
        "event_cls",
        [
            EntitySoftDeleted,
            EntityRecovered,
            HardDeleteScheduled,
            HardDeleteCancelled,
            EntityHardDeleted,
            RetentionWarningDue,
        ],
    )
    def test_unique_event_ids(self, event_cls: type[DomainEvent]) -> None:
        a = event_cls(aggregate_id=uuid.uuid4())
        b = event_cls(aggregate_id=uuid.uuid4())
        assert a.event_id != b.event_id
