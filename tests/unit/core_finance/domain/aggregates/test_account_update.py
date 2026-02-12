import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.events.account_events import AccountUpdated
from emerald.core_finance.domain.exceptions import InvalidAccountNotesError
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money


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


class TestUpdateName:
    def test_changes_name(self) -> None:
        account = _make_account()
        new_name = AccountName("Savings")
        account.update_name(new_name, uuid.uuid4())
        assert account.account_name == new_name

    def test_increments_version(self) -> None:
        account = _make_account()
        old_version = account.version
        account.update_name(AccountName("Savings"), uuid.uuid4())
        assert account.version == old_version + 1

    def test_updates_updated_at(self) -> None:
        account = _make_account()
        old_updated_at = account.updated_at
        account.update_name(AccountName("Savings"), uuid.uuid4())
        assert account.updated_at >= old_updated_at

    def test_sets_updated_by(self) -> None:
        account = _make_account()
        actor = uuid.uuid4()
        account.update_name(AccountName("Savings"), actor)
        assert account.updated_by == actor

    def test_emits_account_updated(self) -> None:
        account = _make_account()
        account.update_name(AccountName("Savings"), uuid.uuid4())
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountUpdated)
        assert event.changed_fields == frozenset({"account_name"})


class TestUpdateAccountType:
    def test_changes_account_type(self) -> None:
        account = _make_account()
        new_type_id = uuid.uuid4()
        account.update_account_type(new_type_id, uuid.uuid4())
        assert account.account_type_id == new_type_id

    def test_increments_version(self) -> None:
        account = _make_account()
        old_version = account.version
        account.update_account_type(uuid.uuid4(), uuid.uuid4())
        assert account.version == old_version + 1

    def test_emits_account_updated(self) -> None:
        account = _make_account()
        account.update_account_type(uuid.uuid4(), uuid.uuid4())
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountUpdated)
        assert event.changed_fields == frozenset({"account_type_id"})


class TestUpdateFinancialInstitution:
    def test_changes_institution(self) -> None:
        account = _make_account()
        new_inst_id = uuid.uuid4()
        account.update_financial_institution(new_inst_id, uuid.uuid4())
        assert account.financial_institution_id == new_inst_id

    def test_increments_version(self) -> None:
        account = _make_account()
        old_version = account.version
        account.update_financial_institution(uuid.uuid4(), uuid.uuid4())
        assert account.version == old_version + 1

    def test_emits_account_updated(self) -> None:
        account = _make_account()
        account.update_financial_institution(uuid.uuid4(), uuid.uuid4())
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountUpdated)
        assert event.changed_fields == frozenset({"financial_institution_id"})


class TestUpdateNotes:
    def test_changes_notes(self) -> None:
        account = _make_account()
        account.update_notes("New notes", uuid.uuid4())
        assert account.notes == "New notes"

    def test_clears_notes_with_none(self) -> None:
        account = _make_account(notes="Old notes")
        account.collect_events()
        account.update_notes(None, uuid.uuid4())
        assert account.notes is None

    def test_increments_version(self) -> None:
        account = _make_account()
        old_version = account.version
        account.update_notes("Notes", uuid.uuid4())
        assert account.version == old_version + 1

    def test_emits_account_updated(self) -> None:
        account = _make_account()
        account.update_notes("Notes", uuid.uuid4())
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountUpdated)
        assert event.changed_fields == frozenset({"notes"})

    def test_rejects_notes_over_500_chars(self) -> None:
        account = _make_account()
        with pytest.raises(InvalidAccountNotesError):
            account.update_notes("A" * 501, uuid.uuid4())

    def test_accepts_notes_exactly_500_chars(self) -> None:
        account = _make_account()
        account.update_notes("A" * 500, uuid.uuid4())
        assert account.notes == "A" * 500
