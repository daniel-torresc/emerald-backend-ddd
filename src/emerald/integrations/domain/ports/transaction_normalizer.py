from typing import Protocol

from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)


class TransactionNormalizer(Protocol):
    """Domain port: raw provider data → NormalizedTransaction."""

    def normalize(self, raw_data: str) -> NormalizedTransaction: ...
