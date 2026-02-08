# Authentication & Sessions Implementation Plan

**Spec:** `.specs/spec-003-authentication-and-sessions/spec.md`
**Version:** 1.0
**Date:** 2026-02-07

---

## 1. Overview

This plan implements password-based authentication, JWT token lifecycle, refresh token rotation with family-based theft detection, session management, password reset, and the `AuthenticatedIdentity` cross-context integration contract — all within the IAM bounded context.

**Approach:** Inside-out (Domain -> Application), extending existing IAM infrastructure from Spec 002. All new code follows the established patterns: frozen dataclass value objects, Protocol-based ports, Entity base class, cooperative mixin constructors, and in-memory test fakes.

**Estimated scope:** ~15 new files, ~8 modified files, ~350+ new tests.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| REQ-VO-301 (SystemRole) | Domain | `SystemRole` enum |
| REQ-VO-302 (PortalContext) | Domain | `PortalContext` enum |
| REQ-VO-303 (AuthenticatedIdentity) | Domain | `AuthenticatedIdentity` frozen dataclass |
| REQ-VO-304 (AccessTokenClaims) | Domain | `AccessTokenClaims` frozen dataclass |
| REQ-ENT-301 (RefreshToken) | Domain | `RefreshToken` entity extending `Entity` |
| REQ-ENT-302 (PasswordResetToken) | Domain | `PasswordResetToken` entity extending `Entity` |
| REQ-USER-301 (SystemRole on User) | Domain | Modify `User.__init__` and `User.register()` |
| REQ-USER-302 (reset_password) | Domain | New method on `User` aggregate |
| REQ-PORT-301 (TokenService) | Domain | `TokenService` Protocol in domain/ports |
| REQ-EVT (6 new events) | Domain | New events in domain/events |
| REQ-EXC (7 new exceptions) | Domain | New exceptions in domain/exceptions |
| REQ-REPO-301 (RefreshTokenRepository) | Application | Protocol in application/ports/outbound |
| REQ-REPO-302 (PasswordResetTokenRepository) | Application | Protocol in application/ports/outbound |
| REQ-UOW-301 (Extend UoW) | Application | Modify `AbstractIamUnitOfWork` |
| REQ-CMD-301 (6 commands) | Application | New commands in application/dto |
| REQ-SVC-301 (AuthenticationService) | Application | New service in application/services |
| LoginResult DTO | Application | DTO in application/dto |

### 2.2 Component Diagram

```
                    DOMAIN LAYER
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Value Objects / Enums:                                     │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────────────────┐│
│  │SystemRole│ │PortalContext │ │AccessTokenClaims         ││
│  └──────────┘ └──────────────┘ └──────────────────────────┘│
│  ┌──────────────────────────┐                               │
│  │AuthenticatedIdentity     │ (integration contract)        │
│  └──────────────────────────┘                               │
│                                                             │
│  Entities:                                                  │
│  ┌──────────────┐  ┌────────────────────┐                   │
│  │RefreshToken   │  │PasswordResetToken  │                  │
│  │(extends Entity)│  │(extends Entity)    │                  │
│  └──────────────┘  └────────────────────┘                   │
│                                                             │
│  User Aggregate (modified):                                 │
│  ┌──────────────────────────────────┐                       │
│  │User + system_role + reset_password│                      │
│  └──────────────────────────────────┘                       │
│                                                             │
│  Ports:                           Events (6 new):           │
│  ┌──────────────┐                ┌────────────────────────┐ │
│  │TokenService   │                │LoginFailed             │ │
│  │(Protocol)     │                │TokenRefreshed          │ │
│  └──────────────┘                │TokenRevoked            │ │
│                                  │TokenFamilyCompromised  │ │
│  Exceptions (7 new):            │AllSessionsRevoked      │ │
│  ┌──────────────────────┐       │PasswordResetRequested  │ │
│  │AuthenticationFailed  │       └────────────────────────┘ │
│  │EmailNotVerified      │                                   │
│  │AccountSuspended      │  Constants:                       │
│  │InvalidToken          │  ┌────────────────────────┐       │
│  │TokenExpired           │  │ACCESS_TOKEN_TTL = 900  │       │
│  │TokenAlreadyRevoked   │  │REFRESH_TTL_REGULAR=7d  │       │
│  │TokenAlreadyUsed      │  │REFRESH_TTL_ADMIN=4h    │       │
│  └──────────────────────┘  │RESET_TTL=1h            │       │
│                             │MAX_SESSIONS=5          │       │
│                             └────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘

                  APPLICATION LAYER
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Commands:                        DTO:                      │
│  ┌──────────────────────┐        ┌────────────┐             │
│  │LoginUser              │        │LoginResult │             │
│  │RefreshAccessToken     │        └────────────┘             │
│  │LogoutSession          │                                   │
│  │LogoutAllSessions      │  Repository Ports:                │
│  │RequestPasswordReset   │  ┌──────────────────────────────┐│
│  │SubmitPasswordReset    │  │RefreshTokenRepository        ││
│  └──────────────────────┘  │PasswordResetTokenRepository  ││
│                             └──────────────────────────────┘│
│  Unit of Work (extended):                                   │
│  ┌──────────────────────────────────────────┐               │
│  │AbstractIamUnitOfWork                      │               │
│  │  .users: UserRepository                   │               │
│  │  .refresh_tokens: RefreshTokenRepository  │               │
│  │  .password_reset_tokens: PwResetTokenRepo │               │
│  └──────────────────────────────────────────┘               │
│                                                             │
│  Service:                                                   │
│  ┌──────────────────────────────────────────┐               │
│  │AuthenticationService                      │               │
│  │  .login(cmd) -> LoginResult               │               │
│  │  .refresh(cmd) -> LoginResult             │               │
│  │  .logout(cmd) -> None                     │               │
│  │  .logout_all(cmd) -> None                 │               │
│  │  .request_password_reset(cmd) -> str|None │               │
│  │  .submit_password_reset(cmd) -> None      │               │
│  │  .verify_access_token(token) -> Identity  │               │
│  └──────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Ports and Adapters

| Port (Protocol) | Purpose | Test Adapter (Fake) |
|------------------|---------|---------------------|
| `TokenService` | JWT signing/verification, refresh token generation | `FakeTokenService` — returns deterministic tokens |
| `RefreshTokenRepository` | Refresh token persistence | `FakeRefreshTokenRepository` — in-memory dict |
| `PasswordResetTokenRepository` | Password reset token persistence | `FakePasswordResetTokenRepository` — in-memory dict |

---

## 3. Technical Decisions

### 3.1 Token Entity Placement
**Decision:** `RefreshToken` and `PasswordResetToken` extend `Entity` directly (not `AggregateRoot`).
**Rationale:** Per the spec, these are not aggregate roots — they are managed by `AuthenticationService`. They need UUID identity from `Entity` but not event collection or timestamped/auditable mixins.

### 3.2 SystemRole on User
**Decision:** Add `system_role` as an `__init__` parameter with default `SystemRole.USER`. Set in `register()` factory.
**Rationale:** The attribute is read-only in this spec (mutation is Spec 004). Adding it to the constructor allows reconstruction from persistence.

### 3.3 Domain Constants
**Decision:** Domain constants (TTLs, session limits) as module-level constants in a dedicated `constants.py` file under `domain/`.
**Rationale:** Spec explicitly states these are domain constants, not infrastructure configuration. Keeping them in the domain layer allows entities and services to reference them without infrastructure dependencies.

### 3.4 LoginFailed Event aggregate_id
**Decision:** Use `uuid.UUID(int=0)` (nil UUID) as the sentinel `aggregate_id` for `LoginFailed` events.
**Rationale:** Per BR-EVT-302, the user may not exist, so there's no real aggregate ID. A nil UUID is a well-known sentinel.

### 3.5 AuthenticatedIdentity Equality
**Decision:** Custom `__eq__` based on `user_id` only (per spec: "Two identities with the same user_id are equal").
**Rationale:** Spec explicitly requires user_id-based equality, which differs from default frozen dataclass field-by-field equality.

### 3.6 Event File Organization
**Decision:** Add new authentication events to a new file `auth_events.py` alongside existing `user_events.py`.
**Rationale:** Keeps event files focused by concern area. Authentication events are conceptually different from user lifecycle events.

### 3.7 Exception Hierarchy Mapping
**Decision:** Follow the exact hierarchy from spec section 5.10:
- `AuthenticationFailedError` → extends `DomainError` directly
- `EmailNotVerifiedError` → extends `DomainError` directly
- `AccountSuspendedError` → extends `DomainError` directly
- `InvalidTokenError` → extends `InvalidValueError`
- `TokenExpiredError` → extends `DomainError` directly
- `TokenAlreadyRevokedError` → extends `ConflictError`
- `TokenAlreadyUsedError` → extends `ConflictError`

**Rationale:** Matches spec exactly. Each base provides the right semantic category for catch-by-type error handling.

---

## 4. Implementation Tasks

### Phase 1: Domain Layer — Value Objects & Enums

#### TASK-001: Create SystemRole Enum
**Layer:** Domain
**Depends On:** None

**Description:**
Create the `SystemRole` enum with values USER, ADMIN, SUPERADMIN.

**Files to Create:**
- `src/emerald/iam/domain/models/system_role.py`

**Tests:**
- `tests/unit/iam/domain/value_objects/test_system_role.py`
  - [ ] Enum has exactly 3 values: USER, ADMIN, SUPERADMIN
  - [ ] Values are string-backed (e.g., `"USER"`)

---

#### TASK-002: Create PortalContext Enum
**Layer:** Domain
**Depends On:** None

**Description:**
Create the `PortalContext` enum with values REGULAR and ADMIN, each carrying its refresh token TTL as a `timedelta`.

**Files to Create:**
- `src/emerald/iam/domain/models/portal_context.py`

**Tests:**
- `tests/unit/iam/domain/value_objects/test_portal_context.py`
  - [ ] Enum has exactly 2 values: REGULAR, ADMIN
  - [ ] REGULAR has 7-day refresh TTL
  - [ ] ADMIN has 4-hour refresh TTL

---

#### TASK-003: Create Domain Constants
**Layer:** Domain
**Depends On:** None

**Description:**
Create a constants module with ACCESS_TOKEN_TTL (900s), REFRESH_TOKEN_TTL_REGULAR (7 days), REFRESH_TOKEN_TTL_ADMIN (4 hours), PASSWORD_RESET_TOKEN_TTL (1 hour), MAX_CONCURRENT_SESSIONS (5).

**Files to Create:**
- `src/emerald/iam/domain/constants.py`

**Tests:**
- `tests/unit/iam/domain/test_constants.py`
  - [ ] All constants have correct values

---

#### TASK-004: Create AccessTokenClaims Value Object
**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Create `AccessTokenClaims` as `@dataclass(frozen=True)` with fields: `sub` (UUID), `email` (str), `system_role` (SystemRole), `iat` (datetime), `exp` (datetime), `jti` (UUID). Validate `exp > iat` and UTC awareness in `__post_init__`.

**Files to Create:**
- `src/emerald/iam/domain/models/access_token_claims.py`

**Tests:**
- `tests/unit/iam/domain/value_objects/test_access_token_claims.py`
  - [ ] Valid construction with all fields
  - [ ] `exp` before or equal to `iat` raises `InvalidValueError`
  - [ ] Non-UTC datetime raises `InvalidValueError`
  - [ ] Frozen (immutable)

---

#### TASK-005: Create AuthenticatedIdentity Value Object
**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Create `AuthenticatedIdentity` as `@dataclass(frozen=True, eq=False)` with fields: `user_id` (UUID), `email` (EmailAddress), `display_name` (str), `system_role` (SystemRole). Custom `__eq__` and `__hash__` based on `user_id` only.

**Files to Create:**
- `src/emerald/iam/domain/models/authenticated_identity.py`

**Tests:**
- `tests/unit/iam/domain/value_objects/test_authenticated_identity.py`
  - [ ] Construction with all fields
  - [ ] Two identities with same `user_id` are equal regardless of other fields
  - [ ] Two identities with different `user_id` are not equal
  - [ ] Usable in set (hashable by `user_id`)
  - [ ] Frozen (immutable)

---

### Phase 2: Domain Layer — Entities

#### TASK-006: Create RefreshToken Entity
**Layer:** Domain
**Depends On:** TASK-002

**Description:**
Create `RefreshToken` extending `Entity` with attributes: `user_id`, `token_hash`, `family_id`, `portal_context`, `expires_at`, `revoked_at` (None), `created_at`. Methods: `revoke()`, `is_active()`, `is_expired()`, `is_revoked()`.

**Files to Create:**
- `src/emerald/iam/domain/models/refresh_token.py`

**Tests:**
- `tests/unit/iam/domain/entities/test_refresh_token.py`
  - [ ] Construction with UUID id from Entity
  - [ ] `revoke()` sets `revoked_at` to current UTC time
  - [ ] `revoke()` on already-revoked raises `TokenAlreadyRevokedError`
  - [ ] `is_active()` True when not revoked and not expired
  - [ ] `is_active()` False when revoked
  - [ ] `is_active()` False when expired
  - [ ] `is_expired()` correctly compares to current time
  - [ ] `is_revoked()` True when `revoked_at` is not None
  - [ ] All datetime attributes are timezone-aware UTC

---

#### TASK-007: Create PasswordResetToken Entity
**Layer:** Domain
**Depends On:** None

**Description:**
Create `PasswordResetToken` extending `Entity` with attributes: `user_id`, `token_hash`, `expires_at`, `used_at` (None), `created_at`. Methods: `mark_used()`, `is_valid()`, `is_expired()`, `is_used()`. Default 1-hour expiry.

**Files to Create:**
- `src/emerald/iam/domain/models/password_reset_token.py`

**Tests:**
- `tests/unit/iam/domain/entities/test_password_reset_token.py`
  - [ ] Construction with UUID id from Entity
  - [ ] `mark_used()` sets `used_at` to current UTC time
  - [ ] `mark_used()` on already-used raises `TokenAlreadyUsedError`
  - [ ] `is_valid()` True when not used and not expired
  - [ ] `is_valid()` False when used
  - [ ] `is_valid()` False when expired
  - [ ] Default 1-hour expiration from creation time
  - [ ] All datetime attributes are timezone-aware UTC

---

### Phase 3: Domain Layer — Events, Exceptions, User Modifications

#### TASK-008: Add Authentication Domain Events
**Layer:** Domain
**Depends On:** None

**Description:**
Create 6 new domain events in a new `auth_events.py` file:
- `LoginFailed` — `email: str`, uses nil UUID as `aggregate_id`
- `TokenRefreshed` — `user_id: UUID`, `family_id: UUID`
- `TokenRevoked` — `user_id: UUID`, `token_id: UUID`
- `TokenFamilyCompromised` — `user_id: UUID`, `family_id: UUID`
- `AllSessionsRevoked` — `user_id: UUID`
- `PasswordResetRequested` — `user_id: UUID`

All extend `DomainEvent` with `aggregate_type = "User"`.

**Files to Create:**
- `src/emerald/iam/domain/events/auth_events.py`

**Files to Modify:**
- `src/emerald/iam/domain/events/__init__.py` — re-export new events

**Tests:**
- `tests/unit/iam/domain/events/test_auth_events.py`
  - [ ] All 6 events are `@dataclass(frozen=True)` extending `DomainEvent`
  - [ ] `LoginFailed` carries `email`, not user_id
  - [ ] `LoginFailed` uses nil UUID as aggregate_id
  - [ ] No event contains raw token values or passwords
  - [ ] Each event has `aggregate_type = "User"`

---

#### TASK-009: Add Authentication Exceptions
**Layer:** Domain
**Depends On:** None

**Description:**
Add 7 new exceptions to `iam_exceptions.py`:
- `AuthenticationFailedError(DomainError)` — code: `"AUTHENTICATION_FAILED"`, intentionally vague message
- `EmailNotVerifiedError(DomainError)` — code: `"EMAIL_NOT_VERIFIED"`
- `AccountSuspendedError(DomainError)` — code: `"ACCOUNT_SUSPENDED"`
- `InvalidTokenError(InvalidValueError)` — code: `"INVALID_TOKEN"`
- `TokenExpiredError(DomainError)` — code: `"TOKEN_EXPIRED"`
- `TokenAlreadyRevokedError(ConflictError)` — code: `"TOKEN_ALREADY_REVOKED"`
- `TokenAlreadyUsedError(ConflictError)` — code: `"TOKEN_ALREADY_USED"`

**Files to Modify:**
- `src/emerald/iam/domain/exceptions/iam_exceptions.py`
- `src/emerald/iam/domain/exceptions/__init__.py` — re-export new exceptions

**Tests:**
- `tests/unit/iam/domain/exceptions/test_auth_exceptions.py`
  - [ ] All 7 exceptions have correct parent class
  - [ ] All have unique `code` strings
  - [ ] `AuthenticationFailedError` message is vague (no hints)
  - [ ] All allow message override

---

#### TASK-010: Add SystemRole to User Aggregate
**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Modify `User.__init__` to accept `system_role: SystemRole = SystemRole.USER`. Modify `User.register()` to set `system_role=SystemRole.USER`. No mutation method in this spec.

**Files to Modify:**
- `src/emerald/iam/domain/models/user.py`

**Tests:**
- `tests/unit/iam/domain/aggregates/test_user_system_role.py`
  - [ ] New users via `register()` have `system_role = SystemRole.USER`
  - [ ] `system_role` is accessible as attribute
  - [ ] Reconstructed user accepts custom `system_role`
  - [ ] Existing tests still pass (no regression)

---

#### TASK-011: Add reset_password() Method to User
**Layer:** Domain
**Depends On:** TASK-010

**Description:**
Add `reset_password(new_hashed: HashedPassword, old_hash_to_archive: str) -> None` method. Allowed from ACTIVE or SUSPENDED status. Archives old hash in history (max 5, FIFO), sets new password, emits `PasswordChanged`.

**Files to Modify:**
- `src/emerald/iam/domain/models/user.py`

**Tests:**
- `tests/unit/iam/domain/aggregates/test_user_reset_password.py`
  - [ ] Succeeds from ACTIVE status
  - [ ] Succeeds from SUSPENDED status
  - [ ] Raises `InvalidStateTransitionError` from PENDING_VERIFICATION
  - [ ] Raises `InvalidStateTransitionError` from DELETED
  - [ ] Archives old password hash in history (max 5, FIFO)
  - [ ] Sets new password
  - [ ] Emits `PasswordChanged` event

---

### Phase 4: Domain Layer — Port

#### TASK-012: Create TokenService Protocol
**Layer:** Domain
**Depends On:** TASK-004

**Description:**
Create `TokenService` as `typing.Protocol` with methods:
- `sign_access_token(claims: AccessTokenClaims) -> str`
- `verify_access_token(token: str) -> AccessTokenClaims`
- `generate_refresh_token() -> tuple[str, str]`
- `hash_token(raw_token: str) -> str`

**Files to Create:**
- `src/emerald/iam/domain/ports/token_service.py`

**Files to Modify:**
- `src/emerald/iam/domain/ports/__init__.py` — re-export `TokenService`

**Tests:**
- Protocol compliance verified via fake in service tests (no dedicated unit test needed for a protocol definition)

---

### Phase 5: Application Layer — Ports & DTOs

#### TASK-013: Create Repository Protocols
**Layer:** Application
**Depends On:** TASK-006, TASK-007

**Description:**
Create `RefreshTokenRepository` and `PasswordResetTokenRepository` as `typing.Protocol` classes.

**RefreshTokenRepository methods:**
- `add(token: RefreshToken) -> None`
- `find_by_hash(token_hash: str) -> RefreshToken | None`
- `find_active_families_by_user(user_id: UUID) -> list[UUID]`
- `revoke_family(family_id: UUID) -> None`
- `revoke_all_for_user(user_id: UUID) -> None`
- `count_active_families(user_id: UUID) -> int`

**PasswordResetTokenRepository methods:**
- `add(token: PasswordResetToken) -> None`
- `find_by_hash(token_hash: str) -> PasswordResetToken | None`
- `invalidate_existing_for_user(user_id: UUID) -> None`

**Files to Create:**
- `src/emerald/iam/application/ports/outbound/refresh_token_repository.py`
- `src/emerald/iam/application/ports/outbound/password_reset_token_repository.py`

**Files to Modify:**
- `src/emerald/iam/application/ports/__init__.py` — re-export new repos
- `src/emerald/iam/application/ports/outbound/__init__.py` — re-export new repos

---

#### TASK-014: Extend AbstractIamUnitOfWork
**Layer:** Application
**Depends On:** TASK-013

**Description:**
Add `refresh_tokens: RefreshTokenRepository` and `password_reset_tokens: PasswordResetTokenRepository` attributes to `AbstractIamUnitOfWork`.

**Files to Modify:**
- `src/emerald/iam/application/ports/outbound/unit_of_work.py`

**Tests:**
- Verified via fake in service tests

---

#### TASK-015: Create Authentication Commands and LoginResult DTO
**Layer:** Application
**Depends On:** None

**Description:**
Create 6 commands extending `Command`:
- `LoginUser(email: str, password: str, portal_context: str)`
- `RefreshAccessToken(refresh_token: str)`
- `LogoutSession(refresh_token: str)`
- `LogoutAllSessions(user_id: str)`
- `RequestPasswordReset(email: str)`
- `SubmitPasswordReset(reset_token: str, new_password: str)`

Create `LoginResult` as `@dataclass(frozen=True)` with `access_token: str`, `refresh_token: str`, `expires_in: int`.

**Files to Create:**
- `src/emerald/iam/application/dto/auth_commands.py`
- `src/emerald/iam/application/dto/auth_dtos.py`

**Files to Modify:**
- `src/emerald/iam/application/dto/__init__.py` — re-export new commands and DTO

**Tests:**
- `tests/unit/iam/application/dto/test_auth_commands.py`
  - [ ] All commands are frozen dataclasses extending `Command`
  - [ ] All carry only primitive types (str)
  - [ ] `LoginUser` includes `portal_context` field
- `tests/unit/iam/application/dto/test_login_result.py`
  - [ ] `LoginResult` is frozen with access_token, refresh_token, expires_in

---

### Phase 6: Application Layer — Service & Fakes

#### TASK-016: Create Test Fakes for Spec 003
**Layer:** Test Infrastructure
**Depends On:** TASK-012, TASK-013, TASK-014

**Description:**
Extend the existing `fakes.py` with:
- `FakeTokenService` — deterministic: `sign_access_token` returns `"fake_access_token:{jti}"`, `verify_access_token` parses it back, `generate_refresh_token` returns `("raw_token_{counter}", "hash_token_{counter}")`, `hash_token` returns `"hashed:{raw}"`.
- `FakeRefreshTokenRepository` — in-memory dict by `id`, supports all 6 protocol methods.
- `FakePasswordResetTokenRepository` — in-memory dict by `id`, supports all 3 protocol methods.
- Update `FakeIamUnitOfWork` to include `refresh_tokens` and `password_reset_tokens` attributes.

**Files to Modify:**
- `tests/unit/iam/fakes.py`

**Acceptance Criteria:**
- [ ] All fakes implement protocol methods correctly
- [ ] `FakeTokenService` is deterministic and predictable
- [ ] `FakeIamUnitOfWork` has all 3 repository attributes
- [ ] Existing tests pass without modification

---

#### TASK-017: Implement AuthenticationService — login()
**Layer:** Application
**Depends On:** TASK-006, TASK-010, TASK-014, TASK-015, TASK-016

**Description:**
Implement `AuthenticationService.__init__` with `uow`, `hasher`, `token_service` dependencies. Implement `login(cmd: LoginUser) -> LoginResult` following the spec steps: resolve portal context, find user, check status, verify password, enforce session limit, create token family, generate tokens, record login, persist, commit, return.

**Files to Create:**
- `src/emerald/iam/application/services/authentication.py`

**Tests:**
- `tests/unit/iam/application/services/test_auth_login.py`
  - [ ] Valid credentials for ACTIVE user returns LoginResult
  - [ ] Invalid password raises AuthenticationFailedError
  - [ ] Non-existent email raises AuthenticationFailedError
  - [ ] PENDING_VERIFICATION raises EmailNotVerifiedError
  - [ ] SUSPENDED raises AccountSuspendedError
  - [ ] DELETED raises AuthenticationFailedError
  - [ ] Records `last_login_at` on user
  - [ ] Emits `UserLoggedIn` event (via User)
  - [ ] Emits `LoginFailed` event on failure
  - [ ] At max sessions (5), oldest family revoked
  - [ ] Access token expires in 900 seconds
  - [ ] Refresh token TTL matches portal context
  - [ ] UoW committed on success

---

#### TASK-018: Implement AuthenticationService — refresh()
**Layer:** Application
**Depends On:** TASK-017

**Description:**
Implement `refresh(cmd: RefreshAccessToken) -> LoginResult` following spec steps: hash token, look up, check expired, check revoked (theft detection), rotate, generate new pair, commit.

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**Tests:**
- `tests/unit/iam/application/services/test_auth_refresh.py`
  - [ ] Valid refresh token returns new token pair
  - [ ] Old refresh token is revoked after rotation
  - [ ] New refresh token is in the same family
  - [ ] Expired token raises TokenExpiredError
  - [ ] Not-found token raises InvalidTokenError
  - [ ] Revoked token triggers theft detection: entire family revoked
  - [ ] Theft detection emits TokenFamilyCompromised event
  - [ ] Emits TokenRefreshed on success

---

#### TASK-019: Implement AuthenticationService — logout() and logout_all()
**Layer:** Application
**Depends On:** TASK-017

**Description:**
Implement `logout(cmd: LogoutSession) -> None` (hash, find, revoke if active, idempotent) and `logout_all(cmd: LogoutAllSessions) -> None` (revoke all for user).

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**Tests:**
- `tests/unit/iam/application/services/test_auth_logout.py`
  - [ ] `logout`: valid token is revoked
  - [ ] `logout`: emits TokenRevoked event
  - [ ] `logout`: non-existent token silently ignored
  - [ ] `logout_all`: all tokens for user revoked
  - [ ] `logout_all`: emits AllSessionsRevoked event

---

#### TASK-020: Implement AuthenticationService — request_password_reset()
**Layer:** Application
**Depends On:** TASK-007, TASK-017

**Description:**
Implement `request_password_reset(cmd: RequestPasswordReset) -> str | None`. Find user by email, return None if not found or DELETED, invalidate existing tokens, generate new reset token, persist, emit event, commit, return raw token.

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**Tests:**
- `tests/unit/iam/application/services/test_auth_password_reset_request.py`
  - [ ] Existing user gets reset token, returns raw token
  - [ ] Non-existent email returns None
  - [ ] DELETED user returns None
  - [ ] Previous reset tokens invalidated
  - [ ] Emits PasswordResetRequested event (when user exists)
  - [ ] Reset token expires in 1 hour

---

#### TASK-021: Implement AuthenticationService — submit_password_reset()
**Layer:** Application
**Depends On:** TASK-011, TASK-020

**Description:**
Implement `submit_password_reset(cmd: SubmitPasswordReset) -> None`. Hash token, find, validate (not expired, not used), validate password strength and history, hash new password, call `user.reset_password()`, mark token used, revoke all refresh tokens, commit.

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**Tests:**
- `tests/unit/iam/application/services/test_auth_password_reset_submit.py`
  - [ ] Valid token + strong password changes password
  - [ ] Old hash archived in history
  - [ ] Token marked as used
  - [ ] All refresh tokens revoked (force re-login)
  - [ ] Expired token raises TokenExpiredError
  - [ ] Used token raises TokenAlreadyUsedError
  - [ ] Not-found token raises InvalidTokenError
  - [ ] Weak password raises PasswordTooWeakError
  - [ ] Password from history raises PasswordReusedError
  - [ ] Works for SUSPENDED user (via reset_password)

---

#### TASK-022: Implement AuthenticationService — verify_access_token()
**Layer:** Application
**Depends On:** TASK-005, TASK-017

**Description:**
Implement `verify_access_token(token: str) -> AuthenticatedIdentity`. Verify via token_service, look up user, resolve display_name, return identity.

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**Tests:**
- `tests/unit/iam/application/services/test_auth_verify_token.py`
  - [ ] Valid token returns AuthenticatedIdentity
  - [ ] Invalid/expired token raises appropriate error
  - [ ] User not found raises InvalidTokenError
  - [ ] `display_name` uses `full_name` when available
  - [ ] `display_name` falls back to `username.value` when no full_name

---

### Phase 7: Public API & Integration

#### TASK-023: Update __init__.py Re-exports
**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-022

**Description:**
Update all `__init__.py` files to re-export new public types:
- `src/emerald/iam/domain/models/__init__.py` — add `SystemRole`, `PortalContext`, `AccessTokenClaims`, `AuthenticatedIdentity`, `RefreshToken`, `PasswordResetToken`
- `src/emerald/iam/domain/events/__init__.py` — add 6 new events
- `src/emerald/iam/domain/exceptions/__init__.py` — add 7 new exceptions
- `src/emerald/iam/domain/ports/__init__.py` — add `TokenService`
- `src/emerald/iam/application/ports/__init__.py` — add `RefreshTokenRepository`, `PasswordResetTokenRepository`
- `src/emerald/iam/application/dto/__init__.py` — add 6 commands, `LoginResult`
- `src/emerald/iam/application/services/__init__.py` — add `AuthenticationService`
- `src/emerald/iam/__init__.py` — add all new public types to `__all__`

**Acceptance Criteria:**
- [ ] All new types importable from `emerald.iam`
- [ ] `__all__` is complete and ordered consistently

---

### Phase 8: Quality Verification

#### TASK-024: Run Full Test Suite and Quality Checks
**Layer:** Cross-cutting
**Depends On:** TASK-023

**Description:**
Run all quality checks and verify no regressions:
1. `uv run pytest -v` — all tests pass (existing 421 + new ~350)
2. `uv run ruff check --fix .` — no lint violations
3. `uv run ruff format .` — code formatted
4. `uv run ty check` — no type errors

**Acceptance Criteria:**
- [ ] All tests pass (zero failures)
- [ ] Ruff check clean
- [ ] Ruff format clean
- [ ] ty check clean
- [ ] No regressions in existing spec-001/spec-002 tests

---

## 5. Task Dependency Graph

```
Phase 1: Value Objects & Enums (parallel)
TASK-001 (SystemRole) ────────┬──► TASK-004 (AccessTokenClaims)
                              ├──► TASK-005 (AuthenticatedIdentity)
                              └──► TASK-010 (SystemRole on User)
TASK-002 (PortalContext) ─────────► TASK-006 (RefreshToken)
TASK-003 (Constants) ─────────────► (used by service tasks)

Phase 2: Entities (after their VOs)
TASK-006 (RefreshToken) ──────┬──► TASK-013 (Repo Protocols)
TASK-007 (PasswordResetToken) ┘

Phase 3: Events, Exceptions, User Mods (parallel)
TASK-008 (Auth Events)  ──────┐
TASK-009 (Auth Exceptions) ───┤
TASK-010 (SystemRole on User) ┼──► TASK-011 (reset_password)
                              │
Phase 4: Port                 │
TASK-004 ──► TASK-012 (TokenService Protocol)

Phase 5: App Ports & DTOs     │
TASK-013 (Repo Protocols) ────┼──► TASK-014 (Extend UoW)
TASK-015 (Commands & DTOs)    │

Phase 6: Service & Fakes      │
TASK-016 (Fakes) ─────────────┤
                              │
TASK-014 + TASK-015 + TASK-016 ──► TASK-017 (login)
                                        │
                                   TASK-017 ──► TASK-018 (refresh)
                                   TASK-017 ──► TASK-019 (logout)
                                   TASK-017 ──► TASK-020 (request_reset)
                                   TASK-020 + TASK-011 ──► TASK-021 (submit_reset)
                                   TASK-017 + TASK-005 ──► TASK-022 (verify_token)

Phase 7: Re-exports
TASK-001..TASK-022 ──► TASK-023 (__init__.py updates)

Phase 8: Quality
TASK-023 ──► TASK-024 (Full verification)
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| User aggregate changes break existing tests | Medium | High | TASK-010 adds optional param with default — backward compatible. Run existing tests after each change. |
| FakeIamUnitOfWork changes break existing service tests | Medium | Medium | New repo attrs are additive, don't change existing attrs. Verify existing tests pass immediately after TASK-016. |
| `ty` type checker strictness on new Protocol types | Medium | Low | Use `**kwargs: Any` pattern. Run `ty check` incrementally per task. |
| Complexity of AuthenticationService methods | Low | Medium | Each method implemented and tested in isolation (TASK-017..22). |
| Event file split confusion (user_events vs auth_events) | Low | Low | Clear naming and `__init__.py` re-exports make it transparent. |

---

## 7. Definition of Done

- [ ] All 24 tasks completed
- [ ] All acceptance criteria met across all spec requirements (REQ-VO-301 through REQ-SVC-301)
- [ ] All user stories (US-301 through US-305) verified
- [ ] All edge cases from spec section 7 covered by tests
- [ ] ~350+ new unit tests passing
- [ ] Existing 421 tests still passing (zero regressions)
- [ ] `uv run ruff check` clean
- [ ] `uv run ruff format .` clean
- [ ] `uv run ty check` clean
- [ ] All new types exported from `emerald.iam` via `__all__`
