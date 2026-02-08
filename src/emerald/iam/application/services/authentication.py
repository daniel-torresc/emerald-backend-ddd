from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from emerald.iam.application.dto.auth_commands import (
    LoginUser,
    LogoutAllSessions,
    LogoutSession,
    RefreshAccessToken,
    RequestPasswordReset,
    SubmitPasswordReset,
)
from emerald.iam.application.dto.auth_dtos import LoginResult
from emerald.iam.application.ports.outbound.unit_of_work import AbstractIamUnitOfWork
from emerald.iam.domain.constants import ACCESS_TOKEN_TTL, MAX_CONCURRENT_SESSIONS
from emerald.iam.domain.events.auth_events import (
    AllSessionsRevoked,
    LoginFailed,
    PasswordResetRequested,
    TokenFamilyCompromised,
    TokenRefreshed,
    TokenRevoked,
)
from emerald.iam.domain.exceptions import (
    AccountSuspendedError,
    AuthenticationFailedError,
    EmailNotVerifiedError,
    InvalidTokenError,
    TokenAlreadyUsedError,
    TokenExpiredError,
)
from emerald.iam.domain.models.access_token_claims import AccessTokenClaims
from emerald.iam.domain.models.authenticated_identity import AuthenticatedIdentity
from emerald.iam.domain.models.email_address import EmailAddress
from emerald.iam.domain.models.hashed_password import HashedPassword
from emerald.iam.domain.models.password_reset_token import PasswordResetToken
from emerald.iam.domain.models.portal_context import PortalContext
from emerald.iam.domain.models.refresh_token import RefreshToken
from emerald.iam.domain.models.user_status import UserStatus
from emerald.iam.domain.ports.password_hasher import PasswordHasher
from emerald.iam.domain.ports.token_service import TokenService
from emerald.iam.domain.services.password_validation import (
    validate_not_in_history,
    validate_password_strength,
)

_NIL_UUID = uuid.UUID(int=0)


class AuthenticationService:
    """Application service handling all authentication flows."""

    def __init__(
        self,
        uow: AbstractIamUnitOfWork,
        hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._token_service = token_service
        self._events: list[object] = []

    def login(self, cmd: LoginUser) -> LoginResult:
        """Authenticate user with email + password and return token pair."""
        with self._uow:
            # 1. Resolve portal context
            portal_context = PortalContext(cmd.portal_context)

            # 2. Find user by email
            user = self._uow.users.find_by_email(EmailAddress(cmd.email))
            if user is None:
                self._events.append(LoginFailed(aggregate_id=_NIL_UUID, email=cmd.email))
                raise AuthenticationFailedError()

            # 3. Check user status
            if user.status == UserStatus.PENDING_VERIFICATION:
                self._events.append(LoginFailed(aggregate_id=user.id, email=cmd.email))
                raise EmailNotVerifiedError()

            if user.status == UserStatus.SUSPENDED:
                self._events.append(LoginFailed(aggregate_id=user.id, email=cmd.email))
                raise AccountSuspendedError()

            if user.status == UserStatus.DELETED:
                self._events.append(LoginFailed(aggregate_id=_NIL_UUID, email=cmd.email))
                raise AuthenticationFailedError()

            # 4. Verify password
            if user.password is None or not self._hasher.verify(
                cmd.password, user.password.hashed_value
            ):
                self._events.append(LoginFailed(aggregate_id=user.id, email=cmd.email))
                raise AuthenticationFailedError()

            # 5. Enforce session limit
            active_count = self._uow.refresh_tokens.count_active_families(user.id)
            if active_count >= MAX_CONCURRENT_SESSIONS:
                active_families = self._uow.refresh_tokens.find_active_families_by_user(user.id)
                if active_families:
                    self._uow.refresh_tokens.revoke_family(active_families[0])

            # 6. Create token family
            family_id = uuid.uuid4()

            # 7. Generate refresh token
            raw_refresh, refresh_hash = self._token_service.generate_refresh_token()

            # 8. Create RefreshToken entity
            now = datetime.now(UTC)
            refresh_token = RefreshToken(
                user_id=user.id,
                token_hash=refresh_hash,
                family_id=family_id,
                portal_context=portal_context,
                expires_at=now + portal_context.refresh_ttl,
                created_at=now,
            )

            # 9. Build AccessTokenClaims
            jti = uuid.uuid4()
            claims = AccessTokenClaims(
                sub=user.id,
                email=str(user.email),
                system_role=user.system_role,
                iat=now,
                exp=now + timedelta(seconds=ACCESS_TOKEN_TTL),
                jti=jti,
            )

            # 10. Sign access token
            access_token_str = self._token_service.sign_access_token(claims)

            # 11. Record login on user
            user.record_login()

            # 12. Persist
            self._uow.refresh_tokens.add(refresh_token)
            self._uow.commit()

            return LoginResult(
                access_token=access_token_str,
                refresh_token=raw_refresh,
                expires_in=ACCESS_TOKEN_TTL,
            )

    def refresh(self, cmd: RefreshAccessToken) -> LoginResult:
        """Refresh an access token using a refresh token with rotation."""
        with self._uow:
            # 1. Hash the presented token
            token_hash = self._token_service.hash_token(cmd.refresh_token)

            # 2. Look up by hash
            token = self._uow.refresh_tokens.find_by_hash(token_hash)
            if token is None:
                raise InvalidTokenError()

            # 3. Check expired
            if token.is_expired():
                raise TokenExpiredError()

            # 4. Check revoked -> THEFT DETECTED
            if token.is_revoked():
                self._uow.refresh_tokens.revoke_family(token.family_id)
                self._events.append(
                    TokenFamilyCompromised(
                        aggregate_id=token.user_id,
                        user_id=token.user_id,
                        family_id=token.family_id,
                    )
                )
                self._uow.commit()
                raise InvalidTokenError()

            # 5. Revoke current refresh token
            token.revoke()

            # 6. Generate new refresh token in same family
            raw_refresh, refresh_hash = self._token_service.generate_refresh_token()
            now = datetime.now(UTC)
            new_refresh_token = RefreshToken(
                user_id=token.user_id,
                token_hash=refresh_hash,
                family_id=token.family_id,
                portal_context=token.portal_context,
                expires_at=now + token.portal_context.refresh_ttl,
                created_at=now,
            )

            # 7. Look up user for current claims
            user = self._uow.users.find_by_id(token.user_id)
            if user is None:
                raise InvalidTokenError()

            # 8. Build new AccessTokenClaims
            jti = uuid.uuid4()
            claims = AccessTokenClaims(
                sub=user.id,
                email=str(user.email),
                system_role=user.system_role,
                iat=now,
                exp=now + timedelta(seconds=ACCESS_TOKEN_TTL),
                jti=jti,
            )

            # 9. Sign new access token
            access_token_str = self._token_service.sign_access_token(claims)

            # 10. Persist new refresh token
            self._uow.refresh_tokens.add(new_refresh_token)

            # 11. Emit event
            self._events.append(
                TokenRefreshed(
                    aggregate_id=token.user_id,
                    user_id=token.user_id,
                    family_id=token.family_id,
                )
            )

            self._uow.commit()

            return LoginResult(
                access_token=access_token_str,
                refresh_token=raw_refresh,
                expires_in=ACCESS_TOKEN_TTL,
            )

    def logout(self, cmd: LogoutSession) -> None:
        """Revoke a single session's refresh token."""
        with self._uow:
            token_hash = self._token_service.hash_token(cmd.refresh_token)
            token = self._uow.refresh_tokens.find_by_hash(token_hash)

            if token is not None and token.is_active():
                token.revoke()
                self._events.append(
                    TokenRevoked(
                        aggregate_id=token.user_id,
                        user_id=token.user_id,
                        token_id=token.id,
                    )
                )

            self._uow.commit()

    def logout_all(self, cmd: LogoutAllSessions) -> None:
        """Revoke all sessions for a user."""
        with self._uow:
            user_id = uuid.UUID(cmd.user_id)
            self._uow.refresh_tokens.revoke_all_for_user(user_id)
            self._events.append(AllSessionsRevoked(aggregate_id=user_id, user_id=user_id))
            self._uow.commit()

    def request_password_reset(self, cmd: RequestPasswordReset) -> str | None:
        """Request a password reset token. Returns raw token or None."""
        with self._uow:
            user = self._uow.users.find_by_email(EmailAddress(cmd.email))
            if user is None:
                return None

            if user.status == UserStatus.DELETED:
                return None

            # Invalidate existing reset tokens
            self._uow.password_reset_tokens.invalidate_existing_for_user(user.id)

            # Generate reset token (reuses same generation mechanism)
            raw_token, token_hash = self._token_service.generate_refresh_token()

            # Create PasswordResetToken entity
            reset_token = PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
            )

            # Persist
            self._uow.password_reset_tokens.add(reset_token)

            # Emit event
            self._events.append(PasswordResetRequested(aggregate_id=user.id, user_id=user.id))

            self._uow.commit()
            return raw_token

    def submit_password_reset(self, cmd: SubmitPasswordReset) -> None:
        """Submit a new password using a reset token."""
        with self._uow:
            # 1. Hash and find token
            token_hash = self._token_service.hash_token(cmd.reset_token)
            reset_token = self._uow.password_reset_tokens.find_by_hash(token_hash)

            if reset_token is None:
                raise InvalidTokenError()

            if reset_token.is_expired():
                raise TokenExpiredError()

            if reset_token.is_used():
                raise TokenAlreadyUsedError()

            # 2. Validate password strength
            validate_password_strength(cmd.new_password)

            # 3. Find user
            user = self._uow.users.find_by_id(reset_token.user_id)
            if user is None:
                raise InvalidTokenError()

            # 4. Validate not in history
            validate_not_in_history(cmd.new_password, user.password_history, self._hasher)

            # 5. Hash new password
            new_hash = self._hasher.hash(cmd.new_password)
            old_hash = user.password.hashed_value if user.password else ""

            # 6. Reset password on user
            user.reset_password(HashedPassword(new_hash), old_hash)

            # 7. Mark reset token as used
            reset_token.mark_used()

            # 8. Revoke all refresh tokens
            self._uow.refresh_tokens.revoke_all_for_user(user.id)
            self._events.append(AllSessionsRevoked(aggregate_id=user.id, user_id=user.id))

            self._uow.commit()

    def verify_access_token(self, token: str) -> AuthenticatedIdentity:
        """Verify an access token and return the authenticated identity."""
        with self._uow:
            # 1. Verify token
            claims = self._token_service.verify_access_token(token)

            # 2. Look up user
            user = self._uow.users.find_by_id(claims.sub)
            if user is None:
                raise InvalidTokenError()

            # 3. Resolve display_name
            display_name = user.full_name if user.full_name else user.username.value

            return AuthenticatedIdentity(
                user_id=user.id,
                email=user.email,
                display_name=display_name,
                system_role=user.system_role,
            )

    def collect_events(self) -> list[object]:
        """Collect and clear service-level events."""
        events = list(self._events)
        self._events.clear()
        return events
