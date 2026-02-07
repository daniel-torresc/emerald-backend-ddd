from __future__ import annotations

import uuid
from collections.abc import Iterator

from emerald.iam.application.ports.outbound.unit_of_work import AbstractIamUnitOfWork
from emerald.iam.domain.models.email_address import EmailAddress
from emerald.iam.domain.models.user import User
from emerald.iam.domain.models.username import Username
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


class FakeUserRepository:
    """In-memory user repository for tests."""

    def __init__(self) -> None:
        self._users: dict[uuid.UUID, User] = {}
        self.seen: set[User] = set()

    def add(self, user: User) -> None:
        self._users[user.id] = user
        self.seen.add(user)

    def find_by_id(self, user_id: uuid.UUID) -> User | None:
        user = self._users.get(user_id)
        if user is not None:
            self.seen.add(user)
        return user

    def find_by_email(self, email: EmailAddress) -> User | None:
        for user in self._users.values():
            if user.email == email:
                self.seen.add(user)
                return user
        return None

    def find_by_username(self, username: Username) -> User | None:
        for user in self._users.values():
            if user.username == username:
                self.seen.add(user)
                return user
        return None

    def exists_by_email(self, email: EmailAddress) -> bool:
        return any(user.email == email for user in self._users.values())

    def exists_by_username(self, username: Username, include_recently_deleted: bool = True) -> bool:
        return any(user.username == username for user in self._users.values())


class FakePasswordHasher:
    """Deterministic password hasher for tests."""

    def hash(self, plaintext: str) -> str:
        return f"hashed:{plaintext}"

    def verify(self, plaintext: str, hashed: str) -> bool:
        return hashed == f"hashed:{plaintext}"


class FakeIamUnitOfWork(AbstractIamUnitOfWork):
    """In-memory Unit of Work for IAM tests."""

    users: FakeUserRepository  # type: narrow from UserRepository

    def __init__(self) -> None:
        self.users = FakeUserRepository()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def collect_new_events(self) -> Iterator[DomainEvent]:
        for aggregate in self.users.seen:
            yield from aggregate.collect_events()
