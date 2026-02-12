import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class AccountCreated(DomainEvent):
    """Emitted when a new account is created."""

    owner_user_id: uuid.UUID = uuid.UUID(int=0)
    currency_code: str = ""
    account_name: str = ""
    opening_balance: Decimal = Decimal("0")
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class AccountUpdated(DomainEvent):
    """Emitted when an account attribute is updated."""

    updated_by: uuid.UUID = uuid.UUID(int=0)
    changed_fields: frozenset[str] = frozenset()
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class AccountSoftDeleted(DomainEvent):
    """Emitted when an account is soft-deleted."""

    deleted_by: uuid.UUID = uuid.UUID(int=0)
    reason: str | None = None
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class AccountRecovered(DomainEvent):
    """Emitted when a soft-deleted account is recovered."""

    recovered_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "account"
