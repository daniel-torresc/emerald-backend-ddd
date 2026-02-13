from enum import Enum


class ImportSourceType(Enum):
    """How a transaction was created."""

    MANUAL = "MANUAL"
    BANK_IMPORT = "BANK_IMPORT"
    BULK_IMPORT = "BULK_IMPORT"
    API = "API"
