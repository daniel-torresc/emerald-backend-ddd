from emerald.shared_kernel.domain.exceptions import (
    InvalidValueError,
    InvariantViolationError,
    NotFoundError,
)


class InvalidCardNumberError(InvalidValueError):
    """Card number fails validation (non-numeric, wrong length, Luhn checksum failure)."""

    def __init__(
        self, message: str = "Invalid card number", code: str = "INVALID_CARD_NUMBER"
    ) -> None:
        super().__init__(message, code)


class InvalidCardDataError(InvalidValueError):
    """Invalid card name (empty/too long) or invalid expiry month/year."""

    def __init__(self, message: str = "Invalid card data", code: str = "INVALID_CARD_DATA") -> None:
        super().__init__(message, code)


class InvalidCreditLimitError(InvalidValueError):
    """Credit limit is zero or negative."""

    def __init__(
        self, message: str = "Invalid credit limit", code: str = "INVALID_CREDIT_LIMIT"
    ) -> None:
        super().__init__(message, code)


class CardNotFoundError(NotFoundError):
    """Card doesn't exist in account or is deleted."""

    def __init__(self, message: str = "Card not found", code: str = "CARD_NOT_FOUND") -> None:
        super().__init__(message, code)


class MaxCardsReachedError(InvariantViolationError):
    """Account already has MAX_CARDS_PER_ACCOUNT active cards."""

    def __init__(
        self, message: str = "Maximum cards per account reached", code: str = "MAX_CARDS_REACHED"
    ) -> None:
        super().__init__(message, code)


class CurrencyMismatchError(InvariantViolationError):
    """Credit limit currency differs from account currency."""

    def __init__(
        self,
        message: str = "Credit limit currency does not match account currency",
        code: str = "CARD_CURRENCY_MISMATCH",
    ) -> None:
        super().__init__(message, code)
