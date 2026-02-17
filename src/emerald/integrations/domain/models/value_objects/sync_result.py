from dataclasses import dataclass

from emerald.integrations.domain.exceptions.connection_exceptions import (
    InvalidNormalizedTransactionError,
)


@dataclass(frozen=True)
class SyncResult:
    """Summary counts for a completed sync."""

    transactions_found: int
    transactions_imported: int
    transactions_duplicate: int
    transactions_staged: int

    def __post_init__(self) -> None:
        for field_name in (
            "transactions_found",
            "transactions_imported",
            "transactions_duplicate",
            "transactions_staged",
        ):
            if getattr(self, field_name) < 0:
                raise InvalidNormalizedTransactionError(f"{field_name} must be >= 0")

        total = self.transactions_imported + self.transactions_duplicate + self.transactions_staged
        if total != self.transactions_found:
            raise InvalidNormalizedTransactionError(
                f"imported ({self.transactions_imported}) + duplicate "
                f"({self.transactions_duplicate}) + staged ({self.transactions_staged}) "
                f"must equal found ({self.transactions_found})"
            )
