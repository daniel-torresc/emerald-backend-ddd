# System Roles & Admin Permissions — Implementation Plan

**Spec:** `.specs/spec-004-system-roles-and-admin-permissions/spec.md`
**Version:** 1.0
**Date:** 2026-02-08

---

## 1. Overview

This plan implements system-level role hierarchy, granular admin permissions, SUPERADMIN provisioning, and the associated domain/application logic within the existing IAM bounded context. The approach follows inside-out Clean Architecture: domain layer first (value objects, aggregate extensions, events, exceptions), then application layer (commands, services), and finally integration (test fakes, `__init__.py` exports).

**Key approach:** Most work extends existing artifacts (SystemRole, User, AuthenticationService, UserRepository, exceptions, events, fakes, `__init__.py`) rather than creating entirely new files. The two genuinely new domain-layer files are `AdminPermission` (value object) and `role_events.py` (new event file). At the application layer, two new files: `role_commands.py` (commands) and `role_management.py` (RoleManagementService) plus `superadmin_provisioning.py` (SuperadminProvisioningService).

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Spec Section | Layer | Components |
|---|---|---|
| 5.1 AdminPermission | Domain (Value Object) | `AdminPermission` frozen dataclass wrapping enum |
| 5.2 SystemRole extensions | Domain (Enum) | `has_at_least()`, `is_admin_or_above()`, `can_access_admin_portal()` on existing `SystemRole` |
| 6.x User aggregate extensions | Domain (Aggregate) | `admin_permissions` attr + 6 new methods on `User` |
| 6.3 SUPERADMIN guards | Domain (Aggregate) | Guards on existing `soft_delete()` and `suspend()` |
| 11 Domain events | Domain (Events) | 5 new events in `role_events.py` |
| 12 Exceptions | Domain (Exceptions) | 10 new exceptions in `iam_exceptions.py` |
| 8.3 Constants | Domain (Constants) | `REFRESH_TOKEN_TTL_SUPERADMIN` |
| 13.1 Commands | Application (DTOs) | 5 new commands in `role_commands.py` |
| 13.2 RoleManagementService | Application (Service) | New service file |
| 13.3 SuperadminProvisioningService | Application (Service) | New service file |
| 13.4 AuthenticationService mods | Application (Service) | TTL override in `login()` and `refresh()` |
| 8.1 UserRepository extension | Application (Port) | `exists_by_role()` method |

### 2.2 Component Diagram

```
Domain Layer (modified/new)
├── models/
│   ├── admin_permission.py       [NEW] AdminPermission value object
│   ├── system_role.py            [MOD] Add hierarchy methods
│   └── user.py                   [MOD] admin_permissions attr + 6 methods + SUPERADMIN guards
├── events/
│   └── role_events.py            [NEW] 5 role/permission events
├── exceptions/
│   └── iam_exceptions.py         [MOD] 10 new exceptions
└── constants.py                  [MOD] REFRESH_TOKEN_TTL_SUPERADMIN

Application Layer (modified/new)
├── dto/
│   └── role_commands.py          [NEW] 5 commands
├── ports/outbound/
│   └── user_repository.py        [MOD] exists_by_role()
├── services/
│   ├── role_management.py        [NEW] RoleManagementService
│   ├── superadmin_provisioning.py [NEW] SuperadminProvisioningService
│   └── authentication.py         [MOD] SUPERADMIN TTL override

Re-exports
├── domain/events/__init__.py     [MOD]
├── domain/exceptions/__init__.py [MOD]
├── domain/models/__init__.py     [MOD]
├── application/dto/__init__.py   [MOD]
├── application/services/__init__.py [MOD]
├── iam/__init__.py               [MOD]

Tests
├── tests/unit/iam/fakes.py       [MOD] exists_by_role on FakeUserRepository
├── tests/unit/iam/domain/models/test_admin_permission.py [NEW]
├── tests/unit/iam/domain/models/test_system_role.py      [NEW]
├── tests/unit/iam/domain/models/test_user_roles.py       [NEW] (role/perm methods on User)
├── tests/unit/iam/domain/events/test_role_events.py      [NEW]
├── tests/unit/iam/domain/exceptions/test_role_exceptions.py [NEW]
├── tests/unit/iam/application/services/test_role_management.py [NEW]
├── tests/unit/iam/application/services/test_superadmin_provisioning.py [NEW]
├── tests/unit/iam/application/services/test_authentication_superadmin_ttl.py [NEW]
```

### 2.3 Ports and Adapters

| Port (Interface) | Purpose | Change |
|---|---|---|
| `UserRepository` | User persistence | Add `exists_by_role(role: SystemRole) -> bool` |
| `FakeUserRepository` | Test double | Implement `exists_by_role()` |

No new ports are introduced — the existing `AbstractIamUnitOfWork` already provides all repository access needed by the new services.

---

## 3. Technical Decisions

### 3.1 AdminPermission as Frozen Dataclass Wrapping Enum

**Decision:** `AdminPermission` is a `@dataclass(frozen=True)` wrapping an inner `AdminPermissionType` enum, consistent with how other value objects work in this project.

**Rationale:** Follows the project's value object pattern. The `includes()` method provides superset semantics for `FULL_ADMIN`.

**Alternative Considered:** Plain enum with methods. Rejected because value objects in this codebase are frozen dataclasses with `__post_init__` validation.

### 3.2 SystemRole Level Mapping via Property

**Decision:** Add a `level` property to `SystemRole` with a static mapping dict, and implement `has_at_least()` using integer comparison.

**Rationale:** Clean, simple, no external dependencies. Avoids modifying enum values (which would break serialization).

### 3.3 User Aggregate admin_permissions Storage

**Decision:** `admin_permissions: frozenset[AdminPermission] | None` defaults to `None`. `None` for USER and SUPERADMIN. Non-empty `frozenset` for ADMIN only.

**Rationale:** Matches spec invariants ID-013, ID-014, ID-016. Using `frozenset` prevents mutation while stored on the aggregate.

### 3.4 Self-Modification Prevention at Application Layer

**Decision:** `RoleManagementService` checks `actor_id != target_user_id` before delegating to aggregate methods. The aggregate itself does not enforce this.

**Rationale:** Spec Section 10 explicitly states this. Keeps the aggregate free from identity-checking logic.

### 3.5 SUPERADMIN Provisioning Bypass

**Decision:** The `SuperadminProvisioningService` creates a user via `User.register()` then uses `object.__setattr__` (or direct attribute assignment since User is not frozen) to override `system_role`, `status`, and `email_verified`.

**Rationale:** The User class is a regular (non-frozen) class, so direct attribute assignment works. This is a privileged bootstrap operation that intentionally bypasses normal flow.

### 3.6 AuthenticationService TTL Override

**Decision:** In `login()` and `refresh()`, after determining the portal context TTL, check if user's `system_role == SUPERADMIN` and override with `REFRESH_TOKEN_TTL_SUPERADMIN` (15 minutes).

**Rationale:** Minimal change to existing code. Two lines added in `login()`, two lines in `refresh()`.

---

## 4. Implementation Tasks

### Phase 1: Domain Layer — Value Objects & Enums

#### TASK-001: Create AdminPermission Value Object

**Layer:** Domain
**Depends On:** None

**Description:**
Create `AdminPermission` as a frozen dataclass wrapping an `AdminPermissionType` enum. Implement `includes()` method with FULL_ADMIN superset semantics.

**Files to Create:**
- `src/emerald/iam/domain/models/admin_permission.py`

**Acceptance Criteria:**
- [ ] `AdminPermissionType` enum has 4 values: `MASTER_DATA_ADMIN`, `USER_SUPPORT_ADMIN`, `COMPLIANCE_ADMIN`, `FULL_ADMIN`
- [ ] `AdminPermission` is `@dataclass(frozen=True)` with `value: AdminPermissionType`
- [ ] `includes(other)` returns True for FULL_ADMIN covering any permission
- [ ] `includes(other)` returns True for self-inclusion
- [ ] `includes(other)` returns False for non-matching individual permissions
- [ ] Constructor validates type in `__post_init__`

**Tests:**
- [ ] `tests/unit/iam/domain/models/test_admin_permission.py` — all inclusion matrix combinations (AC-02)

---

#### TASK-002: Extend SystemRole with Hierarchy Methods

**Layer:** Domain
**Depends On:** None

**Description:**
Add `level` property, `has_at_least()`, `is_admin_or_above()`, and `can_access_admin_portal()` methods to the existing `SystemRole` enum.

**Files to Modify:**
- `src/emerald/iam/domain/models/system_role.py`

**Acceptance Criteria:**
- [ ] `level` property returns 1 for USER, 2 for ADMIN, 3 for SUPERADMIN
- [ ] `has_at_least(required)` returns correct boolean per spec hierarchy table (AC-01)
- [ ] `is_admin_or_above()` returns True for ADMIN and SUPERADMIN, False for USER
- [ ] `can_access_admin_portal()` returns True for ADMIN and SUPERADMIN, False for USER

**Tests:**
- [ ] `tests/unit/iam/domain/models/test_system_role.py` — all 9 `has_at_least()` combinations + `is_admin_or_above()` + `can_access_admin_portal()` (AC-01)

---

### Phase 2: Domain Layer — Exceptions & Events

#### TASK-003: Add New Domain Exceptions

**Layer:** Domain
**Depends On:** None

**Description:**
Add 10 new exception classes to `iam_exceptions.py`, each following the existing pattern (class with `__init__` taking default message and code).

**Files to Modify:**
- `src/emerald/iam/domain/exceptions/iam_exceptions.py`
- `src/emerald/iam/domain/exceptions/__init__.py` (re-exports)

**New Exceptions:**
1. `InvalidRoleTransitionError(InvariantViolationError)` — code: `INVALID_ROLE_TRANSITION`
2. `CannotDemoteSuperadminError(InvariantViolationError)` — code: `CANNOT_DEMOTE_SUPERADMIN`
3. `CannotDeleteSuperadminError(InvariantViolationError)` — code: `CANNOT_DELETE_SUPERADMIN`
4. `CannotSuspendSuperadminError(InvariantViolationError)` — code: `CANNOT_SUSPEND_SUPERADMIN`
5. `EmptyAdminPermissionsError(InvalidValueError)` — code: `EMPTY_ADMIN_PERMISSIONS`
6. `InsufficientPermissionsError(DomainError)` — code: `INSUFFICIENT_PERMISSIONS`
7. `NotAdminError(InvariantViolationError)` — code: `NOT_ADMIN`
8. `CannotGrantUnownedPermissionError(DomainError)` — code: `CANNOT_GRANT_UNOWNED_PERMISSION`
9. `LastAdminPermissionError(InvariantViolationError)` — code: `LAST_ADMIN_PERMISSION`
10. `SuperadminAlreadyExistsError(AlreadyExistsError)` — code: `SUPERADMIN_ALREADY_EXISTS`

**Acceptance Criteria:**
- [ ] All exceptions follow existing pattern with default message and code
- [ ] Each uses correct base class per spec Section 12
- [ ] All re-exported from `__init__.py`

**Tests:**
- [ ] `tests/unit/iam/domain/exceptions/test_role_exceptions.py` — instantiation, code, message, inheritance for each

---

#### TASK-004: Add Domain Events for Role/Permission Mutations

**Layer:** Domain
**Depends On:** None

**Description:**
Create a new `role_events.py` file with 5 frozen dataclass events. All have `aggregate_type = "User"`.

**Files to Create:**
- `src/emerald/iam/domain/events/role_events.py`

**Files to Modify:**
- `src/emerald/iam/domain/events/__init__.py` (re-exports)

**New Events:**
1. `UserPromotedToAdmin` — `permissions: frozenset[str]`, `promoted_by_id: UUID`
2. `UserDemotedToUser` — `demoted_by_id: UUID`
3. `AdminPermissionGranted` — `permission: str`, `granted_by_id: UUID`
4. `AdminPermissionRevoked` — `permission: str`, `revoked_by_id: UUID`
5. `SuperadminProvisioned` — (no extra fields beyond `aggregate_id`)

**Acceptance Criteria:**
- [ ] All events are `@dataclass(frozen=True)` extending `DomainEvent`
- [ ] All have `aggregate_type: ClassVar[str] = "User"`
- [ ] Permissions serialized as strings (enum `.value`)
- [ ] All re-exported from events `__init__.py`

**Tests:**
- [ ] `tests/unit/iam/domain/events/test_role_events.py` — creation, field access, frozen check

---

#### TASK-005: Add SUPERADMIN Refresh Token TTL Constant

**Layer:** Domain
**Depends On:** None

**Description:**
Add `REFRESH_TOKEN_TTL_SUPERADMIN` constant to `constants.py`.

**Files to Modify:**
- `src/emerald/iam/domain/constants.py`

**Acceptance Criteria:**
- [ ] `REFRESH_TOKEN_TTL_SUPERADMIN: timedelta = timedelta(minutes=15)`

**Tests:**
- [ ] No dedicated test file — verified through AuthenticationService tests (TASK-011)

---

### Phase 3: Domain Layer — Aggregate Extensions

#### TASK-006: Extend User Aggregate with Admin Permissions & Role Methods

**Layer:** Domain
**Depends On:** TASK-001, TASK-003, TASK-004

**Description:**
Add `admin_permissions` attribute and 6 new methods to the User aggregate. Also add SUPERADMIN guards on existing `soft_delete()` and `suspend()` methods.

**Files to Modify:**
- `src/emerald/iam/domain/models/user.py`

**New Attribute:**
- `admin_permissions: frozenset[AdminPermission] | None = None` in `__init__`

**New Methods:**
1. `promote_to_admin(permissions, promoted_by_role, promoted_by_id)` — USER → ADMIN
2. `demote_to_user(demoted_by_role, demoted_by_id)` — ADMIN → USER
3. `grant_admin_permission(permission, granted_by_role, granted_by_id, granted_by_has_permission)` — add perm to ADMIN
4. `revoke_admin_permission(permission, revoked_by_role, revoked_by_id)` — remove perm from ADMIN
5. `has_admin_permission(permission) -> bool` — permission check with SUPERADMIN short-circuit
6. `can_access_admin_portal() -> bool` — delegates to `system_role.is_admin_or_above()`

**Modified Methods:**
- `soft_delete()`: Add SUPERADMIN guard before existing status check
- `suspend()`: Add SUPERADMIN guard before existing status check

**New Imports:**
- `AdminPermission` from `admin_permission` module
- New exceptions: `InvalidRoleTransitionError`, `CannotDemoteSuperadminError`, `CannotDeleteSuperadminError`, `CannotSuspendSuperadminError`, `EmptyAdminPermissionsError`, `InsufficientPermissionsError`, `NotAdminError`, `CannotGrantUnownedPermissionError`, `LastAdminPermissionError`
- New events: `UserPromotedToAdmin`, `UserDemotedToUser`, `AdminPermissionGranted`, `AdminPermissionRevoked`

**Acceptance Criteria:**
- [ ] `promote_to_admin()` validates preconditions, sets role/permissions, emits event (AC-03)
- [ ] `demote_to_user()` validates preconditions, clears role/permissions, emits event (AC-04)
- [ ] `grant_admin_permission()` validates preconditions, adds permission, emits event (AC-05)
- [ ] `revoke_admin_permission()` validates preconditions, removes permission, emits event (AC-06)
- [ ] `has_admin_permission()` respects SUPERADMIN, FULL_ADMIN, direct match (AC-07)
- [ ] `can_access_admin_portal()` delegates correctly (AC-07)
- [ ] `soft_delete()` rejects SUPERADMIN with `CannotDeleteSuperadminError` (AC-08)
- [ ] `suspend()` rejects SUPERADMIN with `CannotSuspendSuperadminError` (AC-08)
- [ ] Idempotent behavior for grant (already-held) and revoke (not-held)
- [ ] All invariants from spec Section 7 enforced

**Tests:**
- [ ] `tests/unit/iam/domain/models/test_user_roles.py` — comprehensive tests covering AC-03 through AC-08, AC-11

---

### Phase 4: Application Layer — Commands

#### TASK-007: Add Role Management Commands

**Layer:** Application
**Depends On:** None

**Description:**
Create new commands for role/permission operations and SUPERADMIN provisioning.

**Files to Create:**
- `src/emerald/iam/application/dto/role_commands.py`

**Files to Modify:**
- `src/emerald/iam/application/dto/__init__.py` (re-exports)

**Commands:**
1. `PromoteToAdmin(Command)` — `user_id: str`, `permissions: list[str]`, `promoted_by_id: str`
2. `DemoteToUser(Command)` — `user_id: str`, `demoted_by_id: str`
3. `GrantAdminPermission(Command)` — `user_id: str`, `permission: str`, `granted_by_id: str`
4. `RevokeAdminPermission(Command)` — `user_id: str`, `permission: str`, `revoked_by_id: str`
5. `ProvisionSuperadmin(Command)` — `email: str`, `username: str`, `password: str`

**Acceptance Criteria:**
- [ ] All commands are `@dataclass(frozen=True)` extending `Command`
- [ ] All re-exported from dto `__init__.py`

**Tests:**
- [ ] Tested implicitly through service tests (TASK-009, TASK-010)

---

### Phase 5: Application Layer — Ports & Fakes

#### TASK-008: Extend UserRepository and FakeUserRepository

**Layer:** Application / Tests
**Depends On:** None

**Description:**
Add `exists_by_role(role: SystemRole) -> bool` to the `UserRepository` protocol and implement it on `FakeUserRepository`.

**Files to Modify:**
- `src/emerald/iam/application/ports/outbound/user_repository.py`
- `tests/unit/iam/fakes.py`

**Acceptance Criteria:**
- [ ] `UserRepository` protocol has `exists_by_role(role: SystemRole) -> bool`
- [ ] `FakeUserRepository.exists_by_role()` checks in-memory users for matching role
- [ ] Existing tests unaffected

**Tests:**
- [ ] Verified through SuperadminProvisioningService tests (TASK-010)

---

### Phase 6: Application Layer — Services

#### TASK-009: Create RoleManagementService

**Layer:** Application
**Depends On:** TASK-006, TASK-007, TASK-008

**Description:**
Create the `RoleManagementService` with 4 methods: `promote_to_admin()`, `demote_to_user()`, `grant_admin_permission()`, `revoke_admin_permission()`. Each loads actor and target users, validates preconditions at application level (self-modification prevention, actor role checks), then delegates to aggregate methods.

**Files to Create:**
- `src/emerald/iam/application/services/role_management.py`

**Files to Modify:**
- `src/emerald/iam/application/services/__init__.py` (re-export)

**Implementation Details:**

`promote_to_admin(cmd: PromoteToAdmin)`:
1. Parse UUIDs from command
2. Validate `actor_id != target_user_id` → raise `InsufficientPermissionsError` (self-promotion)
3. Load actor user → assert not None → check `actor.system_role == SUPERADMIN`
4. Load target user → assert not None
5. Parse permissions: `[AdminPermission(AdminPermissionType(p)) for p in cmd.permissions]`
6. Call `target.promote_to_admin(set(permissions), actor.system_role, actor.id)`
7. Commit

`demote_to_user(cmd: DemoteToUser)`:
1. Parse UUIDs
2. Validate self-demotion guard
3. Load actor → check SUPERADMIN
4. Load target
5. Call `target.demote_to_user(actor.system_role, actor.id)`
6. Commit

`grant_admin_permission(cmd: GrantAdminPermission)`:
1. Parse UUIDs and permission
2. Validate self-grant guard
3. Load actor → check `actor.system_role.is_admin_or_above()`
4. Check `actor.has_admin_permission(permission)` → get boolean
5. Load target
6. Call `target.grant_admin_permission(permission, actor.system_role, actor.id, has_perm)`
7. Commit

`revoke_admin_permission(cmd: RevokeAdminPermission)`:
1. Parse UUIDs and permission
2. Validate self-revoke guard
3. Load actor → check SUPERADMIN
4. Load target
5. Call `target.revoke_admin_permission(permission, actor.system_role, actor.id)`
6. Commit

**Acceptance Criteria:**
- [ ] All 4 methods orchestrate correctly
- [ ] Self-modification prevented (AC-12)
- [ ] Actor role validated before aggregate call
- [ ] UserNotFoundError raised for missing users
- [ ] UoW commit called on success

**Tests:**
- [ ] `tests/unit/iam/application/services/test_role_management.py` — happy paths + error cases for all 4 methods, self-modification prevention (AC-12)

---

#### TASK-010: Create SuperadminProvisioningService

**Layer:** Application
**Depends On:** TASK-004, TASK-007, TASK-008

**Description:**
Create the provisioning service that bootstraps the SUPERADMIN user. This service validates password, checks uniqueness, creates user via `User.register()`, then overrides role/status/email_verified.

**Files to Create:**
- `src/emerald/iam/application/services/superadmin_provisioning.py`

**Files to Modify:**
- `src/emerald/iam/application/services/__init__.py` (re-export)

**Implementation Details:**

`provision_superadmin(cmd: ProvisionSuperadmin) -> User`:
1. Validate password strength via `validate_password_strength()`
2. Check no SUPERADMIN exists: `uow.users.exists_by_role(SystemRole.SUPERADMIN)` → raise `SuperadminAlreadyExistsError`
3. Validate email uniqueness: `EmailAddress(cmd.email)` + `uow.users.exists_by_email()` → raise `EmailAlreadyExistsError`
4. Validate username uniqueness: `Username(cmd.username)` + `uow.users.exists_by_username()` → raise `UsernameAlreadyExistsError`
5. Hash password: `hasher.hash(cmd.password)`
6. Create user: `User.register(email, username, HashedPassword(hashed))`
7. Override attributes: `user.system_role = SystemRole.SUPERADMIN`, `user.status = UserStatus.ACTIVE`, `user.email_verified = True`
8. Record `SuperadminProvisioned` event on user (via `user._register_event()`)
9. Persist: `uow.users.add(user)`, `uow.commit()`
10. Return user

**Acceptance Criteria:**
- [ ] SUPERADMIN created with correct role, ACTIVE status, email_verified=True (AC-09)
- [ ] Fails if SUPERADMIN already exists (AC-09)
- [ ] Validates email/username uniqueness (AC-09)
- [ ] Validates password strength (AC-09)
- [ ] `SuperadminProvisioned` event recorded (AC-09)
- [ ] `admin_permissions` is None on SUPERADMIN (AC-08)

**Tests:**
- [ ] `tests/unit/iam/application/services/test_superadmin_provisioning.py` — happy path + all error cases (AC-09)

---

#### TASK-011: Modify AuthenticationService for SUPERADMIN TTL Override

**Layer:** Application
**Depends On:** TASK-005

**Description:**
Modify `login()` and `refresh()` to check user's `system_role` and override refresh token TTL for SUPERADMIN.

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**Changes to `login()`:**
- After step 4 (verify password), before step 6 (create token family):
  - Import `REFRESH_TOKEN_TTL_SUPERADMIN` and `SystemRole`
  - Determine `refresh_ttl`: if `user.system_role == SystemRole.SUPERADMIN` use `REFRESH_TOKEN_TTL_SUPERADMIN`, else `portal_context.refresh_ttl`
  - Use `refresh_ttl` in RefreshToken `expires_at` calculation (line ~117)

**Changes to `refresh()`:**
- After step 7 (look up user), when creating new RefreshToken:
  - Determine `refresh_ttl`: if `user.system_role == SystemRole.SUPERADMIN` use `REFRESH_TOKEN_TTL_SUPERADMIN`, else `token.portal_context.refresh_ttl`
  - Use `refresh_ttl` in new RefreshToken `expires_at` (line ~188)

**Acceptance Criteria:**
- [ ] SUPERADMIN login produces 15-minute refresh token regardless of portal (AC-10)
- [ ] SUPERADMIN refresh produces 15-minute refresh token (AC-10)
- [ ] ADMIN login on admin portal still produces 4-hour TTL (AC-10)
- [ ] USER login still produces 7-day TTL (AC-10)

**Tests:**
- [ ] `tests/unit/iam/application/services/test_authentication_superadmin_ttl.py` — SUPERADMIN TTL override on login and refresh (AC-10)

---

### Phase 7: Re-exports & Public API

#### TASK-012: Update All __init__.py Re-exports

**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-011

**Description:**
Update all intermediate and top-level `__init__.py` files to re-export new public types.

**Files to Modify:**
- `src/emerald/iam/domain/models/__init__.py` — add `AdminPermission`, `AdminPermissionType`
- `src/emerald/iam/domain/events/__init__.py` — add 5 role events
- `src/emerald/iam/domain/exceptions/__init__.py` — add 10 new exceptions
- `src/emerald/iam/application/dto/__init__.py` — add 5 role commands
- `src/emerald/iam/application/services/__init__.py` — add `RoleManagementService`, `SuperadminProvisioningService`
- `src/emerald/iam/__init__.py` — add all new public symbols to imports and `__all__`

**Acceptance Criteria:**
- [ ] All new types importable from `emerald.iam`
- [ ] `__all__` lists updated alphabetically within sections

**Tests:**
- [ ] Verified by running full test suite and import checks

---

### Phase 8: Testing

#### TASK-013: Write Comprehensive Unit Tests

**Layer:** Tests
**Depends On:** TASK-001 through TASK-012

**Description:**
Write all test files with comprehensive coverage of acceptance criteria.

**Files to Create:**
- `tests/unit/iam/domain/models/test_admin_permission.py` — AdminPermission creation, includes() matrix (AC-02)
- `tests/unit/iam/domain/models/test_system_role.py` — hierarchy methods if not already tested (AC-01)
- `tests/unit/iam/domain/models/test_user_roles.py` — promote, demote, grant, revoke, has_permission, can_access, SUPERADMIN guards (AC-03 through AC-08, AC-11)
- `tests/unit/iam/domain/events/test_role_events.py` — event creation, fields, frozen
- `tests/unit/iam/domain/exceptions/test_role_exceptions.py` — instantiation, code, message, hierarchy
- `tests/unit/iam/application/services/test_role_management.py` — all RoleManagementService flows (AC-12)
- `tests/unit/iam/application/services/test_superadmin_provisioning.py` — provisioning flows (AC-09)
- `tests/unit/iam/application/services/test_authentication_superadmin_ttl.py` — TTL override (AC-10)

**Test Factory Helper:**
Add a `make_admin_user(**overrides)` helper to test files or fakes.py that creates a user promoted to ADMIN for testing grant/revoke/demote scenarios.

**Acceptance Criteria:**
- [ ] All acceptance criteria AC-01 through AC-12 have corresponding tests
- [ ] All tests pass
- [ ] No regressions in existing 622 tests

---

### Phase 9: Quality Checks

#### TASK-014: Run All Quality Checks

**Layer:** Cross-cutting
**Depends On:** TASK-013

**Description:**
Run the full quality check suite and fix any issues.

**Commands:**
```bash
uv run pytest -v
uv run ruff check --fix .
uv run ruff format .
uv run ty check
```

**Acceptance Criteria:**
- [ ] All tests pass (existing + new)
- [ ] Ruff check clean (no warnings)
- [ ] Ruff format clean
- [ ] ty check clean

---

## 5. Task Dependency Graph

```
TASK-001 (AdminPermission) ──────┐
TASK-002 (SystemRole extensions) ─┤
TASK-003 (Exceptions) ────────────┤
TASK-004 (Events) ────────────────┼──► TASK-006 (User aggregate) ──┐
TASK-005 (Constants) ─────────────┤                                │
                                  │                                │
TASK-007 (Commands) ──────────────┤                                │
TASK-008 (Repo extension) ────────┤                                │
                                  │                                │
                                  ├──► TASK-009 (RoleManagement) ──┤
                                  ├──► TASK-010 (Provisioning) ────┤
                                  └──► TASK-011 (Auth TTL) ────────┤
                                                                   │
                                       TASK-012 (Re-exports) ◄────┤
                                                                   │
                                       TASK-013 (Tests) ◄─────────┘
                                                                   │
                                       TASK-014 (Quality) ◄───────┘
```

**Parallelizable Groups:**
- **Group A** (all independent): TASK-001, TASK-002, TASK-003, TASK-004, TASK-005, TASK-007, TASK-008
- **Group B** (after Group A): TASK-006, TASK-009, TASK-010, TASK-011
- **Group C** (after Group B): TASK-012
- **Group D** (after Group C): TASK-013, TASK-014

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Modifying `User.soft_delete()` and `suspend()` breaks existing tests | Medium | High | SUPERADMIN guard goes before existing checks, so non-SUPERADMIN paths unchanged. Run full test suite after. |
| `AuthenticationService` TTL change breaks existing auth tests | Low | Medium | Change is additive — only affects SUPERADMIN users, which don't exist in current tests. |
| `ty` strictness issues with `frozenset[AdminPermission]` | Medium | Low | Use `Any` annotations where needed in test helpers, consistent with prior patterns. |
| `FakeUserRepository` `exists_by_role` introduces protocol mismatch | Low | Low | Simple addition — protocol is structural, so existing tests unaffected. |

---

## 7. Definition of Done

- [ ] All 14 tasks completed
- [ ] All acceptance criteria AC-01 through AC-12 covered by tests
- [ ] All unit tests passing (existing 622 + new)
- [ ] Ruff check clean
- [ ] Ruff format clean
- [ ] ty check clean
- [ ] All new types re-exported from `emerald.iam.__init__`
- [ ] No regressions in existing functionality

---

## 8. Estimated New Test Count

| Test File | Approx. Tests |
|---|---|
| `test_admin_permission.py` | ~15 |
| `test_system_role.py` (hierarchy) | ~15 |
| `test_user_roles.py` | ~50 |
| `test_role_events.py` | ~10 |
| `test_role_exceptions.py` | ~15 |
| `test_role_management.py` | ~30 |
| `test_superadmin_provisioning.py` | ~15 |
| `test_authentication_superadmin_ttl.py` | ~10 |
| **Total New** | **~160** |
| **Total (with existing 622)** | **~782** |
