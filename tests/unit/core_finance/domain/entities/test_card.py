from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.exceptions.card_exceptions import (
    InvalidCardDataError,
    InvalidCreditLimitError,
)
from emerald.core_finance.domain.models.entities.card import Card
from emerald.core_finance.domain.models.value_objects.card_network import CardNetwork
from emerald.core_finance.domain.models.value_objects.card_number import CardNumber
from emerald.core_finance.domain.models.value_objects.card_type import CardType
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)


def _make_card(**overrides: Any) -> Card:
    defaults: dict[str, Any] = {
        "account_id": uuid.uuid4(),
        "card_type": CardType.CREDIT,
        "card_name": "My Card",
        "card_number": CardNumber("4111111111111111"),
        "expiry_month": 12,
        "expiry_year": 2030,
    }
    defaults.update(overrides)
    return Card.create(**defaults)


def _default_retention() -> RetentionPeriod:
    return RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)


class TestCardCreate:
    def test_creates_with_defaults(self) -> None:
        card = _make_card()
        assert isinstance(card.id, uuid.UUID)
        assert card.card_name == "My Card"
        assert card.card_type == CardType.CREDIT
        assert card.card_number == CardNumber("4111111111111111")
        assert card.expiry_month == 12
        assert card.expiry_year == 2030
        assert card.card_network is None
        assert card.credit_limit is None
        assert card.issuing_institution is None
        assert card.notes is None

    def test_creates_with_all_optional_fields(self) -> None:
        limit = Money(Decimal("5000.00"), Currency.USD)
        card = _make_card(
            card_network=CardNetwork.VISA,
            credit_limit=limit,
            issuing_institution="Chase Bank",
            notes="Primary card",
        )
        assert card.card_network == CardNetwork.VISA
        assert card.credit_limit == limit
        assert card.issuing_institution == "Chase Bank"
        assert card.notes == "Primary card"

    def test_card_name_is_trimmed(self) -> None:
        card = _make_card(card_name="  My Card  ")
        assert card.card_name == "My Card"

    def test_timestamps_set(self) -> None:
        card = _make_card()
        assert card.created_at is not None
        assert card.updated_at is not None

    def test_id_is_uuid(self) -> None:
        card = _make_card()
        assert isinstance(card.id, uuid.UUID)


class TestCardImmutableFields:
    def test_account_id_is_property(self) -> None:
        card = _make_card()
        with pytest.raises(AttributeError):
            card.account_id = uuid.uuid4()  # type: ignore[misc]

    def test_card_type_is_property(self) -> None:
        card = _make_card()
        with pytest.raises(AttributeError):
            card.card_type = CardType.DEBIT  # type: ignore[misc]

    def test_card_number_is_property(self) -> None:
        card = _make_card()
        with pytest.raises(AttributeError):
            card.card_number = CardNumber("5500000000000004")  # type: ignore[misc]


class TestCardCreateValidation:
    def test_empty_name_raises(self) -> None:
        with pytest.raises(InvalidCardDataError, match="empty"):
            _make_card(card_name="")

    def test_name_exceeding_max_raises(self) -> None:
        with pytest.raises(InvalidCardDataError, match="exceed"):
            _make_card(card_name="A" * 101)

    def test_expiry_month_zero_raises(self) -> None:
        with pytest.raises(InvalidCardDataError, match="month"):
            _make_card(expiry_month=0)

    def test_expiry_month_thirteen_raises(self) -> None:
        with pytest.raises(InvalidCardDataError, match="month"):
            _make_card(expiry_month=13)

    def test_expiry_year_too_old_raises(self) -> None:
        too_old_year = datetime.now(UTC).year - 11
        with pytest.raises(InvalidCardDataError, match="year"):
            _make_card(expiry_year=too_old_year)

    def test_credit_limit_zero_raises(self) -> None:
        with pytest.raises(InvalidCreditLimitError, match="positive"):
            _make_card(credit_limit=Money(Decimal("0"), Currency.USD))

    def test_credit_limit_negative_raises(self) -> None:
        with pytest.raises(InvalidCreditLimitError, match="positive"):
            _make_card(credit_limit=Money(Decimal("-100.00"), Currency.USD))

    def test_issuing_institution_exceeding_max_raises(self) -> None:
        with pytest.raises(InvalidCardDataError, match="exceed"):
            _make_card(issuing_institution="A" * 201)

    def test_notes_exceeding_max_raises(self) -> None:
        with pytest.raises(InvalidCardDataError, match="exceed"):
            _make_card(notes="A" * 501)


class TestCardUpdateName:
    def test_updates_name(self) -> None:
        card = _make_card()
        card.update_name("New Name")
        assert card.card_name == "New Name"

    def test_empty_name_raises(self) -> None:
        card = _make_card()
        with pytest.raises(InvalidCardDataError, match="empty"):
            card.update_name("")

    def test_name_exceeding_max_raises(self) -> None:
        card = _make_card()
        with pytest.raises(InvalidCardDataError, match="exceed"):
            card.update_name("A" * 101)

    def test_trims_name(self) -> None:
        card = _make_card()
        card.update_name("  Trimmed  ")
        assert card.card_name == "Trimmed"

    def test_touches_updated_at(self) -> None:
        card = _make_card()
        old_updated_at = card.updated_at
        card.update_name("New Name")
        assert card.updated_at >= old_updated_at


class TestCardUpdateNetwork:
    def test_accepts_card_network(self) -> None:
        card = _make_card()
        card.update_network(CardNetwork.MASTERCARD)
        assert card.card_network == CardNetwork.MASTERCARD

    def test_accepts_none(self) -> None:
        card = _make_card(card_network=CardNetwork.VISA)
        card.update_network(None)
        assert card.card_network is None

    def test_touches_updated_at(self) -> None:
        card = _make_card()
        old_updated_at = card.updated_at
        card.update_network(CardNetwork.VISA)
        assert card.updated_at >= old_updated_at


class TestCardUpdateExpiry:
    def test_updates_expiry(self) -> None:
        card = _make_card(expiry_month=6, expiry_year=2028)
        card.update_expiry(11, 2031)
        assert card.expiry_month == 11
        assert card.expiry_year == 2031

    def test_invalid_month_raises(self) -> None:
        card = _make_card()
        with pytest.raises(InvalidCardDataError, match="month"):
            card.update_expiry(0, 2030)

    def test_invalid_year_raises(self) -> None:
        card = _make_card()
        too_old_year = datetime.now(UTC).year - 11
        with pytest.raises(InvalidCardDataError, match="year"):
            card.update_expiry(6, too_old_year)

    def test_touches_updated_at(self) -> None:
        card = _make_card()
        old_updated_at = card.updated_at
        card.update_expiry(1, 2031)
        assert card.updated_at >= old_updated_at


class TestCardUpdateCreditLimit:
    def test_updates_with_money(self) -> None:
        card = _make_card()
        limit = Money(Decimal("10000.00"), Currency.USD)
        card.update_credit_limit(limit)
        assert card.credit_limit == limit

    def test_clears_with_none(self) -> None:
        card = _make_card(credit_limit=Money(Decimal("5000.00"), Currency.USD))
        card.update_credit_limit(None)
        assert card.credit_limit is None

    def test_positive_validation_raises(self) -> None:
        card = _make_card()
        with pytest.raises(InvalidCreditLimitError, match="positive"):
            card.update_credit_limit(Money(Decimal("0"), Currency.USD))

    def test_touches_updated_at(self) -> None:
        card = _make_card()
        old_updated_at = card.updated_at
        card.update_credit_limit(Money(Decimal("3000.00"), Currency.USD))
        assert card.updated_at >= old_updated_at


class TestCardUpdateIssuingInstitution:
    def test_updates_institution(self) -> None:
        card = _make_card()
        card.update_issuing_institution("Wells Fargo")
        assert card.issuing_institution == "Wells Fargo"

    def test_clears_with_none(self) -> None:
        card = _make_card(issuing_institution="Chase Bank")
        card.update_issuing_institution(None)
        assert card.issuing_institution is None

    def test_exceeding_max_raises(self) -> None:
        card = _make_card()
        with pytest.raises(InvalidCardDataError, match="exceed"):
            card.update_issuing_institution("A" * 201)

    def test_trims_institution(self) -> None:
        card = _make_card()
        card.update_issuing_institution("  Wells Fargo  ")
        assert card.issuing_institution == "Wells Fargo"

    def test_touches_updated_at(self) -> None:
        card = _make_card()
        old_updated_at = card.updated_at
        card.update_issuing_institution("Bank of America")
        assert card.updated_at >= old_updated_at


class TestCardUpdateNotes:
    def test_updates_notes(self) -> None:
        card = _make_card()
        card.update_notes("My notes")
        assert card.notes == "My notes"

    def test_clears_with_none(self) -> None:
        card = _make_card(notes="Old notes")
        card.update_notes(None)
        assert card.notes is None

    def test_exceeding_max_raises(self) -> None:
        card = _make_card()
        with pytest.raises(InvalidCardDataError, match="exceed"):
            card.update_notes("A" * 501)

    def test_trims_notes(self) -> None:
        card = _make_card()
        card.update_notes("  My notes  ")
        assert card.notes == "My notes"

    def test_touches_updated_at(self) -> None:
        card = _make_card()
        old_updated_at = card.updated_at
        card.update_notes("New notes")
        assert card.updated_at >= old_updated_at


class TestCardLifecycle:
    def test_soft_delete_sets_deleted_at(self) -> None:
        card = _make_card()
        card.soft_delete(deleted_by=uuid.uuid4(), retention=_default_retention())
        assert card.is_deleted()
        assert card.deleted_at is not None

    def test_recover_clears_deleted_at(self) -> None:
        card = _make_card()
        card.soft_delete(deleted_by=uuid.uuid4(), retention=_default_retention())
        card.recover()
        assert not card.is_deleted()
        assert card.deleted_at is None
