# User Registration & Identity — Implementation Plan

**Spec:** `.specs/spec-002-user-registration-and-identity/spec.md`
**Version:** 1.0
**Date:** 2026-02-06

---

## 1. Overview

This plan implements the IAM bounded context's foundational User aggregate with its full lifecycle, value objects, domain events, domain service, and repository protocol. All code lives in `src/emerald/iam/` following the context-first organization established by the Shared Kernel. The implementation is **domain layer only** — zero infrastructure dependencies, 100% unit-testable.

**Approach:** Inside-out (domain first), building value objects → exceptions → domain events → User aggregate → domain service → repository protocol. Tests accompany each task.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement       | Layer                  | Components                                                                                                                                                             |
|-------------------|------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| REQ-VO-101..109   | Domain (Value Objects) | `EmailAddress`, `Username`, `HashedPassword`, `AuthProvider`, `ProviderType`, `UserStatus`, `UserPreferences`, `validate_password_strength`, `validate_not_in_history` |
| REQ-VO-104        | Domain (Port)          | `PasswordHasher` protocol                                                                                                                                              |
| REQ-USER-001..008 | Domain (Aggregate)     | `User` aggregate root                                                                                                                                                  |
| Domain Events     | Domain (Events)        | 12 event dataclasses                                                                                                                                                   |
| REQ-5.7           | Domain (Exceptions)    | 10 IAM-specific exceptions                                                                                                                                             |
| REQ-5.5           | Domain (Service)       | `UserRegistrationService`                                                                                                                                              |
| REQ-5.6           | Domain (Port)          | `UserRepository` protocol                                                                                                                                              |

### 2.2 Directory Structure

```
src/emerald/iam/
├── __init__.py                    # Public API exports
├── value_objects/
│   ├── __init__.py
│   ├── email_address.py           # EmailAddress VO
│   ├── username.py                # Username VO
│   ├── hashed_password.py         # HashedPassword VO
│   ├── auth_provider.py           # AuthProvider VO + ProviderType enum
│   ├── user_status.py             # UserStatus enum
│   ├── user_preferences.py        # UserPreferences VO
│   └── password_validation.py     # validate_password_strength, validate_not_in_history
├── entities/
│   ├── __init__.py
│   └── user.py                    # User aggregate root
├── events/
│   ├── __init__.py
│   └── user_events.py             # All 12 User domain events
├── exceptions/
│   ├── __init__.py
│   └── iam_exceptions.py          # All 10 IAM exceptions
├── services/
│   ├── __init__.py
│   └── user_registration.py       # UserRegistrationService
└── ports/
    ├── __init__.py
    ├── password_hasher.py          # PasswordHasher protocol
    └── user_repository.py          # UserRepository protocol

tests/unit/iam/
├── __init__.py
├── value_objects/
│   ├── __init__.py
│   ├── test_email_address.py
│   ├── test_username.py
│   ├── test_hashed_password.py
│   ├── test_auth_provider.py
│   ├── test_user_status.py
│   ├── test_user_preferences.py
│   └── test_password_validation.py
├── entities/
│   ├── __init__.py
│   └── test_user.py
├── events/
│   ├── __init__.py
│   └── test_user_events.py
├── exceptions/
│   ├── __init__.py
│   └── test_iam_exceptions.py
└── services/
    ├── __init__.py
    └── test_user_registration.py
```

### 2.3 Ports and Adapters

| Port (Protocol) | Purpose | Implementation |
|------------------|---------|----------------|
| `PasswordHasher` | Hash and verify passwords | Argon2id adapter (future Spec) |
| `UserRepository` | User persistence and uniqueness queries | PostgreSQL adapter (future Spec) |

Both are domain-defined protocols. Only the protocol interfaces are implemented in this spec; concrete adapters are infrastructure concerns for future specs. Tests use simple stubs/fakes.

### 2.4 Composition (MRO)

The User aggregate root composes Shared Kernel mixins via cooperative multiple inheritance:

```
User → SoftDeletableMixin → AuditableMixin → AggregateRoot → TimestampedMixin → Entity → object
```

This MRO ensures:
- `Entity` provides `id` (UUID)
- `TimestampedMixin` provides `created_at`, `updated_at`
- `AggregateRoot` provides event collection (`_register_event`, `collect_events`)
- `AuditableMixin` provides `created_by`, `updated_by`
- `SoftDeletableMixin` provides `deleted_at`, `deleted_by`, `deletion_reason`, `hard_delete_scheduled_at`, `soft_delete()`, `recover()`

---

## 3. Technical Decisions

### 3.1 Value Object Implementation
**Decision:** Use `@dataclass(frozen=True)` for all value objects, matching the Shared Kernel pattern.
**Rationale:** Provides immutability, equality-by-value, and hashability automatically. Validation in `__post_init__()`.

### 3.2 User Entity Implementation
**Decision:** Use regular class with cooperative MRO (not dataclass), matching AggregateRoot pattern.
**Rationale:** Aggregate roots are mutable entities with behavior-rich methods. The Shared Kernel's `Entity`/`AggregateRoot` base classes use regular classes with `__init__` and `super().__init__(**kwargs)` for MRO cooperation.

### 3.3 Password Validation as Free Functions
**Decision:** Implement `validate_password_strength()` and `validate_not_in_history()` as module-level functions in `password_validation.py`.
**Rationale:** These are stateless operations that don't belong to any entity or value object. Domain services pattern (functions, not classes) keeps things simple per the architecture-patterns guidance.

### 3.4 PasswordHasher as Protocol
**Decision:** Use `typing.Protocol` (PEP 544 structural subtyping), not ABC.
**Rationale:** Spec explicitly calls for Protocol. Allows any class with matching `hash()` and `verify()` methods to satisfy the contract without inheritance. Consistent with the domain's zero-dependency principle.

### 3.5 UserRepository as Protocol
**Decision:** Use `typing.Protocol` for the repository contract.
**Rationale:** Same as PasswordHasher — structural subtyping keeps the domain layer pure. The domain defines what it needs; infrastructure provides it.

### 3.6 User Factory Method
**Decision:** `User.register()` is a `@classmethod` factory that generates the UUID internally and uses it for both `id` and `created_by`.
**Rationale:** Spec states "the factory generates the UUID and uses it for both `id` and `created_by`." This keeps registration self-contained.

### 3.7 State Machine Enforcement
**Decision:** Guard clauses at the top of each state-transitioning method check current `status` and raise `InvalidStateTransitionError`.
**Rationale:** Simple, explicit, and testable. No need for a separate state machine framework — the User aggregate is the consistency boundary.

### 3.8 Suspension Reason Storage
**Decision:** Store `suspension_reason: str | None` as a mutable field on User.
**Rationale:** Spec says `suspend(reason: str?)` stores an optional reason for audit purposes. This is the simplest approach — the reason is just an attribute, not a value object.

---

## 4. Implementation Tasks

### Phase 1: Domain Exceptions

#### TASK-001: IAM Exception Hierarchy

**Layer:** Domain
**Depends On:** None

**Description:**
Create the 10 IAM-specific exceptions extending Shared Kernel base exceptions. Each exception follows the existing pattern: constructor with `message: str` and `code: str` with a default value.

**Exception tree:**
```
InvalidValueError (Shared Kernel)
├── InvalidEmailError           code: "INVALID_EMAIL"
├── InvalidUsernameError        code: "INVALID_USERNAME"
└── PasswordTooWeakError        code: "PASSWORD_TOO_WEAK"

InvariantViolationError (Shared Kernel)
└── InvalidStateTransitionError code: "INVALID_STATE_TRANSITION"

AlreadyExistsError (Shared Kernel)
├── EmailAlreadyExistsError     code: "EMAIL_ALREADY_EXISTS"
└── UsernameAlreadyExistsError  code: "USERNAME_ALREADY_EXISTS"

ConflictError (Shared Kernel)
├── ProviderAlreadyLinkedError  code: "PROVIDER_ALREADY_LINKED"
└── PasswordAlreadySetError     code: "PASSWORD_ALREADY_SET"

NotFoundError (Shared Kernel)
└── ProviderNotLinkedError      code: "PROVIDER_NOT_LINKED"

ValidationError (Shared Kernel)
└── PasswordReusedError         code: "PASSWORD_REUSED"

InvariantViolationError (Shared Kernel)
└── CannotUnlinkLastProviderError code: "CANNOT_UNLINK_LAST_PROVIDER"
```

**Files to Create:**
- `src/emerald/iam/exceptions/__init__.py`
- `src/emerald/iam/exceptions/iam_exceptions.py`

**Tests to Create:**
- `tests/unit/iam/exceptions/__init__.py`
- `tests/unit/iam/exceptions/test_iam_exceptions.py`

**Acceptance Criteria:**
- [ ] All 10 exceptions created with correct parent classes
- [ ] Each has unique `code` default
- [ ] All carry `code` and `message` attributes
- [ ] Each can be caught by its parent (e.g., `InvalidEmailError` caught by `InvalidValueError`)
- [ ] Parametrized test covers all exceptions

---

### Phase 2: Value Objects

#### TASK-002: EmailAddress Value Object

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Immutable value object for validated, normalized email addresses. Uses `@dataclass(frozen=True)` with validation in `__post_init__()`. Regex pattern: `^[a-zA-Z0-9._%+-]{1,64}@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$` with total length ≤ 254. Normalizes to lowercase. Implements `__str__`.

**Files to Create:**
- `src/emerald/iam/value_objects/__init__.py`
- `src/emerald/iam/value_objects/email_address.py`

**Tests to Create:**
- `tests/unit/iam/value_objects/__init__.py`
- `tests/unit/iam/value_objects/test_email_address.py`

**Acceptance Criteria:**
- [ ] `EmailAddress("User@Example.COM").value` returns `"user@example.com"`
- [ ] Invalid formats raise `InvalidEmailError`
- [ ] Empty string raises `InvalidEmailError`
- [ ] TLD < 2 chars raises `InvalidEmailError`
- [ ] Length > 254 raises `InvalidEmailError`
- [ ] Case-insensitive equality and hash
- [ ] `__str__` returns normalized value
- [ ] Immutable (frozen dataclass)

---

#### TASK-003: Username Value Object

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Immutable value object for validated, normalized usernames. Regex: `^[a-zA-Z0-9][a-zA-Z0-9_-]{1,28}[a-zA-Z0-9]$` (3-30 chars, alphanumeric/underscore/hyphen, cannot start or end with _ or -). Normalizes to lowercase. Implements `__str__`.

**Files to Create:**
- `src/emerald/iam/value_objects/username.py`

**Tests to Create:**
- `tests/unit/iam/value_objects/test_username.py`

**Acceptance Criteria:**
- [ ] `Username("JohnDoe").value` returns `"johndoe"`
- [ ] Too short (< 3) raises `InvalidUsernameError`
- [ ] Too long (> 30) raises `InvalidUsernameError`
- [ ] Starting/ending with `_` or `-` raises `InvalidUsernameError`
- [ ] Spaces and invalid chars raise `InvalidUsernameError`
- [ ] `john_doe-123` is valid
- [ ] Case-insensitive equality
- [ ] Immutable (frozen dataclass)

---

#### TASK-004: HashedPassword Value Object

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Immutable value object holding a pre-hashed password string. Validates non-empty. No hashing logic — just a container for the opaque hash string.

**Files to Create:**
- `src/emerald/iam/value_objects/hashed_password.py`

**Tests to Create:**
- `tests/unit/iam/value_objects/test_hashed_password.py`

**Acceptance Criteria:**
- [ ] Valid construction with non-empty hash string
- [ ] Empty string raises `InvalidValueError`
- [ ] Equality by `hashed_value`
- [ ] Immutable (frozen dataclass)

---

#### TASK-005: AuthProvider Value Object + ProviderType Enum

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
`ProviderType` enum with PASSWORD, GOOGLE, MICROSOFT values. `AuthProvider` frozen dataclass with `provider_type`, `external_id` (str | None), and `linked_at` (datetime UTC). Business rules: PASSWORD requires external_id=None; GOOGLE/MICROSOFT require non-empty external_id. Equality by provider_type only (for set membership).

**Files to Create:**
- `src/emerald/iam/value_objects/auth_provider.py`

**Tests to Create:**
- `tests/unit/iam/value_objects/test_auth_provider.py`

**Acceptance Criteria:**
- [ ] `AuthProvider(ProviderType.PASSWORD, None, now)` is valid
- [ ] `AuthProvider(ProviderType.GOOGLE, None, now)` raises `InvalidValueError`
- [ ] `AuthProvider(ProviderType.GOOGLE, "google-123", now)` is valid
- [ ] `AuthProvider(ProviderType.PASSWORD, "some-id", now)` raises `InvalidValueError`
- [ ] Two AuthProviders with same provider_type are equal
- [ ] `linked_at` must be timezone-aware UTC
- [ ] Immutable

---

#### TASK-006: UserStatus Enum + UserPreferences Value Object

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
`UserStatus` enum: PENDING_VERIFICATION, ACTIVE, SUSPENDED, DELETED. `UserPreferences` frozen dataclass with timezone (str), locale (str), display_currency (Currency from Shared Kernel). Default factory. Validates non-empty timezone and locale.

**Files to Create:**
- `src/emerald/iam/value_objects/user_status.py`
- `src/emerald/iam/value_objects/user_preferences.py`

**Tests to Create:**
- `tests/unit/iam/value_objects/test_user_status.py`
- `tests/unit/iam/value_objects/test_user_preferences.py`

**Acceptance Criteria:**
- [ ] UserStatus has exactly 4 values
- [ ] Default UserPreferences: timezone="UTC", locale="en-US", display_currency=Currency.USD
- [ ] Empty timezone or locale raises `InvalidValueError`
- [ ] UserPreferences is immutable
- [ ] UserPreferences equality by all fields

---

#### TASK-007: Password Validation Functions

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Two pure functions:
1. `validate_password_strength(plaintext: str) -> None` — checks 5 rules (min 12 chars, uppercase, lowercase, digit, special char). Raises `PasswordTooWeakError` with message listing all failed rules.
2. `validate_not_in_history(plaintext: str, history: list[str], hasher: PasswordHasher) -> None` — checks against last N hashes using hasher.verify(). Raises `PasswordReusedError`.

Also defines the `PasswordHasher` protocol in `ports/password_hasher.py`.

**Files to Create:**
- `src/emerald/iam/value_objects/password_validation.py`
- `src/emerald/iam/ports/__init__.py`
- `src/emerald/iam/ports/password_hasher.py`

**Tests to Create:**
- `tests/unit/iam/value_objects/test_password_validation.py`

**Acceptance Criteria:**
- [ ] "Short1!a" fails (too short)
- [ ] "alllowercase1!" fails (no uppercase)
- [ ] "ALLUPPERCASE1!" fails (no lowercase)
- [ ] "NoDigitsHere!!" fails (no digit)
- [ ] "NoSpecialChar1a" fails (no special char)
- [ ] "ValidPass123!!" passes
- [ ] Error message lists which specific rules failed
- [ ] History check raises `PasswordReusedError` when password matches a stored hash
- [ ] History check passes when no match found
- [ ] History with < 5 entries checked fully
- [ ] PasswordHasher protocol defined with hash() and verify()

---

### Phase 3: Domain Events

#### TASK-008: User Domain Events

**Layer:** Domain
**Depends On:** None

**Description:**
Create all 12 domain events as frozen dataclasses extending `DomainEvent` from the Shared Kernel. All carry `aggregate_type = "User"`. Each event includes only the additional data specified in the spec.

**Events:**
1. `UserRegistered` (email: str, username: str)
2. `EmailVerified` (no extra data)
3. `UserEmailChanged` (old_email: str, new_email: str)
4. `UserUsernameChanged` (old_username: str, new_username: str)
5. `PasswordChanged` (no extra data — never include password info)
6. `AuthProviderLinked` (provider_type: str)
7. `AuthProviderUnlinked` (provider_type: str)
8. `UserSuspended` (reason: str | None)
9. `UserUnsuspended` (no extra data)
10. `UserSoftDeleted` (deleted_by: UUID)
11. `UserRecovered` (no extra data)
12. `UserLoggedIn` (no extra data)

**Files to Create:**
- `src/emerald/iam/events/__init__.py`
- `src/emerald/iam/events/user_events.py`

**Tests to Create:**
- `tests/unit/iam/events/__init__.py`
- `tests/unit/iam/events/test_user_events.py`

**Acceptance Criteria:**
- [ ] All 12 events are frozen dataclasses extending DomainEvent
- [ ] All events have aggregate_type field defaulting to "User"
- [ ] Events carry only the additional data specified
- [ ] No event contains password or hash data
- [ ] Events are immutable and hashable

---

### Phase 4: User Aggregate Root

#### TASK-009: User Aggregate Root — Core Entity + Registration

**Layer:** Domain
**Depends On:** TASK-001..008

**Description:**
Implement the User class composing `SoftDeletableMixin`, `AuditableMixin`, and `AggregateRoot` via cooperative MRO. Implement:
- All attributes (email, username, full_name, password, password_history, auth_providers, status, email_verified, preferences, last_login_at, suspension_reason)
- `User.register()` factory method
- `__init__` with full cooperative MRO

**MRO:** `User(SoftDeletableMixin, AuditableMixin, AggregateRoot)`

**Files to Create:**
- `src/emerald/iam/entities/__init__.py`
- `src/emerald/iam/entities/user.py`

**Tests to Create:**
- `tests/unit/iam/entities/__init__.py`
- `tests/unit/iam/entities/test_user.py` (registration tests first)

**Acceptance Criteria:**
- [ ] User inherits from SoftDeletableMixin, AuditableMixin, AggregateRoot
- [ ] `User.register()` returns User with PENDING_VERIFICATION status
- [ ] auth_providers contains exactly one PASSWORD provider
- [ ] email_verified is False
- [ ] password_history is empty
- [ ] preferences are defaults
- [ ] UserRegistered event is registered
- [ ] created_by equals the user's own id
- [ ] Identity-based equality (from Entity base)

---

#### TASK-010: User Aggregate — Email Verification + Profile Updates

**Layer:** Domain
**Depends On:** TASK-009

**Description:**
Implement:
- `verify_email()`: PENDING_VERIFICATION → ACTIVE, emits EmailVerified
- `update_email(new_email)`: ACTIVE only, sets email_verified=False, status=PENDING_VERIFICATION, emits UserEmailChanged
- `update_username(new_username)`: ACTIVE only, emits UserUsernameChanged
- `update_full_name(name)`: ACTIVE only
- `update_preferences(prefs)`: ACTIVE only

**Tests to Add:**
- Email verification transitions and invalid state rejections
- Profile update methods: success cases and state guard rejections
- Email change triggers re-verification flow

**Acceptance Criteria:**
- [ ] verify_email() transitions PENDING_VERIFICATION → ACTIVE
- [ ] verify_email() from any other state raises InvalidStateTransitionError
- [ ] update_email() sets email_verified=False, status=PENDING_VERIFICATION
- [ ] update_email() emits UserEmailChanged with old and new email strings
- [ ] update_email() from non-ACTIVE raises InvalidStateTransitionError
- [ ] update_username() emits UserUsernameChanged
- [ ] All profile updates from SUSPENDED/DELETED raise InvalidStateTransitionError

---

#### TASK-011: User Aggregate — Password Management + Auth Providers

**Layer:** Domain
**Depends On:** TASK-009

**Description:**
Implement:
- `change_password(new_hashed, old_hash_to_archive)`: archives old hash (FIFO, max 5), sets new password, emits PasswordChanged. ACTIVE only.
- `set_initial_password(hashed)`: sets password for social-only user, adds PASSWORD provider, emits PasswordChanged. ACTIVE only. Raises PasswordAlreadySetError if password not None.
- `link_auth_provider(provider)`: adds to set, emits AuthProviderLinked. ACTIVE only. Raises ProviderAlreadyLinkedError.
- `unlink_auth_provider(provider_type)`: removes from set, emits AuthProviderUnlinked. ACTIVE only. Raises CannotUnlinkLastProviderError, ProviderNotLinkedError. Unlinking PASSWORD clears password + history.

**Tests to Add:**
- Password change archives old hash, trims to 5
- Password change on empty history (no old hash to archive)
- set_initial_password success and PasswordAlreadySetError
- Link/unlink providers with all error cases
- Unlink PASSWORD clears password fields
- Cannot unlink last provider

**Acceptance Criteria:**
- [ ] change_password() archives old hash, FIFO trim to 5
- [ ] change_password() emits PasswordChanged
- [ ] set_initial_password() fails with PasswordAlreadySetError if password exists
- [ ] set_initial_password() adds PASSWORD to auth_providers
- [ ] link_auth_provider() rejects duplicate provider_type
- [ ] unlink_auth_provider() raises on last provider
- [ ] Unlinking PASSWORD clears password and password_history
- [ ] All methods require ACTIVE status

---

#### TASK-012: User Aggregate — Lifecycle State Machine

**Layer:** Domain
**Depends On:** TASK-009

**Description:**
Implement:
- `suspend(reason)`: ACTIVE → SUSPENDED, stores reason, emits UserSuspended
- `unsuspend()`: SUSPENDED → ACTIVE, emits UserUnsuspended
- `soft_delete(deleted_by, reason, retention)`: ACTIVE/SUSPENDED → DELETED, delegates to SoftDeletableMixin, emits UserSoftDeleted
- `recover()`: DELETED → ACTIVE, delegates to SoftDeletableMixin.recover(), restores email_verified=True, emits UserRecovered
- `record_login()`: ACTIVE only, updates last_login_at, emits UserLoggedIn

**Tests to Add:**
- All valid transitions with correct state changes
- All invalid transitions raise InvalidStateTransitionError
- soft_delete from both ACTIVE and SUSPENDED
- recover() sets ACTIVE (not back to SUSPENDED)
- record_login() updates timestamp and emits event

**Acceptance Criteria:**
- [ ] suspend() only from ACTIVE, emits UserSuspended with reason
- [ ] unsuspend() only from SUSPENDED, emits UserUnsuspended
- [ ] soft_delete() from ACTIVE or SUSPENDED, sets deletion timestamps
- [ ] soft_delete() from PENDING_VERIFICATION or DELETED raises error
- [ ] recover() from DELETED → ACTIVE, restores email_verified=True
- [ ] record_login() from ACTIVE updates last_login_at, emits UserLoggedIn
- [ ] record_login() from non-ACTIVE raises InvalidStateTransitionError
- [ ] All transitions emit correct domain events

---

### Phase 5: Domain Service + Repository Protocol

#### TASK-013: UserRepository Protocol

**Layer:** Domain (Port)
**Depends On:** TASK-002, TASK-003

**Description:**
Define `UserRepository` protocol with:
- `save(user: User) -> None`
- `find_by_id(user_id: UUID) -> User | None`
- `find_by_email(email: EmailAddress) -> User | None`
- `find_by_username(username: Username) -> User | None`
- `exists_by_email(email: EmailAddress) -> bool`
- `exists_by_username(username: Username, include_recently_deleted: bool = True) -> bool`

**Files to Create:**
- `src/emerald/iam/ports/user_repository.py`

**Tests:** No direct tests needed for protocol definition. Tested indirectly via UserRegistrationService tests.

**Acceptance Criteria:**
- [ ] Protocol defined with all 6 methods
- [ ] Uses domain types (EmailAddress, Username, User, UUID)
- [ ] `include_recently_deleted` defaults to True
- [ ] No implementation — protocol only

---

#### TASK-014: UserRegistrationService

**Layer:** Domain (Service)
**Depends On:** TASK-002, TASK-003, TASK-007, TASK-009, TASK-013

**Description:**
Domain service coordinating the registration flow:
1. Create `EmailAddress(email)` — validates format
2. Create `Username(username)` — validates format
3. `validate_password_strength(plaintext_password)` — validates strength
4. `repository.exists_by_email(email_vo)` — checks uniqueness
5. `repository.exists_by_username(username_vo, include_recently_deleted=True)` — checks uniqueness
6. `hasher.hash(plaintext_password)` — hashes password
7. Create `HashedPassword(hashed)`
8. `User.register(email_vo, username_vo, hashed_password)` — creates user
9. Return user

Validation order: format → strength → uniqueness → creation (fast/cheap first).

**Files to Create:**
- `src/emerald/iam/services/__init__.py`
- `src/emerald/iam/services/user_registration.py`

**Tests to Create:**
- `tests/unit/iam/services/__init__.py`
- `tests/unit/iam/services/test_user_registration.py`

Test stubs:
- `FakePasswordHasher` implementing PasswordHasher protocol
- `FakeUserRepository` implementing UserRepository protocol

**Acceptance Criteria:**
- [ ] Valid registration creates a user with correct initial state
- [ ] Invalid email raises InvalidEmailError before uniqueness check
- [ ] Invalid username raises InvalidUsernameError before uniqueness check
- [ ] Weak password raises PasswordTooWeakError before uniqueness check
- [ ] Duplicate email raises EmailAlreadyExistsError
- [ ] Duplicate username raises UsernameAlreadyExistsError
- [ ] Returned user has UserRegistered domain event
- [ ] Validation order: format → strength → uniqueness → creation

---

### Phase 6: Public API + Quality

#### TASK-015: IAM Module Public API Exports

**Layer:** Domain
**Depends On:** TASK-001..014

**Description:**
Configure `src/emerald/iam/__init__.py` with `__all__` re-exporting all public types following the Shared Kernel pattern. Also create necessary `__init__.py` files for all subpackages.

**Files to Create/Modify:**
- `src/emerald/iam/__init__.py`
- All subpackage `__init__.py` files with appropriate re-exports

**Acceptance Criteria:**
- [ ] All public types importable from `emerald.iam`
- [ ] `__all__` lists all exported names
- [ ] Clean import structure

---

#### TASK-016: Quality Verification

**Layer:** Cross-cutting
**Depends On:** TASK-015

**Description:**
Run the full quality suite to ensure everything passes:
1. `uv run pytest -v` — all tests pass
2. `uv run ruff check .` — no lint errors
3. `uv run ruff format --check .` — formatting clean
4. `uv run ty check` — type checking clean

Fix any issues discovered.

**Acceptance Criteria:**
- [ ] All tests pass (existing 160 + new IAM tests)
- [ ] Ruff check clean
- [ ] Ruff format clean
- [ ] ty check clean
- [ ] No circular imports
- [ ] No unused imports

---

## 5. Task Dependency Graph

```
TASK-001 (Exceptions)
    │
    ├──► TASK-002 (EmailAddress)
    ├──► TASK-003 (Username)
    ├──► TASK-004 (HashedPassword)
    ├──► TASK-005 (AuthProvider)
    ├──► TASK-006 (UserStatus + Prefs)
    └──► TASK-007 (Password Validation)
         │
TASK-008 (Events) ──────────────────────────┐
         │                                   │
         ▼                                   ▼
TASK-009 (User Core + Registration) ◄── TASK-002..008
    │
    ├──► TASK-010 (Verification + Profile)
    ├──► TASK-011 (Password + Auth Providers)
    └──► TASK-012 (Lifecycle State Machine)
         │
         ▼
TASK-013 (UserRepository Protocol) ◄── TASK-002, TASK-003
         │
         ▼
TASK-014 (UserRegistrationService) ◄── TASK-009, TASK-013, TASK-007
         │
         ▼
TASK-015 (Public API Exports) ◄── TASK-001..014
         │
         ▼
TASK-016 (Quality Verification)
```

**Parallelizable groups:**
- TASK-002..008 can all be built in parallel (all depend only on TASK-001)
- TASK-010, TASK-011, TASK-012 can all be built in parallel (all depend only on TASK-009)

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MRO conflicts with 3 mixins + AggregateRoot | Low | High | Follow established pattern: `**kwargs: Any`, cooperative `super().__init__()`. Shared Kernel already proves the approach works. |
| `ty` type checker strictness on Protocol | Medium | Low | Use `typing.Protocol` with `runtime_checkable` if needed. We learned from Spec-001 that `**kwargs: Any` satisfies ty. |
| AuthProvider equality-by-provider_type only | Low | Low | Override `__eq__` and `__hash__` on the frozen dataclass (use `eq=False` in dataclass decorator, then implement manually). |
| Password history FIFO trim edge cases | Low | Low | Thorough test coverage for 0, 1, 4, 5, and 6 entries. |
| Circular imports between iam submodules | Low | Medium | Keep imports unidirectional: exceptions ← value_objects ← events ← entities ← services. Ports have no internal deps. |

---

## 7. Estimated Test Count

| Task | Estimated Tests |
|------|----------------|
| TASK-001 (Exceptions) | ~15 |
| TASK-002 (EmailAddress) | ~12 |
| TASK-003 (Username) | ~12 |
| TASK-004 (HashedPassword) | ~5 |
| TASK-005 (AuthProvider) | ~10 |
| TASK-006 (UserStatus + Prefs) | ~8 |
| TASK-007 (Password Validation) | ~12 |
| TASK-008 (Events) | ~15 |
| TASK-009 (User Core) | ~10 |
| TASK-010 (Verification + Profile) | ~15 |
| TASK-011 (Password + Auth) | ~15 |
| TASK-012 (Lifecycle) | ~20 |
| TASK-014 (Registration Service) | ~10 |
| **Total** | **~160** |

---

## 8. Definition of Done

- [ ] All 16 tasks completed
- [ ] All acceptance criteria met across all tasks
- [ ] All tests passing (`uv run pytest -v`)
- [ ] Ruff check clean (`uv run ruff check .`)
- [ ] Ruff format clean (`uv run ruff format --check .`)
- [ ] Type check clean (`uv run ty check`)
- [ ] No circular imports
- [ ] All domain code has zero infrastructure dependencies
- [ ] All value objects are immutable (frozen dataclass)
- [ ] All domain events are immutable (frozen dataclass)
- [ ] User aggregate enforces all invariants
- [ ] State machine rejects all invalid transitions
- [ ] Spec status updated to "Implemented"
