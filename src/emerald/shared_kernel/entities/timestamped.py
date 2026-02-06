from datetime import UTC, datetime


class TimestampedMixin:
    """Mixin providing created_at and updated_at timestamps in UTC."""

    def __init__(
        self,
        *,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        **kwargs: object,
    ) -> None:
        now = datetime.now(UTC)
        self._created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else self._created_at
        super().__init__(**kwargs)

    @property
    def created_at(self) -> datetime:
        return self._created_at

    def _touch(self) -> None:
        """Update updated_at to current UTC time."""
        self.updated_at = datetime.now(UTC)
