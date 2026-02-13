from dataclasses import dataclass
from datetime import datetime

from emerald.core_finance.domain.models.value_objects.import_source_type import ImportSourceType
from emerald.shared_kernel.domain.exceptions import InvalidValueError


@dataclass(frozen=True)
class ImportSource:
    """Tracks where a transaction originated. Immutable after creation."""

    source_type: ImportSourceType
    source_id: str | None
    imported_at: datetime

    def __post_init__(self) -> None:
        if self.imported_at.tzinfo is None:
            raise InvalidValueError("imported_at must be timezone-aware")
        if self.source_id is not None:
            trimmed = self.source_id.strip()
            if not trimmed:
                raise InvalidValueError("source_id must be non-empty if provided")
            if trimmed != self.source_id:
                object.__setattr__(self, "source_id", trimmed)
