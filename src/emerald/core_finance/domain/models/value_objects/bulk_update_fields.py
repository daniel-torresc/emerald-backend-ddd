from dataclasses import dataclass

from emerald.core_finance.domain.constants import (
    MAX_MERCHANT_LENGTH,
    MAX_USER_DESCRIPTION_LENGTH,
)
from emerald.core_finance.domain.exceptions.bulk_exceptions import EmptyBulkUpdateError
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    EmptyDescriptionError,
    InvalidMerchantError,
)
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus


class _UnsetType:
    """Sentinel type to distinguish 'not provided' from None."""

    _instance: "_UnsetType | None" = None

    def __new__(cls) -> "_UnsetType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "_UNSET"

    def __bool__(self) -> bool:
        return False


_UNSET = _UnsetType()


@dataclass(frozen=True)
class BulkUpdateFields:
    """Fields to apply in a bulk update. Uses _UNSET sentinel to mean 'don't change'."""

    review_status: ReviewStatus | _UnsetType = _UNSET
    user_description: str | None | _UnsetType = _UNSET
    merchant: str | None | _UnsetType = _UNSET

    def __post_init__(self) -> None:
        # At least one field must be set
        if (
            isinstance(self.review_status, _UnsetType)
            and isinstance(self.user_description, _UnsetType)
            and isinstance(self.merchant, _UnsetType)
        ):
            raise EmptyBulkUpdateError()

        # Validate user_description length when set and not None
        if not isinstance(self.user_description, _UnsetType) and self.user_description is not None:
            trimmed = self.user_description.strip()
            if not trimmed:
                raise EmptyDescriptionError("user_description cannot be empty")
            if len(trimmed) > MAX_USER_DESCRIPTION_LENGTH:
                raise EmptyDescriptionError(
                    f"user_description must not exceed {MAX_USER_DESCRIPTION_LENGTH} characters"
                )
            object.__setattr__(self, "user_description", trimmed)

        # Validate merchant length when set and not None
        if not isinstance(self.merchant, _UnsetType) and self.merchant is not None:
            trimmed = self.merchant.strip()
            if not trimmed:
                raise InvalidMerchantError("merchant cannot be empty")
            if len(trimmed) > MAX_MERCHANT_LENGTH:
                raise InvalidMerchantError(
                    f"merchant must not exceed {MAX_MERCHANT_LENGTH} characters"
                )
            object.__setattr__(self, "merchant", trimmed)
