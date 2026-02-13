import uuid
from dataclasses import dataclass
from decimal import Decimal

from emerald.shared_kernel.application.dtos.commands import Command

# -- Card Lifecycle Commands --------------------------------------------------


@dataclass(frozen=True)
class AddCard(Command):
    """Command to add a card to an account."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    card_type: str = ""
    card_name: str = ""
    card_number: str = ""
    expiry_month: int = 0
    expiry_year: int = 0
    card_network: str | None = None
    credit_limit_amount: Decimal | None = None
    credit_limit_currency: str | None = None
    issuing_institution: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class RemoveCard(Command):
    """Command to soft-delete a card."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    reason: str | None = None


@dataclass(frozen=True)
class RecoverCard(Command):
    """Command to recover a soft-deleted card."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)


# -- Card Update Commands -----------------------------------------------------


@dataclass(frozen=True)
class UpdateCardName(Command):
    """Command to update a card's display name."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    card_name: str = ""


@dataclass(frozen=True)
class UpdateCardNetwork(Command):
    """Command to update a card's network."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    card_network: str | None = None


@dataclass(frozen=True)
class UpdateCardExpiry(Command):
    """Command to update a card's expiration date."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    expiry_month: int = 0
    expiry_year: int = 0


@dataclass(frozen=True)
class UpdateCardCreditLimit(Command):
    """Command to update a card's credit limit."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    credit_limit_amount: Decimal | None = None
    credit_limit_currency: str | None = None


@dataclass(frozen=True)
class UpdateCardIssuingInstitution(Command):
    """Command to update a card's issuing institution."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    issuing_institution: str | None = None


@dataclass(frozen=True)
class UpdateCardNotes(Command):
    """Command to update a card's notes."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    notes: str | None = None


# -- Card-Transaction Linking Commands ----------------------------------------


@dataclass(frozen=True)
class LinkTransactionToCard(Command):
    """Command to link a transaction to a card."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)
    card_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class UnlinkTransactionFromCard(Command):
    """Command to unlink a transaction from its card."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
