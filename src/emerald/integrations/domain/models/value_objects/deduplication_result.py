import uuid
from dataclasses import dataclass

from emerald.integrations.domain.models.value_objects.match_status import MatchStatus


@dataclass(frozen=True)
class DeduplicationResult:
    """Output of the deduplication check."""

    match_status: MatchStatus
    confidence: float
    match_reason: str
    matched_transaction_id: uuid.UUID | None = None
