from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from emerald.core_finance.domain.constants import (
    MAX_CARD_ISSUING_INSTITUTION_LENGTH,
    MAX_CARD_NAME_LENGTH,
    MAX_CARD_NOTES_LENGTH,
    MIN_CARD_EXPIRY_YEAR_OFFSET,
)
from emerald.core_finance.domain.exceptions.card_exceptions import (
    InvalidCardDataError,
    InvalidCreditLimitError,
)
from emerald.core_finance.domain.models.value_objects.card_network import CardNetwork
from emerald.core_finance.domain.models.value_objects.card_number import CardNumber
from emerald.core_finance.domain.models.value_objects.card_type import CardType
from emerald.shared_kernel.domain.models.base.entity import Entity
from emerald.shared_kernel.domain.models.base.soft_deletable import SoftDeletableMixin
from emerald.shared_kernel.domain.models.base.timestamped import TimestampedMixin
from emerald.shared_kernel.domain.models.value_objects.money import Money


class Card(SoftDeletableMixin, TimestampedMixin, Entity):
    """A payment card linked to a financial account (child entity of Account)."""

    def __init__(
        self,
        *,
        account_id: uuid.UUID,
        card_type: CardType,
        card_name: str,
        card_number: CardNumber,
        expiry_month: int,
        expiry_year: int,
        card_network: CardNetwork | None = None,
        credit_limit: Money | None = None,
        issuing_institution: str | None = None,
        notes: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._account_id = account_id
        self._card_type = card_type
        self.card_name = card_name
        self._card_number = card_number
        self.expiry_month = expiry_month
        self.expiry_year = expiry_year
        self.card_network = card_network
        self.credit_limit = credit_limit
        self.issuing_institution = issuing_institution
        self.notes = notes

    # -- Immutable properties --------------------------------------------------

    @property
    def account_id(self) -> uuid.UUID:
        return self._account_id

    @property
    def card_type(self) -> CardType:
        return self._card_type

    @property
    def card_number(self) -> CardNumber:
        return self._card_number

    # -- Factory ---------------------------------------------------------------

    @classmethod
    def create(
        cls,
        account_id: uuid.UUID,
        card_type: CardType,
        card_name: str,
        card_number: CardNumber,
        expiry_month: int,
        expiry_year: int,
        card_network: CardNetwork | None = None,
        credit_limit: Money | None = None,
        issuing_institution: str | None = None,
        notes: str | None = None,
    ) -> Card:
        """Create a new Card with all invariants validated."""
        card_name = cls._validate_name(card_name)
        cls._validate_expiry(expiry_month, expiry_year)
        if credit_limit is not None:
            cls._validate_credit_limit(credit_limit)
        if issuing_institution is not None:
            issuing_institution = cls._validate_issuing_institution(issuing_institution)
        if notes is not None:
            notes = cls._validate_notes(notes)

        return cls(
            id=uuid.uuid4(),
            account_id=account_id,
            card_type=card_type,
            card_name=card_name,
            card_number=card_number,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            card_network=card_network,
            credit_limit=credit_limit,
            issuing_institution=issuing_institution,
            notes=notes,
        )

    # -- Update methods --------------------------------------------------------

    def update_name(self, card_name: str) -> None:
        """Update card display name."""
        self.card_name = self._validate_name(card_name)
        self._touch()

    def update_network(self, card_network: CardNetwork | None) -> None:
        """Update card network."""
        self.card_network = card_network
        self._touch()

    def update_expiry(self, month: int, year: int) -> None:
        """Update expiration date."""
        self._validate_expiry(month, year)
        self.expiry_month = month
        self.expiry_year = year
        self._touch()

    def update_credit_limit(self, credit_limit: Money | None) -> None:
        """Update credit limit. Currency match validated by Account."""
        if credit_limit is not None:
            self._validate_credit_limit(credit_limit)
        self.credit_limit = credit_limit
        self._touch()

    def update_issuing_institution(self, institution: str | None) -> None:
        """Update issuing institution name."""
        if institution is not None:
            institution = self._validate_issuing_institution(institution)
        self.issuing_institution = institution
        self._touch()

    def update_notes(self, notes: str | None) -> None:
        """Update card notes."""
        if notes is not None:
            notes = self._validate_notes(notes)
        self.notes = notes
        self._touch()

    # -- Private validation helpers --------------------------------------------

    @staticmethod
    def _validate_name(card_name: str) -> str:
        trimmed = card_name.strip()
        if not trimmed:
            raise InvalidCardDataError("Card name cannot be empty")
        if len(trimmed) > MAX_CARD_NAME_LENGTH:
            raise InvalidCardDataError(
                f"Card name must not exceed {MAX_CARD_NAME_LENGTH} characters"
            )
        return trimmed

    @staticmethod
    def _validate_expiry(month: int, year: int) -> None:
        if month < 1 or month > 12:
            raise InvalidCardDataError(f"Expiry month must be between 1 and 12, got {month}")
        min_year = datetime.now(UTC).year + MIN_CARD_EXPIRY_YEAR_OFFSET
        if year < min_year:
            raise InvalidCardDataError(f"Expiry year must be >= {min_year}, got {year}")

    @staticmethod
    def _validate_credit_limit(credit_limit: Money) -> None:
        if credit_limit.amount <= Decimal("0"):
            raise InvalidCreditLimitError("Credit limit must be positive")

    @staticmethod
    def _validate_issuing_institution(institution: str) -> str:
        trimmed = institution.strip()
        if len(trimmed) > MAX_CARD_ISSUING_INSTITUTION_LENGTH:
            raise InvalidCardDataError(
                f"Issuing institution must not exceed "
                f"{MAX_CARD_ISSUING_INSTITUTION_LENGTH} characters"
            )
        return trimmed

    @staticmethod
    def _validate_notes(notes: str) -> str:
        trimmed = notes.strip()
        if len(trimmed) > MAX_CARD_NOTES_LENGTH:
            raise InvalidCardDataError(
                f"Card notes must not exceed {MAX_CARD_NOTES_LENGTH} characters"
            )
        return trimmed
