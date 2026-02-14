import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from emerald.core_finance.domain.constants import (
    MAX_COMMENTS_LENGTH,
    MAX_MERCHANT_LENGTH,
    MAX_ORIGINAL_DESCRIPTION_LENGTH,
)
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    EmptyDescriptionError,
    InvalidCommentsError,
    InvalidMerchantError,
)
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus


@dataclass(frozen=True)
class TransactionInput:
    """A single item in a bulk create request."""

    transaction_date: date
    amount: Decimal
    original_description: str
    value_date: date | None = None
    merchant: str | None = None
    comments: str | None = None
    review_status: ReviewStatus = ReviewStatus.TO_REVIEW
    external_id: str | None = None
    card_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        # Trim and validate original_description
        trimmed_desc = self.original_description.strip()
        if not trimmed_desc:
            raise EmptyDescriptionError("original_description cannot be empty")
        if len(trimmed_desc) > MAX_ORIGINAL_DESCRIPTION_LENGTH:
            raise EmptyDescriptionError(
                f"original_description must not exceed {MAX_ORIGINAL_DESCRIPTION_LENGTH} characters"
            )
        object.__setattr__(self, "original_description", trimmed_desc)

        # Trim and validate merchant
        if self.merchant is not None:
            trimmed = self.merchant.strip()
            if not trimmed:
                raise InvalidMerchantError("merchant cannot be empty")
            if len(trimmed) > MAX_MERCHANT_LENGTH:
                raise InvalidMerchantError(
                    f"merchant must not exceed {MAX_MERCHANT_LENGTH} characters"
                )
            object.__setattr__(self, "merchant", trimmed)

        # Trim and validate comments
        if self.comments is not None:
            trimmed = self.comments.strip()
            if not trimmed:
                raise InvalidCommentsError("comments cannot be empty")
            if len(trimmed) > MAX_COMMENTS_LENGTH:
                raise InvalidCommentsError(
                    f"comments must not exceed {MAX_COMMENTS_LENGTH} characters"
                )
            object.__setattr__(self, "comments", trimmed)

        # Trim external_id
        if self.external_id is not None:
            trimmed = self.external_id.strip()
            if trimmed != self.external_id:
                object.__setattr__(self, "external_id", trimmed)
