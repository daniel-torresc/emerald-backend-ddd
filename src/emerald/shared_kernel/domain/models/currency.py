from enum import Enum


class Currency(Enum):
    """ISO 4217 currency enum with static members."""

    USD = ("USD", "$", "US Dollar", 2)
    EUR = ("EUR", "\u20ac", "Euro", 2)
    GBP = ("GBP", "\u00a3", "British Pound", 2)
    JPY = ("JPY", "\u00a5", "Japanese Yen", 0)
    CHF = ("CHF", "CHF", "Swiss Franc", 2)
    CAD = ("CAD", "C$", "Canadian Dollar", 2)
    AUD = ("AUD", "A$", "Australian Dollar", 2)
    MXN = ("MXN", "MX$", "Mexican Peso", 2)
    BRL = ("BRL", "R$", "Brazilian Real", 2)
    CNY = ("CNY", "\u00a5", "Chinese Yuan", 2)

    def __init__(self, code: str, symbol: str, currency_name: str, decimal_places: int) -> None:
        self.code = code
        self.symbol = symbol
        self.currency_name = currency_name
        self.decimal_places = decimal_places

    @property
    def name(self) -> str:
        return self.currency_name
