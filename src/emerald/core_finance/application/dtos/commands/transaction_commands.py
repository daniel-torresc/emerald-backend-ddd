import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class CreateTransaction(Command):
    """Command to create a new transaction."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_date: date = date(2000, 1, 1)
    amount: Decimal = Decimal("0")
    currency_code: str = ""
    original_description: str = ""
    value_date: date | None = None
    merchant: str | None = None
    comments: str | None = None
    import_source_type: str = "MANUAL"
    source_id: str | None = None
    external_id: str | None = None


@dataclass(frozen=True)
class UpdateTransactionDescription(Command):
    """Command to update a transaction's user description."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)
    user_description: str | None = None


@dataclass(frozen=True)
class UpdateTransactionMerchant(Command):
    """Command to update a transaction's merchant."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)
    merchant: str | None = None


@dataclass(frozen=True)
class UpdateTransactionComments(Command):
    """Command to update a transaction's comments."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)
    comments: str | None = None


@dataclass(frozen=True)
class UpdateTransactionDates(Command):
    """Command to update a transaction's dates."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)
    transaction_date: date | None = None
    value_date: date | None = None


@dataclass(frozen=True)
class UpdateTransactionAmount(Command):
    """Command to update a transaction's amount."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)
    amount: Decimal = Decimal("0")
    currency_code: str = ""


@dataclass(frozen=True)
class ReviewTransaction(Command):
    """Command to mark a transaction as reviewed."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class UnreviewTransaction(Command):
    """Command to mark a transaction as needing review."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class SoftDeleteTransaction(Command):
    """Command to soft-delete a transaction."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)
    reason: str | None = None


@dataclass(frozen=True)
class RecoverTransaction(Command):
    """Command to recover a soft-deleted transaction."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    transaction_id: uuid.UUID = uuid.UUID(int=0)
