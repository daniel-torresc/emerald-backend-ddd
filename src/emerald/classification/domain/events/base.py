from dataclasses import dataclass
from typing import ClassVar

from emerald.shared_kernel.domain.events.domain_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class TaxonomyEvent(DomainEvent):
    """Base event for the Classification Taxonomy aggregate."""

    aggregate_type: ClassVar[str] = "taxonomy"
