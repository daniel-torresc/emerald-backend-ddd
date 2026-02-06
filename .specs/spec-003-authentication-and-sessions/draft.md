# Spec 003: Authentication & Sessions

**Status:** Draft
**Bounded Context:** Identity & Access Management (IAM)
**Dependencies:** 001 (Shared Kernel), 002 (User Registration & Identity)
**Blocks:** 004, 005

---

## 1. Overview

This spec defines password-based authentication, JWT token lifecycle, refresh token rotation, and session management. It establishes the token infrastructure that all authentication methods (password and federated) rely on.

**Key Principle:** A unified token mechanism serves all users regardless of how they authenticated. Token lifetimes vary by portal context (regular app vs admin portal) for security.

## 2. Scope

### In Scope

- Password login flow (email + password -> tokens)
- Access token (JWT) structure and claims
- Refresh token entity and lifecycle
- Token rotation with family-based theft detection
- Session management (concurrent session limits)
- Logout (single session and all sessions)
- `AuthenticatedIdentity` value object (integration contract)
- Password reset flow

### Out of Scope

- Federated authentication / OAuth flows (Spec 005)
- System roles and admin permissions in token claims (Spec 004 — this spec includes the `system_role` claim but role enforcement is in 004)
- Device binding (future enhancement)
- MFA (future enhancement)

## 3. Authentication Flow

### 3.1 Password Login

```
Client sends: { email, password }
     │
     ▼
Validate credentials:
  1. Find user by email
  2. Verify password hash
  3. Check user status == ACTIVE
     │
     ├── Invalid credentials ──► AuthenticationFailedError
     ├── PENDING_VERIFICATION ──► EmailNotVerifiedError
     ├── SUSPENDED ──► AccountSuspendedError
     ├── DELETED ──► AuthenticationFailedError (same as invalid, no info leak)
     │
     ▼
Create token pair:
  1. Generate access token (JWT)
  2. Create refresh token entity (stored, hashed)
  3. Assign to token family
  4. Record login on user (last_login_at)
     │
     ▼
Return: { access_token, refresh_token, expires_in }
```

### 3.2 Token Refresh

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
     ├── Expired ──► TokenExpiredError
     ├── Revoked ──► THEFT DETECTED (see 3.3)
     │
     ▼
Rotate tokens:
  1. Revoke current refresh token
  2. Generate new access token
  3. Create new refresh token (same family)
  4. Return new token pair
```

### 3.3 Token Theft Detection

When a revoked refresh token is presented, it indicates a potential token theft — the legitimate user already rotated their token, and now a stolen copy is being used.

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

### 3.4 Password Reset

```
User requests reset: { email }
     │
     ▼
  1. Find user by email (if exists)
  2. Generate reset token (short-lived, single-use)
  3. Emit PasswordResetRequested event (triggers email)
  4. Always return success (no user enumeration)

User submits new password: { reset_token, new_password }
     │
     ▼
  1. Validate reset token (exists, not expired, not used)
  2. Validate new password (strength, history)
  3. Change password on User entity
  4. Revoke all refresh tokens for user (force re-login)
  5. Mark reset token as used
  6. Emit PasswordChanged event
```

## 4. Token Specification

### 4.1 Access Token (JWT)

Short-lived, stateless token for API authorization. Not stored server-side.

**Claims:**

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | str (UUID) | User ID |
| `email` | str | User email |
| `system_role` | str | USER, ADMIN, or SUPERADMIN |
| `iat` | int | Issued at (Unix timestamp) |
| `exp` | int | Expiration (Unix timestamp) |
| `jti` | str (UUID) | Unique token ID |

**Lifetimes by Context:**

| Context | Access Token TTL | Purpose |
|---------|-----------------|---------|
| Regular App | 15 minutes | Standard API authorization |
| Admin Portal | 15 minutes | Admin API authorization |

**Rules:**

- Signed with RS256 or ES256 (asymmetric — public key available for verification)
- Never stored server-side (stateless verification via signature)
- Claims are minimal — detailed permissions fetched on demand if needed

### 4.2 Refresh Token

Long-lived, opaque token stored server-side (hashed). Used only to obtain new access tokens.

**Entity Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| token_id | UUID | No | Unique identifier |
| user_id | UUID | No | Owner of this token |
| token_hash | str | No | SHA-256 hash of the opaque token value |
| family_id | UUID | No | Token family for theft detection |
| portal_context | PortalContext | No | REGULAR or ADMIN |
| expires_at | datetime | No | When this token expires |
| revoked_at | datetime? | Yes | When revoked (None = active) |
| created_at | datetime | No | When issued |

**Enum — PortalContext:**

| Value | Refresh TTL | Description |
|-------|-------------|-------------|
| REGULAR | 7 days | Standard application |
| ADMIN | 4 hours | Admin portal (shorter for security) |

**Rules:**

- The raw token value is returned to the client once and never stored server-side (only the hash)
- Each refresh creates a new token in the same family, revoking the old one
- Token families allow detecting stolen tokens (see theft detection)

### 4.3 Token Family

A logical grouping of refresh tokens originating from the same login session.

**Behavior:**

- A new family is created on each login
- Each token rotation creates a new token in the same family
- If a revoked token is reused, the entire family is revoked
- Family is identified by `family_id` on each refresh token

## 5. Session Management

### 5.1 Concurrent Session Limit

| Setting | Default | Description |
|---------|---------|-------------|
| max_concurrent_sessions | 5 | Maximum active token families per user |

**Enforcement:**

```
On new login:
  1. Count active (non-expired, non-revoked) token families for user
  2. If count >= max_concurrent_sessions:
     a. Revoke oldest token family
     b. Proceed with new login
```

### 5.2 Logout

**Single Session:**

```
logout(refresh_token):
  1. Find refresh token by hash
  2. Revoke it
  3. Note: Access token remains valid until expiry (stateless)
     Client should discard access token
```

**All Sessions:**

```
logout_all(user_id):
  1. Revoke ALL active refresh tokens for user
  2. Emit AllSessionsRevoked event
```

## 6. Integration Contract: AuthenticatedIdentity

The value object that IAM exposes to downstream bounded contexts after successful authentication.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| user_id | UUID | User identifier |
| email | EmailAddress | User email |
| display_name | str | Username or full name for display |
| system_role | SystemRole | USER, ADMIN, or SUPERADMIN |
| admin_permissions | set[AdminPermission]? | Granular admin capabilities (None for USER) |

**Rules:**

- Constructed from the access token claims + minimal user lookup if needed
- Passed to downstream contexts (Core Finance, Classification) at the application layer boundary
- Downstream contexts must not access IAM internals — only this value object

**Note:** `system_role` and `admin_permissions` are included here for completeness, but their logic is defined in Spec 004. For pure USER-role users, `admin_permissions` is always None.

## 7. Password Reset Token

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| token_id | UUID | Unique identifier |
| user_id | UUID | User requesting reset |
| token_hash | str | SHA-256 hash of the token value |
| expires_at | datetime | Expiration (short-lived, e.g., 1 hour) |
| used_at | datetime? | When the token was used (None = unused) |
| created_at | datetime | When issued |

**Rules:**

- Single-use: once used, cannot be used again
- Short-lived: expires after 1 hour (configurable)
- Only one active reset token per user (creating a new one invalidates previous)
- Raw token value sent via email, only hash stored server-side

## 8. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `UserLoggedIn` | Successful password login | user_id, portal_context |
| `LoginFailed` | Failed login attempt | email (not user_id — may not exist) |
| `TokenRefreshed` | Successful token rotation | user_id, family_id |
| `TokenRevoked` | Token revocation | user_id, token_id |
| `TokenFamilyCompromised` | Reuse of revoked token detected | user_id, family_id |
| `AllSessionsRevoked` | Logout all sessions | user_id |
| `PasswordResetRequested` | User requests password reset | user_id |

## 9. Repository Interfaces

```
RefreshTokenRepository (Protocol):
  + save(token: RefreshToken) -> None
  + find_by_hash(token_hash: str) -> RefreshToken?
  + find_active_families_by_user(user_id: UUID) -> list[UUID]
  + revoke_family(family_id: UUID) -> None
  + revoke_all_for_user(user_id: UUID) -> None
  + count_active_families(user_id: UUID) -> int

PasswordResetTokenRepository (Protocol):
  + save(token: PasswordResetToken) -> None
  + find_by_hash(token_hash: str) -> PasswordResetToken?
  + invalidate_existing_for_user(user_id: UUID) -> None
```

## 10. Acceptance Criteria

### Password Login

- [ ] Valid email + password for ACTIVE user returns access + refresh token pair
- [ ] Invalid password returns `AuthenticationFailedError` (no hint about what's wrong)
- [ ] Non-existent email returns `AuthenticationFailedError` (no user enumeration)
- [ ] PENDING_VERIFICATION user returns `EmailNotVerifiedError`
- [ ] SUSPENDED user returns `AccountSuspendedError`
- [ ] DELETED user returns `AuthenticationFailedError` (same as invalid)
- [ ] Successful login records `last_login_at` on user
- [ ] Successful login emits `UserLoggedIn` event
- [ ] Failed login emits `LoginFailed` event

### Access Token

- [ ] JWT contains `sub`, `email`, `system_role`, `iat`, `exp`, `jti` claims
- [ ] Token expires after 15 minutes
- [ ] Token is verifiable using public key (asymmetric signing)

### Refresh Token

- [ ] Refresh token stored as SHA-256 hash (raw value never persisted)
- [ ] Refresh for REGULAR context expires after 7 days
- [ ] Refresh for ADMIN context expires after 4 hours
- [ ] Refreshing returns new access + refresh tokens and revokes the old refresh token
- [ ] Refreshing an expired token returns `TokenExpiredError`
- [ ] Refreshing a revoked token revokes the entire token family (theft detection)
- [ ] Theft detection emits `TokenFamilyCompromised` event

### Session Management

- [ ] New login when at max sessions (5) revokes the oldest session
- [ ] Logout revokes the specific refresh token
- [ ] Logout all revokes all refresh tokens for the user
- [ ] Logout all emits `AllSessionsRevoked` event

### Password Reset

- [ ] Reset request always returns success (no user enumeration)
- [ ] Reset request for existing user creates reset token and emits `PasswordResetRequested`
- [ ] Reset token is single-use and expires after 1 hour
- [ ] Creating a new reset token invalidates any previous one for the same user
- [ ] Submitting valid reset token with valid password changes password and revokes all sessions
- [ ] Submitting expired or used reset token returns error

### AuthenticatedIdentity

- [ ] Constructed from valid access token claims
- [ ] Contains user_id, email, display_name, system_role, admin_permissions
- [ ] `admin_permissions` is None for USER role
