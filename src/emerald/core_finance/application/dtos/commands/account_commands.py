import uuid
from dataclasses import dataclass
from decimal import Decimal

from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class CreateAccount(Command):
    """Command to create a new account."""

    owner_user_id: uuid.UUID = uuid.UUID(int=0)
    owner_display_name: str = ""
    account_name: str = ""
    currency_code: str = ""
    opening_balance: Decimal = Decimal("0")
    account_type_id: uuid.UUID = uuid.UUID(int=0)
    financial_institution_id: uuid.UUID = uuid.UUID(int=0)
    iban: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class RenameAccount(Command):
    """Command to rename an account."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    new_name: str = ""


@dataclass(frozen=True)
class UpdateAccountType(Command):
    """Command to update an account's type."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    account_type_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class UpdateFinancialInstitution(Command):
    """Command to update an account's financial institution."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    financial_institution_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True)
class UpdateAccountNotes(Command):
    """Command to update an account's notes."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    notes: str | None = None


@dataclass(frozen=True)
class SoftDeleteAccount(Command):
    """Command to soft-delete an account."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    reason: str | None = None


@dataclass(frozen=True)
class RecoverAccount(Command):
    """Command to recover a soft-deleted account."""

    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
