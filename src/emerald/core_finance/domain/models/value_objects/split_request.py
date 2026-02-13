from __future__ import annotations

from dataclasses import dataclass

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
from emerald.shared_kernel.domain.models.value_objects.money import Money


@dataclass(frozen=True)
class SplitRequest:
    """A single portion of a split operation."""

    amount: Money
    description: str
    merchant: str | None = None
    comments: str | None = None

    def __post_init__(self) -> None:
        # Trim and validate description
        trimmed_desc = self.description.strip()
        if not trimmed_desc:
            raise EmptyDescriptionError("description cannot be empty")
        if len(trimmed_desc) > MAX_ORIGINAL_DESCRIPTION_LENGTH:
            raise EmptyDescriptionError(
                f"description must not exceed {MAX_ORIGINAL_DESCRIPTION_LENGTH} characters"
            )
        object.__setattr__(self, "description", trimmed_desc)

        # Trim and validate merchant
        if self.merchant is not None:
            trimmed_merchant = self.merchant.strip()
            if not trimmed_merchant:
                object.__setattr__(self, "merchant", None)
            elif len(trimmed_merchant) > MAX_MERCHANT_LENGTH:
                raise InvalidMerchantError(
                    f"merchant must not exceed {MAX_MERCHANT_LENGTH} characters"
                )
            else:
                object.__setattr__(self, "merchant", trimmed_merchant)

        # Trim and validate comments
        if self.comments is not None:
            trimmed_comments = self.comments.strip()
            if not trimmed_comments:
                object.__setattr__(self, "comments", None)
            elif len(trimmed_comments) > MAX_COMMENTS_LENGTH:
                raise InvalidCommentsError(
                    f"comments must not exceed {MAX_COMMENTS_LENGTH} characters"
                )
            else:
                object.__setattr__(self, "comments", trimmed_comments)
