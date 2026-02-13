from enum import Enum


class CardNetwork(Enum):
    """Payment card network."""

    VISA = "VISA"
    MASTERCARD = "MASTERCARD"
    AMERICAN_EXPRESS = "AMERICAN_EXPRESS"
    DISCOVER = "DISCOVER"
    OTHER = "OTHER"
