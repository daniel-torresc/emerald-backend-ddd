import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.events.account_events import AccountCreated
from emerald.core_finance.domain.exceptions import InvalidAccountNotesError
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.iban import IBAN
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.exceptions import CurrencyMismatchError
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money


def _make_owner(**overrides: Any) -> UserReference:
    defaults: dict[str, Any] = {
        "user_id": uuid.uuid4(),
        "display_name": "Test User",
    }
    defaults.update(overrides)
    return UserReference(**defaults)


def _make_account(**overrides: Any) -> Account:
    owner = overrides.pop("owner", _make_owner())
    defaults: dict[str, Any] = {
        "account_name": AccountName("Test Account"),
        "currency": Currency.USD,
        "opening_balance": Money(Decimal("1000.00"), Currency.USD),
        "account_type_id": uuid.uuid4(),
        "financial_institution_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    return Account.create(owner=owner, **defaults)


class TestAccountCreate:
    def test_creates_valid_account(self) -> None:
        owner = _make_owner()
        account = _make_account(owner=owner)
        assert account.account_name == AccountName("Test Account")
        assert account.currency == Currency.USD
        assert account.opening_balance == Money(Decimal("1000.00"), Currency.USD)
        assert account.created_by == owner.user_id

    def test_version_starts_at_one(self) -> None:
        account = _make_account()
        assert account.version == 1

    def test_created_by_set_to_owner(self) -> None:
        owner = _make_owner()
        account = _make_account(owner=owner)
        assert account.created_by == owner.user_id

    def test_updated_by_set_to_owner(self) -> None:
        owner = _make_owner()
        account = _make_account(owner=owner)
        assert account.updated_by == owner.user_id

    def test_timestamps_set(self) -> None:
        account = _make_account()
        assert account.created_at is not None
        assert account.updated_at is not None

    def test_id_is_uuid(self) -> None:
        account = _make_account()
        assert isinstance(account.id, uuid.UUID)

    def test_iban_optional_default_none(self) -> None:
        account = _make_account()
        assert account.iban is None

    def test_iban_set_when_provided(self) -> None:
        iban = IBAN("GB29NWBK60161331926819")
        account = _make_account(iban=iban)
        assert account.iban == iban

    def test_notes_optional_default_none(self) -> None:
        account = _make_account()
        assert account.notes is None

    def test_notes_set_when_provided(self) -> None:
        account = _make_account(notes="My checking account")
        assert account.notes == "My checking account"

    def test_negative_opening_balance_allowed(self) -> None:
        account = _make_account(opening_balance=Money(Decimal("-500.00"), Currency.USD))
        assert account.opening_balance.is_negative()

    def test_zero_opening_balance_allowed(self) -> None:
        account = _make_account(opening_balance=Money(Decimal("0"), Currency.USD))
        assert account.opening_balance.is_zero()


class TestAccountCreateValidation:
    def test_currency_mismatch_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            _make_account(
                currency=Currency.USD,
                opening_balance=Money(Decimal("1000.00"), Currency.EUR),
            )

    def test_notes_over_500_raises(self) -> None:
        with pytest.raises(InvalidAccountNotesError):
            _make_account(notes="A" * 501)

    def test_notes_exactly_500_allowed(self) -> None:
        account = _make_account(notes="A" * 500)
        assert len(account.notes) == 500  # type: ignore[arg-type]


class TestAccountCreateEvent:
    def test_emits_account_created(self) -> None:
        owner = _make_owner()
        account = _make_account(owner=owner)
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountCreated)

    def test_event_has_correct_data(self) -> None:
        owner = _make_owner()
        account = _make_account(owner=owner)
        events = account.collect_events()
        event = events[0]
        assert isinstance(event, AccountCreated)
        assert event.aggregate_id == account.id
        assert event.owner_user_id == owner.user_id
        assert event.currency_code == "USD"
        assert event.account_name == "Test Account"
        assert event.opening_balance == Decimal("1000.00")


class TestAccountImmutability:
    def test_no_currency_update_method(self) -> None:
        account = _make_account()
        assert not hasattr(account, "update_currency")

    def test_no_opening_balance_update_method(self) -> None:
        account = _make_account()
        assert not hasattr(account, "update_opening_balance")

    def test_no_iban_update_method(self) -> None:
        account = _make_account()
        assert not hasattr(account, "update_iban")
