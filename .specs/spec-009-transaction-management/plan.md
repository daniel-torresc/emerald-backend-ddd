# Transaction Management Implementation Plan

**Spec:** `.specs/spec-009-transaction-management/spec.md`
**Version:** 1.0
**Date:** 2026-02-13

---

## 1. Overview

This plan implements the Transaction entity — the fundamental unit of financial activity in Core Finance. Transaction is a standalone entity (not an aggregate root) with its own repository, supporting manual and import creation, review workflow, soft-delete lifecycle, and service-level balance calculation. The implementation follows the inside-out approach: domain layer first, then application layer, then tests throughout.

**Key architectural decisions:**
- Transaction extends `Entity` (not `AggregateRoot`) with `SoftDeletableMixin` + `AuditableMixin`
- Transaction holds a lightweight `_events` list (same pattern as AggregateRoot but without version tracking)
- Currency validation lives in the application service (not the entity)
- Balance computation is a service concern: `opening_balance + sum_amounts()`
- Account aggregate stubs (`calculate_balance()`, `transaction_count`) are removed

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement Area | Layer | Components |
|------------------|-------|------------|
| Value Objects (ImportSource, enums) | Domain | `ImportSourceType`, `ReviewStatus`, `ImportSource` |
| Transaction Entity | Domain | `Transaction` entity with mixins |
| Domain Events | Domain | 5 transaction events |
| Domain Exceptions | Domain | 7 new exceptions (2 already exist) |
| Domain Constants | Domain | String limits, pagination defaults |
| TransactionRepository Protocol | Application | Port interface |
| UoW Extension | Application | `transactions` attribute on UoW |
| Transaction Commands | Application | 10 command DTOs |
| TransactionManagementService | Application | Service orchestrating all operations |
| Account Aggregate Cleanup | Domain | Remove balance stubs |

### 2.2 Component Diagram

```
TransactionManagementService (Application)
  ├── AbstractCoreFinanceUnitOfWork
  │     ├── AccountRepository (existing)
  │     └── TransactionRepository (NEW)
  ├── RetentionPolicyService (existing)
  │
  └── Orchestrates:
        ├── Account (load + authorization via has_permission)
        ├── Transaction (create, update, review, lifecycle)
        └── Event collection from Transaction._events
```

### 2.3 Transaction Entity Mixin Composition

```
Transaction(SoftDeletableMixin, AuditableMixin, Entity)
  │
  MRO: SoftDeletableMixin → AuditableMixin → Entity
  │
  ├── From Entity: id, __eq__, __hash__
  ├── From AuditableMixin: created_by (immutable), updated_by, _set_updated_by()
  ├── From SoftDeletableMixin: deleted_at, deleted_by, soft_delete(), recover()
  └── Own: _events list, _register_event(), collect_events(), _touch() (timestamps only, no version)
```

**Note:** Transaction needs `TimestampedMixin` for `created_at`/`updated_at`/`_touch()`. Since `AggregateRoot` composes `TimestampedMixin + Entity`, and Transaction uses `Entity` directly, we need to include `TimestampedMixin` in the MRO. The correct composition is:

```python
class Transaction(SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity)
```

This matches how `Account` gets timestamps via `AggregateRoot(TimestampedMixin, Entity)`, but since Transaction is not an aggregate root, we compose `TimestampedMixin` explicitly.

---

## 3. Technical Decisions

### 3.1 Event Collection on Non-Aggregate Entity
**Decision:** Transaction holds its own `_events: list[DomainEvent]` with `_register_event()` and `collect_events()` methods, mirroring the AggregateRoot pattern.
**Rationale:** The spec explicitly calls for this pattern. Transaction events (TransactionCreated, etc.) are registered by entity methods and collected by the service after each operation.
**Alternative:** Service-only event emission — rejected because it couples event semantics to the service rather than the domain.

### 3.2 Sentinel Pattern for Optional Date Updates
**Decision:** `update_dates()` uses a module-level sentinel `_SENTINEL = object()` for `value_date` parameter to distinguish "not provided" from "set to None" (clear).
**Rationale:** `value_date` is an optional field that can be explicitly cleared (set to None). Using `None` as default would make it impossible to distinguish "don't change" from "clear".

### 3.3 TransactionUpdated Event with changed_fields
**Decision:** Update methods register a `TransactionUpdated` event with a `changed_fields: frozenset[str]` indicating which fields changed, matching the existing `AccountUpdated` pattern.
**Rationale:** Consumers can filter on specific field changes without needing separate events per field.

### 3.4 Balance Calculation Location
**Decision:** Balance is computed in `TransactionManagementService.calculate_balance()`, not inside the Account aggregate.
**Rationale:** Transaction is an independent entity with its own repository. The service has access to both the Account (for `opening_balance`) and the TransactionRepository (for `sum_amounts()`).

### 3.5 AccountNotActiveError Reuse
**Decision:** Reuse the existing `AccountNotActiveError` from sharing_exceptions for transaction operations on deleted accounts.
**Rationale:** Same semantic meaning — operation attempted on a soft-deleted account. No need for a new exception.

### 3.6 TransactionDeletedError vs AlreadyDeletedError
**Decision:** Create a dedicated `TransactionDeletedError` (InvariantViolationError) for update attempts on deleted transactions, separate from the generic `AlreadyDeletedError` used by soft_delete.
**Rationale:** Different semantics — `AlreadyDeletedError` means "already soft-deleted, can't delete again" (from mixin). `TransactionDeletedError` means "cannot update a deleted transaction" (checked by service before calling entity methods).

---

## 4. Implementation Tasks

### Phase 1: Domain Layer — Value Objects & Enums

#### TASK-001: Create ImportSourceType enum and ReviewStatus enum
**Layer:** Domain
**Depends On:** None

**Description:**
Create two simple enums for the transaction domain.

**Files to Create:**
- `src/emerald/core_finance/domain/models/value_objects/import_source_type.py` — `ImportSourceType` enum with members: MANUAL, BANK_IMPORT, BULK_IMPORT, API
- `src/emerald/core_finance/domain/models/value_objects/review_status.py` — `ReviewStatus` enum with members: TO_REVIEW, REVIEWED

**Acceptance Criteria:**
- [ ] Both enums use string values matching member names
- [ ] Follow existing enum patterns (like `PermissionLevel`)

**Tests:**
- `tests/unit/core_finance/domain/value_objects/test_import_source_type.py` — member existence, value access
- `tests/unit/core_finance/domain/value_objects/test_review_status.py` — member existence, value access

---

#### TASK-002: Create ImportSource value object
**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Create the `ImportSource` frozen dataclass value object that tracks where a transaction originated.

**File to Create:**
- `src/emerald/core_finance/domain/models/value_objects/import_source.py`

**Attributes:**
- `source_type: ImportSourceType` — required
- `source_id: str | None` — optional, must be non-empty after trim if provided
- `imported_at: datetime` — required, must be timezone-aware

**Validation in `__post_init__`:**
- `imported_at` must have `tzinfo` (raise `InvalidValueError` if naive)
- `source_id`: if not None, trim and validate non-empty (raise `InvalidValueError`)
- Use `object.__setattr__` for frozen dataclass field mutation in `__post_init__`

**Acceptance Criteria:**
- [ ] Frozen dataclass with `__post_init__` validation
- [ ] Timezone-aware `imported_at` enforced
- [ ] `source_id` trimmed and non-empty validated
- [ ] None `source_id` is valid

**Tests:**
- `tests/unit/core_finance/domain/value_objects/test_import_source.py` — valid creation, timezone validation, source_id validation, None source_id

---

#### TASK-003: Add domain constants for transaction string limits
**Layer:** Domain
**Depends On:** None

**Description:**
Extend `src/emerald/core_finance/domain/constants.py` with transaction-specific constants.

**File to Modify:**
- `src/emerald/core_finance/domain/constants.py`

**Constants to Add:**
```python
MAX_ORIGINAL_DESCRIPTION_LENGTH: int = 500
MAX_USER_DESCRIPTION_LENGTH: int = 500
MAX_MERCHANT_LENGTH: int = 200
MAX_COMMENTS_LENGTH: int = 1000
DEFAULT_TRANSACTION_PAGE_SIZE: int = 50
```

**Acceptance Criteria:**
- [ ] Constants added with correct values
- [ ] No tests needed (trivial constants)

---

### Phase 2: Domain Layer — Exceptions & Events

#### TASK-004: Create transaction domain exceptions
**Layer:** Domain
**Depends On:** None

**Description:**
Create new exception classes for transaction operations. Note that `CurrencyMismatchError` and `AccountNotActiveError` already exist.

**File to Create:**
- `src/emerald/core_finance/domain/exceptions/transaction_exceptions.py`

**Exceptions:**

| Exception | Extends | Code | Default Message |
|-----------|---------|------|-----------------|
| `DuplicateExternalIdError` | `ConflictError` | `DUPLICATE_EXTERNAL_ID` | "Duplicate external ID" |
| `TransactionNotFoundError` | `NotFoundError` | `TRANSACTION_NOT_FOUND` | "Transaction not found" |
| `TransactionDeletedError` | `InvariantViolationError` | `TRANSACTION_DELETED` | "Transaction is deleted" |
| `EmptyDescriptionError` | `InvalidValueError` | `EMPTY_DESCRIPTION` | "Description cannot be empty" |
| `InvalidMerchantError` | `InvalidValueError` | `INVALID_MERCHANT` | "Invalid merchant" |
| `InvalidCommentsError` | `InvalidValueError` | `INVALID_COMMENTS` | "Invalid comments" |
| `ParentAccountDeletedError` | `InvariantViolationError` | `PARENT_ACCOUNT_DELETED` | "Parent account is deleted" |

**Pattern:** Follow existing exception pattern from `sharing_exceptions.py` — each has `message` + `code` default params.

**Files to Modify:**
- `src/emerald/core_finance/domain/exceptions/__init__.py` — add imports and exports

**Acceptance Criteria:**
- [ ] 7 new exception classes with unique codes
- [ ] Each follows the `__init__(self, message, code)` default pattern
- [ ] Exported via exceptions `__init__.py`

**Tests:**
- `tests/unit/core_finance/domain/exceptions/test_transaction_exceptions.py` — construction, code values, inheritance

---

#### TASK-005: Create transaction domain events
**Layer:** Domain
**Depends On:** None

**Description:**
Create frozen dataclass events for transaction lifecycle.

**File to Create:**
- `src/emerald/core_finance/domain/events/transaction_events.py`

**Events (all with `aggregate_type: ClassVar[str] = "transaction"`):**

| Event | Fields (beyond aggregate_id) |
|-------|------------------------------|
| `TransactionCreated` | account_id: UUID, amount: Decimal, currency_code: str, import_source_type: str, created_by: UUID |
| `TransactionUpdated` | account_id: UUID, updated_by: UUID, changed_fields: frozenset[str] |
| `TransactionReviewed` | account_id: UUID, reviewed_by: UUID |
| `TransactionSoftDeleted` | account_id: UUID, deleted_by: UUID |
| `TransactionRecovered` | account_id: UUID |

**Pattern:** Follow `account_events.py` — frozen dataclass with default-initialized fields (UUID(int=0), "", Decimal("0"), frozenset()).

**Files to Modify:**
- `src/emerald/core_finance/domain/events/__init__.py` — add imports and exports

**Acceptance Criteria:**
- [ ] 5 frozen dataclass events extending DomainEvent
- [ ] All have `aggregate_type: ClassVar[str] = "transaction"`
- [ ] Default field values for type checker satisfaction
- [ ] Exported via events `__init__.py`

**Tests:**
- `tests/unit/core_finance/domain/events/test_transaction_events.py` — construction, aggregate_type, field access

---

### Phase 3: Domain Layer — Transaction Entity

#### TASK-006: Create Transaction entity
**Layer:** Domain
**Depends On:** TASK-001, TASK-002, TASK-003, TASK-004, TASK-005

**Description:**
Create the Transaction entity — the core domain object for this spec. This is the largest single task.

**File to Create:**
- `src/emerald/core_finance/domain/models/entities/transaction.py`

**Class definition:**
```python
class Transaction(SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity):
```

**Implementation details:**

1. **Constructor (`__init__`):**
   - Accept all fields as keyword-only args with `**kwargs: Any` for MRO
   - Store immutable fields as `_account_id`, `_original_description`, `_import_source`, `_external_id`, `_parent_transaction_id`
   - Store mutable fields as regular attrs: `transaction_date`, `value_date`, `amount`, `user_description`, `merchant`, `comments`, `review_status`, `card_id`
   - Initialize `_events: list[DomainEvent] = []`

2. **Immutable properties:**
   - `account_id`, `original_description`, `import_source`, `external_id`, `parent_transaction_id` — read-only via `@property`

3. **Computed property:**
   - `effective_description` — returns `user_description` if set, else `original_description`

4. **Factory classmethod `create()`:**
   - Validates `original_description` (trim, 1-500 chars)
   - Validates optional `merchant` (1-200 chars if set)
   - Validates optional `comments` (1-1000 chars if set)
   - Sets `review_status = ReviewStatus.TO_REVIEW`
   - Generates UUID, sets timestamps
   - Returns new Transaction

5. **Update methods** (each calls `_set_updated_by(updated_by)` + `_touch()` + registers `TransactionUpdated`):
   - `update_description(user_description: str | None, updated_by: UUID)`
   - `update_merchant(merchant: str | None, updated_by: UUID)`
   - `update_comments(comments: str | None, updated_by: UUID)`
   - `update_dates(updated_by, transaction_date=None, value_date=_SENTINEL)`
   - `update_amount(amount: Money, updated_by: UUID)`

6. **Review methods:**
   - `mark_as_reviewed(reviewed_by: UUID)` — idempotent, emits TransactionReviewed
   - `mark_for_review(updated_by: UUID)` — idempotent

7. **Lifecycle overrides:**
   - `soft_delete(...)` — calls super, emits TransactionSoftDeleted
   - `recover()` — calls super, emits TransactionRecovered

8. **Stub methods:**
   - `is_split_parent() -> bool` — returns False
   - `is_split_child() -> bool` — returns `parent_transaction_id is not None`

9. **Event collection:**
   - `_register_event(event)` and `collect_events()` — same pattern as AggregateRoot

**String validation helper:** Private `_validate_string(value, field_name, max_length, error_class)` for DRY validation.

**Files to Modify:**
- `src/emerald/core_finance/domain/models/entities/__init__.py` — add Transaction export
- `src/emerald/core_finance/domain/models/__init__.py` — add Transaction export

**Acceptance Criteria:**
- [ ] MRO: `SoftDeletableMixin, AuditableMixin, TimestampedMixin, Entity`
- [ ] All 6 immutable fields exposed as read-only properties
- [ ] `effective_description` property works with fallback chain
- [ ] `create()` factory validates strings, sets defaults
- [ ] 5 update methods with proper validation and event emission
- [ ] Review methods are idempotent
- [ ] Soft delete and recover emit events
- [ ] Event collection pattern (register + collect)
- [ ] Sentinel pattern for `value_date` in `update_dates`

**Tests (multiple files):**
- `tests/unit/core_finance/domain/entities/test_transaction_create.py` — factory method, validation, defaults
- `tests/unit/core_finance/domain/entities/test_transaction_update.py` — each update method, validation, events
- `tests/unit/core_finance/domain/entities/test_transaction_review.py` — review workflow, idempotency, events
- `tests/unit/core_finance/domain/entities/test_transaction_lifecycle.py` — soft delete, recover, events
- `tests/unit/core_finance/domain/entities/test_transaction_properties.py` — immutable fields, effective_description, stubs

---

### Phase 4: Domain Layer — Account Aggregate Cleanup

#### TASK-007: Remove Account balance stubs
**Layer:** Domain
**Depends On:** None (can be done in parallel with entity creation)

**Description:**
Remove the `calculate_balance()` method and `transaction_count` property from the Account aggregate, as these are now service-level concerns.

**File to Modify:**
- `src/emerald/core_finance/domain/models/aggregates/account.py` — remove lines 207-219 (the stub section)

**Also update:**
- Any tests that reference `account.calculate_balance()` or `account.transaction_count` — these test files should be removed or adjusted

**Acceptance Criteria:**
- [ ] `calculate_balance()` method removed from Account
- [ ] `transaction_count` property removed from Account
- [ ] Existing Account tests that tested these stubs are removed/updated
- [ ] All remaining Account tests still pass

**Tests:**
- Remove `tests/unit/core_finance/domain/aggregates/test_account_balance.py` (if it only tests stubs)
- Verify no other tests depend on these methods

---

### Phase 5: Application Layer — Ports

#### TASK-008: Create TransactionRepository protocol
**Layer:** Application
**Depends On:** TASK-006

**Description:**
Create the repository protocol interface for Transaction persistence.

**File to Create:**
- `src/emerald/core_finance/application/ports/outbound/transaction_repository.py`

**Protocol methods:**
```python
class TransactionRepository(Protocol):
    def save(self, transaction: Transaction) -> None: ...
    def save_many(self, transactions: list[Transaction]) -> None: ...
    def find_by_id(self, transaction_id: UUID, include_deleted: bool = False) -> Transaction | None: ...
    def find_by_account(self, account_id: UUID, include_deleted: bool = False, page: int = 1, page_size: int = 50) -> PaginatedResult[Transaction]: ...
    def find_by_account_in_range(self, account_id: UUID, date_range: DateRange, include_deleted: bool = False, page: int = 1, page_size: int = 50) -> PaginatedResult[Transaction]: ...
    def find_by_external_id(self, account_id: UUID, external_id: str) -> Transaction | None: ...
    def count_by_account(self, account_id: UUID, include_deleted: bool = False) -> int: ...
    def sum_amounts(self, account_id: UUID, exclude_split_parents: bool = True) -> Money: ...
```

**Files to Modify:**
- `src/emerald/core_finance/application/ports/outbound/__init__.py` — add export
- `src/emerald/core_finance/application/ports/__init__.py` — add export

**Acceptance Criteria:**
- [ ] `typing.Protocol` interface with all 8 methods
- [ ] Uses `PaginatedResult[Transaction]` for paginated queries
- [ ] Uses `DateRange` for range queries
- [ ] `find_by_external_id` includes soft-deleted (for deduplication)
- [ ] `sum_amounts` excludes soft-deleted
- [ ] Exported via ports `__init__.py`

**Tests:**
- No direct tests for Protocol (it's an interface)

---

#### TASK-009: Extend AbstractCoreFinanceUnitOfWork
**Layer:** Application
**Depends On:** TASK-008

**Description:**
Add the `transactions` attribute to the UoW.

**File to Modify:**
- `src/emerald/core_finance/application/ports/outbound/unit_of_work.py` — add `transactions: TransactionRepository` attribute, add import

**Acceptance Criteria:**
- [ ] `transactions: TransactionRepository` added as abstract attribute
- [ ] TODO comment removed
- [ ] Import added for TransactionRepository

---

### Phase 6: Application Layer — Commands

#### TASK-010: Create transaction command DTOs
**Layer:** Application
**Depends On:** None

**Description:**
Create all 10 transaction command dataclasses.

**File to Create:**
- `src/emerald/core_finance/application/dtos/commands/transaction_commands.py`

**Commands (all `@dataclass(frozen=True)` extending `Command`):**

| Command | Key Fields |
|---------|------------|
| `CreateTransaction` | account_id, requesting_user_id, transaction_date, amount, currency_code, original_description, value_date?, merchant?, comments?, import_source_type, source_id?, external_id? |
| `UpdateTransactionDescription` | account_id, requesting_user_id, transaction_id, user_description: str \| None |
| `UpdateTransactionMerchant` | account_id, requesting_user_id, transaction_id, merchant: str \| None |
| `UpdateTransactionComments` | account_id, requesting_user_id, transaction_id, comments: str \| None |
| `UpdateTransactionDates` | account_id, requesting_user_id, transaction_id, transaction_date: date \| None, value_date: date \| None |
| `UpdateTransactionAmount` | account_id, requesting_user_id, transaction_id, amount, currency_code |
| `ReviewTransaction` | account_id, requesting_user_id, transaction_id |
| `UnreviewTransaction` | account_id, requesting_user_id, transaction_id |
| `SoftDeleteTransaction` | account_id, requesting_user_id, transaction_id, reason: str \| None |
| `RecoverTransaction` | account_id, requesting_user_id, transaction_id |

**Pattern:** Follow `account_commands.py` — default-initialized fields with zero-UUIDs, empty strings, Decimal("0").

**Files to Modify:**
- `src/emerald/core_finance/application/dtos/commands/__init__.py` — add imports and exports
- `src/emerald/core_finance/application/dtos/__init__.py` — add imports and exports

**Acceptance Criteria:**
- [ ] 10 frozen dataclass commands extending Command
- [ ] All have default-initialized fields
- [ ] Exported via commands `__init__.py` and dtos `__init__.py`

**Tests:**
- `tests/unit/core_finance/application/dtos/commands/test_transaction_commands.py` — construction of each command

---

### Phase 7: Application Layer — Service

#### TASK-011: Create TransactionManagementService
**Layer:** Application
**Depends On:** TASK-006, TASK-008, TASK-009, TASK-010

**Description:**
Create the application service that orchestrates all transaction operations including authorization, validation, and event management.

**File to Create:**
- `src/emerald/core_finance/application/services/transaction_management.py`

**Constructor:**
```python
def __init__(self, uow: AbstractCoreFinanceUnitOfWork, retention_policy_service: RetentionPolicyService) -> None
```

**Public methods:**

1. **`create_transaction(cmd) -> Transaction`:**
   - Load account, verify EDITOR permission, verify account active
   - Build ImportSource from command fields
   - Build Money from amount + currency_code
   - Validate currency match (amount.currency == account.currency)
   - Check external_id uniqueness via repo
   - Call `Transaction.create()`
   - Save + register TransactionCreated event + commit

2. **`update_description(cmd) -> None`**, **`update_merchant(cmd) -> None`**, **`update_comments(cmd) -> None`**, **`update_dates(cmd) -> None`**, **`update_amount(cmd) -> None`:**
   - Load account + transaction
   - Verify EDITOR permission
   - Verify transaction not deleted
   - For `update_amount`: validate currency match
   - Call entity method
   - Save + commit

3. **`review_transaction(cmd) -> None`**, **`unreview_transaction(cmd) -> None`:**
   - Load account + transaction
   - Verify EDITOR permission
   - Verify transaction not deleted
   - Call entity method
   - Save + commit

4. **`soft_delete_transaction(cmd) -> None`:**
   - Load account, verify EDITOR
   - Load transaction with include_deleted=True
   - Verify transaction.account_id == account.id
   - Get retention period
   - Call transaction.soft_delete()
   - Save + commit

5. **`recover_transaction(cmd) -> None`:**
   - Load account, verify OWNER
   - Verify account active (raise ParentAccountDeletedError)
   - Load transaction with include_deleted=True
   - Call transaction.recover()
   - Save + commit

6. **Query methods:**
   - `get_transaction(account_id, transaction_id, requesting_user_id) -> Transaction`
   - `list_transactions(account_id, requesting_user_id, page, page_size) -> PaginatedResult[Transaction]`
   - `list_transactions_in_range(account_id, requesting_user_id, date_range, page, page_size) -> PaginatedResult[Transaction]`
   - `calculate_balance(account_id, requesting_user_id) -> Money`
   - `get_transaction_count(account_id, requesting_user_id) -> int`
   - All verify VIEWER permission before querying

7. **Private helpers:**
   - `_load_account(account_id) -> Account` — raises AccountNotFoundError
   - `_load_transaction(transaction_id, include_deleted=False) -> Transaction` — raises TransactionNotFoundError
   - `_verify_permission(account, user_id, required: PermissionLevel) -> None` — raises InsufficientPermissionError
   - `_verify_not_deleted(transaction) -> None` — raises TransactionDeletedError

**Files to Modify:**
- `src/emerald/core_finance/application/services/__init__.py` — add export
- `src/emerald/core_finance/application/__init__.py` — add export

**Acceptance Criteria:**
- [ ] All 14 public methods implemented (5 mutation, 2 review, 2 lifecycle, 5 query)
- [ ] Authorization checked for every operation (VIEWER/EDITOR/OWNER)
- [ ] Currency validation on create and update_amount
- [ ] External ID deduplication on create
- [ ] Deleted transaction guard on all updates
- [ ] Active account guard on create and recover
- [ ] Events collected from Transaction entity
- [ ] UoW committed after every mutation
- [ ] TransactionCreated event registered by service for create

---

### Phase 8: Test Infrastructure

#### TASK-012: Create FakeTransactionRepository and update FakeCoreFinanceUnitOfWork
**Layer:** Tests
**Depends On:** TASK-008, TASK-009

**Description:**
Extend the test fakes to support transaction testing.

**File to Modify:**
- `tests/unit/core_finance/fakes.py`

**FakeTransactionRepository:**
- In-memory dict storage keyed by UUID
- `save()`: store + add to `seen` set
- `save_many()`: iterate and save each
- `find_by_id()`: respect `include_deleted` flag
- `find_by_account()`: filter by account_id, paginate, return `PaginatedResult`
- `find_by_account_in_range()`: filter by account_id + date range, paginate
- `find_by_external_id()`: filter by account_id + external_id (includes soft-deleted)
- `count_by_account()`: count matching, respect `include_deleted`
- `sum_amounts()`: sum of non-deleted transaction amounts for account

**FakeCoreFinanceUnitOfWork update:**
- Add `transactions: FakeTransactionRepository` attribute
- Update `collect_new_events()` to also yield events from transactions (via `seen` set)

**Acceptance Criteria:**
- [ ] Full protocol implementation for FakeTransactionRepository
- [ ] Pagination support returning PaginatedResult
- [ ] `find_by_external_id` includes soft-deleted
- [ ] `sum_amounts` excludes soft-deleted
- [ ] FakeCoreFinanceUnitOfWork updated with transactions attribute
- [ ] Event collection includes transaction events

---

### Phase 9: Domain Tests

#### TASK-013: Write Transaction entity unit tests
**Layer:** Tests
**Depends On:** TASK-006, TASK-012

**Description:**
Comprehensive unit tests for the Transaction entity, organized into multiple files.

**Files to Create:**

1. **`tests/unit/core_finance/domain/entities/test_transaction_create.py`** (~30 tests)
   - Valid manual creation (all defaults)
   - Valid creation with all optional fields
   - original_description validation: empty, whitespace, too long, trimming
   - merchant validation: empty string, whitespace, too long, None (valid)
   - comments validation: empty string, whitespace, too long, None (valid)
   - review_status always TO_REVIEW
   - import_source correctly set
   - created_by correctly set
   - Timestamps set on creation
   - UUID generated

2. **`tests/unit/core_finance/domain/entities/test_transaction_update.py`** (~25 tests)
   - update_description: set, clear (None), empty string rejected, whitespace rejected, too long
   - update_merchant: set, clear, empty rejected, whitespace rejected, too long
   - update_comments: set, clear, empty rejected, whitespace rejected, too long
   - update_dates: transaction_date only, value_date only, both, clear value_date, no-change case
   - update_amount: set new amount, updated_by tracked
   - All updates: _touch() called (updated_at changes), _set_updated_by() called
   - All updates: TransactionUpdated event emitted with correct changed_fields

3. **`tests/unit/core_finance/domain/entities/test_transaction_review.py`** (~8 tests)
   - mark_as_reviewed: TO_REVIEW → REVIEWED, emits TransactionReviewed
   - mark_as_reviewed: already REVIEWED → no-op (idempotent), no event
   - mark_for_review: REVIEWED → TO_REVIEW
   - mark_for_review: already TO_REVIEW → no-op, no event
   - updated_by set on review transitions

4. **`tests/unit/core_finance/domain/entities/test_transaction_lifecycle.py`** (~10 tests)
   - soft_delete: sets deleted_at/deleted_by, emits TransactionSoftDeleted
   - soft_delete: already deleted raises AlreadyDeletedError
   - recover: clears deletion fields, emits TransactionRecovered
   - recover: not deleted raises NotDeletedError

5. **`tests/unit/core_finance/domain/entities/test_transaction_properties.py`** (~12 tests)
   - Immutable fields: account_id, original_description, import_source, external_id, parent_transaction_id, created_by — all read-only
   - effective_description: user_description set → returns user_description
   - effective_description: user_description None → returns original_description
   - is_split_parent → False
   - is_split_child → True when parent_transaction_id set, False otherwise

**Acceptance Criteria:**
- [ ] ~85 tests covering all entity behavior
- [ ] All validation paths tested
- [ ] Event emission verified for each operation
- [ ] Idempotency of review methods verified

---

### Phase 10: Application Tests

#### TASK-014: Write TransactionManagementService unit tests
**Layer:** Tests
**Depends On:** TASK-011, TASK-012

**Description:**
Comprehensive unit tests for the application service, organized by operation.

**Files to Create:**

1. **`tests/unit/core_finance/application/services/test_transaction_create.py`** (~20 tests)
   - Successful manual creation (MANUAL import source)
   - Successful import creation (BANK_IMPORT)
   - Currency mismatch rejected
   - Duplicate external_id rejected
   - Duplicate check includes soft-deleted
   - Account not found
   - Account deleted raises AccountNotActiveError
   - VIEWER permission denied
   - EDITOR permission succeeds
   - UoW committed
   - TransactionCreated event emitted
   - Zero-amount transaction allowed
   - No external_id — no dedup check

2. **`tests/unit/core_finance/application/services/test_transaction_update.py`** (~20 tests)
   - update_description: success, VIEWER denied, deleted transaction rejected
   - update_merchant: success, VIEWER denied
   - update_comments: success, VIEWER denied
   - update_dates: success, VIEWER denied
   - update_amount: success, currency mismatch rejected, VIEWER denied
   - All: UoW committed, transaction not found

3. **`tests/unit/core_finance/application/services/test_transaction_review.py`** (~8 tests)
   - review_transaction: success, VIEWER denied, deleted rejected
   - unreview_transaction: success, VIEWER denied, deleted rejected
   - UoW committed

4. **`tests/unit/core_finance/application/services/test_transaction_lifecycle.py`** (~10 tests)
   - soft_delete: success, VIEWER denied, already deleted
   - recover: success, non-OWNER denied, parent account deleted
   - UoW committed

5. **`tests/unit/core_finance/application/services/test_transaction_query.py`** (~12 tests)
   - get_transaction: success, VIEWER ok, not found
   - list_transactions: success, pagination
   - list_transactions_in_range: success
   - calculate_balance: opening_balance + sum_amounts, VIEWER ok
   - get_transaction_count: success

**Acceptance Criteria:**
- [ ] ~70 tests covering all service operations
- [ ] Authorization verified for every operation
- [ ] Currency validation tested
- [ ] Deduplication tested
- [ ] UoW commit verified
- [ ] Error paths all tested

---

### Phase 11: Public API & Module Exports

#### TASK-015: Update all `__init__.py` exports for transaction types
**Layer:** Cross-cutting
**Depends On:** TASK-004, TASK-005, TASK-006, TASK-008, TASK-010, TASK-011

**Description:**
Update all module `__init__.py` files to export new transaction types through the public API chain.

**Files to Modify (bottom-up):**

1. `src/emerald/core_finance/domain/models/value_objects/__init__.py` — add ImportSourceType, ReviewStatus, ImportSource
2. `src/emerald/core_finance/domain/models/entities/__init__.py` — add Transaction
3. `src/emerald/core_finance/domain/models/__init__.py` — add Transaction, ImportSourceType, ReviewStatus, ImportSource
4. `src/emerald/core_finance/domain/events/__init__.py` — add 5 transaction events
5. `src/emerald/core_finance/domain/exceptions/__init__.py` — add 7 transaction exceptions
6. `src/emerald/core_finance/domain/__init__.py` — add Transaction, ImportSourceType, ReviewStatus, ImportSource, 5 events, 7 exceptions
7. `src/emerald/core_finance/application/dtos/commands/__init__.py` — add 10 commands
8. `src/emerald/core_finance/application/dtos/__init__.py` — add 10 commands
9. `src/emerald/core_finance/application/ports/outbound/__init__.py` — add TransactionRepository
10. `src/emerald/core_finance/application/ports/__init__.py` — add TransactionRepository
11. `src/emerald/core_finance/application/services/__init__.py` — add TransactionManagementService
12. `src/emerald/core_finance/application/__init__.py` — add TransactionRepository, TransactionManagementService, 10 commands
13. `src/emerald/core_finance/__init__.py` — add all new public types to `__all__`

**Acceptance Criteria:**
- [ ] All new types importable from `emerald.core_finance`
- [ ] `__all__` updated in every `__init__.py`
- [ ] Clean import chains (no circular imports)

---

### Phase 12: Quality Assurance

#### TASK-016: Run full quality check suite
**Layer:** Cross-cutting
**Depends On:** All previous tasks

**Description:**
Run all quality checks and fix any issues.

**Commands:**
```bash
uv run pytest -v                    # All tests pass
uv run ruff check --fix .          # Lint clean
uv run ruff format .               # Format clean
uv run ty check                    # Type check clean
```

**Acceptance Criteria:**
- [ ] All tests pass (expect ~1600+ total: ~1442 existing + ~155 new)
- [ ] ruff check clean (no warnings)
- [ ] ruff format clean (no changes)
- [ ] ty check clean (no errors)

---

## 5. Task Dependency Graph

```
TASK-001 (enums) ──────────┐
                           ├──► TASK-006 (Transaction entity) ──┐
TASK-002 (ImportSource) ───┘                                    │
                                                                ├──► TASK-008 (TransactionRepository) ──┐
TASK-003 (constants) ──────────► TASK-006                       │                                       │
                                                                │    TASK-009 (UoW extension) ◄──────────┤
TASK-004 (exceptions) ─────────► TASK-006                       │                                       │
                                                                │    TASK-012 (test fakes) ◄─────────────┤
TASK-005 (events) ─────────────► TASK-006                       │           │                            │
                                                                │           ├──► TASK-013 (domain tests) │
TASK-007 (remove stubs) ───────────────── (parallel) ──────────►│           └──► TASK-014 (service tests)│
                                                                │                                       │
TASK-010 (commands) ───────────────────────────────────────────►├──► TASK-011 (service) ────────────────►┤
                                                                │                                       │
                                                                └──► TASK-015 (exports) ────────────────►┤
                                                                                                        │
                                                                                    TASK-016 (QA) ◄─────┘
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MRO issues with TimestampedMixin + AuditableMixin + Entity | Medium | High | Test mixin composition early; use `**kwargs: Any` pattern |
| Circular imports between transaction and account | Low | Medium | Transaction doesn't import Account; service imports both |
| `ty` type checker strictness on event collection | Medium | Medium | Follow AggregateRoot's exact pattern; test early |
| Sentinel pattern for `update_dates` confusing `ty` | Low | Low | Use explicit `_SENTINEL = object()` at module level |
| FakeTransactionRepository pagination logic errors | Medium | Low | Test pagination edge cases (empty, single page, multi-page) |

---

## 7. Definition of Done

- [ ] All 16 tasks completed
- [ ] ~155+ new tests written and passing
- [ ] All 1442+ existing tests still passing
- [ ] Transaction entity fully functional with all invariants
- [ ] TransactionManagementService orchestrates all operations
- [ ] Balance calculation works at service level
- [ ] Account stubs removed
- [ ] Authorization enforced at all levels
- [ ] All `__init__.py` exports updated
- [ ] `ruff check` clean
- [ ] `ruff format` clean
- [ ] `ty check` clean
