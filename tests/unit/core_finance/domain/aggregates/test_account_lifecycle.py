import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.events.account_events import (
    AccountRecovered,
    AccountSoftDeleted,
)
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.exceptions import AlreadyDeletedError, NotDeletedError
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)


def _make_account(**overrides: Any) -> Account:
    owner = overrides.pop("owner", UserReference(user_id=uuid.uuid4(), display_name="Test User"))
    defaults: dict[str, Any] = {
        "account_name": AccountName("Test Account"),
        "currency": Currency.USD,
        "opening_balance": Money(Decimal("1000.00"), Currency.USD),
        "account_type_id": uuid.uuid4(),
        "financial_institution_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    account = Account.create(owner=owner, **defaults)
    account.collect_events()  # clear creation event
    return account


def _default_retention() -> RetentionPeriod:
    return RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)


class TestSoftDelete:
    def test_marks_as_deleted(self) -> None:
        account = _make_account()
        account.soft_delete(uuid.uuid4(), _default_retention())
        assert account.is_deleted()
        assert not account.is_active()

    def test_sets_deleted_at(self) -> None:
        account = _make_account()
        account.soft_delete(uuid.uuid4(), _default_retention())
        assert account.deleted_at is not None

    def test_sets_deleted_by(self) -> None:
        account = _make_account()
        actor = uuid.uuid4()
        account.soft_delete(actor, _default_retention())
        assert account.deleted_by == actor

    def test_sets_deletion_reason(self) -> None:
        account = _make_account()
        account.soft_delete(uuid.uuid4(), _default_retention(), reason="No longer needed")
        assert account.deletion_reason == "No longer needed"

    def test_sets_hard_delete_scheduled_at(self) -> None:
        account = _make_account()
        account.soft_delete(uuid.uuid4(), _default_retention())
        assert account.hard_delete_scheduled_at is not None

    def test_increments_version(self) -> None:
        account = _make_account()
        old_version = account.version
        account.soft_delete(uuid.uuid4(), _default_retention())
        assert account.version == old_version + 1

    def test_emits_account_soft_deleted(self) -> None:
        account = _make_account()
        actor = uuid.uuid4()
        account.soft_delete(actor, _default_retention(), reason="Test")
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountSoftDeleted)
        assert event.deleted_by == actor
        assert event.reason == "Test"

    def test_double_soft_delete_raises(self) -> None:
        account = _make_account()
        account.soft_delete(uuid.uuid4(), _default_retention())
        with pytest.raises(AlreadyDeletedError):
            account.soft_delete(uuid.uuid4(), _default_retention())


class TestRecover:
    def test_clears_deletion_fields(self) -> None:
        account = _make_account()
        account.soft_delete(uuid.uuid4(), _default_retention())
        account.collect_events()
        account.recover()
        assert account.deleted_at is None
        assert account.deleted_by is None
        assert account.deletion_reason is None
        assert account.hard_delete_scheduled_at is None

    def test_marks_as_active(self) -> None:
        account = _make_account()
        account.soft_delete(uuid.uuid4(), _default_retention())
        account.collect_events()
        account.recover()
        assert account.is_active()
        assert not account.is_deleted()

    def test_increments_version(self) -> None:
        account = _make_account()
        account.soft_delete(uuid.uuid4(), _default_retention())
        account.collect_events()
        old_version = account.version
        account.recover()
        assert account.version == old_version + 1

    def test_emits_account_recovered(self) -> None:
        account = _make_account()
        actor = uuid.uuid4()
        account.soft_delete(actor, _default_retention())
        account.collect_events()
        account.recover()
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountRecovered)
        assert event.recovered_by == actor

    def test_recover_non_deleted_raises(self) -> None:
        account = _make_account()
        with pytest.raises(NotDeletedError):
            account.recover()
