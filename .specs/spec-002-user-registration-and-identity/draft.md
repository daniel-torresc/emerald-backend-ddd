# Spec 002: User Registration & Identity

**Status:** Draft
**Bounded Context:** Identity & Access Management (IAM)
**Dependencies:** 001 (Shared Kernel)
**Blocks:** 003, 004, 005, 007, 013

---

## 1. Overview

This spec defines the User entity, its lifecycle, and the registration flow for the Emerald Finance Platform. Every person in the system has exactly one User identity with one set of credentials. This spec covers the foundational identity model — authentication mechanisms (tokens, OAuth) are covered in subsequent specs.

**Key Principle:** One person, one account, one login. The User entity is the single identity record for all platform interactions.

## 2. Scope

### In Scope

- User entity with all attributes and invariants
- Value objects: `EmailAddress`, `Username`, `Password`, `AuthProvider`
- User lifecycle state machine (`PendingVerification` -> `Active` -> `Suspended` -> `Deleted`)
- Password registration flow (email + password)
- Email verification requirement
- Password complexity validation (domain rule)
- Password history tracking
- User preferences value object

### Out of Scope

- Token-based sessions and JWT (Spec 003)
- System roles and admin permissions (Spec 004)
- Federated authentication / OAuth (Spec 005)
- Soft delete retention and hard delete mechanics (Spec 006 — this spec only covers the `Deleted` lifecycle state transition)

## 3. Value Objects

### 3.1 EmailAddress

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Normalized email address |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Validate format and normalize | `InvalidEmailError` |
| `__eq__` / `__hash__` | Case-insensitive comparison | - |

**Business Rules:**

- Must be a valid email format (RFC 5322 simplified)
- Normalized to lowercase for storage and comparison
- Globally unique across the entire system (enforced by domain service)

### 3.2 Username

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Normalized username |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Validate format and normalize | `InvalidUsernameError` |
| `__eq__` / `__hash__` | Case-insensitive comparison | - |

**Business Rules:**

- Must be unique globally, including deleted users within a 90-day window
- Minimum length: 3 characters
- Maximum length: 30 characters
- Allowed characters: alphanumeric, underscores, hyphens
- Cannot start or end with underscore/hyphen
- Normalized to lowercase for uniqueness checks

### 3.3 Password

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| hashed_value | str | Argon2id hash of the password |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `create(plaintext: str) -> Password` | Validate strength, hash, return Password | `PasswordTooWeakError` |
| `verify(plaintext: str) -> bool` | Verify plaintext against hash | - |
| `validate_not_in_history(history: list[str]) -> None` | Check against previous hashes | `PasswordReusedError` |

**Business Rules (Domain — NOT infrastructure):**

| Rule | Specification |
|------|---------------|
| Minimum length | 12 characters |
| Complexity | At least 1 uppercase, 1 lowercase, 1 digit, 1 special character |
| History | Cannot reuse last 5 passwords |
| Algorithm | Argon2id |
| Expiration | Optional, configurable (default: never) |

### 3.4 AuthProvider

Represents an authentication method linked to a user.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| provider | ProviderType | PASSWORD, GOOGLE, or MICROSOFT |
| external_id | str? | Provider's unique user ID (None for PASSWORD) |
| linked_at | datetime | When this provider was linked |

**Enum — ProviderType:**

| Value | Description |
|-------|-------------|
| PASSWORD | Email + password authentication |
| GOOGLE | Google Sign-In via OIDC |
| MICROSOFT | Microsoft Identity Platform |

**Business Rules:**

- `external_id` is None for PASSWORD, required for social providers
- A user can have multiple providers linked simultaneously (e.g., PASSWORD + GOOGLE)

### 3.5 UserStatus

**Enum:**

| Value | Description |
|-------|-------------|
| PENDING_VERIFICATION | Registered but email not yet verified |
| ACTIVE | Email verified, full access |
| SUSPENDED | Temporarily locked by admin |
| DELETED | Soft deleted, in retention period |

### 3.6 UserPreferences

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| timezone | str | User's timezone (IANA, e.g., "America/New_York") |
| locale | str | Display locale (e.g., "en-US") |
| display_currency | str | Preferred currency code for consolidated views |

## 4. User Entity

### 4.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| user_id | UUID | No | Unique identifier |
| email | EmailAddress | Yes | Email address (globally unique) |
| username | Username | Yes | Unique display name |
| full_name | str? | Yes | Optional full name |
| password | Password? | Yes | Hashed password (None if social-only) |
| password_history | list[str] | Yes | Previous password hashes (max 5) |
| auth_providers | set[AuthProvider] | Yes | Linked authentication methods |
| status | UserStatus | Yes | Current lifecycle state |
| email_verified | bool | Yes | Whether email has been verified |
| preferences | UserPreferences | Yes | User settings |
| created_at | datetime | No | Registration timestamp |
| last_login_at | datetime? | Yes | Last successful login |
| deleted_at | datetime? | Yes | Soft delete timestamp |
| hard_delete_scheduled_at | datetime? | Yes | When permanent deletion will occur |

### 4.2 Domain Methods

```
User:
  // Registration
  + register(email, username, password) -> User  [class method]
      Creates a new user with:
        - status = PENDING_VERIFICATION
        - auth_providers = {AuthProvider(PASSWORD)}
        - email_verified = False
      Raises: InvalidEmailError, InvalidUsernameError, PasswordTooWeakError

  // Email verification
  + verify_email() -> None
      Transitions: PENDING_VERIFICATION -> ACTIVE
      Sets: email_verified = True
      Raises: InvalidStateTransitionError (if not PENDING_VERIFICATION)

  // Profile management
  + update_email(new_email: EmailAddress) -> None
      Raises: InvalidEmailError
      Note: Uniqueness checked by domain service

  + update_username(new_username: Username) -> None
      Raises: InvalidUsernameError
      Note: Uniqueness checked by domain service

  + update_full_name(name: str?) -> None

  + update_preferences(preferences: UserPreferences) -> None

  // Password management
  + change_password(new_password: str) -> None
      Validates: strength, not in history
      Updates: password, password_history (push old, trim to 5)
      Raises: PasswordTooWeakError, PasswordReusedError

  + set_initial_password(password: str) -> None
      For social-only users adding a password
      Validates: no existing password, strength
      Adds PASSWORD to auth_providers
      Raises: PasswordAlreadySetError, PasswordTooWeakError

  // Auth provider management
  + link_auth_provider(provider: AuthProvider) -> None
      Adds provider to auth_providers set
      Raises: ProviderAlreadyLinkedError

  + unlink_auth_provider(provider_type: ProviderType) -> None
      Removes provider from auth_providers set
      Raises: CannotUnlinkLastProviderError, ProviderNotLinkedError

  // Lifecycle
  + suspend(reason: str?) -> None
      Transitions: ACTIVE -> SUSPENDED
      Raises: InvalidStateTransitionError

  + unsuspend() -> None
      Transitions: SUSPENDED -> ACTIVE
      Raises: InvalidStateTransitionError

  + soft_delete(deleted_by: UUID, reason: str?) -> None
      Transitions: ACTIVE or SUSPENDED -> DELETED
      Sets: deleted_at, hard_delete_scheduled_at
      Raises: InvalidStateTransitionError

  + recover() -> None
      Transitions: DELETED -> ACTIVE
      Clears: deleted_at, hard_delete_scheduled_at
      Raises: InvalidStateTransitionError

  + record_login() -> None
      Updates: last_login_at
```

### 4.3 Lifecycle State Machine

```
                    ┌──────────────────┐
                    │  register()      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
     ┌─────────────►│ PENDING_VERIFY   │
     │              └────────┬─────────┘
     │                       │ verify_email()
     │                       ▼
     │              ┌──────────────────┐
     │ unsuspend()  │     ACTIVE       │◄───────────────┐
     │              └────────┬─────────┘                │
     │                       │                          │
     │          ┌────────────┴──────────┐               │
     │          │                       │               │
     │          ▼                       ▼               │
     │    ┌──────────┐           ┌──────────┐           │
     └────│SUSPENDED │           │ DELETED  │───────────┘
          └──────────┘           └──────────┘  recover()
```

**Valid Transitions:**

| From | To | Via | Conditions |
|------|-----|-----|------------|
| PENDING_VERIFICATION | ACTIVE | `verify_email()` | — |
| ACTIVE | SUSPENDED | `suspend()` | Admin action |
| ACTIVE | DELETED | `soft_delete()` | User or admin action |
| SUSPENDED | ACTIVE | `unsuspend()` | Admin action |
| DELETED | ACTIVE | `recover()` | Within retention period |

**Invalid Transitions (raise `InvalidStateTransitionError`):**

- PENDING_VERIFICATION -> SUSPENDED (must verify first)
- PENDING_VERIFICATION -> DELETED (must verify first)
- SUSPENDED -> DELETED (must unsuspend first)
- DELETED -> SUSPENDED (must recover first)

## 5. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `UserRegistered` | `register()` | user_id, email, username |
| `EmailVerified` | `verify_email()` | user_id |
| `PasswordChanged` | `change_password()` | user_id |
| `AuthProviderLinked` | `link_auth_provider()` | user_id, provider_type |
| `AuthProviderUnlinked` | `unlink_auth_provider()` | user_id, provider_type |
| `UserSuspended` | `suspend()` | user_id, reason |
| `UserUnsuspended` | `unsuspend()` | user_id |
| `UserSoftDeleted` | `soft_delete()` | user_id, deleted_by |
| `UserRecovered` | `recover()` | user_id |

## 6. Invariants

These rules must **always** hold true for any User instance:

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| ID-016 | `auth_providers` must contain at least one provider | Checked on `unlink_auth_provider()` |
| ID-017 | `password` is required when `auth_providers` contains PASSWORD | Checked on construction and `unlink_auth_provider()` |
| ID-002 | Email must be globally unique | Domain service (not entity — requires repo lookup) |
| ID-003 | Username must be globally unique (including 90-day deleted window) | Domain service |
| ID-013 | `admin_permissions` must be None when `system_role` is USER | Deferred to Spec 004 |
| ID-014 | ADMIN must have at least one admin permission | Deferred to Spec 004 |

## 7. Domain Service: User Registration Service

Uniqueness validation requires repository access, so it lives in a domain service:

```
UserRegistrationService:
  + register_user(email: str, username: str, password: str) -> User
      1. Create EmailAddress (validates format)
      2. Create Username (validates format)
      3. Check email uniqueness via repository
         Raises: EmailAlreadyExistsError
      4. Check username uniqueness via repository (including 90-day deleted)
         Raises: UsernameAlreadyExistsError
      5. Create User.register(email, username, password)
      6. Return user with collected domain events
```

**Repository Interface (defined by domain, implemented by infrastructure):**

```
UserRepository (Protocol):
  + exists_by_email(email: EmailAddress) -> bool
  + exists_by_username(username: Username, include_recently_deleted: bool = True) -> bool
  + save(user: User) -> None
  + find_by_id(user_id: UUID) -> User?
  + find_by_email(email: EmailAddress) -> User?
```

## 8. Acceptance Criteria

### Value Objects

- [ ] `EmailAddress` rejects invalid formats and normalizes to lowercase
- [ ] `Username` enforces 3-30 chars, alphanumeric + underscore/hyphen, no leading/trailing special chars
- [ ] `Password.create()` enforces 12+ chars with uppercase, lowercase, digit, and special character
- [ ] `Password.verify()` correctly validates plaintext against Argon2id hash
- [ ] `Password.validate_not_in_history()` rejects last 5 passwords
- [ ] `AuthProvider` requires `external_id` for social providers, None for PASSWORD

### User Entity

- [ ] `register()` creates user in PENDING_VERIFICATION with PASSWORD auth provider
- [ ] `verify_email()` transitions PENDING_VERIFICATION -> ACTIVE
- [ ] `verify_email()` raises error if not PENDING_VERIFICATION
- [ ] `change_password()` validates strength and history, updates hash and history list
- [ ] `set_initial_password()` works only when password is None and adds PASSWORD provider
- [ ] `link_auth_provider()` adds provider, raises if already linked
- [ ] `unlink_auth_provider()` prevents removing last provider
- [ ] `suspend()` only works from ACTIVE state
- [ ] `unsuspend()` only works from SUSPENDED state
- [ ] `soft_delete()` works from ACTIVE or SUSPENDED, sets timestamps
- [ ] `recover()` only works from DELETED, clears deletion fields
- [ ] All state transitions raise `InvalidStateTransitionError` for invalid paths

### Domain Service

- [ ] Registration checks email uniqueness before creating user
- [ ] Registration checks username uniqueness (including 90-day deleted window)
- [ ] Registration emits `UserRegistered` domain event

### Domain Events

- [ ] Each lifecycle transition emits the corresponding domain event
- [ ] Events contain the specified key data
