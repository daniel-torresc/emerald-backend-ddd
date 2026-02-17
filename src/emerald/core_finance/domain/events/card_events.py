import uuid
from dataclasses import dataclass

from emerald.core_finance.domain.events.base import AccountEvent


@dataclass(frozen=True)
class CardCreated(AccountEvent):
    """Emitted when a card is added to an account."""

    card_id: uuid.UUID
    account_id: uuid.UUID
    card_type: str
    card_name: str
    card_number_masked: str


@dataclass(frozen=True)
class CardUpdated(AccountEvent):
    """Emitted when a card attribute is updated."""

    card_id: uuid.UUID
    account_id: uuid.UUID
    changed_fields: frozenset[str]


@dataclass(frozen=True)
class CardSoftDeleted(AccountEvent):
    """Emitted when a card is soft-deleted."""

    card_id: uuid.UUID
    account_id: uuid.UUID
    deleted_by: uuid.UUID


@dataclass(frozen=True)
class CardRecovered(AccountEvent):
    """Emitted when a soft-deleted card is recovered."""

    card_id: uuid.UUID
    account_id: uuid.UUID
