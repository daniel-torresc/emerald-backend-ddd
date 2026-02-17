import enum


class UncategorizationReason(enum.StrEnum):
    """Reason why a transaction lost its categorization."""

    MANUAL = "manual"
    TERM_DELETED = "term_deleted"
    TAXONOMY_DELETED = "taxonomy_deleted"
    TRANSACTION_DELETED = "transaction_deleted"
