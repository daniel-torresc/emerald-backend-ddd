import uuid
from dataclasses import dataclass, field
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class CardCreated(DomainEvent):
    """Emitted when a card is added to an account."""

    card_id: uuid.UUID = uuid.UUID(int=0)
    account_id: uuid.UUID = uuid.UUID(int=0)
    card_type: str = ""
    card_name: str = ""
    card_number_masked: str = ""
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class CardUpdated(DomainEvent):
    """Emitted when a card attribute is updated."""

    card_id: uuid.UUID = uuid.UUID(int=0)
    account_id: uuid.UUID = uuid.UUID(int=0)
    changed_fields: list[str] = field(default_factory=list)
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class CardSoftDeleted(DomainEvent):
    """Emitted when a card is soft-deleted."""

    card_id: uuid.UUID = uuid.UUID(int=0)
    account_id: uuid.UUID = uuid.UUID(int=0)
    deleted_by: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "account"


@dataclass(frozen=True)
class CardRecovered(DomainEvent):
    """Emitted when a soft-deleted card is recovered."""

    card_id: uuid.UUID = uuid.UUID(int=0)
    account_id: uuid.UUID = uuid.UUID(int=0)
    aggregate_type: ClassVar[str] = "account"
