from dataclasses import dataclass


@dataclass(frozen=True)
class TaxonomyPath:
    """Full hierarchy path from root to a term."""

    segments: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("TaxonomyPath must have at least one segment")

    @property
    def depth(self) -> int:
        """Level in tree: root=0, child=1, grandchild=2, etc."""
        return len(self.segments) - 1

    def parent_path(self) -> "TaxonomyPath | None":
        """Path without the last segment, or None for root-level terms."""
        if len(self.segments) <= 1:
            return None
        return TaxonomyPath(segments=self.segments[:-1])

    def __str__(self) -> str:
        return " > ".join(self.segments)
