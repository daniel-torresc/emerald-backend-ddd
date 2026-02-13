from dataclasses import dataclass

from emerald.core_finance.domain.constants import MAX_CARD_NUMBER_LENGTH, MIN_CARD_NUMBER_LENGTH
from emerald.core_finance.domain.exceptions.card_exceptions import InvalidCardNumberError


@dataclass(frozen=True)
class CardNumber:
    """Full card number (PAN) with Luhn validation (ISO/IEC 7812).

    Stored as digits only. Provides masked display and last_four.
    """

    value: str
    last_four: str = ""

    def __post_init__(self) -> None:
        # 1. Normalize: strip whitespace, remove dashes and spaces
        normalized = self.value.replace("-", "").replace(" ", "").strip()

        # 2. Digits only
        if not normalized.isdigit():
            raise InvalidCardNumberError("Card number must contain only digits")

        # 3. Length check
        if len(normalized) < MIN_CARD_NUMBER_LENGTH:
            raise InvalidCardNumberError(
                f"Card number must be at least {MIN_CARD_NUMBER_LENGTH} digits, "
                f"got {len(normalized)}"
            )
        if len(normalized) > MAX_CARD_NUMBER_LENGTH:
            raise InvalidCardNumberError(
                f"Card number must be at most {MAX_CARD_NUMBER_LENGTH} digits, "
                f"got {len(normalized)}"
            )

        # 4. Luhn checksum (MOD-10)
        total = 0
        for i, digit in enumerate(reversed(normalized)):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        if total % 10 != 0:
            raise InvalidCardNumberError("Card number fails Luhn checksum validation")

        # 5. Store normalized value and derive last_four
        object.__setattr__(self, "value", normalized)
        object.__setattr__(self, "last_four", normalized[-4:])

    def masked(self) -> str:
        """Returns masked display, e.g. '****1234'."""
        return f"****{self.last_four}"

    def __str__(self) -> str:
        return self.value
