# Account Management Implementation Plan

**Spec:** `.specs/spec-007-account-management/spec.md`
**Version:** 1.0
**Date:** 2026-02-12

---

## 1. Overview

This plan implements the **Account aggregate** — the first entity in the **Core Finance** bounded context. It introduces:

- An Anti-Corruption Layer (`UserReference`) to translate IAM identity into Core Finance domain concepts
- Two new value objects (`AccountName`, `IBAN`) with full validation
- The `Account` aggregate root composing `SoftDeletableMixin`, `AuditableMixin`, and `AggregateRoot`
- 4 domain events, 7 exceptions, 7 commands
- `AccountRepository` protocol and `AbstractCoreFinanceUnitOfWork`
- `AccountManagementService` application service

**Key constraint:** The Core Finance domain layer must have zero IAM imports. `AuthenticatedIdentity` is only referenced at the application layer for translation to `UserReference`.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Spec Section | Layer | Components |
|---|---|---|
| §4 ACL | Domain (value object) | `UserReference` |
| §5.1 | Domain (value object) | `AccountName` |
| §5.2 | Domain (value object) | `IBAN` |
| §6 | Domain (aggregate) | `Account` |
| §7 | Domain (events) | `AccountCreated`, `AccountUpdated`, `AccountSoftDeleted`, `AccountRecovered` |
| §8 | Domain (exceptions) | 7 exception classes |
| §9 | Application (commands) | 7 command dataclasses |
| §11.1 | Application (port) | `AccountRepository` protocol |
| §11.2 | Application (port) | `AbstractCoreFinanceUnitOfWork` |
| §10 | Application (service) | `AccountManagementService` |

### 2.2 Directory Structure

```
src/emerald/core_finance/
├── domain/
│   ├── events/
│   │   ├── __init__.py
│   │   └── account_events.py
│   ├── exceptions/
│   │   ├── __init__.py
│   │   └── account_exceptions.py
│   ├── models/
│   │   ├── aggregates/
│   │   │   ├── __init__.py
│   │   │   └── account.py
│   │   └── value_objects/
│   │       ├── __init__.py
│   │       ├── user_reference.py
│   │       ├── account_name.py
│   │       └── iban.py
│   └── __init__.py           (re-exports domain models)
├── application/
│   ├── dtos/
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   └── account_commands.py
│   │   └── __init__.py
│   ├── ports/
│   │   └── outbound/
│   │       ├── __init__.py
│   │       ├── account_repository.py
│   │       └── unit_of_work.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── account_management.py
│   └── __init__.py
└── __init__.py               (public API re-exports)
```

### 2.3 Test Structure

```
tests/unit/core_finance/
├── fakes.py
├── domain/
│   ├── aggregates/
│   │   ├── test_account_create.py
│   │   ├── test_account_update.py
│   │   ├── test_account_lifecycle.py
│   │   └── test_account_balance.py
│   ├── events/
│   │   └── test_account_events.py
│   ├── exceptions/
│   │   └── test_account_exceptions.py
│   └── value_objects/
│       ├── test_user_reference.py
│       ├── test_account_name.py
│       └── test_iban.py
└── application/
    ├── dtos/
    │   └── commands/
    │       └── test_account_commands.py
    └── services/
        ├── test_account_create.py
        ├── test_account_rename.py
        ├── test_account_update.py
        ├── test_account_soft_delete.py
        └── test_account_recover.py
```

### 2.4 Ports and Adapters

| Port (Protocol) | Purpose | Test Fake |
|---|---|---|
| `AccountRepository` | Account persistence & uniqueness queries | `FakeAccountRepository` |
| `AbstractCoreFinanceUnitOfWork` | Transaction boundary with `accounts` repo | `FakeCoreFinanceUnitOfWork` |
| `RetentionPolicyService` (from shared kernel) | Calculate retention for soft delete | Already has `FakeRetentionPolicyRepository` |

---

## 3. Technical Decisions

### 3.1 Mixin Composition Order

**Decision:** `class Account(SoftDeletableMixin, AuditableMixin, AggregateRoot)`

**Rationale:** Follows the established pattern from `User` aggregate. MRO order: SoftDeletable → Auditable → AggregateRoot → TimestampedMixin → Entity. All use cooperative `super().__init__(**kwargs)`.

### 3.2 Immutable Fields

**Decision:** `currency`, `opening_balance`, and `iban` have no update methods — immutability is enforced at the API level (no setter).

**Rationale:** Per spec §6.3, changing currency would invalidate all transactions, opening_balance preserves historical accuracy, and bank account numbers don't change. No runtime checks needed — it's a type-level guarantee.

### 3.3 AccountName Case-Insensitive Equality

**Decision:** Override `__eq__` and `__hash__` on frozen dataclass to use `normalized()` (lowercase).

**Rationale:** Per spec §5.1, `"My Account" == "my account"` for uniqueness. Use `object.__setattr__` in `__post_init__` to store trimmed value, then custom `__eq__`/`__hash__` based on `normalized()`.

### 3.4 IBAN Validation

**Decision:** Full MOD-97 checksum validation per ISO 13616 in `__post_init__`.

**Rationale:** Per spec §5.2, IBANs must be validated at construction. The algorithm: strip whitespace, uppercase, validate length/format, then move first 4 chars to end, convert letters to digits (A=10..Z=35), check `mod 97 == 1`.

### 3.5 UserReference ACL

**Decision:** `UserReference` is a pure domain value object with a `from_identity(AuthenticatedIdentity)` class method.

**Rationale:** The `from_identity()` method imports `AuthenticatedIdentity` — but this is acceptable because `UserReference` itself is used at the application layer boundary. The domain aggregate accepts `UserReference` directly, never `AuthenticatedIdentity`. **However**, to keep the domain layer truly free of IAM imports, the `from_identity()` classmethod will accept parameters by name (user_id and display_name) and the application service will call `UserReference(user_id=cmd.owner_user_id, display_name=cmd.owner_display_name)`. The `from_identity()` classmethod is a convenience that lives in the value object but only imported at the application layer.

### 3.6 Authorization Model

**Decision:** Simple `account.created_by == requesting_user_id` check in the application service.

**Rationale:** Per spec §10.3, this is a temporary model until Spec 008 introduces share-based authorization. No need for a separate authorization service yet.

---

## 4. Implementation Tasks

### Phase 1: Domain Layer — Exceptions

#### TASK-001: Create Core Finance exception classes

**Layer:** Domain
**Depends On:** None

**Description:**
Create all 7 exception classes extending the shared kernel hierarchy. Each has a unique error code.

**Files to Create:**
- `src/emerald/core_finance/domain/exceptions/__init__.py`
- `src/emerald/core_finance/domain/exceptions/account_exceptions.py`

**Exception Classes:**

| Exception | Extends | Code |
|---|---|---|
| `InvalidAccountNameError` | `InvalidValueError` | `INVALID_ACCOUNT_NAME` |
| `InvalidIBANError` | `InvalidValueError` | `INVALID_IBAN` |
| `InvalidAccountNotesError` | `InvalidValueError` | `INVALID_ACCOUNT_NOTES` |
| `InvalidUserReferenceError` | `InvalidValueError` | `INVALID_USER_REFERENCE` |
| `AccountNameAlreadyExistsError` | `AlreadyExistsError` | `ACCOUNT_NAME_ALREADY_EXISTS` |
| `AccountNotFoundError` | `NotFoundError` | `ACCOUNT_NOT_FOUND` |
| `NotAccountOwnerError` | `AuthorizationError` | `NOT_ACCOUNT_OWNER` |

**Tests to Create:**
- `tests/unit/core_finance/domain/exceptions/test_account_exceptions.py`

**Acceptance Criteria:**
- [ ] All 7 exceptions defined with correct hierarchy and codes
- [ ] Each exception can be instantiated with a message
- [ ] Each has correct default `code` attribute

---

### Phase 2: Domain Layer — Value Objects

#### TASK-002: Implement UserReference value object (ACL)

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Create the Anti-Corruption Layer value object. `@dataclass(frozen=True)` with `user_id: UUID` and `display_name: str`. Validation: user_id not None, display_name not blank after strip. Class method `from_identity()` translates from `AuthenticatedIdentity`.

**Files to Create:**
- `src/emerald/core_finance/domain/models/value_objects/__init__.py`
- `src/emerald/core_finance/domain/models/value_objects/user_reference.py`

**Key Implementation Details:**
- `from_identity(identity)` classmethod: extracts `user_id` and `display_name` only (discards email, system_role)
- Raises `InvalidUserReferenceError` on validation failure
- `from_identity()` imports `AuthenticatedIdentity` inside the method body or uses `TYPE_CHECKING` to avoid making the domain depend on IAM at runtime

**Tests to Create:**
- `tests/unit/core_finance/domain/value_objects/test_user_reference.py`

**Acceptance Criteria:**
- [ ] Valid construction with UUID and non-blank display_name
- [ ] Rejects `None` user_id → `InvalidUserReferenceError`
- [ ] Rejects blank/whitespace-only display_name → `InvalidUserReferenceError`
- [ ] `from_identity()` correctly translates, discarding email and system_role
- [ ] No IAM domain types imported at module level

---

#### TASK-003: Implement AccountName value object

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
`@dataclass(frozen=True)` with case-insensitive equality. Stores trimmed original-case value. `normalized()` returns lowercase for uniqueness comparisons.

**Files to Create/Modify:**
- `src/emerald/core_finance/domain/models/value_objects/account_name.py`

**Key Implementation Details:**
- `__post_init__`: strip whitespace, validate non-empty, validate <= 100 chars, store trimmed value via `object.__setattr__`
- Override `__eq__` and `__hash__` using `self.normalized()` (since `eq=False` on dataclass)
- `normalized() -> str`: returns `self.value.strip().lower()`
- Use `@dataclass(frozen=True, eq=False)` to allow custom equality

**Tests to Create:**
- `tests/unit/core_finance/domain/value_objects/test_account_name.py`

**Acceptance Criteria:**
- [ ] Rejects empty string → `InvalidAccountNameError`
- [ ] Rejects whitespace-only → `InvalidAccountNameError`
- [ ] Rejects > 100 chars → `InvalidAccountNameError`
- [ ] Stores trimmed value (original case)
- [ ] `"My Account" == "my account"` (case-insensitive equality)
- [ ] Same hash for different-case names
- [ ] `normalized()` returns lowercase trimmed

---

#### TASK-004: Implement IBAN value object

**Layer:** Domain
**Depends On:** TASK-001

**Description:**
`@dataclass(frozen=True)` with MOD-97 validation per ISO 13616. Normalizes input (uppercase, strip spaces). Provides `masked()` and `last_four`.

**Files to Create/Modify:**
- `src/emerald/core_finance/domain/models/value_objects/iban.py`

**Key Implementation Details:**
- `__post_init__`: strip whitespace, uppercase, validate length (15-34), validate country code (2 letters), check digits (2 digits), remaining alphanumeric, MOD-97 checksum
- MOD-97: move first 4 chars to end, convert letters to digits (A=10..Z=35), compute `int(digit_string) % 97 == 1`
- `last_four`: derived from last 4 chars of normalized value
- `masked() -> str`: returns `"****" + self.last_four`
- Store normalized value and derived `last_four` via `object.__setattr__`

**Tests to Create:**
- `tests/unit/core_finance/domain/value_objects/test_iban.py`

**Acceptance Criteria:**
- [ ] Valid IBANs pass: `GB29 NWBK 6016 1331 9268 19`, `DE89 3704 0044 0532 0130 00`
- [ ] Normalizes: strips spaces, uppercases
- [ ] Rejects < 15 chars → `InvalidIBANError`
- [ ] Rejects > 34 chars → `InvalidIBANError`
- [ ] Rejects invalid country code format → `InvalidIBANError`
- [ ] Rejects bad MOD-97 checksum → `InvalidIBANError`
- [ ] `last_four` correctly derived
- [ ] `masked()` returns `"****XXXX"` format

---

### Phase 3: Domain Layer — Events

#### TASK-005: Create Account domain events

**Layer:** Domain
**Depends On:** None

**Description:**
Create 4 domain events as `@dataclass(frozen=True)` extending `DomainEvent` with `aggregate_type = "account"`.

**Files to Create:**
- `src/emerald/core_finance/domain/events/__init__.py`
- `src/emerald/core_finance/domain/events/account_events.py`

**Events:**

| Event | Fields |
|---|---|
| `AccountCreated` | `owner_user_id: UUID`, `currency_code: str`, `account_name: str`, `opening_balance: Decimal` |
| `AccountUpdated` | `updated_by: UUID`, `changed_fields: frozenset[str]` |
| `AccountSoftDeleted` | `deleted_by: UUID`, `reason: str \| None` |
| `AccountRecovered` | `recovered_by: UUID` |

**Tests to Create:**
- `tests/unit/core_finance/domain/events/test_account_events.py`

**Acceptance Criteria:**
- [ ] All 4 events defined with correct fields
- [ ] All have `aggregate_type = "account"` ClassVar
- [ ] All are frozen dataclasses extending `DomainEvent`
- [ ] Events can be instantiated with correct data types

---

### Phase 4: Domain Layer — Account Aggregate

#### TASK-006: Implement Account aggregate root

**Layer:** Domain
**Depends On:** TASK-001, TASK-002, TASK-003, TASK-004, TASK-005

**Description:**
Create the Account aggregate root composing `SoftDeletableMixin`, `AuditableMixin`, and `AggregateRoot`. Includes factory method, update methods, balance stub, and lifecycle methods.

**Files to Create:**
- `src/emerald/core_finance/domain/models/aggregates/__init__.py`
- `src/emerald/core_finance/domain/models/aggregates/account.py`
- `src/emerald/core_finance/domain/models/__init__.py`
- `src/emerald/core_finance/domain/__init__.py`

**Key Implementation Details:**

**Class signature:**
```python
class Account(SoftDeletableMixin, AuditableMixin, AggregateRoot):
```

**`__init__` params** (all keyword-only, forwarding `**kwargs: Any`):
- `account_name: AccountName`
- `account_type_id: UUID`
- `financial_institution_id: UUID`
- `currency: Currency`
- `opening_balance: Money`
- `iban: IBAN | None = None`
- `notes: str | None = None`
- Plus `**kwargs: Any` for MRO forwarding

**Factory: `Account.create(owner, account_name, currency, opening_balance, ...)`:**
- Validates `opening_balance.currency == currency` → `CurrencyMismatchError`
- Validates notes length <= 500 → `InvalidAccountNotesError`
- Sets `created_by=owner.user_id`
- Emits `AccountCreated`

**Update methods** (`update_name`, `update_account_type`, `update_financial_institution`, `update_notes`):
- Each calls `_touch()`, `_set_updated_by()`, `_register_event(AccountUpdated(...))`
- `update_notes` validates max 500 chars

**Balance stub:**
- `calculate_balance() -> Money`: returns `opening_balance`
- `transaction_count -> int` (property): returns `0`

**Lifecycle:**
- `soft_delete(deleted_by, retention_period, reason)`: delegates to mixin, emits `AccountSoftDeleted`
- `recover()`: delegates to mixin, emits `AccountRecovered`

**Tests to Create:**
- `tests/unit/core_finance/domain/aggregates/test_account_create.py`
- `tests/unit/core_finance/domain/aggregates/test_account_update.py`
- `tests/unit/core_finance/domain/aggregates/test_account_lifecycle.py`
- `tests/unit/core_finance/domain/aggregates/test_account_balance.py`

**Acceptance Criteria:**
- [ ] Factory creates valid Account with all attributes, `version=1`
- [ ] `created_by` set to `owner.user_id`
- [ ] Currency mismatch raises `CurrencyMismatchError`
- [ ] Notes > 500 chars raises `InvalidAccountNotesError`
- [ ] `AccountCreated` event emitted on create
- [ ] Each update method changes the field, touches timestamp/version, sets updated_by
- [ ] Each update emits `AccountUpdated` with correct `changed_fields`
- [ ] `calculate_balance()` returns `opening_balance`
- [ ] `transaction_count` returns `0`
- [ ] `soft_delete()` delegates to mixin, emits `AccountSoftDeleted`
- [ ] `recover()` delegates to mixin, emits `AccountRecovered`
- [ ] Double soft-delete raises `AlreadyDeletedError`
- [ ] Recover non-deleted raises `NotDeletedError`
- [ ] No update methods for `currency`, `opening_balance`, `iban`

---

### Phase 5: Application Layer — Commands

#### TASK-007: Create Account commands

**Layer:** Application
**Depends On:** None

**Description:**
Create 7 command dataclasses extending `Command`.

**Files to Create:**
- `src/emerald/core_finance/application/dtos/__init__.py`
- `src/emerald/core_finance/application/dtos/commands/__init__.py`
- `src/emerald/core_finance/application/dtos/commands/account_commands.py`

**Commands:** `CreateAccount`, `RenameAccount`, `UpdateAccountType`, `UpdateFinancialInstitution`, `UpdateAccountNotes`, `SoftDeleteAccount`, `RecoverAccount` (all per spec §9)

**Tests to Create:**
- `tests/unit/core_finance/application/dtos/commands/test_account_commands.py`

**Acceptance Criteria:**
- [ ] All 7 commands defined as frozen dataclasses extending `Command`
- [ ] Fields match spec §9 exactly
- [ ] All can be instantiated with correct types

---

### Phase 6: Application Layer — Ports

#### TASK-008: Create AccountRepository protocol and UoW

**Layer:** Application
**Depends On:** TASK-003, TASK-006

**Description:**
Define the `AccountRepository` protocol port and `AbstractCoreFinanceUnitOfWork`.

**Files to Create:**
- `src/emerald/core_finance/application/ports/__init__.py`
- `src/emerald/core_finance/application/ports/outbound/__init__.py`
- `src/emerald/core_finance/application/ports/outbound/account_repository.py`
- `src/emerald/core_finance/application/ports/outbound/unit_of_work.py`
- `src/emerald/core_finance/application/__init__.py`

**AccountRepository methods:**
- `save(account: Account) -> None`
- `find_by_id(account_id: UUID, include_deleted: bool = False) -> Account | None`
- `find_by_owner(user_id: UUID, include_deleted: bool = False) -> list[Account]`
- `exists_by_name_for_user(account_name: AccountName, user_id: UUID) -> bool`

**AbstractCoreFinanceUnitOfWork:**
- Extends `AbstractUnitOfWork`
- Has `accounts: AccountRepository`

**Acceptance Criteria:**
- [ ] `AccountRepository` is a `Protocol` with all 4 methods
- [ ] `AbstractCoreFinanceUnitOfWork` extends `AbstractUnitOfWork`
- [ ] `accounts` attribute typed as `AccountRepository`

---

### Phase 7: Test Fakes

#### TASK-009: Create test fakes for Core Finance

**Layer:** Tests
**Depends On:** TASK-006, TASK-008

**Description:**
Create in-memory test doubles for `AccountRepository` and `AbstractCoreFinanceUnitOfWork`.

**Files to Create:**
- `tests/unit/core_finance/__init__.py`
- `tests/unit/core_finance/fakes.py`

**FakeAccountRepository:**
- `_accounts: dict[UUID, Account]`
- `seen: set[Account]` for event harvesting
- `save()`: stores account in dict, adds to seen
- `find_by_id()`: respects `include_deleted` (checks `is_deleted()`)
- `find_by_owner()`: filters by `created_by`, respects `include_deleted`
- `exists_by_name_for_user()`: case-insensitive via `AccountName.normalized()`, excludes soft-deleted

**FakeCoreFinanceUnitOfWork:**
- `accounts: FakeAccountRepository`
- `committed: bool` tracking flag
- `collect_new_events()`: yields from seen aggregates

**Acceptance Criteria:**
- [ ] `FakeAccountRepository` implements all 4 protocol methods
- [ ] `find_by_id` excludes soft-deleted by default
- [ ] `exists_by_name_for_user` uses case-insensitive comparison
- [ ] `exists_by_name_for_user` always excludes soft-deleted accounts
- [ ] `FakeCoreFinanceUnitOfWork` tracks committed state

---

### Phase 8: Application Layer — Service

#### TASK-010: Implement AccountManagementService

**Layer:** Application
**Depends On:** TASK-006, TASK-007, TASK-008, TASK-009

**Description:**
Implement the application service that orchestrates all account operations per spec §10.

**Files to Create:**
- `src/emerald/core_finance/application/services/__init__.py`
- `src/emerald/core_finance/application/services/account_management.py`

**Constructor:** `__init__(self, uow: AbstractCoreFinanceUnitOfWork, retention_policy_service: RetentionPolicyService)`

**Methods:**
1. `create_account(cmd: CreateAccount) -> Account` — Build VOs, check name uniqueness, create aggregate, save, commit
2. `rename_account(cmd: RenameAccount) -> None` — Load, verify owner, check uniqueness, update, commit
3. `update_account_type(cmd: UpdateAccountType) -> None` — Load, verify owner, update, commit
4. `update_financial_institution(cmd: UpdateFinancialInstitution) -> None` — Load, verify owner, update, commit
5. `update_account_notes(cmd: UpdateAccountNotes) -> None` — Load, verify owner, update, commit
6. `soft_delete_account(cmd: SoftDeleteAccount) -> None` — Load, verify owner, get retention, soft_delete, commit
7. `recover_account(cmd: RecoverAccount) -> None` — Load (include_deleted), verify owner, recover, commit

**Ownership check helper:**
```python
def _verify_ownership(self, account: Account, requesting_user_id: UUID) -> None:
    if account.created_by != requesting_user_id:
        raise NotAccountOwnerError(f"User {requesting_user_id} is not the owner")
```

**Tests to Create:**
- `tests/unit/core_finance/application/services/test_account_create.py`
- `tests/unit/core_finance/application/services/test_account_rename.py`
- `tests/unit/core_finance/application/services/test_account_update.py`
- `tests/unit/core_finance/application/services/test_account_soft_delete.py`
- `tests/unit/core_finance/application/services/test_account_recover.py`

**Acceptance Criteria:**
- [ ] `create_account`: builds VOs, checks uniqueness, creates & persists, commits, returns account
- [ ] `create_account`: raises `AccountNameAlreadyExistsError` on duplicate name
- [ ] `create_account`: raises `CurrencyMismatchError` if balance currency differs
- [ ] `rename_account`: loads, checks ownership, checks uniqueness, updates, commits
- [ ] All update methods verify ownership → `NotAccountOwnerError`
- [ ] All update methods raise `AccountNotFoundError` if not found
- [ ] `soft_delete_account`: gets retention from `RetentionPolicyService`, delegates to aggregate
- [ ] `recover_account`: loads with `include_deleted=True`
- [ ] All methods commit the UoW on success

---

### Phase 9: Public API & Package Structure

#### TASK-011: Wire up `__init__.py` re-exports and package files

**Layer:** All
**Depends On:** TASK-001 through TASK-010

**Description:**
Create all intermediate `__init__.py` files and the top-level `src/emerald/core_finance/__init__.py` with explicit `__all__` re-exports. Ensure all subpackages are importable.

**Files to Create/Modify:**
- `src/emerald/core_finance/__init__.py` — public API with `__all__`
- All intermediate `__init__.py` files (domain/models/, domain/events/, etc.)

**Re-export Categories:**
- Aggregates: `Account`
- Value Objects: `UserReference`, `AccountName`, `IBAN`
- Events: `AccountCreated`, `AccountUpdated`, `AccountSoftDeleted`, `AccountRecovered`
- Exceptions: all 7
- Commands: all 7
- Ports: `AccountRepository`, `AbstractCoreFinanceUnitOfWork`
- Services: `AccountManagementService`

**Acceptance Criteria:**
- [ ] `from emerald.core_finance import Account, AccountName, IBAN` works
- [ ] `from emerald.core_finance import AccountManagementService` works
- [ ] All types listed in `__all__`
- [ ] No circular imports

---

### Phase 10: Quality Assurance

#### TASK-012: Run full test suite and quality checks

**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-011

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
- [ ] All existing tests still pass (1094 from spec-006)
- [ ] All new tests pass
- [ ] `ruff check` clean (no warnings)
- [ ] `ruff format` clean (no changes)
- [ ] `ty check` clean (no errors)
- [ ] No IAM domain types imported in Core Finance domain layer

---

## 5. Task Dependency Graph

```
TASK-001 (exceptions) ──┬──► TASK-002 (UserReference) ──┐
                        ├──► TASK-003 (AccountName)  ────┤
                        └──► TASK-004 (IBAN)         ────┤
                                                         │
TASK-005 (events) ───────────────────────────────────────┤
                                                         ▼
                                                   TASK-006 (Account aggregate)
                                                         │
TASK-007 (commands) ─────────────────────────────────────┤
                                                         ▼
                                                   TASK-008 (ports: repo + UoW)
                                                         │
                                                         ▼
                                                   TASK-009 (test fakes)
                                                         │
                                                         ▼
                                                   TASK-010 (AccountManagementService)
                                                         │
                                                         ▼
                                                   TASK-011 (public API __init__.py)
                                                         │
                                                         ▼
                                                   TASK-012 (quality checks)
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| IAM types leaking into Core Finance domain | Medium | High | Review imports in every domain file; `from_identity()` uses TYPE_CHECKING or deferred import |
| MRO issues with 3-mixin composition | Low | Medium | Follow exact same pattern as User aggregate (SoftDeletable, Auditable, AggregateRoot) |
| IBAN MOD-97 implementation errors | Low | Medium | Test with known valid/invalid IBANs from ISO 13616 examples |
| Case-insensitive AccountName equality breaking frozen dataclass | Low | Low | Use `@dataclass(frozen=True, eq=False)` and implement `__eq__`/`__hash__` manually |
| `ty` strict type checking failures | Medium | Low | Use `**kwargs: Any` pattern, `dict[str, Any]` in test factories |

---

## 7. Estimated Test Count

| Area | Estimated Tests |
|---|---|
| Value Objects (UserReference, AccountName, IBAN) | ~35 |
| Exceptions | ~10 |
| Events | ~8 |
| Account Aggregate (create, update, lifecycle, balance) | ~40 |
| Commands | ~10 |
| Application Service (create, rename, update, delete, recover) | ~50 |
| **Total new tests** | **~153** |
| **Total with existing (1094)** | **~1247** |

---

## 8. Definition of Done

- [ ] All tasks completed (TASK-001 through TASK-012)
- [ ] All acceptance criteria from spec §12 met (AC-01 through AC-10)
- [ ] All edge cases from spec §13 covered by tests
- [ ] All new tests passing
- [ ] All existing 1094 tests still passing
- [ ] `ruff check` clean
- [ ] `ruff format` clean
- [ ] `ty check` clean
- [ ] No IAM domain types in Core Finance domain layer
- [ ] Public API re-exports complete with `__all__`
