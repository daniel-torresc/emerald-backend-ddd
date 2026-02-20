import uuid

from emerald.integrations.application.ports.outbound.transaction_import_port import (
    TransactionImportPort,
)
from emerald.integrations.domain.constants import AMOUNT_TOLERANCE
from emerald.integrations.domain.models.value_objects.deduplication_result import (
    DeduplicationResult,
)
from emerald.integrations.domain.models.value_objects.match_status import MatchStatus
from emerald.integrations.domain.models.value_objects.normalized_transaction import (
    NormalizedTransaction,
)


class DeduplicationService:
    """Application service implementing the 4-tier deduplication algorithm."""

    def __init__(self, transaction_import_port: TransactionImportPort) -> None:
        self._port = transaction_import_port

    async def check(
        self, normalized: NormalizedTransaction, account_id: uuid.UUID
    ) -> DeduplicationResult:
        """Check a normalized transaction against existing transactions."""
        # 1. Exact external_id match
        if await self._port.find_by_external_id(account_id, normalized.external_id):
            return DeduplicationResult(
                match_status=MatchStatus.DUPLICATE,
                confidence=1.0,
                match_reason="Exact external_id match",
            )

        # 2-3. Date + amount matching
        matches = await self._port.find_by_date_and_amount(
            account_id,
            normalized.transaction_date,
            normalized.amount,
            normalized.description,
        )

        # 2. Exact date + amount + description
        exact_matches = [m for m in matches if m.description == normalized.description]
        if exact_matches:
            return DeduplicationResult(
                match_status=MatchStatus.DUPLICATE,
                confidence=0.95,
                match_reason="Exact date + amount + description",
                matched_transaction_id=exact_matches[0].transaction_id,
            )

        # 3. Fuzzy date + approximate amount
        fuzzy_matches = [
            m for m in matches if abs(m.amount - normalized.amount) <= AMOUNT_TOLERANCE
        ]
        if fuzzy_matches:
            return DeduplicationResult(
                match_status=MatchStatus.NEEDS_REVIEW,
                confidence=0.6,
                match_reason="Same date + approximate amount",
                matched_transaction_id=fuzzy_matches[0].transaction_id,
            )

        # 4. No match
        return DeduplicationResult(
            match_status=MatchStatus.NEW,
            confidence=0.0,
            match_reason="No matching transaction found",
        )
