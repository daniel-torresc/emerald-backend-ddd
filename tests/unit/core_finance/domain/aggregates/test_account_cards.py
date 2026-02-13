from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.events.account_events import AccountSoftDeleted
from emerald.core_finance.domain.events.card_events import (
    CardCreated,
    CardRecovered,
    CardSoftDeleted,
    CardUpdated,
)
from emerald.core_finance.domain.exceptions.card_exceptions import (
    CardNotFoundError,
    CurrencyMismatchError,
    InvalidCardDataError,
    MaxCardsReachedError,
)
from emerald.core_finance.domain.exceptions.sharing_exceptions import AccountNotActiveError
from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.entities.card import Card
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.card_network import CardNetwork
from emerald.core_finance.domain.models.value_objects.card_number import CardNumber
from emerald.core_finance.domain.models.value_objects.card_type import CardType
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.exceptions import AlreadyDeletedError, NotDeletedError
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)


def _make_account(owner_id: uuid.UUID | None = None, **overrides: Any) -> Account:
    uid = owner_id or uuid.uuid4()
    owner = UserReference(user_id=uid, display_name="Owner")
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


def _make_card(account_id: uuid.UUID, **overrides: Any) -> Card:
    defaults: dict[str, Any] = {
        "account_id": account_id,
        "card_type": CardType.CREDIT,
        "card_name": "My Card",
        "card_number": CardNumber("4111111111111111"),
        "expiry_month": 12,
        "expiry_year": 2030,
    }
    defaults.update(overrides)
    return Card.create(**defaults)


def _retention() -> RetentionPeriod:
    return RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)


# ---------------------------------------------------------------------------
# TestAddCard
# ---------------------------------------------------------------------------


class TestAddCard:
    def test_adds_card_successfully(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)
        assert account.active_card_count == 1
        assert len(account.get_cards()) == 1

    def test_emits_card_created_event(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CardCreated)
        assert event.card_id == card.id
        assert event.account_id == account.id
        assert event.card_type == CardType.CREDIT.value
        assert event.card_name == "My Card"
        assert event.card_number_masked == "****1111"

    def test_rejects_card_for_deleted_account(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        account.soft_delete(owner_id, _retention())
        account.collect_events()

        card = _make_card(account.id)
        with pytest.raises(AccountNotActiveError):
            account.add_card(card)

    def test_rejects_mismatched_account_id(self) -> None:
        account = _make_account()
        card = _make_card(uuid.uuid4())  # different account
        with pytest.raises(InvalidCardDataError):
            account.add_card(card)

    def test_rejects_exceeding_max_cards(self) -> None:
        account = _make_account()
        for _ in range(10):
            card = _make_card(account.id)
            account.add_card(card)
        account.collect_events()

        card = _make_card(account.id)
        with pytest.raises(MaxCardsReachedError):
            account.add_card(card)

    def test_rejects_currency_mismatch(self) -> None:
        account = _make_account()  # USD account
        card = _make_card(
            account.id,
            credit_limit=Money(Decimal("5000.00"), Currency.EUR),
        )
        with pytest.raises(CurrencyMismatchError):
            account.add_card(card)

    def test_accepts_no_credit_limit(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        assert card.credit_limit is None
        account.add_card(card)
        assert account.active_card_count == 1

    def test_accepts_matching_currency(self) -> None:
        account = _make_account()
        card = _make_card(
            account.id,
            credit_limit=Money(Decimal("5000.00"), Currency.USD),
        )
        account.add_card(card)
        assert account.active_card_count == 1

    def test_add_multiple_cards(self) -> None:
        account = _make_account()
        card1 = _make_card(account.id, card_name="Card A")
        card2 = _make_card(account.id, card_name="Card B")
        account.add_card(card1)
        account.add_card(card2)
        assert account.active_card_count == 2

    def test_increments_version(self) -> None:
        account = _make_account()
        old_version = account.version
        card = _make_card(account.id)
        account.add_card(card)
        assert account.version == old_version + 1


# ---------------------------------------------------------------------------
# TestRemoveCard
# ---------------------------------------------------------------------------


class TestRemoveCard:
    def test_removes_card_successfully(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        account.remove_card(card.id, owner_id, _retention())
        assert card.is_deleted()

    def test_emits_card_soft_deleted_event(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        account.remove_card(card.id, owner_id, _retention())
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CardSoftDeleted)
        assert event.card_id == card.id
        assert event.account_id == account.id
        assert event.deleted_by == owner_id

    def test_card_not_found(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        with pytest.raises(CardNotFoundError):
            account.remove_card(uuid.uuid4(), owner_id, _retention())

    def test_already_deleted_card(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        account.remove_card(card.id, owner_id, _retention())
        account.collect_events()
        with pytest.raises(AlreadyDeletedError):
            account.remove_card(card.id, owner_id, _retention())


# ---------------------------------------------------------------------------
# TestRecoverCard
# ---------------------------------------------------------------------------


class TestRecoverCard:
    def test_recovers_card_successfully(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card = _make_card(account.id)
        account.add_card(card)
        account.remove_card(card.id, owner_id, _retention())
        account.collect_events()

        account.recover_card(card.id)
        assert not card.is_deleted()

    def test_emits_card_recovered_event(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card = _make_card(account.id)
        account.add_card(card)
        account.remove_card(card.id, owner_id, _retention())
        account.collect_events()

        account.recover_card(card.id)
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CardRecovered)
        assert event.card_id == card.id
        assert event.account_id == account.id

    def test_recover_on_deleted_account(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        # Delete account (cascades to cards)
        account.soft_delete(owner_id, _retention())
        account.collect_events()

        with pytest.raises(AccountNotActiveError):
            account.recover_card(card.id)

    def test_recover_non_deleted_card(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        with pytest.raises(NotDeletedError):
            account.recover_card(card.id)


# ---------------------------------------------------------------------------
# TestUpdateCardMethods
# ---------------------------------------------------------------------------


class TestUpdateCardMethods:
    def test_update_card_name(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        account.update_card_name(card.id, "New Name")
        assert card.card_name == "New Name"
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CardUpdated)
        assert event.changed_fields == ["card_name"]

    def test_update_card_network(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        account.update_card_network(card.id, CardNetwork.VISA)
        assert card.card_network == CardNetwork.VISA
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CardUpdated)
        assert event.changed_fields == ["card_network"]

    def test_update_card_expiry(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        account.update_card_expiry(card.id, 6, 2028)
        assert card.expiry_month == 6
        assert card.expiry_year == 2028
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CardUpdated)
        assert event.changed_fields == ["expiry_month", "expiry_year"]

    def test_update_card_credit_limit(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        new_limit = Money(Decimal("3000.00"), Currency.USD)
        account.update_card_credit_limit(card.id, new_limit)
        assert card.credit_limit == new_limit
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CardUpdated)
        assert event.changed_fields == ["credit_limit"]

    def test_update_card_credit_limit_currency_mismatch(self) -> None:
        account = _make_account()  # USD account
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        eur_limit = Money(Decimal("3000.00"), Currency.EUR)
        with pytest.raises(CurrencyMismatchError):
            account.update_card_credit_limit(card.id, eur_limit)

    def test_update_card_issuing_institution(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        account.update_card_issuing_institution(card.id, "Chase Bank")
        assert card.issuing_institution == "Chase Bank"
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CardUpdated)
        assert event.changed_fields == ["issuing_institution"]

    def test_update_card_notes(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)
        account.collect_events()

        account.update_card_notes(card.id, "Primary card for groceries")
        assert card.notes == "Primary card for groceries"
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CardUpdated)
        assert event.changed_fields == ["notes"]

    def test_update_deleted_card_raises(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card = _make_card(account.id)
        account.add_card(card)
        account.remove_card(card.id, owner_id, _retention())
        account.collect_events()

        with pytest.raises(CardNotFoundError):
            account.update_card_name(card.id, "Should Fail")


# ---------------------------------------------------------------------------
# TestCardQueryMethods
# ---------------------------------------------------------------------------


class TestCardQueryMethods:
    def test_get_card_found(self) -> None:
        account = _make_account()
        card = _make_card(account.id)
        account.add_card(card)

        result = account.get_card(card.id)
        assert result is not None
        assert result.id == card.id

    def test_get_card_not_found(self) -> None:
        account = _make_account()
        result = account.get_card(uuid.uuid4())
        assert result is None

    def test_get_cards_excludes_deleted(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card1 = _make_card(account.id, card_name="Card A")
        card2 = _make_card(account.id, card_name="Card B")
        account.add_card(card1)
        account.add_card(card2)
        account.remove_card(card1.id, owner_id, _retention())
        account.collect_events()

        active_cards = account.get_cards()
        assert len(active_cards) == 1
        assert active_cards[0].id == card2.id

    def test_get_cards_include_deleted(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card1 = _make_card(account.id, card_name="Card A")
        card2 = _make_card(account.id, card_name="Card B")
        account.add_card(card1)
        account.add_card(card2)
        account.remove_card(card1.id, owner_id, _retention())
        account.collect_events()

        all_cards = account.get_cards(include_deleted=True)
        assert len(all_cards) == 2

    def test_active_card_count(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card1 = _make_card(account.id, card_name="Card A")
        card2 = _make_card(account.id, card_name="Card B")
        card3 = _make_card(account.id, card_name="Card C")
        account.add_card(card1)
        account.add_card(card2)
        account.add_card(card3)
        account.remove_card(card2.id, owner_id, _retention())
        account.collect_events()

        assert account.active_card_count == 2


# ---------------------------------------------------------------------------
# TestAccountSoftDeleteCascade
# ---------------------------------------------------------------------------


class TestAccountSoftDeleteCascade:
    def test_cascade_deletes_active_cards(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card1 = _make_card(account.id, card_name="Card A")
        card2 = _make_card(account.id, card_name="Card B")
        account.add_card(card1)
        account.add_card(card2)
        account.collect_events()

        account.soft_delete(owner_id, _retention())
        assert card1.is_deleted()
        assert card2.is_deleted()

    def test_cascade_does_not_emit_individual_card_events(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card1 = _make_card(account.id, card_name="Card A")
        card2 = _make_card(account.id, card_name="Card B")
        account.add_card(card1)
        account.add_card(card2)
        account.collect_events()

        account.soft_delete(owner_id, _retention())
        events = account.collect_events()
        # Only AccountSoftDeleted, no individual CardSoftDeleted events
        card_events = [e for e in events if isinstance(e, CardSoftDeleted)]
        assert len(card_events) == 0
        account_events = [e for e in events if isinstance(e, AccountSoftDeleted)]
        assert len(account_events) == 1

    def test_recover_does_not_recover_cards(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card1 = _make_card(account.id, card_name="Card A")
        card2 = _make_card(account.id, card_name="Card B")
        account.add_card(card1)
        account.add_card(card2)
        account.collect_events()

        account.soft_delete(owner_id, _retention())
        account.collect_events()
        account.recover()

        # Cards remain deleted after account recovery
        assert card1.is_deleted()
        assert card2.is_deleted()
        assert account.active_card_count == 0

    def test_cascade_skips_already_deleted_cards(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id=owner_id)
        card1 = _make_card(account.id, card_name="Card A")
        card2 = _make_card(account.id, card_name="Card B")
        account.add_card(card1)
        account.add_card(card2)
        # Delete card1 first
        account.remove_card(card1.id, owner_id, _retention())
        account.collect_events()

        # Then delete account -- should not error on already-deleted card1
        account.soft_delete(owner_id, _retention())
        assert card1.is_deleted()
        assert card2.is_deleted()
        assert account.is_deleted()
