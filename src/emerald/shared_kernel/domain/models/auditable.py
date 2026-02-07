import uuid


class AuditableMixin:
    """Mixin providing created_by and updated_by actor tracking."""

    def __init__(
        self,
        *,
        created_by: uuid.UUID,
        updated_by: uuid.UUID | None = None,
        **kwargs: object,
    ) -> None:
        self._created_by = created_by
        self.updated_by = updated_by if updated_by is not None else created_by
        super().__init__(**kwargs)

    @property
    def created_by(self) -> uuid.UUID:
        return self._created_by

    def _set_updated_by(self, actor_id: uuid.UUID) -> None:
        """Set updated_by to reflect the current actor."""
        self.updated_by = actor_id
