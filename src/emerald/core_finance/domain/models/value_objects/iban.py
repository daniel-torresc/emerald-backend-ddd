from dataclasses import dataclass

from emerald.core_finance.domain.exceptions import InvalidIBANError

_MIN_IBAN_LENGTH = 15
_MAX_IBAN_LENGTH = 34


@dataclass(frozen=True)
class IBAN:
    """International Bank Account Number (ISO 13616) with MOD-97 validation.

    Stored uppercase without spaces. Provides masked display and last_four.
    """

    value: str
    last_four: str = ""

    def __post_init__(self) -> None:
        # 1. Normalize: strip whitespace, uppercase
        normalized = "".join(self.value.split()).upper()

        # 2. Validate length
        if len(normalized) < _MIN_IBAN_LENGTH:
            raise InvalidIBANError(
                f"IBAN must be at least {_MIN_IBAN_LENGTH} characters, got {len(normalized)}"
            )
        if len(normalized) > _MAX_IBAN_LENGTH:
            raise InvalidIBANError(
                f"IBAN must be at most {_MAX_IBAN_LENGTH} characters, got {len(normalized)}"
            )

        # 3. Validate country code (first 2 chars are letters)
        if not normalized[:2].isalpha():
            raise InvalidIBANError("IBAN must start with a two-letter country code")

        # 4. Validate check digits (chars 3-4 are digits)
        if not normalized[2:4].isdigit():
            raise InvalidIBANError("IBAN check digits (positions 3-4) must be numeric")

        # 5. Validate remaining characters are alphanumeric
        if not normalized[4:].isalnum():
            raise InvalidIBANError("IBAN body must contain only alphanumeric characters")

        # 6. MOD-97 checksum per ISO 13616
        rearranged = normalized[4:] + normalized[:4]
        digit_string = ""
        for char in rearranged:
            if char.isdigit():
                digit_string += char
            else:
                digit_string += str(ord(char) - ord("A") + 10)
        if int(digit_string) % 97 != 1:
            raise InvalidIBANError("IBAN checksum validation failed (MOD-97)")

        # 7. Store normalized value and derive last_four
        object.__setattr__(self, "value", normalized)
        object.__setattr__(self, "last_four", normalized[-4:])

    def masked(self) -> str:
        """Returns masked display, e.g. '****1234'."""
        return f"****{self.last_four}"
