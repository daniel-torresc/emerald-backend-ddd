from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from emerald.iam.application.dtos.commands import (
    LoginUser,
    LogoutAllSessions,
    LogoutSession,
    RefreshAccessToken,
    RequestPasswordReset,
    SubmitPasswordReset,
)
from emerald.iam.application.dtos.commands.social_auth import (
    SetOnboardingUsername,
    UnlinkAuthProvider,
)
from emerald.iam.application.dtos.responses import LoginResult
from emerald.iam.application.ports.outbound.token_service import TokenService
from emerald.iam.application.ports.outbound.unit_of_work import AbstractIamUnitOfWork
from emerald.iam.domain.constants import (
    ACCESS_TOKEN_TTL,
    MAX_CONCURRENT_SESSIONS,
    REFRESH_TOKEN_TTL_SUPERADMIN,
)
from emerald.iam.domain.events.auth_events import (
    AllSessionsRevoked,
    LoginFailed,
    PasswordResetRequested,
    TokenFamilyCompromised,
    TokenRefreshed,
    TokenRevoked,
)
from emerald.iam.domain.events.social_events import SocialLoginCompleted
from emerald.iam.domain.exceptions import (
    AccountSuspendedError,
    AuthenticationFailedError,
    EmailNotVerifiedError,
    InvalidTokenError,
    ProviderEmailMismatchError,
    ProviderEmailNotVerifiedError,
    ProviderExternalIdMismatchError,
    TokenAlreadyUsedError,
    TokenExpiredError,
    UsernameAlreadyExistsError,
)
from emerald.iam.domain.models.access_token_claims import AccessTokenClaims
from emerald.iam.domain.models.auth_provider import AuthProvider, ProviderType
from emerald.iam.domain.models.authenticated_identity import AuthenticatedIdentity
from emerald.iam.domain.models.email_address import EmailAddress
from emerald.iam.domain.models.hashed_password import HashedPassword
from emerald.iam.domain.models.oidc_claims import OidcClaims
from emerald.iam.domain.models.password_reset_token import PasswordResetToken
from emerald.iam.domain.models.portal_context import PortalContext
from emerald.iam.domain.models.refresh_token import RefreshToken
from emerald.iam.domain.models.system_role import SystemRole
from emerald.iam.domain.models.user import User
from emerald.iam.domain.models.user_status import UserStatus
from emerald.iam.domain.models.username import Username
from emerald.iam.domain.ports.password_hasher import PasswordHasher
from emerald.iam.domain.services.password_validation import (
    validate_not_in_history,
    validate_password_strength,
)

if TYPE_CHECKING:
    from emerald.iam.application.ports.outbound.oidc_provider import OidcProvider

_NIL_UUID = uuid.UUID(int=0)


class AuthenticationService:
    """Application service handling all authentication flows."""

    def __init__(
        self,
        uow: AbstractIamUnitOfWork,
        hasher: PasswordHasher,
        token_service: TokenService,
        oidc_provider: OidcProvider | None = None,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._token_service = token_service
        self._oidc_provider = oidc_provider
        self._events: list[object] = []

    # -- Private Helpers -------------------------------------------------------

    def _issue_tokens(
        self,
        user: User,
        portal_context: PortalContext,
        is_new_registration: bool = False,
    ) -> LoginResult:
        """Shared token issuance logic for login and social login flows."""
        # Enforce session limit
        active_count = self._uow.refresh_tokens.count_active_families(user.id)
        if active_count >= MAX_CONCURRENT_SESSIONS:
            active_families = self._uow.refresh_tokens.find_active_families_by_user(user.id)
            if active_families:
                self._uow.refresh_tokens.revoke_family(active_families[0])

        # Create token family
        family_id = uuid.uuid4()

        # Generate refresh token
        raw_refresh, refresh_hash = self._token_service.generate_refresh_token()

        # Create RefreshToken entity
        now = datetime.now(UTC)
        refresh_ttl = (
            REFRESH_TOKEN_TTL_SUPERADMIN
            if user.system_role == SystemRole.SUPERADMIN
            else portal_context.refresh_ttl
        )
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            family_id=family_id,
            portal_context=portal_context,
            expires_at=now + refresh_ttl,
            created_at=now,
        )

        # Build AccessTokenClaims
        jti = uuid.uuid4()
        claims = AccessTokenClaims(
            sub=user.id,
            email=str(user.email),
            system_role=user.system_role,
            iat=now,
            exp=now + timedelta(seconds=ACCESS_TOKEN_TTL),
            jti=jti,
            username=user.username.value if user.username else None,
        )

        # Sign access token
        access_token_str = self._token_service.sign_access_token(claims)

        # Persist
        self._uow.refresh_tokens.add(refresh_token)

        return LoginResult(
            access_token=access_token_str,
            refresh_token=raw_refresh,
            expires_in=ACCESS_TOKEN_TTL,
            is_new_registration=is_new_registration,
        )

    # -- Password Login --------------------------------------------------------

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
            try:
                user.validate_can_authenticate()
            except AuthenticationFailedError:
                # DELETED users get NIL UUID for privacy (same as non-existent)
                self._events.append(LoginFailed(aggregate_id=_NIL_UUID, email=cmd.email))
                raise
            except (EmailNotVerifiedError, AccountSuspendedError):
                self._events.append(LoginFailed(aggregate_id=user.id, email=cmd.email))
                raise

            # 4. Verify password
            if user.password is None or not self._hasher.verify(
                cmd.password, user.password.hashed_value
            ):
                self._events.append(LoginFailed(aggregate_id=user.id, email=cmd.email))
                raise AuthenticationFailedError()

            # 5. Record login on user
            user.record_login()

            # 6. Issue tokens
            result = self._issue_tokens(user, portal_context)

            self._uow.commit()
            return result

    # -- Social Login ----------------------------------------------------------

    def login_with_provider(self, claims: OidcClaims) -> LoginResult:
        """Authenticate or register a user via social provider claims."""
        with self._uow:
            # 1. Validate email verified (defense-in-depth; OidcClaims already validates)
            if not claims.email_verified:
                raise ProviderEmailNotVerifiedError()

            # 2. Normalize email
            email = EmailAddress(claims.email)

            # 3. Look up user by email
            user = self._uow.users.find_by_email(email)

            if user is not None:
                return self._handle_existing_user_social_login(user, claims)

            # No existing user — social registration
            return self._handle_social_registration(email, claims)

    def _handle_existing_user_social_login(self, user: User, claims: OidcClaims) -> LoginResult:
        """Handle social login for an existing user (linking/verification)."""
        # Check status (social login allows PENDING_VERIFICATION)
        user.validate_can_social_login()

        # Check if provider type already linked
        existing_provider = None
        for p in user.auth_providers:
            if p.provider_type == claims.provider_type:
                existing_provider = p
                break

        if existing_provider is not None:
            # Provider type is linked — check external_id
            if existing_provider.external_id != claims.external_id:
                raise ProviderExternalIdMismatchError()
            # Same type + same external_id — proceed to login
        else:
            # Provider type not yet linked — auto-link
            now = datetime.now(UTC)
            new_provider = AuthProvider(claims.provider_type, claims.external_id, now)
            user.link_auth_provider(new_provider)

        # If PENDING_VERIFICATION, upgrade to ACTIVE
        if user.status == UserStatus.PENDING_VERIFICATION:
            user.verify_email()

        # Record login
        user.record_login()

        # Emit social login event
        self._events.append(
            SocialLoginCompleted(
                aggregate_id=user.id,
                user_id=user.id,
                provider_type=claims.provider_type.value,
            )
        )

        # Issue tokens
        portal_context = PortalContext("REGULAR")
        result = self._issue_tokens(user, portal_context)

        self._uow.commit()
        return result

    def _handle_social_registration(self, email: EmailAddress, claims: OidcClaims) -> LoginResult:
        """Handle social registration for a new user."""
        now = datetime.now(UTC)
        auth_provider = AuthProvider(claims.provider_type, claims.external_id, now)

        user = User.register_via_social(
            email=email,
            full_name=claims.full_name,
            auth_provider=auth_provider,
        )

        self._uow.users.add(user)

        # Issue tokens
        portal_context = PortalContext("REGULAR")
        result = self._issue_tokens(user, portal_context, is_new_registration=True)

        self._uow.commit()
        return result

    # -- Provider Management ---------------------------------------------------

    def link_provider(self, user_id: uuid.UUID, claims: OidcClaims) -> None:
        """Link a social provider to an authenticated user's account."""
        with self._uow:
            user = self._uow.users.find_by_id(user_id)
            if user is None:
                raise AuthenticationFailedError()

            user.validate_can_link_provider()

            # Verify provider email matches user email
            provider_email = EmailAddress(claims.email)
            if provider_email != user.email:
                raise ProviderEmailMismatchError()

            # Link provider (raises ProviderAlreadyLinkedError if already linked)
            now = datetime.now(UTC)
            new_provider = AuthProvider(claims.provider_type, claims.external_id, now)
            user.link_auth_provider(new_provider)

            self._uow.commit()

    def unlink_provider(self, cmd: UnlinkAuthProvider) -> None:
        """Remove a linked provider from a user's account."""
        with self._uow:
            user_id = uuid.UUID(cmd.user_id)
            user = self._uow.users.find_by_id(user_id)
            if user is None:
                raise AuthenticationFailedError()

            provider_type = ProviderType(cmd.provider_type)
            user.unlink_auth_provider(provider_type)

            self._uow.commit()

    # -- Username Onboarding ---------------------------------------------------

    def set_onboarding_username(self, cmd: SetOnboardingUsername) -> None:
        """Set username for a socially registered user (onboarding)."""
        with self._uow:
            user_id = uuid.UUID(cmd.user_id)
            user = self._uow.users.find_by_id(user_id)
            if user is None:
                raise AuthenticationFailedError()

            user.validate_can_set_username()

            # Validate and create username
            username = Username(cmd.username)

            # Check uniqueness (including 90-day deleted window)
            if self._uow.users.exists_by_username(username, include_recently_deleted=True):
                raise UsernameAlreadyExistsError()

            user.update_username(username)

            self._uow.commit()

    # -- Token Refresh ---------------------------------------------------------

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

            # 7. Look up user for current claims
            user = self._uow.users.find_by_id(token.user_id)
            if user is None:
                raise InvalidTokenError()

            # 7b. Create new refresh token with SUPERADMIN TTL override
            refresh_ttl = (
                REFRESH_TOKEN_TTL_SUPERADMIN
                if user.system_role == SystemRole.SUPERADMIN
                else token.portal_context.refresh_ttl
            )
            new_refresh_token = RefreshToken(
                user_id=token.user_id,
                token_hash=refresh_hash,
                family_id=token.family_id,
                portal_context=token.portal_context,
                expires_at=now + refresh_ttl,
                created_at=now,
            )

            # 8. Build new AccessTokenClaims
            jti = uuid.uuid4()
            claims = AccessTokenClaims(
                sub=user.id,
                email=str(user.email),
                system_role=user.system_role,
                iat=now,
                exp=now + timedelta(seconds=ACCESS_TOKEN_TTL),
                jti=jti,
                username=user.username.value if user.username else None,
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

    # -- Session Management ----------------------------------------------------

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

    # -- Password Reset --------------------------------------------------------

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

    # -- Token Verification ----------------------------------------------------

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
            display_name = (
                user.full_name
                if user.full_name
                else (user.username.value if user.username else str(user.email))
            )

            return AuthenticatedIdentity(
                user_id=user.id,
                email=user.email,
                display_name=display_name,
                system_role=user.system_role,
            )

    # -- Event Collection ------------------------------------------------------

    def collect_events(self) -> list[object]:
        """Collect and clear service-level events."""
        events = list(self._events)
        self._events.clear()
        return events
