from enum import Enum


class DeletableEntityType(Enum):
    """Central registry of all entity types that support soft delete."""

    USER = "USER"
    FINANCIAL_ACCOUNT = "FINANCIAL_ACCOUNT"
    TRANSACTION = "TRANSACTION"
    CARD = "CARD"
    ACCOUNT_SHARE = "ACCOUNT_SHARE"
    TAXONOMY = "TAXONOMY"
    TAXONOMY_TERM = "TAXONOMY_TERM"
    BANK_CONNECTION = "BANK_CONNECTION"
