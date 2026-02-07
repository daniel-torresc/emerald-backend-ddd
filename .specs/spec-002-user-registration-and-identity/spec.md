# User Registration & Identity Specification

**Version:** 1.0
**Status:** Implemented
**Date:** 2026-02-06
**Bounded Context:** Identity & Access Management (IAM)
**Dependencies:** Spec 001 (Shared Kernel)
**Blocks:** 003, 004, 005, 007, 013

---

## 1. Overview

This spec defines the User aggregate root, its lifecycle state machine, and the password-based registration flow for the Emerald Finance Platform. Every person in the system has exactly one User identity. The User entity is the IAM bounded context's central aggregate, composed from Shared Kernel entity traits (identity, timestamps, soft-delete, auditability) and extended with IAM-specific value objects, domain events, and business rules.

**Key Principle:** One person, one account, one login. The User entity is the single identity record for all platform interactions.

---

## 2. Background & Context

### Problem Statement

The platform needs a foundational identity model before any other business capability can be built. Accounts, transactions, sharing, and classification all reference users. Without a well-defined User aggregate, there is no way to enforce ownership, permissions, or audit trails.

### Business Goals

- Establish a secure, self-service registration flow with email verification
- Provide a robust user lifecycle (active, suspended, deleted, recoverable)
- Support multiple authentication providers per user (password + social) for future federation
- Enforce strong password policies as a domain-level concern
- Enable profile management and user preferences

### Success Metrics

- All downstream specs (003-005, 007, 013) can reference User identity without ambiguity
- Password policy enforced at the domain layer, not at the infrastructure boundary
- State machine prevents invalid transitions at compile/test time
- 100% of domain logic unit-testable without infrastructure dependencies

---

## 3. Scope

### In Scope

- User aggregate root with all attributes and invariants
- Value objects: `EmailAddress`, `Username`, `HashedPassword`, `AuthProvider`, `UserStatus`, `UserPreferences`
- `PasswordHasher` protocol (domain port for hashing — implementation is infrastructure)
- User lifecycle state machine (PENDING_VERIFICATION -> ACTIVE -> SUSPENDED -> DELETED)
- Password registration flow (email + password)
- Email verification requirement
- Email change with re-verification
- Password complexity validation (domain rules, no infrastructure dependency)
- Password history tracking (last 5 hashes)
- Domain events for all lifecycle transitions
- Domain service: `UserRegistrationService` (uniqueness enforcement)
- Repository protocol: `UserRepository`
- IAM-specific exception hierarchy

### Out of Scope

- Token-based sessions and JWT (Spec 003)
- System roles and admin permissions (Spec 004)
- Federated authentication / OAuth flows (Spec 005)
- Soft delete retention policies and hard delete scheduling logic (Spec 006 — this spec uses the `SoftDeletableMixin` from Shared Kernel but does not define retention policy values)
- Email sending / verification token generation (infrastructure concern, not domain)
- Rate limiting on registration or login (infrastructure concern)

---

## 4. Users & Personas

### Primary Users

- **End users** registering for the platform with email + password
- **Administrators** managing user lifecycle (suspend, unsuspend, delete)
- **Developers** building bounded contexts that reference User identity

### User Goals

- Register with an email and password, verify email, gain access
- Manage profile (email, username, full name, preferences)
- Change password with strong security guarantees
- Link additional authentication providers (future: Spec 005)
- Recover a deleted account within the retention window

---

## 5. Requirements

### 5.1 Value Objects

All IAM value objects are **immutable** and implement **equality by value**. They are hashable and safe for use in sets and as dictionary keys.

---

#### REQ-VO-101: EmailAddress

**Priority:** Must Have

A validated, normalized email address.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Normalized email address (lowercase) |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Validate format and normalize to lowercase | `InvalidEmailError` |
| `__eq__` / `__hash__` | Case-insensitive comparison (via normalized value) | — |
| `__str__` | Returns the normalized email string | — |

**Business Rules:**

- BR-EMAIL-001: Must match a simplified RFC 5322 format: `local@domain` where local is 1-64 chars of alphanumeric/`._%+-`, domain is 1+ labels of alphanumeric/hyphens separated by dots, TLD is 2+ alpha chars
- BR-EMAIL-002: Normalized to lowercase for storage and comparison
- BR-EMAIL-003: Globally unique across the entire system (enforced by domain service, not by value object)
- BR-EMAIL-004: Maximum total length: 254 characters (per RFC 5321)

**Acceptance Criteria:**

- [ ] `EmailAddress("User@Example.COM").value` returns `"user@example.com"`
- [ ] `EmailAddress("invalid")` raises `InvalidEmailError`
- [ ] `EmailAddress("")` raises `InvalidEmailError`
- [ ] `EmailAddress("a@b.c")` raises `InvalidEmailError` (TLD too short)
- [ ] `EmailAddress("user@example.com") == EmailAddress("USER@EXAMPLE.COM")` is `True`
- [ ] Two equal EmailAddress instances have the same hash

---

#### REQ-VO-102: Username

**Priority:** Must Have

A validated, normalized username for display and identification.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Normalized username (lowercase) |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Validate format and normalize to lowercase | `InvalidUsernameError` |
| `__eq__` / `__hash__` | Case-insensitive comparison (via normalized value) | — |
| `__str__` | Returns the normalized username string | — |

**Business Rules:**

- BR-USER-001: Length: 3–30 characters
- BR-USER-002: Allowed characters: alphanumeric (`a-z`, `0-9`), underscores (`_`), hyphens (`-`)
- BR-USER-003: Cannot start or end with underscore or hyphen
- BR-USER-004: Normalized to lowercase for uniqueness checks
- BR-USER-005: Globally unique, including deleted users within a 90-day window (enforced by domain service)

**Acceptance Criteria:**

- [ ] `Username("JohnDoe").value` returns `"johndoe"`
- [ ] `Username("ab")` raises `InvalidUsernameError` (too short)
- [ ] `Username("a" * 31)` raises `InvalidUsernameError` (too long)
- [ ] `Username("_john")` raises `InvalidUsernameError` (starts with underscore)
- [ ] `Username("john-")` raises `InvalidUsernameError` (ends with hyphen)
- [ ] `Username("john doe")` raises `InvalidUsernameError` (space not allowed)
- [ ] `Username("john_doe-123")` is valid
- [ ] `Username("john") == Username("JOHN")` is `True`

---

#### REQ-VO-103: HashedPassword

**Priority:** Must Have

Represents a hashed password. The value object holds the hash string only — it does **not** perform hashing or verification itself. Hashing and verification are delegated to a `PasswordHasher` protocol, keeping the domain pure.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| hashed_value | str | The password hash string (opaque to domain) |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(hashed_value: str)` | Store pre-hashed value | `InvalidValueError` if empty |
| `__eq__` / `__hash__` | Equality by hashed_value | — |

**Note:** This is intentionally named `HashedPassword` (not `Password`) to make clear it holds a hash, never plaintext.

---

#### REQ-VO-104: PasswordHasher Protocol

**Priority:** Must Have

A domain port (protocol) for password hashing and verification. The domain defines the contract; infrastructure provides the implementation (e.g., Argon2id).

**Protocol Methods:**

| Method | Description |
|--------|-------------|
| `hash(plaintext: str) -> str` | Hash a plaintext password, return hash string |
| `verify(plaintext: str, hashed: str) -> bool` | Verify plaintext against a hash |

**Business Rules:**

- BR-HASH-001: The protocol does not specify the algorithm — that is an infrastructure concern
- BR-HASH-002: The recommended implementation uses Argon2id (configured in infrastructure layer)

---

#### REQ-VO-105: Password Strength Validation

**Priority:** Must Have

A pure domain function (or static method) that validates password strength. No hashing — just rule checking.

**Function:** `validate_password_strength(plaintext: str) -> None`

**Raises:** `PasswordTooWeakError` with a message describing which rules failed.

**Business Rules:**

| Rule | Specification |
|------|---------------|
| BR-PWD-001: Minimum length | 12 characters |
| BR-PWD-002: Uppercase | At least 1 uppercase letter |
| BR-PWD-003: Lowercase | At least 1 lowercase letter |
| BR-PWD-004: Digit | At least 1 digit |
| BR-PWD-005: Special character | At least 1 special character (non-alphanumeric) |

**Acceptance Criteria:**

- [ ] `"Short1!a"` fails (too short, < 12 chars)
- [ ] `"alllowercase1!"` fails (no uppercase)
- [ ] `"ALLUPPERCASE1!"` fails (no lowercase)
- [ ] `"NoDigitsHere!!"` fails (no digit)
- [ ] `"NoSpecialChar1a"` fails (no special character)
- [ ] `"ValidPass123!!"` passes all rules
- [ ] Error message indicates which specific rules failed

---

#### REQ-VO-106: Password History Validation

**Priority:** Must Have

A pure domain function that checks whether a plaintext password matches any hash in the history.

**Function:** `validate_not_in_history(plaintext: str, history: list[str], hasher: PasswordHasher) -> None`

**Raises:** `PasswordReusedError`

**Business Rules:**

- BR-HIST-001: Cannot reuse any of the last 5 password hashes
- BR-HIST-002: Uses the `PasswordHasher` protocol to verify against stored hashes

**Acceptance Criteria:**

- [ ] A password matching any of the last 5 hashes raises `PasswordReusedError`
- [ ] A password not matching any history entry passes validation
- [ ] History with fewer than 5 entries is checked fully (no padding needed)

---

#### REQ-VO-107: AuthProvider

**Priority:** Must Have

Represents an authentication method linked to a user.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| provider_type | ProviderType | PASSWORD, GOOGLE, or MICROSOFT |
| external_id | str? | Provider's unique user ID (None for PASSWORD) |
| linked_at | datetime (UTC) | When this provider was linked |

**Enum — ProviderType:**

| Value | Description |
|-------|-------------|
| PASSWORD | Email + password authentication |
| GOOGLE | Google Sign-In via OIDC |
| MICROSOFT | Microsoft Identity Platform |

**Business Rules:**

- BR-AUTH-001: `external_id` must be `None` for PASSWORD provider
- BR-AUTH-002: `external_id` is required (non-None, non-empty) for GOOGLE and MICROSOFT providers
- BR-AUTH-003: A user can have multiple providers linked simultaneously (e.g., PASSWORD + GOOGLE)
- BR-AUTH-004: `linked_at` must be timezone-aware UTC
- BR-AUTH-005: Two AuthProviders are equal if they have the same `provider_type` (for set membership — a user has at most one of each type)

**Acceptance Criteria:**

- [ ] `AuthProvider(ProviderType.PASSWORD, None, now)` is valid
- [ ] `AuthProvider(ProviderType.GOOGLE, None, now)` raises `InvalidValueError`
- [ ] `AuthProvider(ProviderType.GOOGLE, "google-123", now)` is valid
- [ ] `AuthProvider(ProviderType.PASSWORD, "some-id", now)` raises `InvalidValueError`
- [ ] Two AuthProviders with same provider_type are equal (regardless of external_id or linked_at)

---

#### REQ-VO-108: UserStatus Enum

**Priority:** Must Have

The lifecycle state of a User.

| Value | Description |
|-------|-------------|
| PENDING_VERIFICATION | Registered but email not yet verified |
| ACTIVE | Email verified, full access |
| SUSPENDED | Temporarily locked by admin |
| DELETED | Soft deleted, in retention period |

---

#### REQ-VO-109: UserPreferences

**Priority:** Must Have

User display and localization settings.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| timezone | str | User's timezone (IANA format, e.g., "America/New_York") |
| locale | str | Display locale (e.g., "en-US") |
| display_currency | Currency | Preferred currency for consolidated views (Shared Kernel Currency enum) |

**Business Rules:**

- BR-PREF-001: `timezone` must be a non-empty string (IANA timezone validation is an infrastructure concern)
- BR-PREF-002: `locale` must be a non-empty string
- BR-PREF-003: `display_currency` must be a valid Shared Kernel `Currency` enum value
- BR-PREF-004: Default preferences: timezone `"UTC"`, locale `"en-US"`, display_currency `Currency.USD`

**Acceptance Criteria:**

- [ ] Default UserPreferences has timezone="UTC", locale="en-US", display_currency=Currency.USD
- [ ] UserPreferences is immutable after construction
- [ ] Empty timezone or locale raises `InvalidValueError`

---

### 5.2 User Aggregate Root

#### REQ-USER-001: User Entity

**Priority:** Must Have

The User aggregate root is the central identity entity. It composes Shared Kernel traits for reusable behavior.

**Composition:**

- `AggregateRoot` (provides: `id`, `created_at`, `updated_at`, event collection)
- `SoftDeletableMixin` (provides: `deleted_at`, `deleted_by`, `deletion_reason`, `hard_delete_scheduled_at`, `soft_delete()`, `recover()`, `is_deleted()`, `is_active()`)
- `AuditableMixin` (provides: `created_by`, `updated_by`)

**Additional Attributes:**

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| email | EmailAddress | Yes | Email address (globally unique) |
| username | Username | Yes | Unique display name |
| full_name | str? | Yes | Optional full name |
| password | HashedPassword? | Yes | Hashed password (None if social-only) |
| password_history | list[str] | Yes | Previous password hashes (max 5) |
| auth_providers | set[AuthProvider] | Yes | Linked authentication methods |
| status | UserStatus | Yes | Current lifecycle state |
| email_verified | bool | Yes | Whether email has been verified |
| preferences | UserPreferences | Yes | User display settings |
| last_login_at | datetime? | Yes | Last successful login timestamp (UTC) |

**Business Rules:**

- BR-USR-001: The `id` field from AggregateRoot serves as the `user_id`
- BR-USR-002: `password_history` stores raw hash strings, maximum of 5 entries (FIFO)
- BR-USR-003: `auth_providers` must always contain at least one provider (invariant ID-016)
- BR-USR-004: When `auth_providers` contains PASSWORD, `password` must not be None (invariant ID-017)

---

#### REQ-USER-002: User Registration (Factory Method)

**Priority:** Must Have

**Method:** `User.register(email: EmailAddress, username: Username, hashed_password: HashedPassword, created_by: UUID) -> User`

Creates a new User with:
- `status` = `PENDING_VERIFICATION`
- `auth_providers` = `{AuthProvider(PASSWORD, None, now)}`
- `email_verified` = `False`
- `password_history` = `[]` (empty — current password is not in history)
- `preferences` = default UserPreferences

**Emits:** `UserRegistered` domain event

**Notes:**
- The caller (domain service) is responsible for creating and validating `EmailAddress`, `Username`, and hashing the password via `PasswordHasher` before calling this factory.
- `created_by` is the user's own ID (self-registration) — the factory generates the UUID and uses it for both `id` and `created_by`.

**Acceptance Criteria:**

- [ ] Returns a User with status PENDING_VERIFICATION
- [ ] auth_providers contains exactly one PASSWORD provider
- [ ] email_verified is False
- [ ] password_history is empty
- [ ] preferences are defaults
- [ ] A UserRegistered event is registered
- [ ] created_by equals the user's own id

---

#### REQ-USER-003: Email Verification

**Priority:** Must Have

**Method:** `verify_email() -> None`

**Transitions:** PENDING_VERIFICATION -> ACTIVE

**Sets:** `email_verified = True`

**Raises:** `InvalidStateTransitionError` if status is not PENDING_VERIFICATION

**Emits:** `EmailVerified` domain event

**Acceptance Criteria:**

- [ ] PENDING_VERIFICATION -> ACTIVE succeeds, sets email_verified=True
- [ ] Calling from ACTIVE, SUSPENDED, or DELETED raises `InvalidStateTransitionError`

---

#### REQ-USER-004: Profile Updates

**Priority:** Must Have

**Methods:**

| Method | Description | Side Effects | Raises |
|--------|-------------|-------------|--------|
| `update_email(new_email: EmailAddress) -> None` | Change email, require re-verification | Sets `email_verified=False`, transitions to `PENDING_VERIFICATION`, emits `UserEmailChanged` | `InvalidStateTransitionError` if not ACTIVE |
| `update_username(new_username: Username) -> None` | Change username | Emits `UserUsernameChanged` | `InvalidStateTransitionError` if not ACTIVE |
| `update_full_name(name: str?) -> None` | Change or clear full name | — | `InvalidStateTransitionError` if not ACTIVE |
| `update_preferences(preferences: UserPreferences) -> None` | Update display settings | — | `InvalidStateTransitionError` if not ACTIVE |

**Business Rules:**

- BR-PROF-001: Profile updates are only allowed in ACTIVE status
- BR-PROF-002: Email change resets `email_verified` to `False` and transitions user to PENDING_VERIFICATION
- BR-PROF-003: Email and username uniqueness is enforced by the domain service, not the entity
- BR-PROF-004: After email change, user must re-verify to return to ACTIVE

**Acceptance Criteria:**

- [ ] `update_email()` sets email_verified=False and status=PENDING_VERIFICATION
- [ ] `update_email()` emits `UserEmailChanged` event
- [ ] `update_email()` from non-ACTIVE state raises `InvalidStateTransitionError`
- [ ] `update_username()` from ACTIVE succeeds, emits `UserUsernameChanged`
- [ ] `update_full_name()` from ACTIVE succeeds
- [ ] `update_preferences()` from ACTIVE succeeds
- [ ] All profile updates from SUSPENDED or DELETED raise `InvalidStateTransitionError`

---

#### REQ-USER-005: Password Management

**Priority:** Must Have

**Methods:**

| Method | Description | Raises |
|--------|-------------|--------|
| `change_password(new_hashed: HashedPassword, old_hashes_to_archive: str) -> None` | Change password, archive old hash in history | `InvalidStateTransitionError` if not ACTIVE |
| `set_initial_password(hashed: HashedPassword) -> None` | Add password for social-only user | `PasswordAlreadySetError` if password is not None, `InvalidStateTransitionError` if not ACTIVE |

**Business Rules:**

- BR-PASS-001: `change_password()` pushes the old password hash onto `password_history` and trims to 5 entries (FIFO)
- BR-PASS-002: `change_password()` sets the new `HashedPassword`
- BR-PASS-003: Strength validation and history checking happen **before** calling these methods (in the application/domain service layer using `validate_password_strength` and `validate_not_in_history`)
- BR-PASS-004: `set_initial_password()` only works when `password` is None (social-only users)
- BR-PASS-005: `set_initial_password()` adds `AuthProvider(PASSWORD)` to `auth_providers`

**Emits:**
- `change_password()` -> `PasswordChanged`
- `set_initial_password()` -> `PasswordChanged`

**Acceptance Criteria:**

- [ ] `change_password()` replaces password, archives old hash, trims history to 5
- [ ] `change_password()` emits `PasswordChanged` event
- [ ] `set_initial_password()` fails with `PasswordAlreadySetError` if password exists
- [ ] `set_initial_password()` adds PASSWORD to auth_providers
- [ ] Both methods require ACTIVE status

---

#### REQ-USER-006: Auth Provider Management

**Priority:** Must Have

**Methods:**

| Method | Description | Raises |
|--------|-------------|--------|
| `link_auth_provider(provider: AuthProvider) -> None` | Add provider to set | `ProviderAlreadyLinkedError` |
| `unlink_auth_provider(provider_type: ProviderType) -> None` | Remove provider from set | `CannotUnlinkLastProviderError`, `ProviderNotLinkedError` |

**Business Rules:**

- BR-LINK-001: Cannot link a provider_type that is already in the set
- BR-LINK-002: Cannot unlink the last remaining provider (invariant ID-016)
- BR-LINK-003: Unlinking PASSWORD also clears the `password` field and `password_history`
- BR-LINK-004: Auth provider management requires ACTIVE status

**Emits:**
- `link_auth_provider()` -> `AuthProviderLinked`
- `unlink_auth_provider()` -> `AuthProviderUnlinked`

**Acceptance Criteria:**

- [ ] Linking a new provider adds it to the set
- [ ] Linking an already-linked provider_type raises `ProviderAlreadyLinkedError`
- [ ] Unlinking the last provider raises `CannotUnlinkLastProviderError`
- [ ] Unlinking PASSWORD clears password and password_history
- [ ] Unlinking a non-linked provider raises `ProviderNotLinkedError`
- [ ] Both methods require ACTIVE status

---

#### REQ-USER-007: Lifecycle State Machine

**Priority:** Must Have

**Valid Transitions:**

| From | To | Method | Conditions |
|------|-----|--------|------------|
| PENDING_VERIFICATION | ACTIVE | `verify_email()` | — |
| ACTIVE | PENDING_VERIFICATION | `update_email()` | Email change triggers re-verification |
| ACTIVE | SUSPENDED | `suspend(reason: str?)` | Admin action |
| ACTIVE | DELETED | `soft_delete(deleted_by, reason, retention)` | User or admin action |
| SUSPENDED | ACTIVE | `unsuspend()` | Admin action |
| SUSPENDED | DELETED | `soft_delete(deleted_by, reason, retention)` | Admin action |
| DELETED | ACTIVE | `recover()` | Within retention period |

**State Machine Diagram:**

```
                    ┌──────────────────┐
                    │  register()      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
     ┌─────────────►│ PENDING_VERIFY   │◄────────────┐
     │              └────────┬─────────┘             │
     │                       │ verify_email()        │ update_email()
     │                       ▼                       │
     │              ┌──────────────────┐             │
     │ unsuspend()  │     ACTIVE       │─────────────┘
     │              └────────┬─────────┘
     │                       │
     │          ┌────────────┴──────────┐
     │          │ suspend()             │ soft_delete()
     │          ▼                       ▼
     │    ┌──────────┐           ┌──────────┐
     └────│SUSPENDED │──────────►│ DELETED  │───────────┐
          └──────────┘           └──────────┘           │
              soft_delete()                   recover() │
                                                        ▼
                                                   -> ACTIVE
```

**Invalid Transitions (raise `InvalidStateTransitionError`):**

- PENDING_VERIFICATION -> SUSPENDED (must verify first)
- PENDING_VERIFICATION -> DELETED (must verify first)
- DELETED -> SUSPENDED (must recover first)
- DELETED -> PENDING_VERIFICATION (must recover first)

**Lifecycle Methods:**

| Method | From States | To State | Emits |
|--------|-------------|----------|-------|
| `suspend(reason: str?) -> None` | ACTIVE | SUSPENDED | `UserSuspended` |
| `unsuspend() -> None` | SUSPENDED | ACTIVE | `UserUnsuspended` |
| `soft_delete(deleted_by: UUID, reason: str?, retention: RetentionPeriod) -> None` | ACTIVE, SUSPENDED | DELETED | `UserSoftDeleted` |
| `recover() -> None` | DELETED | ACTIVE | `UserRecovered` |

**Business Rules:**

- BR-LC-001: `soft_delete()` delegates to `SoftDeletableMixin.soft_delete()` for timestamp/retention handling, then sets `status = DELETED`
- BR-LC-002: `recover()` delegates to `SoftDeletableMixin.recover()` to clear deletion fields, then sets `status = ACTIVE` and `email_verified = True` (restoring verified state)
- BR-LC-003: `suspend()` stores an optional reason (for audit purposes)
- BR-LC-004: The retention period is provided by the caller (application layer resolves the policy)

**Acceptance Criteria:**

- [ ] `suspend()` only works from ACTIVE
- [ ] `unsuspend()` only works from SUSPENDED
- [ ] `soft_delete()` works from ACTIVE or SUSPENDED, sets deletion timestamps
- [ ] `recover()` only works from DELETED, clears deletion fields, sets status ACTIVE
- [ ] All invalid transitions raise `InvalidStateTransitionError`
- [ ] Each transition emits the corresponding domain event
- [ ] soft_delete() from SUSPENDED works without requiring unsuspend first

---

#### REQ-USER-008: Login Recording

**Priority:** Must Have

**Method:** `record_login() -> None`

**Business Rules:**

- BR-LOGIN-001: Updates `last_login_at` to current UTC time
- BR-LOGIN-002: Only allowed in ACTIVE status
- BR-LOGIN-003: Emits `UserLoggedIn` domain event

**Acceptance Criteria:**

- [ ] `record_login()` sets `last_login_at` to current UTC timestamp
- [ ] `record_login()` emits `UserLoggedIn` event
- [ ] `record_login()` from non-ACTIVE state raises `InvalidStateTransitionError`

---

### 5.3 Domain Events

All domain events extend `DomainEvent` from the Shared Kernel. `aggregate_type` is always `"User"`.

| Event | Trigger | Additional Data |
|-------|---------|-----------------|
| `UserRegistered` | `register()` | email: str, username: str |
| `EmailVerified` | `verify_email()` | — |
| `UserEmailChanged` | `update_email()` | old_email: str, new_email: str |
| `UserUsernameChanged` | `update_username()` | old_username: str, new_username: str |
| `PasswordChanged` | `change_password()`, `set_initial_password()` | — (no password data in events) |
| `AuthProviderLinked` | `link_auth_provider()` | provider_type: str |
| `AuthProviderUnlinked` | `unlink_auth_provider()` | provider_type: str |
| `UserSuspended` | `suspend()` | reason: str? |
| `UserUnsuspended` | `unsuspend()` | — |
| `UserSoftDeleted` | `soft_delete()` | deleted_by: UUID |
| `UserRecovered` | `recover()` | — |
| `UserLoggedIn` | `record_login()` | — |

**Business Rules:**

- BR-EVT-101: Events never contain plaintext or hashed passwords
- BR-EVT-102: Email and username events carry the string values (not the value objects) for serialization simplicity
- BR-EVT-103: All events carry `aggregate_id` (user_id) and `aggregate_type` ("User") from the base DomainEvent

---

### 5.4 Invariants

These rules must **always** hold true for any User instance:

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| ID-016 | `auth_providers` must contain at least one provider | Checked on `unlink_auth_provider()` — raises `CannotUnlinkLastProviderError` |
| ID-017 | `password` is required when `auth_providers` contains PASSWORD | Checked on construction and `unlink_auth_provider()` (clear password when unlinking PASSWORD) |
| ID-002 | Email must be globally unique | Domain service via repository lookup |
| ID-003 | Username must be globally unique (including 90-day deleted window) | Domain service via repository lookup |

---

### 5.5 Domain Service: UserRegistrationService

**Priority:** Must Have

Uniqueness validation requires repository access, so it lives in a domain service.

**Method:** `register_user(email: str, username: str, plaintext_password: str, hasher: PasswordHasher) -> User`

**Steps:**

1. Create `EmailAddress(email)` — validates format, normalizes
   - Raises: `InvalidEmailError`
2. Create `Username(username)` — validates format, normalizes
   - Raises: `InvalidUsernameError`
3. `validate_password_strength(plaintext_password)`
   - Raises: `PasswordTooWeakError`
4. Check email uniqueness via `repository.exists_by_email(email_vo)`
   - Raises: `EmailAlreadyExistsError`
5. Check username uniqueness via `repository.exists_by_username(username_vo, include_recently_deleted=True)`
   - Raises: `UsernameAlreadyExistsError`
6. Hash password: `hashed = hasher.hash(plaintext_password)`
7. Create `HashedPassword(hashed)`
8. Call `User.register(email_vo, username_vo, hashed_password, created_by=generated_user_id)`
9. Return user with collected domain events

**Business Rules:**

- BR-REG-001: Validation order is: format -> strength -> uniqueness -> creation. This ensures fast, cheap validations run first.
- BR-REG-002: The service receives a `PasswordHasher` instance (injected dependency)
- BR-REG-003: The service receives a `UserRepository` instance (injected dependency)

**Acceptance Criteria:**

- [ ] Valid registration creates a user with all correct initial state
- [ ] Invalid email format raises `InvalidEmailError` before uniqueness check
- [ ] Invalid username format raises `InvalidUsernameError` before uniqueness check
- [ ] Weak password raises `PasswordTooWeakError` before uniqueness check
- [ ] Duplicate email raises `EmailAlreadyExistsError`
- [ ] Duplicate username (including recently deleted) raises `UsernameAlreadyExistsError`
- [ ] Returned user has a `UserRegistered` domain event

---

### 5.6 Repository Protocol: UserRepository

**Priority:** Must Have

Defined by the domain, implemented by infrastructure.

**Protocol Methods:**

| Method | Description |
|--------|-------------|
| `save(user: User) -> None` | Persist a new or updated user |
| `find_by_id(user_id: UUID) -> User?` | Find user by ID, returns None if not found |
| `find_by_email(email: EmailAddress) -> User?` | Find user by email, returns None if not found |
| `find_by_username(username: Username) -> User?` | Find user by username, returns None if not found |
| `exists_by_email(email: EmailAddress) -> bool` | Check if email is taken |
| `exists_by_username(username: Username, include_recently_deleted: bool = True) -> bool` | Check if username is taken (optionally including recently deleted within 90-day window) |

**Business Rules:**

- BR-REPO-001: This is a protocol/interface only — no implementation in this spec
- BR-REPO-002: `include_recently_deleted` defaults to `True` for username uniqueness (90-day reservation)
- BR-REPO-003: The repository handles persistence concerns (ORM mapping, query optimization)

---

### 5.7 IAM Exception Hierarchy

**Priority:** Must Have

All IAM exceptions extend from the Shared Kernel base exceptions. They live in `src/emerald/iam/exceptions/`.

**Hierarchy:**

```
DomainError (Shared Kernel)
├── ValidationError (Shared Kernel)
│   ├── InvalidValueError (Shared Kernel)
│   │   ├── InvalidEmailError           [IAM] code: "INVALID_EMAIL"
│   │   ├── InvalidUsernameError        [IAM] code: "INVALID_USERNAME"
│   │   └── PasswordTooWeakError        [IAM] code: "PASSWORD_TOO_WEAK"
│   └── InvariantViolationError (Shared Kernel)
│       └── InvalidStateTransitionError [IAM] code: "INVALID_STATE_TRANSITION"
├── ConflictError (Shared Kernel)
│   ├── AlreadyExistsError (Shared Kernel)
│   │   ├── EmailAlreadyExistsError     [IAM] code: "EMAIL_ALREADY_EXISTS"
│   │   └── UsernameAlreadyExistsError  [IAM] code: "USERNAME_ALREADY_EXISTS"
│   └── ProviderAlreadyLinkedError      [IAM] code: "PROVIDER_ALREADY_LINKED"
├── NotFoundError (Shared Kernel)
│   └── ProviderNotLinkedError          [IAM] code: "PROVIDER_NOT_LINKED"
├── PasswordReusedError                 [IAM] code: "PASSWORD_REUSED" (extends ValidationError)
├── PasswordAlreadySetError             [IAM] code: "PASSWORD_ALREADY_SET" (extends ConflictError)
└── CannotUnlinkLastProviderError       [IAM] code: "CANNOT_UNLINK_LAST_PROVIDER" (extends InvariantViolationError)
```

**Acceptance Criteria:**

- [ ] All IAM exceptions extend from Shared Kernel base exceptions
- [ ] Each exception has a unique, machine-readable `code`
- [ ] All exceptions carry `code` and `message` attributes
- [ ] Exception hierarchy matches the tree above

---

### 5.8 Non-Functional Requirements

#### Performance

- Value object construction and validation have negligible overhead (no I/O)
- Password strength validation is pure string analysis — no hashing during validation

#### Security

- Plaintext passwords never stored, never included in domain events, never logged
- Password hashing delegated to infrastructure via protocol (algorithm configurable)
- Password history stores only hashes, never plaintext
- Email verification required before full access

#### Testability

- The entire IAM domain layer has **zero infrastructure dependencies**
- `PasswordHasher` is a protocol — tests use a simple stub/fake implementation
- `UserRepository` is a protocol — tests use in-memory fakes
- 100% unit testable without database, network, or file system

#### Scalability

- User aggregate is a single consistency boundary — no cross-aggregate transactions needed for registration
- Uniqueness checks are optimized by the repository implementation (indexed lookups)

---

## 6. User Stories

### US-101: User Registration

**As a** new user
**I want** to register with my email, username, and password
**So that** I can create my account and start managing my finances

**Acceptance Criteria:**
- [ ] Given valid email, username, and strong password, when I register, then my account is created with PENDING_VERIFICATION status
- [ ] Given a weak password, when I register, then I see which password rules failed
- [ ] Given an email already in use, when I register, then I'm told the email is taken
- [ ] Given a username taken by another user (including recently deleted), when I register, then I'm told the username is taken

### US-102: Email Verification

**As a** newly registered user
**I want** to verify my email address
**So that** I can access the full platform

**Acceptance Criteria:**
- [ ] Given a PENDING_VERIFICATION user, when email is verified, then status becomes ACTIVE
- [ ] Given an already ACTIVE user, when verify_email is called, then an error is raised

### US-103: Password Change

**As an** active user
**I want** to change my password
**So that** I can maintain account security

**Acceptance Criteria:**
- [ ] Given a valid new password not in my history, when I change password, then the old hash is archived and new password is set
- [ ] Given a password matching one of my last 5 passwords, when I change password, then I'm told I can't reuse recent passwords
- [ ] Given a weak new password, when I change password, then I see which rules failed

### US-104: Email Change with Re-verification

**As an** active user
**I want** to change my email address
**So that** I can update my contact information

**Acceptance Criteria:**
- [ ] Given I'm ACTIVE, when I change my email, then my status becomes PENDING_VERIFICATION and email_verified becomes False
- [ ] Given I'm SUSPENDED, when I try to change email, then an error is raised

### US-105: Account Suspension and Recovery

**As an** administrator
**I want** to suspend and unsuspend user accounts
**So that** I can enforce platform policies

**Acceptance Criteria:**
- [ ] Given an ACTIVE user, when suspended, then status becomes SUSPENDED
- [ ] Given a SUSPENDED user, when unsuspended, then status becomes ACTIVE
- [ ] Given a SUSPENDED user, when soft deleted, then status becomes DELETED directly

### US-106: Soft Delete and Recovery

**As a** user or administrator
**I want** to soft-delete and recover accounts
**So that** deletions are reversible within a retention window

**Acceptance Criteria:**
- [ ] Given an ACTIVE or SUSPENDED user, when soft deleted with a retention period, then deletion timestamps are set
- [ ] Given a DELETED user, when recovered, then status returns to ACTIVE
- [ ] Given a PENDING_VERIFICATION user, when soft delete is attempted, then an error is raised

---

## 7. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Register with email that has mixed case | Normalized to lowercase, succeeds |
| Register with email that has leading/trailing whitespace | Trimmed during normalization or rejected — implementation choice |
| Username with consecutive special chars (e.g., `a--b`) | Allowed (only start/end restrictions apply) |
| `set_initial_password()` when password already exists | Raises `PasswordAlreadySetError` |
| `change_password()` when user is social-only (no password) | Should not happen — caller checks. If called, archives None (no-op on history) |
| Unlink PASSWORD provider | Clears `password` and `password_history` fields |
| Unlink the only remaining provider | Raises `CannotUnlinkLastProviderError` |
| `recover()` from DELETED when user was previously SUSPENDED | Recovers to ACTIVE (not back to SUSPENDED) |
| `update_email()` with same email as current | Allowed — still triggers re-verification (simplest invariant) |
| `record_login()` from SUSPENDED state | Raises `InvalidStateTransitionError` |
| Password history with < 5 entries | All entries checked; no padding needed |
| Password history at exactly 5 entries when changing | Oldest entry evicted (FIFO) |
| Register with username reserved by recently deleted user (< 90 days) | Raises `UsernameAlreadyExistsError` |
| Register with username of user deleted > 90 days ago | Succeeds (username is released) |

---

## 8. Dependencies

### Internal Dependencies

- **Spec 001 (Shared Kernel)**: `AggregateRoot`, `SoftDeletableMixin`, `AuditableMixin`, `TimestampedMixin`, `DomainEvent`, `Currency`, `RetentionPeriod`, exception base classes

### Downstream Dependents (Blocks)

- **Spec 003 (Authentication & Sessions)**: Token management, session handling for authenticated users
- **Spec 004 (System Roles & Admin Permissions)**: Role assignment and admin permission management on User
- **Spec 005 (Federated Authentication)**: OAuth/OIDC flows linking social providers to User
- **Spec 007 (Account Management)**: Account ownership references User identity
- **Spec 013 (Classification & Taxonomies)**: Taxonomy ownership references User identity

### External Dependencies

- Python standard library only for domain layer (`uuid`, `datetime`, `re`, `enum`, `dataclasses`)
- `PasswordHasher` implementation (e.g., `argon2-cffi`) is an infrastructure concern, not a domain dependency

---

## 9. Constraints

- **Pure domain layer**: Zero framework/infrastructure dependencies in value objects, entity, and domain service
- **Protocol-based ports**: `PasswordHasher` and `UserRepository` are protocols (interfaces) defined in domain, implemented in infrastructure
- **UTC only**: All timestamps are UTC with timezone awareness
- **Immutable value objects**: `EmailAddress`, `Username`, `HashedPassword`, `AuthProvider`, `UserPreferences` cannot be modified after construction
- **Identity equality**: User instances are equal by ID (from AggregateRoot), not by attributes
- **No email sending**: This spec defines the `email_verified` flag and state transition, but email dispatch is an infrastructure concern triggered by `UserRegistered` / `UserEmailChanged` events

---

## 10. Open Questions

None — all questions were resolved during the clarification phase.

---

## 11. Appendix

### Glossary

| Term | Definition |
|------|------------|
| **Aggregate Root** | An entity that serves as the consistency boundary for a group of related entities and value objects. All external access goes through the root. |
| **Domain Service** | A stateless operation that doesn't naturally belong to an entity or value object, typically coordinating multiple domain concepts. |
| **Protocol** | A structural typing interface in Python (PEP 544). Defines a contract without requiring inheritance. |
| **Port** | An interface defined by the domain that infrastructure implements. Part of hexagonal architecture. |
| **PENDING_VERIFICATION** | Initial user state after registration, before email is verified. Limited access. |
| **Retention Period** | The duration a soft-deleted entity is kept before automatic hard deletion. |
| **Password History** | A list of previous password hashes used to prevent password reuse. |
| **Auth Provider** | A method of authentication linked to a user account (password, Google, Microsoft). |

### References

- [Functional Requirements Document](../../docs/functional-requirements.md)
- [Specification Index](../README.md)
- [Spec 001: Shared Kernel](../spec-001-shared-kernel/spec.md)
- RFC 5322 — Internet Message Format (email validation reference)
- RFC 5321 — SMTP (email address length limits)
- OWASP Password Storage Cheat Sheet (Argon2id recommendation)

---
