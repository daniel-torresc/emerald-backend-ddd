from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any

from emerald.shared_kernel.exceptions import CurrencyMismatchError, InvalidValueError
from emerald.shared_kernel.value_objects.currency import Currency


@dataclass(frozen=True)
class Money:
    """A monetary amount paired with its currency. Immutable."""

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidValueError(
                f"Money amount must be Decimal, got {type(self.amount).__name__}"
            )
        if not self.amount.is_finite():
            raise InvalidValueError(f"Money amount must be finite, got {self.amount}")

    @classmethod
    def zero(cls, currency: Currency) -> "Money":
        """Create zero-amount Money."""
        return cls(Decimal("0"), currency)

    def _ensure_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot operate on {self.currency.code} and {other.currency.code}"
            )

    def __add__(self, other: Any) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Any) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return self.amount >= other.amount

    def is_zero(self) -> bool:
        return self.amount == Decimal("0")

    def is_positive(self) -> bool:
        return self.amount > Decimal("0")

    def is_negative(self) -> bool:
        return self.amount < Decimal("0")

    def round_to_currency(self) -> "Money":
        """Round to currency's decimal places using Banker's rounding."""
        try:
            quantize_exp = Decimal(10) ** -self.currency.decimal_places
        except InvalidOperation:
            quantize_exp = Decimal("1")
        rounded = self.amount.quantize(quantize_exp, rounding=ROUND_HALF_EVEN)
        return Money(rounded, self.currency)
