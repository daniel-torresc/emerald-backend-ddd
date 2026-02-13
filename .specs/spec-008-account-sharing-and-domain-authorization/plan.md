# Spec 008: Account Sharing & Domain Authorization — Implementation Plan

**Spec:** `.specs/spec-008-account-sharing-and-domain-authorization/spec.md`
**Version:** 1.0
**Date:** 2026-02-13

---

## 1. Overview

This plan implements account sharing and domain authorization for the Core Finance bounded context. The work adds a `PermissionLevel` value object, an `AccountShare` child entity within the Account aggregate, share management methods, authorization check methods, a soft-delete cascade for shares, a new `AccountSharingService`, and migrates the existing `AccountManagementService` from simple ownership checks to share-based permission checks.

**Approach:** Inside-out (domain layer first, then application layer). The Account aggregate grows an internal `_shares` collection. No separate repository for shares — they are persisted as part of the Account aggregate.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| REQ-001 PermissionLevel | Domain | `PermissionLevel` enum value object |
| REQ-002 AccountShare entity | Domain | `AccountShare` entity (extends `Entity`) |
| REQ-003–008 Share operations | Domain | Methods on `Account` aggregate |
| REQ-009 Authorization checks | Domain | Query methods on `Account` aggregate |
| REQ-010 Access matrix | Domain | Encoded in `PermissionLevel` hierarchy |
| REQ-011 Deletion cascade | Domain | Extended `Account.soft_delete()` |
| REQ-012 Mgmt service migration | Application | `AccountManagementService` refactor |
| REQ-013 Sharing service | Application | New `AccountSharingService` |
| REQ-014 Repository extension | Application | `AccountRepository` + `find_accessible_by_user` |
| Domain constants | Domain | `MAX_SHARES_PER_ACCOUNT` in `constants.py` |
| New exceptions | Domain | 12 new exceptions in `sharing_exceptions.py` |
| New events | Domain | 5 new events in `sharing_events.py` |
| New commands | Application | 5 new commands in `sharing_commands.py` |

### 2.2 Component Diagram

```
Account Aggregate (extended)
  ├── _shares: list[AccountShare]    ← NEW child entity collection
  ├── share_with()                   ← NEW
  ├── update_share_permission()      ← NEW
  ├── revoke_share()                 ← NEW
  ├── leave_share()                  ← NEW
  ├── transfer_ownership()           ← NEW
  ├── has_permission() / is_owner()  ← NEW authorization checks
  ├── get_active_shares()            ← NEW query methods
  ├── soft_delete()                  ← MODIFIED (cascade)
  └── create()                       ← MODIFIED (initial OWNER share)

AccountShare Entity (NEW)
  ├── account_id, user_id, permission_level
  ├── granted_by, granted_at, updated_at
  ├── revoked_at, revoked_by
  ├── is_active() / is_revoked()
  ├── revoke(revoked_by)
  └── update_permission(new_level)

PermissionLevel (NEW)
  ├── VIEWER(1), EDITOR(2), OWNER(3)
  ├── has_at_least(required)
  └── can_grant(level)

AccountSharingService (NEW)
  └── Orchestrates share commands via UoW

AccountManagementService (MODIFIED)
  └── _verify_ownership() → account.is_owner()
```

### 2.3 Files Created/Modified

**New files (13 source + 11 test):**

| File | Layer | Purpose |
|------|-------|---------|
| `core_finance/domain/constants.py` | Domain | `MAX_SHARES_PER_ACCOUNT = 20` |
| `core_finance/domain/models/value_objects/permission_level.py` | Domain | `PermissionLevel` enum |
| `core_finance/domain/models/entities/__init__.py` | Domain | Package init |
| `core_finance/domain/models/entities/account_share.py` | Domain | `AccountShare` entity |
| `core_finance/domain/events/sharing_events.py` | Domain | 5 sharing events |
| `core_finance/domain/exceptions/sharing_exceptions.py` | Domain | 12 sharing exceptions |
| `core_finance/application/dtos/commands/sharing_commands.py` | Application | 5 sharing commands |
| `core_finance/application/services/account_sharing.py` | Application | `AccountSharingService` |
| `tests/unit/core_finance/domain/value_objects/test_permission_level.py` | Test | PermissionLevel tests |
| `tests/unit/core_finance/domain/entities/__init__.py` | Test | Package init |
| `tests/unit/core_finance/domain/entities/test_account_share.py` | Test | AccountShare unit tests |
| `tests/unit/core_finance/domain/aggregates/test_account_sharing.py` | Test | Aggregate share methods |
| `tests/unit/core_finance/domain/aggregates/test_account_authorization.py` | Test | Authorization checks |
| `tests/unit/core_finance/domain/aggregates/test_account_share_cascade.py` | Test | Soft-delete cascade |
| `tests/unit/core_finance/domain/events/test_sharing_events.py` | Test | Sharing event tests |
| `tests/unit/core_finance/domain/exceptions/test_sharing_exceptions.py` | Test | Sharing exception tests |
| `tests/unit/core_finance/application/dtos/commands/test_sharing_commands.py` | Test | Command tests |
| `tests/unit/core_finance/application/services/test_account_sharing.py` | Test | AccountSharingService tests |

**Modified files (8):**

| File | Change |
|------|--------|
| `core_finance/domain/models/aggregates/account.py` | Add `_shares`, share methods, authorization methods, cascade |
| `core_finance/domain/exceptions/__init__.py` | Re-export sharing exceptions, remove `NotAccountOwnerError` |
| `core_finance/domain/exceptions/account_exceptions.py` | Remove `NotAccountOwnerError` |
| `core_finance/domain/events/__init__.py` | Re-export sharing events |
| `core_finance/application/dtos/commands/__init__.py` | Re-export sharing commands |
| `core_finance/application/services/account_management.py` | Replace `_verify_ownership` with share-based checks |
| `core_finance/application/ports/outbound/account_repository.py` | Add `find_accessible_by_user` |
| `core_finance/__init__.py` | Export all new public types |
| `tests/unit/core_finance/fakes.py` | Add `find_accessible_by_user` to fake |
| `tests/unit/core_finance/application/services/test_account_*.py` | Adapt existing tests to share model |

---

## 3. Technical Decisions

### 3.1 AccountShare as Child Entity (Not Separate Aggregate)
**Decision:** AccountShare lives inside the Account aggregate's `_shares` collection.
**Rationale:** Sharing invariants (exactly one OWNER, max shares, no duplicate active shares) are Account aggregate invariants. Persisting shares as part of the account maintains transactional consistency. The spec explicitly states no separate `AccountShareRepository`.

### 3.2 PermissionLevel as Enum with Integer Hierarchy
**Decision:** Python `Enum` with integer `level` property, not a frozen dataclass.
**Rationale:** Matches the `SystemRole` pattern from IAM (spec-004) which uses the same `has_at_least()` hierarchy pattern. Simple, well-tested approach.

### 3.3 AccountShare Constructor — Explicit Fields (No Mixins)
**Decision:** AccountShare uses plain `Entity` base with explicit `granted_at`, `updated_at`, `revoked_at`, `revoked_by` fields. No `AuditableMixin` or `SoftDeletableMixin`.
**Rationale:** Spec explicitly states "No mixins: Uses explicit domain-specific fields rather than SoftDeletableMixin or AuditableMixin". The revocation model (simple `revoked_at`/`revoked_by`) differs from the full soft-delete lifecycle.

### 3.4 AccountNotActiveError Reuse
**Decision:** Create a new `AccountNotActiveError` exception for share operations on deleted accounts, distinct from `AlreadyDeletedError` (which is raised by `SoftDeletableMixin`).
**Rationale:** The spec defines `AccountNotActiveError` with code `ACCOUNT_NOT_ACTIVE` extending `InvariantViolationError`. This is semantically different from the generic `AlreadyDeletedError` — it means "you cannot share a deleted account" rather than "you tried to delete an already-deleted entity".

### 3.5 Replacing NotAccountOwnerError
**Decision:** Remove `NotAccountOwnerError` entirely. Replace all usages with `InsufficientPermissionError`.
**Rationale:** Spec explicitly states deprecation. The new exception is more general (covers OWNER, EDITOR, VIEWER checks) and uses code `INSUFFICIENT_PERMISSION`.

### 3.6 Account Constructor Accepts shares Parameter
**Decision:** The `Account.__init__` accepts an optional `shares: list[AccountShare] | None = None` parameter for repository hydration.
**Rationale:** When loading from persistence, the repository must be able to reconstruct the aggregate with its shares. The factory `create()` will build the initial OWNER share internally.

---

## 4. Implementation Tasks

### Phase 1: Domain Layer — Value Objects & Constants

#### TASK-001: Create domain constants
**Layer:** Domain
**Depends On:** None

**Description:**
Create `core_finance/domain/constants.py` with the `MAX_SHARES_PER_ACCOUNT` constant.

**Files:**
- `src/emerald/core_finance/domain/constants.py` — **CREATE**

**Implementation Details:**
```python
MAX_SHARES_PER_ACCOUNT: int = 20
```

**Acceptance Criteria:**
- [ ] `MAX_SHARES_PER_ACCOUNT = 20` is defined
- [ ] Importable from `emerald.core_finance.domain.constants`

**Tests:** No dedicated test file — constant is tested transitively via aggregate tests.

---

#### TASK-002: Create PermissionLevel value object
**Layer:** Domain
**Depends On:** None

**Description:**
Create `PermissionLevel` enum with `VIEWER`, `EDITOR`, `OWNER` members, integer hierarchy via `level` property, `has_at_least()` comparison, and `can_grant()` authorization check.

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/permission_level.py` — **CREATE**
- `tests/unit/core_finance/domain/value_objects/test_permission_level.py` — **CREATE**

**Implementation Details:**
- Python `Enum` (not IntEnum — use explicit `level` property via dict lookup, matching `SystemRole` pattern)
- `VIEWER = "VIEWER"`, `EDITOR = "EDITOR"`, `OWNER = "OWNER"` with levels 1, 2, 3
- `has_at_least(required: PermissionLevel) -> bool` — `self.level >= required.level`
- `can_grant(level: PermissionLevel) -> bool` — `True` only when `self == OWNER`
- `level` property returns integer from `_PERMISSION_LEVELS` dict

**Tests (~15):**
- `has_at_least()` — all 9 combinations (3×3 matrix)
- `can_grant()` — OWNER can grant VIEWER/EDITOR, OWNER cannot grant OWNER, EDITOR/VIEWER cannot grant anything
- `level` property returns correct integers
- Enum members have correct string values

---

#### TASK-003: Create sharing exceptions
**Layer:** Domain
**Depends On:** None

**Description:**
Create all 12 sharing-related exceptions as defined in spec section 13. Also remove `NotAccountOwnerError` from `account_exceptions.py`.

**Files:**
- `src/emerald/core_finance/domain/exceptions/sharing_exceptions.py` — **CREATE**
- `src/emerald/core_finance/domain/exceptions/account_exceptions.py` — **MODIFY** (remove `NotAccountOwnerError`)
- `src/emerald/core_finance/domain/exceptions/__init__.py` — **MODIFY** (re-export sharing exceptions, remove `NotAccountOwnerError`)
- `tests/unit/core_finance/domain/exceptions/test_sharing_exceptions.py` — **CREATE**

**Implementation Details:**

| Exception | Parent | Code |
|-----------|--------|------|
| `InsufficientPermissionError` | `AuthorizationError` | `INSUFFICIENT_PERMISSION` |
| `CannotGrantOwnerError` | `InvariantViolationError` | `CANNOT_GRANT_OWNER` |
| `CannotShareWithSelfError` | `InvariantViolationError` | `CANNOT_SHARE_WITH_SELF` |
| `AlreadySharedError` | `ConflictError` | `ALREADY_SHARED` |
| `ShareNotFoundError` | `NotFoundError` | `SHARE_NOT_FOUND` |
| `CannotRevokeOwnerError` | `InvariantViolationError` | `CANNOT_REVOKE_OWNER` |
| `CannotModifyOwnerShareError` | `InvariantViolationError` | `CANNOT_MODIFY_OWNER_SHARE` |
| `AlreadyOwnerError` | `InvariantViolationError` | `ALREADY_OWNER` |
| `AccountNotActiveError` | `InvariantViolationError` | `ACCOUNT_NOT_ACTIVE` |
| `MaxSharesReachedError` | `InvariantViolationError` | `MAX_SHARES_REACHED` |
| `CannotLeaveAsOwnerError` | `InvariantViolationError` | `CANNOT_LEAVE_AS_OWNER` |
| `ShareAlreadyRevokedError` | `ConflictError` | `SHARE_ALREADY_REVOKED` |

Follow existing pattern: each exception has `__init__(self, message: str = "...", code: str = "...") -> None` calling `super().__init__(message, code)`.

**Tests (~12):**
- Each exception instantiates with defaults and custom messages
- Each has correct `code` attribute
- Each extends the correct parent class

---

#### TASK-004: Create sharing events
**Layer:** Domain
**Depends On:** None

**Description:**
Create 5 domain events for share lifecycle operations.

**Files:**
- `src/emerald/core_finance/domain/events/sharing_events.py` — **CREATE**
- `src/emerald/core_finance/domain/events/__init__.py` — **MODIFY** (re-export)
- `tests/unit/core_finance/domain/events/test_sharing_events.py` — **CREATE**

**Implementation Details:**
All `@dataclass(frozen=True)` extending `DomainEvent` with `aggregate_type: ClassVar[str] = "account"`:

```python
class AccountShared(DomainEvent):
    user_id: uuid.UUID = uuid.UUID(int=0)
    permission_level: str = ""
    granted_by: uuid.UUID = uuid.UUID(int=0)

class AccountShareUpdated(DomainEvent):
    user_id: uuid.UUID = uuid.UUID(int=0)
    old_permission: str = ""
    new_permission: str = ""
    updated_by: uuid.UUID = uuid.UUID(int=0)

class AccountShareRevoked(DomainEvent):
    user_id: uuid.UUID = uuid.UUID(int=0)
    revoked_by: uuid.UUID = uuid.UUID(int=0)

class AccountShareLeft(DomainEvent):
    user_id: uuid.UUID = uuid.UUID(int=0)

class AccountOwnershipTransferred(DomainEvent):
    old_owner_id: uuid.UUID = uuid.UUID(int=0)
    new_owner_id: uuid.UUID = uuid.UUID(int=0)
```

All events carry `aggregate_id` (= account_id) from `DomainEvent` base.

**Tests (~10):**
- Each event instantiates with defaults
- Each event carries correct `aggregate_type = "account"`
- Each event stores its specific data fields
- `occurred_at` and `event_id` are auto-generated

---

### Phase 2: Domain Layer — AccountShare Entity

#### TASK-005: Create AccountShare entity
**Layer:** Domain
**Depends On:** TASK-002 (PermissionLevel), TASK-003 (ShareAlreadyRevokedError)

**Description:**
Create the `AccountShare` child entity with all attributes, `is_active()`, `is_revoked()`, `revoke()`, and `update_permission()` methods.

**Files:**
- `src/emerald/core_finance/domain/models/entities/__init__.py` — **CREATE** (package)
- `src/emerald/core_finance/domain/models/entities/account_share.py` — **CREATE**
- `tests/unit/core_finance/domain/entities/__init__.py` — **CREATE** (package)
- `tests/unit/core_finance/domain/entities/test_account_share.py` — **CREATE**

**Implementation Details:**
- Extends `Entity` (not `AggregateRoot`)
- Constructor: keyword-only args with `**kwargs` not needed (no mixin MRO)
- Fields: `account_id`, `user_id`, `permission_level`, `granted_by`, `granted_at`, `updated_at`, `revoked_at`, `revoked_by`
- `granted_at` and `updated_at` default to `datetime.now(UTC)` in constructor
- `revoked_at` and `revoked_by` default to `None`
- `is_active() -> bool`: `revoked_at is None`
- `is_revoked() -> bool`: `revoked_at is not None`
- `revoke(revoked_by: uuid.UUID) -> None`: validates not already revoked (raises `ShareAlreadyRevokedError`), sets `revoked_at` and `revoked_by`
- `update_permission(new_level: PermissionLevel) -> None`: sets `permission_level` and `updated_at`
- Identity-based equality from `Entity` base (by `id`)

**Tests (~15):**
- Construction with all required fields
- `is_active()` returns True when not revoked
- `is_revoked()` returns True after revocation
- `revoke()` sets `revoked_at` and `revoked_by`
- `revoke()` on already-revoked raises `ShareAlreadyRevokedError`
- `update_permission()` changes level and refreshes `updated_at`
- Identity-based equality (two shares with same id are equal)
- Identity-based equality (two shares with different ids are not equal)

---

### Phase 3: Domain Layer — Account Aggregate Extensions

#### TASK-006: Extend Account aggregate with shares collection and factory
**Layer:** Domain
**Depends On:** TASK-001 (constants), TASK-002 (PermissionLevel), TASK-005 (AccountShare)

**Description:**
Add `_shares: list[AccountShare]` to Account, accept optional `shares` in constructor for hydration, and modify `Account.create()` to produce the initial OWNER share.

**Files:**
- `src/emerald/core_finance/domain/models/aggregates/account.py` — **MODIFY**
- `tests/unit/core_finance/domain/aggregates/test_account_create.py` — **MODIFY** (adapt existing tests)

**Implementation Details:**

Constructor changes:
```python
def __init__(self, *, shares: list[AccountShare] | None = None, **kwargs: Any) -> None:
    super().__init__(**kwargs)
    # ... existing fields ...
    self._shares: list[AccountShare] = shares if shares is not None else []
```

Factory changes:
```python
@classmethod
def create(cls, owner: UserReference, ...) -> Account:
    # ... existing validation ...
    account = cls(...)
    # Create initial OWNER share
    owner_share = AccountShare(
        account_id=account.id,
        user_id=owner.user_id,
        permission_level=PermissionLevel.OWNER,
        granted_by=owner.user_id,
    )
    account._shares.append(owner_share)
    # Remove TODO comment about spec-008
    account._register_event(AccountCreated(...))
    return account
```

**Acceptance Criteria:**
- [ ] `Account.create()` produces an account with exactly 1 active share
- [ ] The share is OWNER level with `user_id == granted_by == owner.user_id`
- [ ] `account.active_share_count` is 1 after creation
- [ ] Existing creation tests still pass (adapted to include share assertions)
- [ ] Constructor accepts `shares` parameter for repository hydration

**Tests:** Modify existing `test_account_create.py` to assert OWNER share is present. Add new assertions for `active_share_count`, `is_owner(creator_id)`.

---

#### TASK-007: Add share management methods to Account
**Layer:** Domain
**Depends On:** TASK-003 (exceptions), TASK-004 (events), TASK-006 (shares collection)

**Description:**
Implement `share_with()`, `update_share_permission()`, `revoke_share()`, `leave_share()`, and `transfer_ownership()` on the Account aggregate.

**Files:**
- `src/emerald/core_finance/domain/models/aggregates/account.py` — **MODIFY**
- `tests/unit/core_finance/domain/aggregates/test_account_sharing.py` — **CREATE**

**Implementation Details:**

Each method follows the pattern: validate preconditions → mutate state → register event → touch aggregate.

**`share_with(user_id, permission, granted_by) -> AccountShare`:**
1. Validate account is active (`not self.is_deleted()`) → `AccountNotActiveError`
2. Validate `granted_by` is OWNER → `InsufficientPermissionError`
3. Validate `permission` is not OWNER → `CannotGrantOwnerError`
4. Validate `user_id != granted_by` → `CannotShareWithSelfError`
5. Validate no active share for `user_id` → `AlreadySharedError`
6. Validate `active_share_count < MAX_SHARES_PER_ACCOUNT` → `MaxSharesReachedError`
7. Create `AccountShare`, append to `_shares`
8. Register `AccountShared` event, `_touch()`
9. Return created share

**`update_share_permission(user_id, new_permission, updated_by) -> None`:**
1. Validate `updated_by` is OWNER → `InsufficientPermissionError`
2. Find active share for `user_id` → `ShareNotFoundError`
3. Validate `new_permission` is not OWNER → `CannotGrantOwnerError`
4. Validate `user_id` is not the owner → `CannotModifyOwnerShareError`
5. Call `share.update_permission(new_permission)`
6. Register `AccountShareUpdated` event, `_touch()`

**`revoke_share(user_id, revoked_by) -> None`:**
1. Validate `revoked_by` is OWNER → `InsufficientPermissionError`
2. Find active share for `user_id` → `ShareNotFoundError`
3. Validate `user_id` is not the owner → `CannotRevokeOwnerError`
4. Call `share.revoke(revoked_by)`
5. Register `AccountShareRevoked` event, `_touch()`

**`leave_share(user_id) -> None`:**
1. Find active share for `user_id` → `ShareNotFoundError`
2. Validate `user_id` is NOT the owner → `CannotLeaveAsOwnerError`
3. Call `share.revoke(user_id)` (self-revoke)
4. Register `AccountShareLeft` event, `_touch()`

**`transfer_ownership(new_owner_id, current_owner_id) -> None`:**
1. Validate `current_owner_id` is the current OWNER → `InsufficientPermissionError`
2. Find active share for `new_owner_id` → `ShareNotFoundError`
3. Validate `new_owner_id != current_owner_id` → `AlreadyOwnerError`
4. Current owner share: `update_permission(EDITOR)`
5. New owner share: `update_permission(OWNER)`
6. Register `AccountOwnershipTransferred` event, `_touch()`

Helper for owner lookup:
```python
def _get_owner_share(self) -> AccountShare:
    for share in self._shares:
        if share.is_active() and share.permission_level == PermissionLevel.OWNER:
            return share
    raise InvariantViolationError(...)  # should never happen
```

Helper for active share lookup:
```python
def _find_active_share(self, user_id: uuid.UUID) -> AccountShare | None:
    for share in self._shares:
        if share.is_active() and share.user_id == user_id:
            return share
    return None
```

**Tests (~45):**
- **share_with:** happy path VIEWER, happy path EDITOR, all 6 error cases, event emitted, share attributes correct
- **update_share_permission:** happy VIEWER→EDITOR, EDITOR→VIEWER, all 4 error cases, event with old/new, updated_at refreshed
- **revoke_share:** happy path, all 3 error cases, event emitted, share marked revoked, re-sharing after revoke allowed
- **leave_share:** happy EDITOR leaves, happy VIEWER leaves, owner cannot leave, no share raises error, event emitted
- **transfer_ownership:** happy path, old owner becomes EDITOR, new owner becomes OWNER, all 3 error cases, event emitted, both shares updated_at refreshed, transfer VIEWER→OWNER allowed

---

#### TASK-008: Add authorization check methods to Account
**Layer:** Domain
**Depends On:** TASK-006 (shares collection)

**Description:**
Implement `get_share_for_user()`, `get_permission_level()`, `has_permission()`, `is_owner()`, `can_edit()`, `can_view()`, `get_active_shares()`, `get_owner()`, and `active_share_count` property.

**Files:**
- `src/emerald/core_finance/domain/models/aggregates/account.py` — **MODIFY**
- `tests/unit/core_finance/domain/aggregates/test_account_authorization.py` — **CREATE**

**Implementation Details:**

```python
def get_share_for_user(self, user_id: uuid.UUID) -> AccountShare | None:
    return self._find_active_share(user_id)

def get_permission_level(self, user_id: uuid.UUID) -> PermissionLevel | None:
    share = self._find_active_share(user_id)
    return share.permission_level if share is not None else None

def has_permission(self, user_id: uuid.UUID, required: PermissionLevel) -> bool:
    share = self._find_active_share(user_id)
    return share is not None and share.permission_level.has_at_least(required)

def is_owner(self, user_id: uuid.UUID) -> bool:
    return self.has_permission(user_id, PermissionLevel.OWNER)

def can_edit(self, user_id: uuid.UUID) -> bool:
    return self.has_permission(user_id, PermissionLevel.EDITOR)

def can_view(self, user_id: uuid.UUID) -> bool:
    return self.has_permission(user_id, PermissionLevel.VIEWER)

def get_active_shares(self) -> list[AccountShare]:
    return [s for s in self._shares if s.is_active()]

def get_owner(self) -> AccountShare:
    return self._get_owner_share()

@property
def active_share_count(self) -> int:
    return sum(1 for s in self._shares if s.is_active())
```

**Tests (~25):**
- `has_permission()`: True for matching/exceeding level, False for insufficient, False for revoked, False for no share
- `is_owner()`: True for owner, False for editor/viewer/no share
- `can_edit()`: True for owner+editor, False for viewer/no share
- `can_view()`: True for owner+editor+viewer, False for no share
- `get_active_shares()`: excludes revoked, returns all active
- `get_owner()`: returns the OWNER share
- `active_share_count`: correct after create, share, revoke
- SUPERADMIN with no share is denied (demonstrated via `has_permission` returning False for unknown user_id)

---

#### TASK-009: Implement soft-delete cascade for shares
**Layer:** Domain
**Depends On:** TASK-007 (share management), TASK-008 (authorization checks)

**Description:**
Extend `Account.soft_delete()` to cascade-revoke all non-owner active shares. Verify `Account.recover()` does NOT restore revoked shares.

**Files:**
- `src/emerald/core_finance/domain/models/aggregates/account.py` — **MODIFY**
- `tests/unit/core_finance/domain/aggregates/test_account_share_cascade.py` — **CREATE**
- `tests/unit/core_finance/domain/aggregates/test_account_lifecycle.py` — **MODIFY** (adapt existing tests)

**Implementation Details:**

```python
def soft_delete(self, deleted_by: uuid.UUID, retention: RetentionPeriod, reason: str | None = None) -> None:
    # Cascade: revoke all non-owner active shares
    for share in self._shares:
        if share.is_active() and share.permission_level != PermissionLevel.OWNER:
            share.revoke(deleted_by)
    # Existing behavior
    super().soft_delete(deleted_by=deleted_by, retention=retention, reason=reason)
    self._touch()
    self._register_event(AccountSoftDeleted(...))
```

Note: Cascade revocation happens BEFORE `super().soft_delete()` so that shares are revoked while the account is still in active state. The OWNER share is preserved.

`recover()` — no changes needed. Shares remain revoked after recovery per spec.

**Tests (~12):**
- Soft-delete with 3 shared users: 2 non-owner shares revoked, owner retained
- Each cascaded share has `revoked_by` set to the deleting user
- After recovery: owner is active, non-owner shares remain revoked
- `active_share_count` is 1 after recovery (only owner)
- Soft-delete with no non-owner shares: only owner remains, no errors
- Existing lifecycle tests adapted to account for shares in create

---

### Phase 4: Application Layer

#### TASK-010: Create sharing commands
**Layer:** Application
**Depends On:** None

**Description:**
Create 5 command dataclasses for sharing operations.

**Files:**
- `src/emerald/core_finance/application/dtos/commands/sharing_commands.py` — **CREATE**
- `src/emerald/core_finance/application/dtos/commands/__init__.py` — **MODIFY** (re-export)
- `tests/unit/core_finance/application/dtos/commands/test_sharing_commands.py` — **CREATE**

**Implementation Details:**
All `@dataclass(frozen=True)` extending `Command`, with default values per established pattern:

```python
class ShareAccountWith(Command):
    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    target_user_id: uuid.UUID = uuid.UUID(int=0)
    permission_level: str = ""

class UpdateSharePermission(Command):
    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    target_user_id: uuid.UUID = uuid.UUID(int=0)
    new_permission_level: str = ""

class RevokeAccountShare(Command):
    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    target_user_id: uuid.UUID = uuid.UUID(int=0)

class LeaveAccountShare(Command):
    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)

class TransferAccountOwnership(Command):
    account_id: uuid.UUID = uuid.UUID(int=0)
    requesting_user_id: uuid.UUID = uuid.UUID(int=0)
    new_owner_id: uuid.UUID = uuid.UUID(int=0)
```

**Tests (~5):**
- Each command is frozen (immutable)
- Each command extends `Command`
- Fields have correct defaults

---

#### TASK-011: Extend AccountRepository protocol
**Layer:** Application
**Depends On:** None

**Description:**
Add `find_accessible_by_user()` method to the `AccountRepository` protocol and update the fake.

**Files:**
- `src/emerald/core_finance/application/ports/outbound/account_repository.py` — **MODIFY**
- `tests/unit/core_finance/fakes.py` — **MODIFY**

**Implementation Details:**

Protocol addition:
```python
def find_accessible_by_user(
    self, user_id: uuid.UUID, include_deleted: bool = False
) -> list[Account]: ...
```

Fake implementation:
```python
def find_accessible_by_user(
    self, user_id: uuid.UUID, include_deleted: bool = False
) -> list[Account]:
    results: list[Account] = []
    for account in self._accounts.values():
        if not include_deleted and account.is_deleted():
            continue
        if account.has_permission(user_id, PermissionLevel.VIEWER):
            self.seen.add(account)
            results.append(account)
    return results
```

Note: The UoW `TODO(spec-008)` comment about `shares: AccountShareRepository` should be **removed** (not implemented) since shares live inside the Account aggregate per spec.

**Acceptance Criteria:**
- [ ] Protocol defines `find_accessible_by_user`
- [ ] Fake returns accounts where user has any active share
- [ ] `include_deleted=False` excludes soft-deleted accounts

---

#### TASK-012: Create AccountSharingService
**Layer:** Application
**Depends On:** TASK-007 (aggregate methods), TASK-010 (commands), TASK-011 (repository)

**Description:**
Create the `AccountSharingService` application service that orchestrates all share operations.

**Files:**
- `src/emerald/core_finance/application/services/account_sharing.py` — **CREATE**
- `src/emerald/core_finance/application/services/__init__.py` — **MODIFY** (re-export)
- `tests/unit/core_finance/application/services/test_account_sharing.py` — **CREATE**

**Implementation Details:**

```python
class AccountSharingService:
    def __init__(self, uow: AbstractCoreFinanceUnitOfWork) -> None:
        self._uow = uow

    def share_account(self, cmd: ShareAccountWith) -> AccountShare:
        account = self._load_account(cmd.account_id)
        permission = PermissionLevel[cmd.permission_level]
        share = account.share_with(
            user_id=cmd.target_user_id,
            permission=permission,
            granted_by=cmd.requesting_user_id,
        )
        self._uow.commit()
        return share

    def update_share_permission(self, cmd: UpdateSharePermission) -> None:
        account = self._load_account(cmd.account_id)
        permission = PermissionLevel[cmd.new_permission_level]
        account.update_share_permission(
            user_id=cmd.target_user_id,
            new_permission=permission,
            updated_by=cmd.requesting_user_id,
        )
        self._uow.commit()

    def revoke_share(self, cmd: RevokeAccountShare) -> None:
        account = self._load_account(cmd.account_id)
        account.revoke_share(
            user_id=cmd.target_user_id,
            revoked_by=cmd.requesting_user_id,
        )
        self._uow.commit()

    def leave_share(self, cmd: LeaveAccountShare) -> None:
        account = self._load_account(cmd.account_id)
        account.leave_share(user_id=cmd.requesting_user_id)
        self._uow.commit()

    def transfer_ownership(self, cmd: TransferAccountOwnership) -> None:
        account = self._load_account(cmd.account_id)
        account.transfer_ownership(
            new_owner_id=cmd.new_owner_id,
            current_owner_id=cmd.requesting_user_id,
        )
        self._uow.commit()

    def _load_account(self, account_id: uuid.UUID) -> Account:
        account = self._uow.accounts.find_by_id(account_id)
        if account is None:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account
```

**Tests (~20):**
- **share_account:** happy path, commits UoW, returns created share, not found raises error
- **update_share_permission:** happy path, commits, not found raises error
- **revoke_share:** happy path, commits, not found raises error
- **leave_share:** happy path, commits, not found raises error
- **transfer_ownership:** happy path, commits, not found raises error
- All domain validation errors propagate through service (tested at domain layer)

---

#### TASK-013: Migrate AccountManagementService to share-based permissions
**Layer:** Application
**Depends On:** TASK-006 (Account with shares), TASK-008 (authorization methods), TASK-003 (InsufficientPermissionError)

**Description:**
Replace `_verify_ownership()` with `account.is_owner()` checks. Remove `NotAccountOwnerError` import. All existing service tests must be adapted.

**Files:**
- `src/emerald/core_finance/application/services/account_management.py` — **MODIFY**
- `tests/unit/core_finance/application/services/test_account_create.py` — **MODIFY**
- `tests/unit/core_finance/application/services/test_account_rename.py` — **MODIFY**
- `tests/unit/core_finance/application/services/test_account_update.py` — **MODIFY**
- `tests/unit/core_finance/application/services/test_account_soft_delete.py` — **MODIFY**
- `tests/unit/core_finance/application/services/test_account_recover.py` — **MODIFY**

**Implementation Details:**

1. Remove `_verify_ownership()` method entirely
2. Remove `NotAccountOwnerError` import
3. Import `InsufficientPermissionError` from sharing exceptions
4. Replace each call:

```python
# Before:
self._verify_ownership(account, cmd.requesting_user_id)

# After:
if not account.is_owner(cmd.requesting_user_id):
    raise InsufficientPermissionError(
        f"User {cmd.requesting_user_id} does not have OWNER permission on account {account.id}"
    )
```

5. In `create_account()`: Remove the `TODO(spec-008)` comment (OWNER share is now created by `Account.create()`)
6. In `rename_account()`: The `exists_by_name_for_user` check continues using `account.created_by` (the original creator). However, after ownership transfer, the new owner should be checked. To handle this correctly, use the owner's user_id from the aggregate: `account.get_owner().user_id`.

**Test Adaptations:**
- All tests that assert `NotAccountOwnerError` must be changed to assert `InsufficientPermissionError`
- Account factory helpers must be updated — `Account.create()` now creates an OWNER share, so any test that checks `created_by` ownership implicitly works via shares
- Tests that use non-owner user_ids for permission-denied cases remain valid

---

### Phase 5: Exports & Integration

#### TASK-014: Update public API exports
**Layer:** All
**Depends On:** All previous tasks

**Description:**
Update all `__init__.py` files to export new public types and remove deprecated ones.

**Files:**
- `src/emerald/core_finance/domain/__init__.py` — **MODIFY**
- `src/emerald/core_finance/domain/models/__init__.py` — **MODIFY** (if needed)
- `src/emerald/core_finance/domain/models/value_objects/__init__.py` — **MODIFY**
- `src/emerald/core_finance/application/__init__.py` — **MODIFY**
- `src/emerald/core_finance/__init__.py` — **MODIFY**

**New exports to add:**
```python
# Value Objects
"PermissionLevel",
# Entities
"AccountShare",
# Events
"AccountShared",
"AccountShareUpdated",
"AccountShareRevoked",
"AccountShareLeft",
"AccountOwnershipTransferred",
# Exceptions (add new, remove NotAccountOwnerError)
"InsufficientPermissionError",
"CannotGrantOwnerError",
"CannotShareWithSelfError",
"AlreadySharedError",
"ShareNotFoundError",
"CannotRevokeOwnerError",
"CannotModifyOwnerShareError",
"AlreadyOwnerError",
"AccountNotActiveError",
"MaxSharesReachedError",
"CannotLeaveAsOwnerError",
"ShareAlreadyRevokedError",
# Commands
"ShareAccountWith",
"UpdateSharePermission",
"RevokeAccountShare",
"LeaveAccountShare",
"TransferAccountOwnership",
# Services
"AccountSharingService",
```

**Remove from exports:**
```python
"NotAccountOwnerError",
```

**Acceptance Criteria:**
- [ ] All new types importable from `emerald.core_finance`
- [ ] `NotAccountOwnerError` no longer exported
- [ ] No circular imports

---

### Phase 6: Quality Assurance

#### TASK-015: Run full test suite and quality checks
**Layer:** Cross-cutting
**Depends On:** All previous tasks

**Description:**
Run all tests, linting, formatting, and type checking. Fix any issues.

**Commands:**
```bash
uv run pytest -v
uv run ruff check --fix .
uv run ruff format .
uv run ty check
```

**Acceptance Criteria:**
- [ ] All tests pass (existing 1278 + ~160 new ≈ 1438 total)
- [ ] `ruff check` clean
- [ ] `ruff format` clean
- [ ] `ty check` clean
- [ ] No regressions in existing tests

---

## 5. Task Dependency Graph

```
TASK-001 (constants)     ─┐
TASK-002 (PermLevel)     ─┼─► TASK-005 (AccountShare) ─┐
TASK-003 (exceptions)    ─┤                             ├─► TASK-006 (shares+factory) ─┐
TASK-004 (events)        ─┘                             │                              │
                                                        │                              │
                                                        └──────────────────────────────┤
                                                                                       │
                         TASK-010 (commands)            ─┐                             │
                         TASK-011 (repository)          ─┤    ┌────────────────────────┤
                                                        │    │                        │
                                                        │    ▼                        ▼
                                                        ├─► TASK-012 (SharingService) │
                                                        │                             │
                                                        │   TASK-007 (share methods)──┤
                                                        │   TASK-008 (auth checks)  ──┤
                                                        │   TASK-009 (cascade)      ──┤
                                                        │                             │
                                                        └─► TASK-013 (mgmt migration)┤
                                                                                      │
                                                        TASK-014 (exports)  ◄─────────┘
                                                                │
                                                                ▼
                                                        TASK-015 (QA)
```

**Parallelizable groups:**
- Group A (no deps): TASK-001, TASK-002, TASK-003, TASK-004, TASK-010, TASK-011
- Group B (after Group A): TASK-005
- Group C (after TASK-005): TASK-006, TASK-007, TASK-008
- Group D (after TASK-007+008): TASK-009, TASK-012, TASK-013
- Group E (after all): TASK-014, TASK-015

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Existing tests break due to Account.create() change | High | Medium | Adapt test factories to expect OWNER share; update assertions incrementally |
| MRO interaction with shares parameter in Account constructor | Low | Medium | `shares` is a simple list field set after `super().__init__()`, no MRO issues |
| Circular import between sharing_exceptions and Account | Low | High | Exceptions have no dependency on Account; Account imports exceptions |
| `ty` strict checking on share collection operations | Medium | Low | Use `dict[str, Any]` for test factories, `Any` for kwargs as established |
| Cascade revocation ordering (before vs after super().soft_delete) | Medium | Medium | Cascade BEFORE super() so shares are revoked while account is still "active" |

---

## 7. Definition of Done

- [ ] All 15 tasks completed
- [ ] All acceptance criteria from spec sections 15–16 met
- [ ] ~1438 total tests passing (1278 existing + ~160 new)
- [ ] `ruff check` clean
- [ ] `ruff format` clean
- [ ] `ty check` clean
- [ ] `NotAccountOwnerError` fully removed from codebase
- [ ] All TODO(spec-008) comments resolved
- [ ] Public API exports updated
- [ ] No regressions in existing functionality
