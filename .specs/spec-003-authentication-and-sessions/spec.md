# Authentication & Sessions Specification

**Version:** 1.0
**Status:** Draft
**Date:** 2026-02-07
**Bounded Context:** Identity & Access Management (IAM)
**Dependencies:** Spec 001 (Shared Kernel), Spec 002 (User Registration & Identity)
**Blocks:** 004, 005

---

## 1. Overview

This spec defines password-based authentication, JWT token lifecycle, refresh token rotation with family-based theft detection, session management, password reset, and the `AuthenticatedIdentity` cross-context integration contract. It establishes the token infrastructure that all authentication methods (password and federated) will rely on.

**Key Principle:** A unified token mechanism serves all users regardless of how they authenticated. Token lifetimes vary by portal context (regular app vs admin portal) for security.

---

## 2. Background & Context

### Problem Statement

Users can register (Spec 002) but cannot yet authenticate, obtain tokens, or maintain sessions. Without authentication, no API endpoint can verify caller identity. The platform needs a secure, stateless access token mechanism paired with a server-side refresh token for long-lived sessions, plus a password reset flow for account recovery.

### Business Goals

- Enable secure password-based login returning short-lived access tokens and rotatable refresh tokens
- Detect token theft through refresh token family tracking and automatic revocation
- Support concurrent sessions with configurable limits
- Provide password reset as a self-service account recovery mechanism
- Establish `AuthenticatedIdentity` as the single contract downstream contexts use to identify callers

### Success Metrics

- All authentication flows unit-testable without infrastructure dependencies (JWT library, database)
- Token theft detection correctly revokes entire families on reuse of revoked tokens
- Password reset flow prevents user enumeration at every step
- Downstream contexts (Core Finance, Classification) can consume `AuthenticatedIdentity` without IAM internals

---

## 3. Scope

### In Scope

- Password login flow (email + password -> token pair)
- `SystemRole` enum (USER, ADMIN, SUPERADMIN) with default USER for all users
- Access token (JWT) claims structure and domain protocol for signing/verification
- Refresh token entity and lifecycle
- Token rotation with family-based theft detection
- `PortalContext` enum (REGULAR, ADMIN) — client-specified at login
- Session management (concurrent session limits)
- Logout (single session and all sessions)
- `AuthenticatedIdentity` value object (integration contract)
- Password reset flow (request + submit)
- Password reset token entity
- New domain events for authentication lifecycle
- New IAM exceptions for authentication errors
- Commands for all authentication operations
- Extension of `AbstractIamUnitOfWork` with token repositories

### Out of Scope

- Federated authentication / OAuth flows (Spec 005)
- Admin permission enforcement and role mutation logic (Spec 004 — this spec includes `SystemRole` as a read-only default, role assignment is in 004)
- Device binding (future enhancement)
- MFA (future enhancement)
- Rate limiting on login attempts (infrastructure concern — `LoginFailed` event enables it)
- Email dispatch for password reset (infrastructure concern triggered by service return value)

---

## 4. Users & Personas

### Primary Users

- **End users** logging in with email + password to access the platform
- **End users** requesting password resets when they forget credentials
- **Developers** building downstream bounded contexts that consume `AuthenticatedIdentity`

### User Goals

- Authenticate securely and receive tokens for API access
- Maintain sessions across devices with automatic token refresh
- Reset forgotten passwords via email-based recovery
- Log out from a single session or all sessions

---

## 5. Requirements

### 5.1 Value Objects & Enums

---

#### REQ-VO-301: SystemRole Enum

**Priority:** Must Have

The system-level role of a User. Determines portal access and coarse-grained authorization.

| Value | Description |
|-------|-------------|
| USER | Standard platform user (default) |
| ADMIN | Platform administrator |
| SUPERADMIN | Super administrator with full system access |

**Business Rules:**

- BR-ROLE-001: All users default to `USER` upon registration
- BR-ROLE-002: Role mutation logic (promoting to ADMIN/SUPERADMIN) is defined in Spec 004
- BR-ROLE-003: This spec treats `SystemRole` as read-only — the User entity stores it but only Spec 004 adds methods to change it

**Acceptance Criteria:**

- [ ] `SystemRole` enum has exactly three values: USER, ADMIN, SUPERADMIN
- [ ] Default value is USER

---

#### REQ-VO-302: PortalContext Enum

**Priority:** Must Have

Identifies which portal a login session targets. Determines refresh token TTL.

| Value | Refresh TTL | Description |
|-------|-------------|-------------|
| REGULAR | 7 days | Standard application portal |
| ADMIN | 4 hours | Admin portal (shorter for security) |

**Business Rules:**

- BR-PORTAL-001: The client specifies the portal context at login time
- BR-PORTAL-002: ADMIN portal context is available regardless of role (role enforcement is Spec 004)
- BR-PORTAL-003: Portal context is immutable once the token family is created

**Acceptance Criteria:**

- [ ] `PortalContext` enum has exactly two values: REGULAR, ADMIN
- [ ] REGULAR has a 7-day refresh TTL
- [ ] ADMIN has a 4-hour refresh TTL

---

#### REQ-VO-303: AuthenticatedIdentity

**Priority:** Must Have

The value object that IAM exposes to downstream bounded contexts after successful authentication. This is the **sole integration contract** — downstream contexts must not access IAM internals.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| user_id | UUID | User identifier |
| email | EmailAddress | User email |
| display_name | str | `full_name` if set, otherwise `username.value` |
| system_role | SystemRole | USER, ADMIN, or SUPERADMIN |

**Business Rules:**

- BR-IDENT-001: Constructed from access token claims + minimal user lookup for display_name
- BR-IDENT-002: `display_name` resolves to `full_name` if non-None, otherwise falls back to `username.value`
- BR-IDENT-003: Passed to downstream contexts (Core Finance, Classification) at the application layer boundary
- BR-IDENT-004: Downstream contexts must not import User or any IAM domain model — only this value object
- BR-IDENT-005: `admin_permissions` field will be added by Spec 004 when `AdminPermission` is defined

**Acceptance Criteria:**

- [ ] `AuthenticatedIdentity` is `@dataclass(frozen=True)`
- [ ] Contains `user_id`, `email`, `display_name`, `system_role`
- [ ] `display_name` is a `str` (resolved before construction)
- [ ] Two identities with the same `user_id` are equal

---

#### REQ-VO-304: AccessTokenClaims

**Priority:** Must Have

A value object representing the decoded claims from a valid access token. Used internally — never sent to downstream contexts (use `AuthenticatedIdentity` instead).

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| sub | UUID | User ID |
| email | str | User email (raw string, not EmailAddress) |
| system_role | SystemRole | User's system role |
| iat | datetime | Issued at (UTC) |
| exp | datetime | Expiration (UTC) |
| jti | UUID | Unique token ID |

**Business Rules:**

- BR-CLAIMS-001: All datetime fields must be timezone-aware UTC
- BR-CLAIMS-002: `exp` must be after `iat`
- BR-CLAIMS-003: `jti` is a unique identifier per access token (for potential revocation lists)

**Acceptance Criteria:**

- [ ] `AccessTokenClaims` is `@dataclass(frozen=True)`
- [ ] `exp` before or equal to `iat` raises `InvalidValueError`
- [ ] All datetime fields are UTC

---

### 5.2 Entities

---

#### REQ-ENT-301: RefreshToken Entity

**Priority:** Must Have

A server-side token entity used to obtain new access tokens. Stored hashed. Not an aggregate root — managed by the `AuthenticationService`.

**Inheritance:** Extends `Entity` (Shared Kernel) for UUID-based identity.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| id | UUID | No | Unique token identifier (from Entity base) |
| user_id | UUID | No | Owner of this token |
| token_hash | str | No | SHA-256 hash of the opaque token value |
| family_id | UUID | No | Token family for theft detection |
| portal_context | PortalContext | No | REGULAR or ADMIN |
| expires_at | datetime | No | When this token expires (UTC) |
| revoked_at | datetime? | Yes | When revoked (None = active) |
| created_at | datetime | No | When issued (UTC) |

**Methods:**

| Method | Description | Raises |
|--------|-------------|--------|
| `revoke() -> None` | Sets `revoked_at` to current UTC time | `TokenAlreadyRevokedError` if already revoked |
| `is_active() -> bool` | Returns `True` if not revoked and not expired | — |
| `is_expired() -> bool` | Returns `True` if `expires_at` < now | — |
| `is_revoked() -> bool` | Returns `True` if `revoked_at` is not None | — |

**Business Rules:**

- BR-RT-001: The raw token value is returned to the client once and never stored server-side (only the hash)
- BR-RT-002: `token_hash` is a SHA-256 hex digest of the raw opaque token
- BR-RT-003: `revoked_at` transitions from None to a datetime exactly once (irreversible)
- BR-RT-004: `expires_at` is computed at creation: `now + PortalContext TTL`
- BR-RT-005: All datetime fields must be timezone-aware UTC

**Acceptance Criteria:**

- [ ] RefreshToken extends Entity (has UUID `id`)
- [ ] `revoke()` sets `revoked_at` to current UTC time
- [ ] `revoke()` on already-revoked token raises `TokenAlreadyRevokedError`
- [ ] `is_active()` returns False when revoked
- [ ] `is_active()` returns False when expired
- [ ] `is_active()` returns True when neither revoked nor expired
- [ ] `is_expired()` correctly compares `expires_at` to current time
- [ ] All datetime attributes are timezone-aware UTC

---

#### REQ-ENT-302: PasswordResetToken Entity

**Priority:** Must Have

A short-lived, single-use token for password reset. Stored hashed. Not an aggregate root.

**Inheritance:** Extends `Entity` (Shared Kernel) for UUID-based identity.

**Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| id | UUID | No | Unique token identifier (from Entity base) |
| user_id | UUID | No | User requesting reset |
| token_hash | str | No | SHA-256 hash of the token value |
| expires_at | datetime | No | Expiration — 1 hour from creation (UTC) |
| used_at | datetime? | Yes | When the token was consumed (None = unused) |
| created_at | datetime | No | When issued (UTC) |

**Methods:**

| Method | Description | Raises |
|--------|-------------|--------|
| `mark_used() -> None` | Sets `used_at` to current UTC time | `TokenAlreadyUsedError` if already used |
| `is_valid() -> bool` | Returns `True` if not used and not expired | — |
| `is_expired() -> bool` | Returns `True` if `expires_at` < now | — |
| `is_used() -> bool` | Returns `True` if `used_at` is not None | — |

**Business Rules:**

- BR-PRT-001: Single-use — once `used_at` is set, cannot be used again
- BR-PRT-002: Short-lived — expires after 1 hour (configurable at creation)
- BR-PRT-003: Only one active reset token per user — creating a new one invalidates all previous via repository
- BR-PRT-004: Raw token value sent to the caller (API layer dispatches email), only hash stored server-side
- BR-PRT-005: All datetime fields must be timezone-aware UTC

**Acceptance Criteria:**

- [ ] PasswordResetToken extends Entity (has UUID `id`)
- [ ] `mark_used()` sets `used_at` to current UTC time
- [ ] `mark_used()` on already-used token raises `TokenAlreadyUsedError`
- [ ] `is_valid()` returns False when used
- [ ] `is_valid()` returns False when expired
- [ ] `is_valid()` returns True when neither used nor expired
- [ ] Token defaults to 1-hour expiration from creation time

---

### 5.3 User Aggregate Modifications

---

#### REQ-USER-301: Add SystemRole to User

**Priority:** Must Have

Extend the User aggregate (from Spec 002) with a `system_role` attribute.

**New Attribute:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| system_role | SystemRole | Yes (Spec 004) | Default USER. Read-only in this spec. |

**Modifications:**

- `User.register()` factory sets `system_role = SystemRole.USER`
- No mutation method in this spec — Spec 004 adds `assign_role()`

**Acceptance Criteria:**

- [ ] New users have `system_role = SystemRole.USER`
- [ ] `system_role` attribute is accessible on the User entity
- [ ] No method exists to change `system_role` in this spec

---

#### REQ-USER-302: Add reset_password() Method to User

**Priority:** Must Have

A new method on the User aggregate that allows password reset from both ACTIVE and SUSPENDED states. Unlike `change_password()` (which requires ACTIVE), this method serves the password reset flow where a suspended user should still be able to recover via email.

**Method:** `reset_password(new_hashed: HashedPassword, old_hash_to_archive: str) -> None`

**Allowed States:** ACTIVE, SUSPENDED

**Behavior:**
1. Validate status is ACTIVE or SUSPENDED (raise `InvalidStateTransitionError` otherwise)
2. Push old password hash onto `password_history` (trim to 5 entries, FIFO)
3. Set new `password`
4. Emit `PasswordChanged` event

**Business Rules:**

- BR-RESET-001: Works from ACTIVE or SUSPENDED (unlike `change_password()` which requires ACTIVE only)
- BR-RESET-002: Password strength and history validation happen **before** calling this method (in the service layer)
- BR-RESET-003: After reset, all refresh tokens are revoked by the service (not by this method)

**Acceptance Criteria:**

- [ ] `reset_password()` succeeds from ACTIVE status
- [ ] `reset_password()` succeeds from SUSPENDED status
- [ ] `reset_password()` from PENDING_VERIFICATION raises `InvalidStateTransitionError`
- [ ] `reset_password()` from DELETED raises `InvalidStateTransitionError`
- [ ] Old password hash is archived in history (max 5, FIFO)
- [ ] Emits `PasswordChanged` event

---

### 5.4 Domain Ports (Protocols)

---

#### REQ-PORT-301: TokenService Protocol

**Priority:** Must Have

A domain port for access token signing/verification and refresh token generation. Infrastructure implements this with a JWT library and cryptographic random generation.

**Protocol Methods:**

| Method | Description |
|--------|-------------|
| `sign_access_token(claims: AccessTokenClaims) -> str` | Sign claims into a JWT string |
| `verify_access_token(token: str) -> AccessTokenClaims` | Verify JWT and extract claims |
| `generate_refresh_token() -> tuple[str, str]` | Generate `(raw_token, token_hash)` pair |
| `hash_token(raw_token: str) -> str` | Hash a raw token value (SHA-256 hex digest) |

**Business Rules:**

- BR-TS-001: `sign_access_token` produces a JWT signed with an asymmetric algorithm (RS256 or ES256)
- BR-TS-002: `verify_access_token` raises `InvalidTokenError` if signature is invalid, `TokenExpiredError` if expired
- BR-TS-003: `generate_refresh_token` returns a cryptographically random opaque string and its SHA-256 hash
- BR-TS-004: The protocol does not specify the signing algorithm — that is an infrastructure concern
- BR-TS-005: `hash_token` is a pure function used to hash presented refresh/reset tokens for lookup

**Acceptance Criteria:**

- [ ] `TokenService` is a `typing.Protocol`
- [ ] `sign_access_token` takes `AccessTokenClaims` and returns `str`
- [ ] `verify_access_token` takes `str` and returns `AccessTokenClaims`
- [ ] `verify_access_token` raises `InvalidTokenError` for bad signature
- [ ] `verify_access_token` raises `TokenExpiredError` for expired tokens
- [ ] `generate_refresh_token` returns a `tuple[str, str]` of `(raw, hash)`
- [ ] `hash_token` takes `str` and returns `str` (hex digest)

---

### 5.5 Repository Protocols

---

#### REQ-REPO-301: RefreshTokenRepository

**Priority:** Must Have

**Protocol Methods:**

| Method | Description |
|--------|-------------|
| `add(token: RefreshToken) -> None` | Persist a new refresh token |
| `find_by_hash(token_hash: str) -> RefreshToken?` | Find token by its hash |
| `find_active_families_by_user(user_id: UUID) -> list[UUID]` | List active (non-expired, non-revoked) family IDs for a user |
| `revoke_family(family_id: UUID) -> None` | Revoke all tokens in a family |
| `revoke_all_for_user(user_id: UUID) -> None` | Revoke all tokens for a user |
| `count_active_families(user_id: UUID) -> int` | Count active token families for session limit check |

**Acceptance Criteria:**

- [ ] All methods defined as protocol (no implementation)
- [ ] `find_by_hash` returns `None` when not found (not an exception)
- [ ] `revoke_family` revokes all tokens sharing the given `family_id`
- [ ] `revoke_all_for_user` revokes every active token for the user

---

#### REQ-REPO-302: PasswordResetTokenRepository

**Priority:** Must Have

**Protocol Methods:**

| Method | Description |
|--------|-------------|
| `add(token: PasswordResetToken) -> None` | Persist a new reset token |
| `find_by_hash(token_hash: str) -> PasswordResetToken?` | Find token by its hash |
| `invalidate_existing_for_user(user_id: UUID) -> None` | Invalidate (revoke/delete) all existing reset tokens for a user |

**Acceptance Criteria:**

- [ ] All methods defined as protocol (no implementation)
- [ ] `find_by_hash` returns `None` when not found
- [ ] `invalidate_existing_for_user` ensures only one active reset token per user

---

### 5.6 Unit of Work Extension

---

#### REQ-UOW-301: Extend AbstractIamUnitOfWork

**Priority:** Must Have

Add token repository properties to the existing `AbstractIamUnitOfWork`.

**New Properties:**

| Property | Type | Description |
|----------|------|-------------|
| refresh_tokens | RefreshTokenRepository | Refresh token persistence |
| password_reset_tokens | PasswordResetTokenRepository | Password reset token persistence |

**Existing Properties (from Spec 002):**

| Property | Type | Description |
|----------|------|-------------|
| users | UserRepository | User persistence |

**Acceptance Criteria:**

- [ ] `AbstractIamUnitOfWork` has `refresh_tokens` property
- [ ] `AbstractIamUnitOfWork` has `password_reset_tokens` property
- [ ] Existing `users` property is unchanged

---

### 5.7 Application Layer: Commands

---

#### REQ-CMD-301: Authentication Commands

**Priority:** Must Have

All commands extend `Command` from the Shared Kernel (`@dataclass(frozen=True)`).

**LoginUser:**

| Field | Type | Description |
|-------|------|-------------|
| email | str | User email |
| password | str | Plaintext password |
| portal_context | str | "REGULAR" or "ADMIN" — resolved to PortalContext enum by service |

**RefreshAccessToken:**

| Field | Type | Description |
|-------|------|-------------|
| refresh_token | str | Raw refresh token value |

**LogoutSession:**

| Field | Type | Description |
|-------|------|-------------|
| refresh_token | str | Raw refresh token to revoke |

**LogoutAllSessions:**

| Field | Type | Description |
|-------|------|-------------|
| user_id | str | UUID string of the user |

**RequestPasswordReset:**

| Field | Type | Description |
|-------|------|-------------|
| email | str | Email of the user requesting reset |

**SubmitPasswordReset:**

| Field | Type | Description |
|-------|------|-------------|
| reset_token | str | Raw reset token value |
| new_password | str | New plaintext password |

**Acceptance Criteria:**

- [ ] All commands are `@dataclass(frozen=True)` extending `Command`
- [ ] All commands carry only primitive types (str) — no value objects
- [ ] `LoginUser` includes `portal_context` field

---

### 5.8 Application Layer: Service

---

#### REQ-SVC-301: AuthenticationService

**Priority:** Must Have

A single application service handling all authentication flows. Uses Unit of Work pattern with `AbstractIamUnitOfWork`.

**Constructor Dependencies:**

| Dependency | Type | Description |
|------------|------|-------------|
| uow | AbstractIamUnitOfWork | Transaction boundary with all repos |
| hasher | PasswordHasher | Password verification (from Spec 002) |
| token_service | TokenService | JWT signing/verification and token generation |

---

##### Method: `login(cmd: LoginUser) -> LoginResult`

**Returns:** `LoginResult` — a `@dataclass(frozen=True)` with `access_token: str`, `refresh_token: str`, `expires_in: int` (seconds).

**Steps:**

1. Resolve `PortalContext` from `cmd.portal_context` string
2. Find user by email via `uow.users.find_by_email(EmailAddress(cmd.email))`
3. If user not found → raise `AuthenticationFailedError`
4. Check user status:
   - PENDING_VERIFICATION → raise `EmailNotVerifiedError`
   - SUSPENDED → raise `AccountSuspendedError`
   - DELETED → raise `AuthenticationFailedError` (no info leak)
5. Verify password: `hasher.verify(cmd.password, user.password.hashed_value)`
   - If False → raise `AuthenticationFailedError`
6. Enforce session limit:
   a. Count active families: `uow.refresh_tokens.count_active_families(user.id)`
   b. If count >= MAX_CONCURRENT_SESSIONS (5):
      - Get active families: `uow.refresh_tokens.find_active_families_by_user(user.id)`
      - Revoke the oldest family
7. Create token family: generate new `family_id` (UUID)
8. Generate refresh token: `token_service.generate_refresh_token()` → `(raw_refresh, refresh_hash)`
9. Create `RefreshToken` entity with `user_id`, `refresh_hash`, `family_id`, `portal_context`, computed `expires_at`
10. Build `AccessTokenClaims` with `sub=user.id`, `email`, `system_role`, 15-minute expiry, new `jti`
11. Sign access token: `token_service.sign_access_token(claims)` → `access_token_str`
12. Record login on user: `user.record_login()`
13. Persist refresh token: `uow.refresh_tokens.add(refresh_token)`
14. Commit UoW
15. Return `LoginResult(access_token_str, raw_refresh, 900)`

**Events Emitted (via User aggregate):**
- `UserLoggedIn` (from `user.record_login()`)

**Events Emitted (via service, recorded on a collector):**
- `LoginFailed` — emitted on any authentication failure (before raising exception)

**Acceptance Criteria:**

- [ ] Valid credentials for ACTIVE user returns `LoginResult` with access + refresh tokens
- [ ] Invalid password raises `AuthenticationFailedError`
- [ ] Non-existent email raises `AuthenticationFailedError` (no user enumeration)
- [ ] PENDING_VERIFICATION user raises `EmailNotVerifiedError`
- [ ] SUSPENDED user raises `AccountSuspendedError`
- [ ] DELETED user raises `AuthenticationFailedError` (same as invalid)
- [ ] Successful login records `last_login_at` on user
- [ ] Successful login emits `UserLoggedIn` event
- [ ] Failed login emits `LoginFailed` event
- [ ] At max sessions (5), oldest family is revoked before new login
- [ ] Access token expires in 15 minutes (900 seconds)
- [ ] Refresh token TTL matches portal context (7 days REGULAR, 4 hours ADMIN)

---

##### Method: `refresh(cmd: RefreshAccessToken) -> LoginResult`

**Steps:**

1. Hash the presented token: `token_service.hash_token(cmd.refresh_token)`
2. Look up by hash: `uow.refresh_tokens.find_by_hash(token_hash)`
3. If not found → raise `InvalidTokenError`
4. If expired → raise `TokenExpiredError`
5. If revoked → **THEFT DETECTED**:
   a. Revoke entire family: `uow.refresh_tokens.revoke_family(token.family_id)`
   b. Emit `TokenFamilyCompromised` event
   c. Commit and raise `InvalidTokenError`
6. Revoke current refresh token: `token.revoke()`
7. Generate new refresh token in same family
8. Look up user for current claims: `uow.users.find_by_id(token.user_id)`
9. Build new `AccessTokenClaims` with fresh expiry
10. Sign new access token
11. Persist new refresh token
12. Commit UoW
13. Return `LoginResult` with new tokens

**Events Emitted:**
- `TokenRefreshed` on successful rotation
- `TokenFamilyCompromised` on theft detection

**Acceptance Criteria:**

- [ ] Valid refresh token returns new access + refresh token pair
- [ ] Old refresh token is revoked after rotation
- [ ] New refresh token is in the same family
- [ ] Expired token raises `TokenExpiredError`
- [ ] Not-found token raises `InvalidTokenError`
- [ ] Revoked token triggers theft detection: entire family revoked
- [ ] Theft detection emits `TokenFamilyCompromised` event

---

##### Method: `logout(cmd: LogoutSession) -> None`

**Steps:**

1. Hash the presented token
2. Find by hash
3. If found and active → revoke it
4. Emit `TokenRevoked` event
5. Commit

**Note:** Access token remains valid until expiry (stateless). Client should discard it.

**Acceptance Criteria:**

- [ ] Valid refresh token is revoked
- [ ] Emits `TokenRevoked` event
- [ ] Non-existent token is silently ignored (idempotent)

---

##### Method: `logout_all(cmd: LogoutAllSessions) -> None`

**Steps:**

1. Parse `user_id` from command
2. Revoke all tokens: `uow.refresh_tokens.revoke_all_for_user(user_id)`
3. Emit `AllSessionsRevoked` event
4. Commit

**Acceptance Criteria:**

- [ ] All refresh tokens for the user are revoked
- [ ] Emits `AllSessionsRevoked` event

---

##### Method: `request_password_reset(cmd: RequestPasswordReset) -> str | None`

**Returns:** The raw reset token string if user exists, `None` otherwise. The caller (API layer) sends the email. The API layer **always** returns success to the client regardless of return value (no user enumeration).

**Steps:**

1. Find user by email: `uow.users.find_by_email(EmailAddress(cmd.email))`
2. If not found → return `None`
3. If user status is DELETED → return `None` (no reset for deleted users)
4. Invalidate existing reset tokens: `uow.password_reset_tokens.invalidate_existing_for_user(user.id)`
5. Generate reset token: `token_service.generate_refresh_token()` → `(raw_token, token_hash)` (reuses the same generation mechanism)
6. Create `PasswordResetToken` entity with `user_id`, `token_hash`, 1-hour expiry
7. Persist: `uow.password_reset_tokens.add(reset_token)`
8. Emit `PasswordResetRequested` event
9. Commit
10. Return `raw_token`

**Acceptance Criteria:**

- [ ] Existing user gets a reset token created, returns raw token
- [ ] Non-existent email returns `None` (no exception)
- [ ] DELETED user returns `None`
- [ ] Previous reset tokens for the user are invalidated
- [ ] Emits `PasswordResetRequested` event (only when user exists)
- [ ] Reset token expires in 1 hour

---

##### Method: `submit_password_reset(cmd: SubmitPasswordReset) -> None`

**Steps:**

1. Hash the presented token: `token_service.hash_token(cmd.reset_token)`
2. Find by hash: `uow.password_reset_tokens.find_by_hash(token_hash)`
3. If not found → raise `InvalidTokenError`
4. If expired → raise `TokenExpiredError`
5. If already used → raise `TokenAlreadyUsedError`
6. Validate password strength: `validate_password_strength(cmd.new_password)`
7. Find user: `uow.users.find_by_id(reset_token.user_id)`
8. Validate not in history: `validate_not_in_history(cmd.new_password, user.password_history, hasher)`
9. Hash new password: `hasher.hash(cmd.new_password)`
10. Reset password on user: `user.reset_password(HashedPassword(new_hash), old_hash_to_archive)`
11. Mark reset token as used: `reset_token.mark_used()`
12. Revoke all refresh tokens: `uow.refresh_tokens.revoke_all_for_user(user.id)`
13. Commit

**Events Emitted (via User aggregate):**
- `PasswordChanged` (from `user.reset_password()`)

**Events Emitted (via service):**
- `AllSessionsRevoked` (force re-login after password reset)

**Acceptance Criteria:**

- [ ] Valid reset token + strong password changes the user's password
- [ ] Old password hash is archived in history
- [ ] Reset token is marked as used
- [ ] All refresh tokens for the user are revoked (force re-login)
- [ ] Expired reset token raises `TokenExpiredError`
- [ ] Already-used reset token raises `TokenAlreadyUsedError`
- [ ] Not-found reset token raises `InvalidTokenError`
- [ ] Weak new password raises `PasswordTooWeakError`
- [ ] Password matching history raises `PasswordReusedError`

---

##### Method: `verify_access_token(token: str) -> AuthenticatedIdentity`

**Steps:**

1. Verify token: `token_service.verify_access_token(token)` → `AccessTokenClaims`
2. Look up user: `uow.users.find_by_id(claims.sub)`
3. If not found → raise `InvalidTokenError`
4. Resolve display_name: `user.full_name if user.full_name else user.username.value`
5. Return `AuthenticatedIdentity(user_id, email, display_name, system_role)`

**Note:** This is the method API middleware calls on every authenticated request.

**Acceptance Criteria:**

- [ ] Valid access token returns `AuthenticatedIdentity`
- [ ] Invalid/expired token raises appropriate error (delegated to `TokenService`)
- [ ] User not found (deleted after token issued) raises `InvalidTokenError`
- [ ] `display_name` uses `full_name` when available, falls back to `username`

---

### 5.9 Domain Events

All domain events extend `DomainEvent` from the Shared Kernel (`@dataclass(frozen=True)`).

**New Events (Spec 003):**

| Event | aggregate_type | Trigger | Additional Data |
|-------|---------------|---------|-----------------|
| `LoginFailed` | `"User"` | Failed login attempt | `email: str` (not user_id — user may not exist) |
| `TokenRefreshed` | `"User"` | Successful token rotation | `user_id: UUID`, `family_id: UUID` |
| `TokenRevoked` | `"User"` | Token revocation (logout) | `user_id: UUID`, `token_id: UUID` |
| `TokenFamilyCompromised` | `"User"` | Reuse of revoked token | `user_id: UUID`, `family_id: UUID` |
| `AllSessionsRevoked` | `"User"` | Logout all / password reset | `user_id: UUID` |
| `PasswordResetRequested` | `"User"` | Password reset requested | `user_id: UUID` |

**Existing Events Reused (from Spec 002):**

| Event | Trigger in Spec 003 |
|-------|---------------------|
| `UserLoggedIn` | Successful login (`user.record_login()`) |
| `PasswordChanged` | Password reset (`user.reset_password()`) |

**Business Rules:**

- BR-EVT-301: `LoginFailed` uses `email` (string), not `user_id`, because the user may not exist
- BR-EVT-302: `LoginFailed` uses a sentinel `aggregate_id` (e.g., nil UUID) since there may be no aggregate
- BR-EVT-303: Events never contain raw token values or password data
- BR-EVT-304: `PasswordResetRequested` does NOT carry the raw reset token (security)

**Acceptance Criteria:**

- [ ] All 6 new events are `@dataclass(frozen=True)` extending `DomainEvent`
- [ ] `LoginFailed` carries `email` as string, not user_id
- [ ] No event contains raw token values or passwords
- [ ] `PasswordResetRequested` carries only `user_id`

---

### 5.10 IAM Exception Hierarchy (Extensions)

New exceptions added to the existing hierarchy from Spec 002.

**New Exceptions:**

```
DomainError (Shared Kernel)
├── ValidationError (Shared Kernel)
│   └── InvalidValueError (Shared Kernel)
│       └── InvalidTokenError               [IAM] code: "INVALID_TOKEN"
├── DomainError
│   ├── AuthenticationFailedError            [IAM] code: "AUTHENTICATION_FAILED"
│   ├── EmailNotVerifiedError                [IAM] code: "EMAIL_NOT_VERIFIED"
│   ├── AccountSuspendedError                [IAM] code: "ACCOUNT_SUSPENDED"
│   ├── TokenExpiredError                    [IAM] code: "TOKEN_EXPIRED"
│   ├── TokenAlreadyRevokedError             [IAM] code: "TOKEN_ALREADY_REVOKED"
│   └── TokenAlreadyUsedError                [IAM] code: "TOKEN_ALREADY_USED"
```

**Design Decisions:**

- `AuthenticationFailedError` extends `DomainError` directly — it's not a validation error, it's a security boundary. Intentionally vague message (no hints about what's wrong).
- `EmailNotVerifiedError` extends `DomainError` — specific enough for the client to show a "check your email" message.
- `AccountSuspendedError` extends `DomainError` — client can show a "contact support" message.
- `InvalidTokenError` extends `InvalidValueError` — the token value is structurally invalid or unrecognized.
- `TokenExpiredError` extends `DomainError` — distinct from invalid so clients can trigger a refresh flow.
- `TokenAlreadyRevokedError` extends `ConflictError` — attempting to revoke an already-revoked token.
- `TokenAlreadyUsedError` extends `ConflictError` — attempting to use an already-consumed reset token.

**Acceptance Criteria:**

- [ ] All 7 new exceptions extend from Shared Kernel base exceptions
- [ ] Each has a unique `code` string
- [ ] `AuthenticationFailedError` message is intentionally vague
- [ ] Exception hierarchy matches the tree above

---

### 5.11 Non-Functional Requirements

#### Performance

- Access token verification is stateless (signature check only, no database hit) — except for `verify_access_token` on the service which does a user lookup
- Refresh token lookup is by hash (indexed in repository implementation)
- Session limit enforcement requires a count query (not loading all tokens)

#### Security

- Raw token values never stored server-side (only hashes)
- Access tokens signed with asymmetric keys (public key available for verification by other services)
- Refresh tokens are opaque, cryptographically random, stored as SHA-256 hashes
- Password reset tokens are single-use, short-lived (1 hour), one active per user
- No user enumeration on login failure or password reset request
- Token theft detection via family-based revocation
- All sessions revoked on password reset (force re-authentication)
- `LoginFailed` event enables infrastructure-level rate limiting without domain coupling

#### Testability

- `TokenService` is a protocol — tests use a fake that returns predictable tokens
- `RefreshTokenRepository` and `PasswordResetTokenRepository` are protocols — tests use in-memory fakes
- `PasswordHasher` reused from Spec 002 — same fake
- `AbstractIamUnitOfWork` extended — same fake pattern, adds token repos
- 100% of domain and application logic testable without JWT library, database, or crypto

---

## 6. User Stories

### US-301: Password Login

**As a** registered, active user
**I want** to log in with my email and password
**So that** I receive tokens to access the platform

**Acceptance Criteria:**
- [ ] Given valid credentials for an ACTIVE user, when I log in, then I receive an access token and refresh token
- [ ] Given invalid credentials, when I log in, then I see a generic "authentication failed" error (no hints)
- [ ] Given my email is not verified, when I log in, then I'm told to verify my email
- [ ] Given my account is suspended, when I log in, then I'm told my account is suspended

### US-302: Token Refresh

**As an** authenticated user
**I want** to refresh my access token using my refresh token
**So that** I maintain my session without re-entering credentials

**Acceptance Criteria:**
- [ ] Given a valid refresh token, when I refresh, then I receive new access + refresh tokens
- [ ] Given an expired refresh token, when I refresh, then I'm told the token expired
- [ ] Given a revoked refresh token (stolen), when I refresh, then ALL tokens in my family are revoked

### US-303: Logout

**As an** authenticated user
**I want** to log out from my current session or all sessions
**So that** I can secure my account

**Acceptance Criteria:**
- [ ] Given a valid refresh token, when I log out, then that session's refresh token is revoked
- [ ] When I log out from all sessions, then all my refresh tokens are revoked

### US-304: Password Reset

**As a** user who forgot their password
**I want** to reset my password via email
**So that** I can regain access to my account

**Acceptance Criteria:**
- [ ] Given any email, when I request a reset, then I always see a success message (no enumeration)
- [ ] Given a valid reset token and strong new password, when I submit, then my password is changed and all sessions are revoked
- [ ] Given an expired or used reset token, when I submit, then I see an appropriate error
- [ ] Given a suspended account, when I reset my password, then it succeeds (reset works from SUSPENDED)

### US-305: Session Limits

**As the** platform
**I want** to limit concurrent sessions to 5 per user
**So that** compromised accounts have bounded exposure

**Acceptance Criteria:**
- [ ] Given I have 5 active sessions, when I log in again, then the oldest session is automatically revoked
- [ ] The session count is based on active token families (not individual tokens)

---

## 7. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Login with email that doesn't exist | `AuthenticationFailedError` (same as wrong password — no enumeration) |
| Login with correct email but wrong password | `AuthenticationFailedError` (generic) |
| Login with DELETED user's email | `AuthenticationFailedError` (same as non-existent) |
| Refresh with a token from a revoked family | Theft detection: entire family revoked, `InvalidTokenError` |
| Refresh with a token that was already rotated | Same as revoked — theft detection triggers |
| Logout with non-existent refresh token | Silently ignored (idempotent) |
| Logout all when user has no active sessions | No-op, event still emitted |
| Password reset for non-existent email | Returns `None`, API returns success (no enumeration) |
| Password reset for DELETED user | Returns `None`, treated same as non-existent |
| Password reset for PENDING_VERIFICATION user | Token created, reset works (allows recovery) |
| Two reset requests in quick succession | Second invalidates first token |
| Submit reset with token from a previous (invalidated) request | Token not found → `InvalidTokenError` |
| Submit reset with expired token | `TokenExpiredError` |
| Submit reset with weak new password | `PasswordTooWeakError` (token NOT consumed — can retry) |
| Submit reset with password from history | `PasswordReusedError` (token NOT consumed — can retry) |
| Access token used after user is deleted | `verify_access_token` finds no user → `InvalidTokenError` |
| Concurrent session count exactly at limit (5) | Oldest family revoked, new login proceeds |
| Concurrent session count below limit | Login proceeds normally, no revocation |
| Revoke an already-revoked refresh token | `TokenAlreadyRevokedError` (entity method), but logout service handles gracefully |
| Mark an already-used reset token | `TokenAlreadyUsedError` |

---

## 8. Authentication Flows (Detailed)

### 8.1 Password Login Flow

```
Client sends: { email, password, portal_context }
     │
     ▼
Validate credentials:
  1. Find user by email
  2. Verify password hash
  3. Check user status == ACTIVE
     │
     ├── User not found ──────────► AuthenticationFailedError
     ├── Invalid password ─────────► AuthenticationFailedError
     ├── PENDING_VERIFICATION ─────► EmailNotVerifiedError
     ├── SUSPENDED ────────────────► AccountSuspendedError
     ├── DELETED ──────────────────► AuthenticationFailedError (same as invalid)
     │
     ▼
Enforce session limit:
  1. Count active token families for user
  2. If count >= 5: revoke oldest family
     │
     ▼
Create token pair:
  1. Generate access token (JWT, 15min)
  2. Create refresh token entity (hashed, stored)
  3. Assign to new token family
  4. Record login on user (last_login_at)
     │
     ▼
Return: LoginResult { access_token, refresh_token, expires_in: 900 }
```

### 8.2 Token Refresh Flow

```
Client sends: { refresh_token }
     │
     ▼
Validate refresh token:
  1. Hash the presented token
  2. Look up by hash in repository
  3. Check not expired
  4. Check not revoked
     │
     ├── Not found ──► InvalidTokenError
     ├── Expired ────► TokenExpiredError
     ├── Revoked ────► THEFT DETECTED (see 8.3)
     │
     ▼
Rotate tokens:
  1. Revoke current refresh token
  2. Generate new access token
  3. Create new refresh token (same family)
  4. Return new token pair
```

### 8.3 Token Theft Detection

```
Revoked token presented:
     │
     ▼
Revoke ENTIRE token family:
  1. Find all tokens in the same family
  2. Revoke all of them
  3. Emit TokenFamilyCompromised event
  4. Return InvalidTokenError
     │
     ▼
Result: Both legitimate user and attacker are logged out.
User must re-authenticate.
```

### 8.4 Password Reset Flow

```
User requests reset: { email }
     │
     ▼
  1. Find user by email (if exists and not DELETED)
  2. Invalidate existing reset tokens for user
  3. Generate reset token (1-hour, single-use)
  4. Emit PasswordResetRequested event
  5. Return raw token to caller (API sends email)
  6. Always return success to client (no enumeration)

User submits new password: { reset_token, new_password }
     │
     ▼
  1. Validate reset token (exists, not expired, not used)
  2. Validate new password (strength, history)
  3. Reset password on User entity (ACTIVE or SUSPENDED)
  4. Mark reset token as used
  5. Revoke all refresh tokens for user (force re-login)
  6. Emit PasswordChanged event
```

---

## 9. Constants & Configuration

| Constant | Value | Description |
|----------|-------|-------------|
| ACCESS_TOKEN_TTL | 15 minutes (900 seconds) | Access token expiration |
| REFRESH_TOKEN_TTL_REGULAR | 7 days | Refresh token TTL for REGULAR portal |
| REFRESH_TOKEN_TTL_ADMIN | 4 hours | Refresh token TTL for ADMIN portal |
| PASSWORD_RESET_TOKEN_TTL | 1 hour | Reset token expiration |
| MAX_CONCURRENT_SESSIONS | 5 | Maximum active token families per user |

These are domain constants, not infrastructure configuration. They live in the IAM domain layer.

---

## 10. Dependencies

### Internal Dependencies

- **Spec 001 (Shared Kernel):** `Entity`, `DomainEvent`, `Command`, `AbstractUnitOfWork`, exception base classes
- **Spec 002 (User Registration & Identity):** `User` aggregate, `EmailAddress`, `Username`, `HashedPassword`, `UserStatus`, `PasswordHasher`, `UserRepository`, `AbstractIamUnitOfWork`, `validate_password_strength`, `validate_not_in_history`, `UserLoggedIn`, `PasswordChanged`

### Downstream Dependents (Blocks)

- **Spec 004 (System Roles & Admin Permissions):** Extends `SystemRole` with mutation methods, adds `AdminPermission` to `AuthenticatedIdentity`
- **Spec 005 (Federated Authentication):** OAuth flows create token pairs using the same `TokenService` and `RefreshToken` infrastructure

### External Dependencies

- Python standard library only for domain layer (`uuid`, `datetime`, `enum`, `dataclasses`, `typing`)
- JWT signing/verification implementation is an infrastructure concern (e.g., `PyJWT`, `python-jose`)
- Cryptographic random token generation is an infrastructure concern (e.g., `secrets` module)

---

## 11. Constraints

- **Pure domain layer:** Zero framework/infrastructure dependencies in entities, value objects, and domain services
- **Protocol-based ports:** `TokenService`, `RefreshTokenRepository`, `PasswordResetTokenRepository` are protocols
- **UTC only:** All timestamps are UTC with timezone awareness
- **Stateless access tokens:** Access tokens are never stored server-side; verification is by signature only
- **No email dispatch:** This spec generates the reset token but does not send emails — that is triggered by the API layer using the returned raw token
- **Immutable events:** All domain events are `@dataclass(frozen=True)`, no sensitive data in events

---

## 12. Open Questions

None — all questions were resolved during the clarification phase.

---

## 13. Appendix

### Glossary

| Term | Definition |
|------|------------|
| **Access Token** | A short-lived JWT used for API authorization. Stateless — verified by signature only. |
| **Refresh Token** | A long-lived, opaque token stored server-side (hashed). Used to obtain new access tokens. |
| **Token Family** | A logical grouping of refresh tokens originating from the same login session. Used for theft detection. |
| **Token Rotation** | The practice of issuing a new refresh token on each use, revoking the old one. |
| **Theft Detection** | When a revoked refresh token is reused, the entire family is revoked, logging out all parties. |
| **Portal Context** | Identifies whether a session is for the regular app (REGULAR) or admin portal (ADMIN). Affects token TTL. |
| **SystemRole** | Coarse-grained role: USER, ADMIN, SUPERADMIN. Determines portal access. |
| **AuthenticatedIdentity** | The value object IAM provides to downstream contexts as the sole identity contract. |
| **LoginResult** | The DTO returned by login/refresh containing access_token, refresh_token, and expires_in. |

### References

- [Functional Requirements Document](../../docs/functional-requirements.md)
- [Specification Index](../README.md)
- [Spec 001: Shared Kernel](../spec-001-shared-kernel/spec.md)
- [Spec 002: User Registration & Identity](../spec-002-user-registration-and-identity/spec.md)
- RFC 7519 — JSON Web Token (JWT)
- RFC 7518 — JSON Web Algorithms (JWA) — RS256, ES256
- OWASP Session Management Cheat Sheet
- Auth0 — Refresh Token Rotation (family-based theft detection reference)

---
