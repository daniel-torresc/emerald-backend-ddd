from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from emerald.iam.application.ports.outbound.unit_of_work import AbstractIamUnitOfWork
from emerald.iam.domain.models.access_token_claims import AccessTokenClaims
from emerald.iam.domain.models.email_address import EmailAddress
from emerald.iam.domain.models.password_reset_token import PasswordResetToken
from emerald.iam.domain.models.refresh_token import RefreshToken
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


class FakeTokenService:
    """Deterministic token service for tests."""

    def __init__(self) -> None:
        self._counter = 0
        self._claims_store: dict[str, AccessTokenClaims] = {}

    def sign_access_token(self, claims: AccessTokenClaims) -> str:
        token = f"fake_access_token:{claims.jti}"
        self._claims_store[token] = claims
        return token

    def verify_access_token(self, token: str) -> AccessTokenClaims:
        from emerald.iam.domain.exceptions import InvalidTokenError, TokenExpiredError

        claims = self._claims_store.get(token)
        if claims is None:
            raise InvalidTokenError("Invalid token")
        if claims.exp <= datetime.now(UTC):
            raise TokenExpiredError("Token expired")
        return claims

    def generate_refresh_token(self) -> tuple[str, str]:
        self._counter += 1
        raw = f"raw_token_{self._counter}"
        return (raw, self.hash_token(raw))

    def hash_token(self, raw_token: str) -> str:
        return f"hashed:{raw_token}"


class FakeRefreshTokenRepository:
    """In-memory refresh token repository for tests."""

    def __init__(self) -> None:
        self._tokens: dict[uuid.UUID, RefreshToken] = {}

    def add(self, token: RefreshToken) -> None:
        self._tokens[token.id] = token

    def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self._tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    def find_active_families_by_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        families: dict[uuid.UUID, datetime] = {}
        now = datetime.now(UTC)
        for token in self._tokens.values():
            if token.user_id == user_id and token.revoked_at is None and token.expires_at > now:
                existing = families.get(token.family_id)
                if existing is None or token.created_at < existing:
                    families[token.family_id] = token.created_at
        # Sort by earliest creation time (oldest first)
        sorted_families = sorted(families.items(), key=lambda x: x[1])
        return [fid for fid, _ in sorted_families]

    def revoke_family(self, family_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        for token in self._tokens.values():
            if token.family_id == family_id and token.revoked_at is None:
                token.revoked_at = now

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        for token in self._tokens.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = now

    def count_active_families(self, user_id: uuid.UUID) -> int:
        return len(self.find_active_families_by_user(user_id))


class FakePasswordResetTokenRepository:
    """In-memory password reset token repository for tests."""

    def __init__(self) -> None:
        self._tokens: dict[uuid.UUID, PasswordResetToken] = {}

    def add(self, token: PasswordResetToken) -> None:
        self._tokens[token.id] = token

    def find_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        for token in self._tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    def invalidate_existing_for_user(self, user_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        for token in self._tokens.values():
            if token.user_id == user_id and token.used_at is None:
                token.used_at = now


class FakeIamUnitOfWork(AbstractIamUnitOfWork):
    """In-memory Unit of Work for IAM tests."""

    users: FakeUserRepository
    refresh_tokens: FakeRefreshTokenRepository
    password_reset_tokens: FakePasswordResetTokenRepository

    def __init__(self) -> None:
        self.users = FakeUserRepository()
        self.refresh_tokens = FakeRefreshTokenRepository()
        self.password_reset_tokens = FakePasswordResetTokenRepository()
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def collect_new_events(self) -> Iterator[DomainEvent]:
        for aggregate in self.users.seen:
            yield from aggregate.collect_events()
