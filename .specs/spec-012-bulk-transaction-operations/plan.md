# Spec 012: Bulk Transaction Operations — Implementation Plan

**Spec:** `.specs/spec-012-bulk-transaction-operations/spec.md`
**Version:** 1.0
**Date:** 2026-02-14

---

## 1. Overview

This plan implements bulk transaction operations — create, update, delete, and recover — with partial-success semantics and per-item error reporting. The implementation adds 5 value objects (`BulkResult`, `BulkSuccess`, `BulkFailure`, `TransactionInput`, `BulkUpdateFields`), 4 commands, 4 aggregate bulk events, 3 new exceptions, 2 domain constants, and a `BulkTransactionService` that orchestrates two-phase validation (fail-fast request-level + per-item partial-success).

**Approach:** Inside-out (Domain → Application), split into two phases:
- **Phase 1 (Domain Layer):** Constants, value objects, exceptions, events, domain exports
- **Phase 2 (Application Layer):** Commands, BulkTransactionService, test fakes extension, public API exports

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| Bulk limits | Domain / Constants | `constants.py` (modified) |
| BulkResult, BulkSuccess, BulkFailure | Domain / Value Objects | `bulk_result.py` |
| TransactionInput | Domain / Value Objects | `transaction_input.py` |
| BulkUpdateFields (sentinel) | Domain / Value Objects | `bulk_update_fields.py` |
| Bulk exceptions | Domain / Exceptions | `bulk_exceptions.py` |
| Bulk aggregate events | Domain / Events | `transaction_events.py` (modified) |
| Bulk commands | Application / Commands | `bulk_transaction_commands.py` |
| BulkTransactionService | Application / Services | `bulk_transaction.py` |

### 2.2 Component Diagram

```
BulkTransactionService (Application)
  │
  ├── uses ──► AbstractCoreFinanceUnitOfWork
  │               ├── accounts: AccountRepository
  │               └── transactions: TransactionRepository
  │
  ├── uses ──► RetentionPolicyService
  │
  └── orchestrates ──► Transaction (Entity)
                         ├── create() / soft_delete() / recover()
                         ├── update_description() / update_merchant()
                         └── mark_as_reviewed() / mark_for_review()

Input VOs:
  TransactionInput ──► fed into Transaction.create()
  BulkUpdateFields ──► sentinel-driven field application

Output VO:
  BulkResult ──► contains BulkSuccess[] + BulkFailure[]
```

### 2.3 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate `BulkTransactionService` from `TransactionManagementService` | Keeps single-item and bulk concerns cleanly separated; reuses same UoW/repos/entities |
| Non-generic `BulkResult` | Spec requires a single concrete type returned by all four operations |
| `TransactionInput` as domain VO | Validates string lengths against domain constants in `__post_init__`, decoupled from commands |
| `_UNSET` sentinel in `BulkUpdateFields` | Same pattern as `_SENTINEL` in `Transaction.update_dates()` — distinguishes "don't change" from `None` |
| No new repository methods | Existing `save()`, `save_many()`, `find_by_id()`, `find_by_external_id()`, `find_children()` sufficient |
| Bulk events emitted by service | One aggregate event per bulk operation (e.g., `TransactionsBulkCreated`) with summary counts, separate from per-item entity events |
| `DomainError` catch per item | All domain exceptions extend `DomainError`; catching at that level captures any validation failure |

---

## 3. Implementation Tasks

### Phase 1: Domain Layer

#### TASK-001: Add bulk operation domain constants

**Layer:** Domain
**Depends On:** None

**Description:**
Add bulk operation constants to `core_finance/domain/constants.py`.

**Files:**
- `src/emerald/core_finance/domain/constants.py` — MODIFIED: Add `MAX_BULK_ITEMS = 1000`, `DEFAULT_BULK_BATCH_SIZE = 100`

**Acceptance Criteria:**
- [ ] Both constants defined with values from spec section 10

---

#### TASK-002: Create BulkSuccess and BulkFailure value objects

**Layer:** Domain / Value Objects
**Depends On:** None

**Description:**
Create `BulkSuccess` and `BulkFailure` frozen dataclasses. `BulkSuccess` holds `index: int` and `entity_id: uuid.UUID`. `BulkFailure` holds `index: int`, `entity_id: uuid.UUID | None`, `error_code: str`, and `error_message: str`. Both are simple data carriers with no validation beyond frozen immutability.

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/bulk_result.py` — NEW: `BulkSuccess`, `BulkFailure`, `BulkResult` (all in one file)

**Tests:**
- `tests/unit/core_finance/domain/value_objects/test_bulk_result.py` — NEW: construction, frozen, field access

**Acceptance Criteria:**
- [ ] `BulkSuccess(index=0, entity_id=uuid)` constructs correctly
- [ ] `BulkFailure(index=0, entity_id=None, error_code="CODE", error_message="msg")` constructs correctly
- [ ] Both are frozen dataclasses

---

#### TASK-003: Create BulkResult value object

**Layer:** Domain / Value Objects
**Depends On:** TASK-002

**Description:**
Create `BulkResult` frozen dataclass in the same file as `BulkSuccess`/`BulkFailure`. Fields: `success_count: int`, `failure_count: int`, `total_count: int`, `successes: tuple[BulkSuccess, ...]`, `failures: tuple[BulkFailure, ...]`. Validation in `__post_init__`: non-negative counts, `total_count == success_count + failure_count`, tuple lengths match counts. Convenience properties: `is_complete_success`, `is_complete_failure`, `has_failures`.

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/bulk_result.py` — NEW (same file as TASK-002)

**Tests:**
- `tests/unit/core_finance/domain/value_objects/test_bulk_result.py` — NEW (same file as TASK-002): valid construction, invariant violations (count mismatch, negative counts, tuple length mismatch), convenience properties (complete success, complete failure, mixed, has_failures)

**Acceptance Criteria:**
- [ ] Valid construction with matching counts and tuple lengths
- [ ] `__post_init__` raises `ValueError` for `success_count < 0`
- [ ] `__post_init__` raises `ValueError` for `failure_count < 0`
- [ ] `__post_init__` raises `ValueError` for `total_count != success_count + failure_count`
- [ ] `__post_init__` raises `ValueError` for `len(successes) != success_count`
- [ ] `__post_init__` raises `ValueError` for `len(failures) != failure_count`
- [ ] `is_complete_success` returns `True` when `failure_count == 0`
- [ ] `is_complete_failure` returns `True` when `success_count == 0`
- [ ] `has_failures` returns `True` when `failure_count > 0`
- [ ] Frozen/immutable dataclass

---

#### TASK-004: Create TransactionInput value object

**Layer:** Domain / Value Objects
**Depends On:** TASK-001 (constants for string length limits)

**Description:**
Create `TransactionInput` frozen dataclass. Fields: `transaction_date: date`, `amount: Decimal`, `original_description: str` (required), `value_date: date | None`, `merchant: str | None`, `comments: str | None`, `review_status: ReviewStatus` (default `TO_REVIEW`), `external_id: str | None`, `card_id: uuid.UUID | None`. Validation in `__post_init__`: trims whitespace on all string fields, validates `original_description` is non-empty and within `MAX_ORIGINAL_DESCRIPTION_LENGTH`, validates `merchant` within `MAX_MERCHANT_LENGTH`, validates `comments` within `MAX_COMMENTS_LENGTH`. Raises existing domain exceptions (`EmptyDescriptionError`, `InvalidMerchantError`, `InvalidCommentsError`).

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/transaction_input.py` — NEW

**Tests:**
- `tests/unit/core_finance/domain/value_objects/test_transaction_input.py` — NEW: valid construction, whitespace trimming, empty description error, description too long, merchant too long, comments too long, defaults (review_status=TO_REVIEW, optionals=None)

**Acceptance Criteria:**
- [ ] Valid construction with all required fields
- [ ] String fields trimmed in `__post_init__`
- [ ] Empty/whitespace-only `original_description` raises `EmptyDescriptionError`
- [ ] `original_description` exceeding `MAX_ORIGINAL_DESCRIPTION_LENGTH` raises `EmptyDescriptionError`
- [ ] `merchant` exceeding `MAX_MERCHANT_LENGTH` raises `InvalidMerchantError`
- [ ] `comments` exceeding `MAX_COMMENTS_LENGTH` raises `InvalidCommentsError`
- [ ] `review_status` defaults to `ReviewStatus.TO_REVIEW`
- [ ] Optional fields default to `None`
- [ ] Frozen/immutable dataclass

---

#### TASK-005: Create BulkUpdateFields value object with sentinel

**Layer:** Domain / Value Objects
**Depends On:** TASK-001 (constants), TASK-006 (EmptyBulkUpdateError exception)

**Description:**
Create `BulkUpdateFields` frozen dataclass with module-level `_UNSET` sentinel (same pattern as `_SENTINEL` in `transaction.py`). Fields: `review_status: ReviewStatus | _UnsetType` (default `_UNSET`), `user_description: str | None | _UnsetType` (default `_UNSET`), `merchant: str | None | _UnsetType` (default `_UNSET`). Validation in `__post_init__`: at least one field must be non-`_UNSET` (raises `EmptyBulkUpdateError`), string fields validated against domain constants when set (not `_UNSET` and not `None`). Export the `_UNSET` sentinel and `_UnsetType` for use by the service.

The sentinel should use a dedicated class `_UnsetType` with a singleton `_UNSET = _UnsetType()` instance, so type checkers can distinguish it from other types.

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/bulk_update_fields.py` — NEW

**Tests:**
- `tests/unit/core_finance/domain/value_objects/test_bulk_update_fields.py` — NEW: valid construction with one field, all fields _UNSET raises EmptyBulkUpdateError, string validation (description too long, merchant too long), None clears field (doesn't raise), sentinel identity checks

**Acceptance Criteria:**
- [ ] Construction with at least one non-`_UNSET` field succeeds
- [ ] All fields `_UNSET` raises `EmptyBulkUpdateError`
- [ ] `user_description` exceeding `MAX_USER_DESCRIPTION_LENGTH` raises validation error
- [ ] `merchant` exceeding `MAX_MERCHANT_LENGTH` raises validation error
- [ ] `None` values pass validation (they mean "clear field")
- [ ] `_UNSET` is exported for service use
- [ ] Frozen/immutable dataclass

---

#### TASK-006: Create bulk operation exceptions

**Layer:** Domain / Exceptions
**Depends On:** None

**Description:**
Create 3 new exceptions in a `bulk_exceptions.py` file following the established exception pattern.

**Files:**
- `src/emerald/core_finance/domain/exceptions/bulk_exceptions.py` — NEW

**Exceptions:**

| Exception | Base | Code |
|-----------|------|------|
| `BulkLimitExceededError` | `InvariantViolationError` | `BULK_LIMIT_EXCEEDED` |
| `EmptyBulkRequestError` | `InvariantViolationError` | `EMPTY_BULK_REQUEST` |
| `EmptyBulkUpdateError` | `InvalidValueError` | `EMPTY_BULK_UPDATE` |

**Tests:**
- `tests/unit/core_finance/domain/exceptions/test_bulk_exceptions.py` — NEW: construction, correct base class, error codes

**Acceptance Criteria:**
- [ ] All 3 exceptions defined with correct base classes and codes
- [ ] Each has customizable message with sensible default
- [ ] `BulkLimitExceededError` default message mentions the 1000 limit
- [ ] `EmptyBulkRequestError` default message indicates empty request
- [ ] `EmptyBulkUpdateError` default message indicates no fields set

---

#### TASK-007: Create bulk aggregate domain events

**Layer:** Domain / Events
**Depends On:** None

**Description:**
Add 4 bulk aggregate events to `transaction_events.py`. These are summary events emitted once per bulk operation (in addition to the per-item entity events).

**Files:**
- `src/emerald/core_finance/domain/events/transaction_events.py` — MODIFIED: Add `TransactionsBulkCreated`, `TransactionsBulkUpdated`, `TransactionsBulkDeleted`, `TransactionsBulkRecovered`

**Tests:**
- `tests/unit/core_finance/domain/events/test_bulk_transaction_events.py` — NEW: construction, field defaults, aggregate_type

**Events:**

| Event | Key Fields |
|-------|------------|
| `TransactionsBulkCreated` | `account_id`, `success_count`, `failure_count`, `import_source_type`, `created_by` |
| `TransactionsBulkUpdated` | `account_id`, `success_count`, `failure_count`, `updated_fields: frozenset[str]`, `updated_by` |
| `TransactionsBulkDeleted` | `account_id`, `success_count`, `failure_count`, `deleted_by` |
| `TransactionsBulkRecovered` | `account_id`, `success_count`, `failure_count`, `recovered_by` |

**Acceptance Criteria:**
- [ ] All 4 events are frozen dataclasses extending `DomainEvent`
- [ ] All have `aggregate_type: ClassVar[str] = "transaction"`
- [ ] Fields use UUID defaults `uuid.UUID(int=0)`, int defaults `0`, string defaults `""`, frozenset defaults `frozenset()`
- [ ] `TransactionsBulkUpdated` includes `updated_fields: frozenset[str]`

---

#### TASK-008: Update domain layer exports

**Layer:** Domain
**Depends On:** TASK-002 through TASK-007

**Description:**
Update all `__init__.py` files in the domain layer to export new types.

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/__init__.py` — Add `BulkResult`, `BulkSuccess`, `BulkFailure`, `TransactionInput`, `BulkUpdateFields`
- `src/emerald/core_finance/domain/events/__init__.py` — Add `TransactionsBulkCreated`, `TransactionsBulkUpdated`, `TransactionsBulkDeleted`, `TransactionsBulkRecovered`
- `src/emerald/core_finance/domain/exceptions/__init__.py` — Add `BulkLimitExceededError`, `EmptyBulkRequestError`, `EmptyBulkUpdateError`
- `src/emerald/core_finance/domain/__init__.py` — Add all new domain types

**Acceptance Criteria:**
- [ ] All new types importable from their respective `__init__.py`
- [ ] All new types listed in `__all__` exports
- [ ] Also export `_UNSET` sentinel from value objects `__init__.py` for service use

---

### Phase 2: Application Layer

#### TASK-009: Create bulk transaction commands

**Layer:** Application / Commands
**Depends On:** None (commands use primitive types only)

**Description:**
Create 4 bulk commands in a new `bulk_transaction_commands.py` file. All are `@dataclass(frozen=True)` extending `Command`. Commands use primitive types — conversion to domain types happens in the service. `BulkCreateTransactions` takes `tuple[TransactionInput, ...]` since TransactionInput is a domain VO that performs its own validation.

**Files:**
- `src/emerald/core_finance/application/dtos/commands/bulk_transaction_commands.py` — NEW

**Commands:**

| Command | Key Fields |
|---------|------------|
| `BulkCreateTransactions` | `account_id: UUID`, `requesting_user_id: UUID`, `transactions: tuple[TransactionInput, ...]`, `import_source_type: str`, `source_id: str \| None` |
| `BulkUpdateTransactions` | `account_id: UUID`, `requesting_user_id: UUID`, `transaction_ids: tuple[UUID, ...]`, `updates: BulkUpdateFields` |
| `BulkDeleteTransactions` | `account_id: UUID`, `requesting_user_id: UUID`, `transaction_ids: tuple[UUID, ...]`, `reason: str \| None` |
| `BulkRecoverTransactions` | `account_id: UUID`, `requesting_user_id: UUID`, `transaction_ids: tuple[UUID, ...]` |

**Acceptance Criteria:**
- [ ] All 4 commands are frozen dataclasses extending `Command`
- [ ] `BulkCreateTransactions` accepts `tuple[TransactionInput, ...]` for transactions
- [ ] `BulkUpdateTransactions` accepts `BulkUpdateFields` for updates
- [ ] `BulkDeleteTransactions` includes optional `reason: str | None`
- [ ] Default sentinels follow project conventions (`uuid.UUID(int=0)` for UUIDs, `()` for tuples, `None` for optionals, `""` for strings)

---

#### TASK-010: Create BulkTransactionService

**Layer:** Application / Services
**Depends On:** TASK-001 through TASK-009

**Description:**
Create `BulkTransactionService` with `uow: AbstractCoreFinanceUnitOfWork` and `retention_policy_service: RetentionPolicyService` dependencies. Implements 4 public methods: `bulk_create_transactions()`, `bulk_update_transactions()`, `bulk_delete_transactions()`, `bulk_recover_transactions()`. Each follows the two-phase validation pattern from spec section 7.

**Private helpers** (follow `TransactionManagementService` patterns):
- `_load_account(account_id, include_deleted=False)` — load via UoW, raise `AccountNotFoundError`
- `_verify_permission(account, user_id, level)` — raise `InsufficientPermissionError`
- `_verify_not_deleted(account)` — raise `AccountNotActiveError`
- `_validate_bulk_count(count)` — raise `EmptyBulkRequestError` or `BulkLimitExceededError`
- `_build_result(successes, failures)` — construct `BulkResult` from lists

**Service also has `_events` list and `collect_events()` method** for aggregate bulk events (same pattern as `TransactionManagementService`).

**Files:**
- `src/emerald/core_finance/application/services/bulk_transaction.py` — NEW

**Tests:**
- `tests/unit/core_finance/application/test_bulk_transaction_service.py` — NEW

**Key behaviors per method:**

`bulk_create_transactions()`:
- Phase 1: load account, verify EDITOR, verify not deleted, validate count
- Build `ImportSource` from `cmd.import_source_type` + `cmd.source_id`
- Track seen `external_id` set for within-batch dedup
- Phase 2: for each `TransactionInput` — dedup check, build `Money`, `Transaction.create()`, save, record success; catch `DomainError` → record failure
- Commit, emit `TransactionsBulkCreated`, return `BulkResult`

`bulk_update_transactions()`:
- Phase 1: load account, verify EDITOR, verify not deleted, validate count
- Phase 2: for each `transaction_id` — load, verify not deleted, apply non-`_UNSET` fields via entity methods, save, record success; catch `DomainError` → record failure
- Derive `updated_fields` frozenset from non-`_UNSET` field names in `BulkUpdateFields`
- Commit, emit `TransactionsBulkUpdated`, return `BulkResult`

`bulk_delete_transactions()`:
- Phase 1: load account, verify EDITOR, verify not deleted, validate count
- Get retention via `RetentionPolicyService`
- Phase 2: for each `transaction_id` — load, soft_delete, cascade to children if split parent, save; catch `DomainError` → record failure
- Cascaded children NOT counted in `BulkResult`
- Commit, emit `TransactionsBulkDeleted`, return `BulkResult`

`bulk_recover_transactions()`:
- Phase 1: load account, verify OWNER, verify not deleted, validate count
- Phase 2: for each `transaction_id` — load (include_deleted=True), verify deleted (recover will raise `NotDeletedError`), check split child parent status, cascade children if split parent, save; catch `DomainError` → record failure
- Cascaded children NOT counted in `BulkResult`
- Commit, emit `TransactionsBulkRecovered`, return `BulkResult`

**Acceptance Criteria:**
- [ ] All 4 methods follow two-phase validation
- [ ] Phase 1 failures raise exceptions (fail-fast, entire request rejected)
- [ ] Phase 2 failures recorded as `BulkFailure` entries (partial success)
- [ ] `DomainError` caught per item with `error_code` and `str(e)` as `error_message`
- [ ] External ID dedup: within-batch (later occurrence fails) AND against existing
- [ ] Split parent cascade on delete: children soft-deleted, not in `BulkResult`
- [ ] Split parent cascade on recover: deleted children recovered, not in `BulkResult`
- [ ] Split child recover with deleted parent fails with `ParentDeletedError`
- [ ] UoW committed after all items processed
- [ ] Aggregate bulk event emitted after processing
- [ ] Individual per-item events emitted by entity methods (e.g., `TransactionCreated`, `TransactionSoftDeleted`)
- [ ] `AccountNotFoundError` raised when account missing
- [ ] `AccountNotActiveError` raised when account deleted
- [ ] `InsufficientPermissionError` raised when user lacks permission
- [ ] `EmptyBulkRequestError` raised for 0 items
- [ ] `BulkLimitExceededError` raised for >1000 items
- [ ] EDITOR required for create, update, delete
- [ ] OWNER required for recover

**Tests (comprehensive):**

Request validation tests:
- [ ] Account not found raises `AccountNotFoundError`
- [ ] Deleted account raises `AccountNotActiveError`
- [ ] Insufficient permission raises `InsufficientPermissionError`
- [ ] Empty items list raises `EmptyBulkRequestError`
- [ ] 1001 items raises `BulkLimitExceededError`
- [ ] Exactly 1 item succeeds (lower bound)
- [ ] Exactly 1000 items accepted (upper bound)

Bulk create tests:
- [ ] Successful bulk create returns `BulkResult` with correct counts
- [ ] Each created transaction has correct account_id, amount, currency, import_source
- [ ] Mixed valid/invalid — valid items succeed, invalid items in failures
- [ ] Within-batch external_id dedup — first succeeds, later fails
- [ ] Against-existing external_id dedup — item fails with `DUPLICATE_EXTERNAL_ID`
- [ ] Empty description fails with `EMPTY_DESCRIPTION`
- [ ] All items invalid returns `BulkResult(success_count=0, failure_count=N)`
- [ ] `TransactionsBulkCreated` event emitted with correct counts
- [ ] Individual `TransactionCreated` events on each successful item

Bulk update tests:
- [ ] Successful bulk update with review_status change
- [ ] Successful bulk update with user_description change
- [ ] Successful bulk update with merchant change
- [ ] Mixed: some transactions not found, others succeed
- [ ] Deleted transaction fails with `TRANSACTION_DELETED`
- [ ] `TransactionsBulkUpdated` event with correct `updated_fields`

Bulk delete tests:
- [ ] Successful bulk delete soft-deletes transactions
- [ ] Already-deleted fails with `ALREADY_DELETED`
- [ ] Not-found fails with `TRANSACTION_NOT_FOUND`
- [ ] Split parent cascade — children soft-deleted, not in result
- [ ] `TransactionsBulkDeleted` event emitted

Bulk recover tests:
- [ ] Successful bulk recover restores transactions
- [ ] Requires OWNER permission
- [ ] Non-deleted fails with `NOT_DELETED`
- [ ] Split child with deleted parent fails with `PARENT_DELETED`
- [ ] Split parent cascade — deleted children recovered, not in result
- [ ] `TransactionsBulkRecovered` event emitted

---

#### TASK-011: Update application layer exports

**Layer:** Application
**Depends On:** TASK-009, TASK-010

**Description:**
Update all `__init__.py` files in the application layer and the context root `__init__.py` to export new types.

**Files:**
- `src/emerald/core_finance/application/dtos/commands/__init__.py` — Add 4 bulk commands
- `src/emerald/core_finance/application/services/__init__.py` — Add `BulkTransactionService`
- `src/emerald/core_finance/application/__init__.py` — Add all bulk-related exports
- `src/emerald/core_finance/__init__.py` — Add all bulk-related exports to context public API

**Acceptance Criteria:**
- [ ] All bulk commands importable from commands `__init__.py`
- [ ] `BulkTransactionService` importable from services `__init__.py`
- [ ] All types listed in `__all__` at each level
- [ ] All types importable from `emerald.core_finance`

---

## 4. Task Dependency Graph

```
TASK-001 (constants) ──────┬──► TASK-004 (TransactionInput) ──────┐
                           │                                       │
TASK-002 (BulkSuccess/Fail)┼──► TASK-003 (BulkResult) ───────────►│
                           │                                       │
TASK-006 (exceptions) ─────┼──► TASK-005 (BulkUpdateFields) ─────►├──► TASK-008 (domain exports)
                           │                                       │
TASK-007 (bulk events) ────┘                                       │
                                                                   │
TASK-009 (commands) ───────────────────────────────────────────────►├──► TASK-010 (BulkTransactionService)
                                                                   │
                                                                   └──► TASK-011 (app exports)
```

**Parallelizable groups:**
- TASK-001, TASK-002, TASK-006, TASK-007, TASK-009 can all start in parallel (no dependencies)
- TASK-003 depends on TASK-002
- TASK-004 depends on TASK-001
- TASK-005 depends on TASK-001 + TASK-006
- TASK-008 depends on TASK-002 through TASK-007
- TASK-010 depends on everything in Phase 1 + TASK-009
- TASK-011 depends on TASK-009 + TASK-010

---

## 5. File Inventory

### New Files (10)

| File | Description |
|------|-------------|
| `src/emerald/core_finance/domain/models/value_objects/bulk_result.py` | BulkResult, BulkSuccess, BulkFailure VOs |
| `src/emerald/core_finance/domain/models/value_objects/transaction_input.py` | TransactionInput VO |
| `src/emerald/core_finance/domain/models/value_objects/bulk_update_fields.py` | BulkUpdateFields VO with sentinel |
| `src/emerald/core_finance/domain/exceptions/bulk_exceptions.py` | 3 bulk exceptions |
| `src/emerald/core_finance/application/dtos/commands/bulk_transaction_commands.py` | 4 bulk commands |
| `src/emerald/core_finance/application/services/bulk_transaction.py` | BulkTransactionService |
| `tests/unit/core_finance/domain/value_objects/test_bulk_result.py` | BulkResult/Success/Failure tests |
| `tests/unit/core_finance/domain/value_objects/test_transaction_input.py` | TransactionInput tests |
| `tests/unit/core_finance/domain/value_objects/test_bulk_update_fields.py` | BulkUpdateFields tests |
| `tests/unit/core_finance/domain/exceptions/test_bulk_exceptions.py` | Bulk exception tests |
| `tests/unit/core_finance/domain/events/test_bulk_transaction_events.py` | Bulk event tests |
| `tests/unit/core_finance/application/test_bulk_transaction_service.py` | BulkTransactionService tests |

### Modified Files (8)

| File | Changes |
|------|---------|
| `src/emerald/core_finance/domain/constants.py` | Add 2 bulk constants |
| `src/emerald/core_finance/domain/events/transaction_events.py` | Add 4 bulk aggregate events |
| `src/emerald/core_finance/domain/models/value_objects/__init__.py` | Export BulkResult, BulkSuccess, BulkFailure, TransactionInput, BulkUpdateFields |
| `src/emerald/core_finance/domain/events/__init__.py` | Export 4 bulk events |
| `src/emerald/core_finance/domain/exceptions/__init__.py` | Export 3 bulk exceptions |
| `src/emerald/core_finance/domain/__init__.py` | Export all new domain types |
| `src/emerald/core_finance/application/dtos/commands/__init__.py` | Export 4 bulk commands |
| `src/emerald/core_finance/application/services/__init__.py` | Export BulkTransactionService |
| `src/emerald/core_finance/application/__init__.py` | Export all new app types |
| `src/emerald/core_finance/__init__.py` | Export all new context types |

### No Changes Needed

| File | Reason |
|------|--------|
| `application/ports/outbound/unit_of_work.py` | No new repository protocols needed |
| `application/ports/outbound/transaction_repository.py` | Existing methods sufficient (save, save_many, find_by_id, find_by_external_id, find_children) |
| `domain/models/entities/transaction.py` | No entity modifications — bulk operations use existing entity methods |
| `domain/models/aggregates/account.py` | No aggregate modifications — permission checks use existing `has_permission()` |
| `tests/unit/core_finance/fakes.py` | Existing fakes sufficient — bulk service uses same repos/UoW |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Sentinel type confuses `ty` type checker | Medium | Medium | Use dedicated `_UnsetType` class with singleton, test with `ty check` |
| Per-item error catch too broad | Low | High | Catch `DomainError` specifically (not `Exception`), document which errors are expected per operation |
| BulkResult validation too strict for edge cases | Low | Medium | Test all edge cases: 0/0 counts, all-success, all-failure, mixed |
| Split cascade logic duplication from TransactionManagementService | Medium | Low | Extract helpers if needed; for now, mirror the existing tested patterns exactly |
| External ID dedup race condition within batch | Low | Low | In-memory set tracking within single method call; no concurrency concern at domain level |

---

## 7. Definition of Done

- [ ] All 11 tasks completed
- [ ] All acceptance criteria met
- [ ] All new unit tests passing
- [ ] All existing tests still passing (no regressions)
- [ ] `uv run ruff check .` — clean
- [ ] `uv run ruff format .` — clean
- [ ] `uv run ty check` — clean
- [ ] All new types exported in `__init__.py` at every level
