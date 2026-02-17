from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from emerald.integrations.domain.constants import MAX_DESCRIPTION_LENGTH, MAX_MERCHANT_LENGTH
from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidNormalizedTransactionError,
)


@dataclass(frozen=True)
class NormalizedTransaction:
    """Provider-agnostic representation of a bank transaction."""

    transaction_date: date
    amount: Decimal
    currency_code: str
    description: str
    external_id: str
    value_date: date | None = None
    merchant: str | None = None

    def __post_init__(self) -> None:
        if self.amount == Decimal("0"):
            raise InvalidNormalizedTransactionError("Amount must be non-zero")

        code = self.currency_code
        if not code or len(code) != 3 or not code.isupper():
            raise InvalidNormalizedTransactionError(
                "Currency code must be 3 uppercase characters (ISO 4217)"
            )

        desc = self.description.strip()
        if not desc:
            raise InvalidNormalizedTransactionError("Description is required")
        if len(desc) > MAX_DESCRIPTION_LENGTH:
            raise InvalidNormalizedTransactionError(
                f"Description must not exceed {MAX_DESCRIPTION_LENGTH} characters"
            )
        object.__setattr__(self, "description", desc)

        ext_id = self.external_id.strip()
        if not ext_id:
            raise InvalidNormalizedTransactionError("External ID is required")
        object.__setattr__(self, "external_id", ext_id)

        if self.merchant is not None:
            merchant = self.merchant.strip()
            if len(merchant) > MAX_MERCHANT_LENGTH:
                raise InvalidNormalizedTransactionError(
                    f"Merchant must not exceed {MAX_MERCHANT_LENGTH} characters"
                )
            object.__setattr__(self, "merchant", merchant if merchant else None)
