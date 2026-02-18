from __future__ import annotations

import uuid
from datetime import UTC, datetime

from emerald.iam.application.ports.outbound.unit_of_work import AbstractIamUnitOfWork
from emerald.iam.domain.exceptions import OAuthCodeExchangeError
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.entities.password_reset_token import PasswordResetToken
from emerald.iam.domain.models.entities.refresh_token import RefreshToken
from emerald.iam.domain.models.value_objects.access_token_claims import AccessTokenClaims
from emerald.iam.domain.models.value_objects.auth_provider import ProviderType
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.oidc_claims import OidcClaims
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.iam.domain.models.value_objects.username import Username


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

    def exists_by_role(self, role: SystemRole) -> bool:
        return any(user.system_role == role for user in self._users.values())


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


class FakeOidcProvider:
    """Fake OIDC provider for testing social auth flows."""

    def __init__(self) -> None:
        self._claims: dict[str, OidcClaims] = {}
        self._auth_urls: dict[str, str] = {}
        self.generate_call_count: int = 0
        self.exchange_call_count: int = 0

    def set_claims_for_code(self, code: str, claims: OidcClaims) -> None:
        self._claims[code] = claims

    def set_auth_url(self, state: str, url: str) -> None:
        self._auth_urls[state] = url

    def generate_authorization_url(
        self, provider_type: ProviderType, redirect_uri: str, state: str
    ) -> str:
        self.generate_call_count += 1
        return self._auth_urls.get(state, f"https://provider.example.com/auth?state={state}")

    def exchange_code_for_claims(
        self, provider_type: ProviderType, code: str, redirect_uri: str
    ) -> OidcClaims:
        self.exchange_call_count += 1
        if code not in self._claims:
            raise OAuthCodeExchangeError()
        return self._claims[code]


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

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass
