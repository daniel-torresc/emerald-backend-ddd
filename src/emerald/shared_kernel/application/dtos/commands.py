from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    """Base class for all commands — represents user intent."""
