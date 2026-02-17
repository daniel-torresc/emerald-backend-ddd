import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class TransactionMatch:
    """Potential match for deduplication checking."""

    transaction_id: uuid.UUID
    transaction_date: date
    amount: Decimal
    description: str
    external_id: str | None = None
