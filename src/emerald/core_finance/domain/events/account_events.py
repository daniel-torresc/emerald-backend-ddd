import uuid
from dataclasses import dataclass
from decimal import Decimal

from emerald.core_finance.domain.events.base import AccountEvent


@dataclass(frozen=True)
class AccountCreated(AccountEvent):
    """Emitted when a new account is created."""

    owner_user_id: uuid.UUID
    currency_code: str
    account_name: str
    opening_balance: Decimal


@dataclass(frozen=True)
class AccountUpdated(AccountEvent):
    """Emitted when an account attribute is updated."""

    updated_by: uuid.UUID
    changed_fields: frozenset[str]


@dataclass(frozen=True)
class AccountSoftDeleted(AccountEvent):
    """Emitted when an account is soft-deleted."""

    deleted_by: uuid.UUID
    reason: str | None = None


@dataclass(frozen=True)
class AccountRecovered(AccountEvent):
    """Emitted when a soft-deleted account is recovered."""

    recovered_by: uuid.UUID
