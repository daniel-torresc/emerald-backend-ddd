import uuid
from typing import Any


class Entity:
    """Base entity with UUID-based identity and identity-based equality."""

    def __init__(self, id: uuid.UUID | None = None) -> None:
        self._id = id if id is not None else uuid.uuid4()

    @property
    def id(self) -> uuid.UUID:
        return self._id

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, type(self)) and not isinstance(self, type(other)):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._id})"
