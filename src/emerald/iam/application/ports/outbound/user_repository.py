from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from emerald.iam.domain.models.email_address import EmailAddress
    from emerald.iam.domain.models.user import User
    from emerald.iam.domain.models.username import Username


class UserRepository(Protocol):
    """Domain port for user persistence and uniqueness queries."""

    def add(self, user: User) -> None:
        """Add a new user aggregate to the collection."""
        ...

    def find_by_id(self, user_id: uuid.UUID) -> User | None:
        """Find user by ID, returns None if not found."""
        ...

    def find_by_email(self, email: EmailAddress) -> User | None:
        """Find user by email, returns None if not found."""
        ...

    def find_by_username(self, username: Username) -> User | None:
        """Find user by username, returns None if not found."""
        ...

    def exists_by_email(self, email: EmailAddress) -> bool:
        """Check if email is taken."""
        ...

    def exists_by_username(self, username: Username, include_recently_deleted: bool = True) -> bool:
        """Check if username is taken (optionally including recently deleted)."""
        ...
