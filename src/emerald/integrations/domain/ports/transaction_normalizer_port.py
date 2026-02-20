from typing import Protocol

from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)


class TransactionNormalizerPort(Protocol):
    """Domain port: raw provider data → NormalizedTransaction."""

    async def normalize(self, raw_data: str) -> NormalizedTransaction: ...
