# Transaction Splitting — Implementation Plan

**Spec:** `.specs/spec-010-transaction-splitting/spec.md`
**Version:** 1.0
**Date:** 2025-02-13

---

## 1. Overview

Implement transaction splitting — the ability to divide a single transaction into 2–50 child transactions whose amounts sum exactly to the parent. The parent becomes excluded from balance calculations; only children contribute. Splitting is reversible via a join operation that hard-deletes children. Lifecycle operations (soft-delete, recover) cascade between parent and children.

**Approach:** Extend the existing Transaction entity with a `_is_split_parent` flag and `split()`/`join_splits()` domain methods. Add a `SplitRequest` value object. Extend `TransactionManagementService` with `split_transaction()`, `join_transaction_splits()`, and split-aware overrides for `update_amount()`, `soft_delete_transaction()`, and `recover_transaction()`. Extend `TransactionRepository` protocol with `find_children()` and `hard_delete_children()`.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| SplitRequest value object | Domain | `SplitRequest` frozen dataclass |
| Split/join domain logic | Domain | `Transaction.split()`, `Transaction.join_splits()` |
| `_is_split_parent` flag | Domain | Transaction entity extension |
| Domain events | Domain | `TransactionSplit`, `TransactionSplitsJoined` |
| Split exceptions (7) | Domain | New exception classes |
| Domain constants | Domain | `MAX_SPLITS_PER_TRANSACTION`, `MIN_SPLITS_PER_TRANSACTION` |
| Commands | Application | `SplitTransaction`, `JoinTransactionSplits` |
| Service orchestration | Application | `TransactionManagementService` extensions |
| Repository extensions | Application | `TransactionRepository` protocol additions |
| Balance exclusion | Application (fake) | `FakeTransactionRepository.sum_amounts()` fix |

### 2.2 Component Diagram

```
SplitRequest (VO)
    │
    ▼
Transaction Entity ──── TransactionSplit / TransactionSplitsJoined (events)
    │                    MinimumSplitsRequiredError
    │                    MaxSplitsExceededError
    │                    SplitAmountMismatchError
    │                    CannotSplitChildError
    │                    AlreadySplitError
    │                    NotSplitParentError
    │                    ParentDeletedError
    │
    ▼
TransactionManagementService ──── SplitTransaction (cmd)
    │                              JoinTransactionSplits (cmd)
    │
    ▼
TransactionRepository (protocol) ──── find_children()
                                       hard_delete_children()
```

### 2.3 Ports and Adapters

| Port | Purpose | Test Adapter |
|------|---------|--------------|
| `TransactionRepository.find_children()` | Load child transactions for a parent | `FakeTransactionRepository.find_children()` |
| `TransactionRepository.hard_delete_children()` | Permanently delete all children | `FakeTransactionRepository.hard_delete_children()` |

---

## 3. Technical Decisions

### 3.1 `_is_split_parent` as Constructor Parameter
**Decision:** Add `_is_split_parent` as a constructor parameter (default `False`), set internally by `split()` and `join_splits()`. Hydrated by repository during load.
**Rationale:** Consistent with spec — the flag is determined by the repository based on existence of active children, not by maintaining a child collection in memory.

### 3.2 No Child Collection on Transaction
**Decision:** Transaction does NOT hold a `_children` list. Children are loaded via `TransactionRepository.find_children()` by the service.
**Rationale:** Unlike Account→AccountShare (aggregate manages children), Transaction→children is a cross-entity relationship managed by the service layer. Keeping the Transaction entity lightweight avoids loading children for every transaction load.

### 3.3 `split()` Creates Child Transactions
**Decision:** `Transaction.split()` is a domain method that creates and returns child Transaction instances. The service persists them.
**Rationale:** Creation logic (field inheritance, validation) is domain knowledge. The entity creates children using `Transaction.create()`, service handles persistence.

### 3.4 Auto-Join is Service-Level
**Decision:** Auto-join on parent amount update is handled by the service, not the entity.
**Rationale:** Auto-join requires loading children from repository (infrastructure concern) and hard-deleting them — both outside entity scope. The entity's `update_amount()` remains unchanged.

### 3.5 Split Child Amount Validation is Service-Level
**Decision:** Sum re-validation when updating a child's amount is done by the service.
**Rationale:** Requires loading siblings from repository to compute the new sum — outside entity scope.

---

## 4. Implementation Tasks

### Phase 1: Domain Layer

#### TASK-001: Add split domain constants
**Layer:** Domain
**Depends On:** None

**Description:**
Add `MAX_SPLITS_PER_TRANSACTION = 50` and `MIN_SPLITS_PER_TRANSACTION = 2` to `core_finance/domain/constants.py`.

**Files:**
- `src/emerald/core_finance/domain/constants.py` — add 2 constants

**Acceptance Criteria:**
- [ ] Constants defined with correct values
- [ ] Existing constants unchanged

**Tests:**
- [ ] No dedicated tests (constants are tested transitively via entity tests)

---

#### TASK-002: Add SplitRequest value object
**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Create `SplitRequest` as a `@dataclass(frozen=True)` value object. Validates:
- `amount`: `Money`, required
- `description`: `str`, required, 1–500 chars, trimmed
- `merchant`: `str | None`, optional, max 200 chars, trimmed
- `comments`: `str | None`, optional, max 1000 chars, trimmed

Uses `MAX_ORIGINAL_DESCRIPTION_LENGTH`, `MAX_MERCHANT_LENGTH`, `MAX_COMMENTS_LENGTH` from domain constants. Raises `EmptyDescriptionError`, `InvalidMerchantError`, `InvalidCommentsError` for invalid inputs.

**Files:**
- `src/emerald/core_finance/domain/models/value_objects/split_request.py` — new file
- `src/emerald/core_finance/domain/models/value_objects/__init__.py` — add export

**Acceptance Criteria:**
- [ ] Frozen dataclass with `__post_init__` validation
- [ ] Trims whitespace on all string fields
- [ ] Validates description non-empty and within max length
- [ ] Validates merchant and comments within max length when provided
- [ ] Re-uses existing exception types for validation errors

**Tests:**
- [ ] `tests/unit/core_finance/domain/value_objects/test_split_request.py`
- [ ] Valid creation with all fields
- [ ] Valid creation with optional fields as None
- [ ] Empty description raises EmptyDescriptionError
- [ ] Whitespace-only description raises EmptyDescriptionError
- [ ] Description exceeding 500 chars raises EmptyDescriptionError
- [ ] Merchant exceeding 200 chars raises InvalidMerchantError
- [ ] Comments exceeding 1000 chars raises InvalidCommentsError
- [ ] String fields are trimmed
- [ ] Frozen (immutable)

---

#### TASK-003: Add split domain exceptions
**Layer:** Domain
**Depends On:** None

**Description:**
Add 7 new exception classes to `transaction_exceptions.py`:
- `MinimumSplitsRequiredError(InvariantViolationError)` — code: `MINIMUM_SPLITS_REQUIRED`
- `MaxSplitsExceededError(InvariantViolationError)` — code: `MAX_SPLITS_EXCEEDED`
- `SplitAmountMismatchError(InvariantViolationError)` — code: `SPLIT_AMOUNT_MISMATCH`
- `CannotSplitChildError(InvariantViolationError)` — code: `CANNOT_SPLIT_CHILD`
- `AlreadySplitError(InvariantViolationError)` — code: `ALREADY_SPLIT`
- `NotSplitParentError(InvariantViolationError)` — code: `NOT_SPLIT_PARENT`
- `ParentDeletedError(InvariantViolationError)` — code: `PARENT_DELETED`

`SplitAmountMismatchError` includes `expected` and `actual` Money in its message.

**Files:**
- `src/emerald/core_finance/domain/exceptions/transaction_exceptions.py` — add 7 exception classes
- `src/emerald/core_finance/domain/exceptions/__init__.py` — add exports

**Acceptance Criteria:**
- [ ] Each exception has unique code string
- [ ] All extend `InvariantViolationError`
- [ ] `SplitAmountMismatchError` includes expected/actual in message
- [ ] Follow existing exception pattern (message + code constructor)

**Tests:**
- [ ] `tests/unit/core_finance/domain/exceptions/test_transaction_exceptions.py` — extend existing test file
- [ ] Each exception instantiable with default message
- [ ] Each exception has correct code
- [ ] `SplitAmountMismatchError` formats expected/actual amounts

---

#### TASK-004: Add split domain events
**Layer:** Domain
**Depends On:** None

**Description:**
Add 2 new event classes to `transaction_events.py`:
- `TransactionSplit(DomainEvent)` — `parent_transaction_id`, `account_id`, `child_count`, `child_ids: tuple[UUID, ...]`
- `TransactionSplitsJoined(DomainEvent)` — `parent_transaction_id`, `account_id`, `removed_child_count`

Both use `aggregate_type: ClassVar[str] = "transaction"`.

**Files:**
- `src/emerald/core_finance/domain/events/transaction_events.py` — add 2 event classes
- `src/emerald/core_finance/domain/events/__init__.py` — add exports

**Acceptance Criteria:**
- [ ] Frozen dataclasses extending DomainEvent
- [ ] All fields have defaults (UUID(int=0), 0, empty tuple)
- [ ] `child_ids` is `tuple[uuid.UUID, ...]` (immutable)
- [ ] `aggregate_type` ClassVar is "transaction"

**Tests:**
- [ ] `tests/unit/core_finance/domain/events/test_transaction_events.py` — extend existing test file
- [ ] Both events instantiable with all fields
- [ ] Both events are frozen
- [ ] Default values work

---

#### TASK-005: Extend Transaction entity with split logic
**Layer:** Domain
**Depends On:** TASK-001, TASK-002, TASK-003, TASK-004

**Description:**
Modify the Transaction entity:

1. **Constructor:** Add `is_split_parent: bool = False` parameter. Store as `self._is_split_parent`.

2. **Replace `is_split_parent()` stub** with a property:
   ```python
   @property
   def is_split_parent(self) -> bool:
       return self._is_split_parent
   ```

3. **Add `split()` method:**
   ```python
   def split(self, splits: list[SplitRequest], split_by: uuid.UUID) -> list[Transaction]:
   ```
   Validates (in order):
   - Not deleted → `TransactionDeletedError`
   - Not a split child → `CannotSplitChildError`
   - Not already split → `AlreadySplitError`
   - len(splits) >= MIN_SPLITS → `MinimumSplitsRequiredError`
   - len(splits) <= MAX_SPLITS → `MaxSplitsExceededError`
   - All split amounts same currency as self → `CurrencyMismatchError`
   - Sum of split amounts == self.amount → `SplitAmountMismatchError`

   Creates child transactions via `Transaction.create()` inheriting:
   - `account_id`, `transaction_date`, `value_date`, `import_source`, `card_id`
   - `parent_transaction_id = self.id`
   - `external_id = None`
   - Child `original_description` from split.description
   - Child `merchant`, `comments` from split
   - `created_by = split_by`

   Sets `self._is_split_parent = True`, touches, registers `TransactionSplit` event.
   Returns list of created children.

   **Important:** Children must be created with `review_status=REVIEWED`. Since `Transaction.create()` defaults to `TO_REVIEW`, we need to set `review_status` on each child after creation OR pass it to the constructor. The cleanest approach: create via constructor kwargs rather than `create()` factory, OR call `mark_as_reviewed()` immediately after creation. Per spec, use the `create()` factory and then set `review_status = ReviewStatus.REVIEWED` directly (since the entity is just being constructed, not loaded from DB).

4. **Add `join_splits()` method:**
   ```python
   def join_splits(self, child_count: int) -> None:
   ```
   Validates:
   - Not deleted → `TransactionDeletedError`
   - Is split parent → `NotSplitParentError`

   Sets `self._is_split_parent = False`, touches, registers `TransactionSplitsJoined` event.

**Files:**
- `src/emerald/core_finance/domain/models/entities/transaction.py` — modify entity

**Acceptance Criteria:**
- [ ] `_is_split_parent` field added with default False
- [ ] `is_split_parent` is now a property (not a method) returning `_is_split_parent`
- [ ] `split()` validates all 7 conditions in order
- [ ] `split()` creates correct child transactions with inherited fields
- [ ] `split()` sets `_is_split_parent = True`
- [ ] `split()` emits `TransactionSplit` event with correct data
- [ ] `join_splits()` validates deleted and split parent status
- [ ] `join_splits()` sets `_is_split_parent = False`
- [ ] `join_splits()` emits `TransactionSplitsJoined` event
- [ ] `Transaction.create()` always sets `_is_split_parent = False`
- [ ] Children have `review_status = REVIEWED`
- [ ] Children have `external_id = None`

**Tests:**
- [ ] `tests/unit/core_finance/domain/entities/test_transaction_split.py` — new file

Split operation tests:
- [ ] Successful split with 2 children
- [ ] Successful split with MAX (50) children
- [ ] Children inherit parent account_id, transaction_date, value_date, import_source, card_id
- [ ] Children have parent_transaction_id set
- [ ] Children have external_id = None
- [ ] Children have review_status = REVIEWED
- [ ] Children have correct amounts, descriptions, merchants, comments
- [ ] Parent _is_split_parent set to True after split
- [ ] TransactionSplit event emitted with correct child_ids and child_count
- [ ] Raises TransactionDeletedError when deleted
- [ ] Raises CannotSplitChildError when is_split_child
- [ ] Raises AlreadySplitError when already split
- [ ] Raises MinimumSplitsRequiredError for 0 or 1 splits
- [ ] Raises MaxSplitsExceededError for 51+ splits
- [ ] Raises CurrencyMismatchError for wrong currency
- [ ] Raises SplitAmountMismatchError for sum mismatch
- [ ] Zero-amount splits valid when parent is zero
- [ ] Negative split amounts valid when sum matches
- [ ] Children with None merchant and comments

Join operation tests:
- [ ] Successful join sets _is_split_parent to False
- [ ] TransactionSplitsJoined event emitted with correct removed_child_count
- [ ] Raises TransactionDeletedError when deleted
- [ ] Raises NotSplitParentError when not split parent

Property tests:
- [ ] is_split_parent returns False by default
- [ ] is_split_parent returns True after split
- [ ] is_split_parent returns False after join
- [ ] is_split_child unchanged (returns parent_transaction_id is not None)

---

### Phase 2: Application Layer

#### TASK-006: Add split commands
**Layer:** Application
**Depends On:** TASK-002

**Description:**
Add 2 new command DTOs:
- `SplitTransaction(Command)` — `account_id`, `transaction_id`, `splits: tuple[SplitRequest, ...]`, `user_id` (note: spec says `user_id`, but existing commands use `requesting_user_id` — use `requesting_user_id` for consistency)
- `JoinTransactionSplits(Command)` — `account_id`, `transaction_id`, `requesting_user_id`

**Files:**
- `src/emerald/core_finance/application/dtos/commands/transaction_commands.py` — add 2 commands
- `src/emerald/core_finance/application/dtos/commands/__init__.py` — add exports
- `src/emerald/core_finance/application/dtos/__init__.py` — add exports

**Acceptance Criteria:**
- [ ] Frozen dataclasses extending Command
- [ ] All fields have defaults
- [ ] `SplitTransaction.splits` uses `tuple[SplitRequest, ...]` (immutable)
- [ ] Consistent naming: `requesting_user_id` (not `user_id`)

**Tests:**
- [ ] `tests/unit/core_finance/application/dtos/commands/test_transaction_commands.py` — extend existing
- [ ] Both commands instantiable with defaults and with values
- [ ] Both commands are frozen

---

#### TASK-007: Extend TransactionRepository protocol
**Layer:** Application
**Depends On:** None

**Description:**
Add 2 new methods to `TransactionRepository` protocol:
```python
def find_children(
    self,
    parent_transaction_id: uuid.UUID,
    include_deleted: bool = False,
) -> list[Transaction]: ...

def hard_delete_children(self, parent_transaction_id: uuid.UUID) -> int: ...
```

**Files:**
- `src/emerald/core_finance/application/ports/outbound/transaction_repository.py` — add 2 methods

**Acceptance Criteria:**
- [ ] Methods added to Protocol class
- [ ] Correct signatures with defaults
- [ ] `hard_delete_children` returns int (count of deleted)

**Tests:**
- [ ] No dedicated tests (protocol is structural, tested via fakes)

---

#### TASK-008: Extend TransactionManagementService
**Layer:** Application
**Depends On:** TASK-005, TASK-006, TASK-007

**Description:**
Add new methods and modify existing ones:

1. **`split_transaction(cmd: SplitTransaction) -> list[Transaction]`**
   - Load account, verify not deleted, verify EDITOR permission
   - Load parent transaction
   - Verify not deleted
   - Call `parent.split(cmd.splits, cmd.requesting_user_id)` → returns children
   - Save parent via `self._uow.transactions.save(parent)`
   - Save children via `self._uow.transactions.save_many(children)`
   - Commit
   - Return children

2. **`join_transaction_splits(cmd: JoinTransactionSplits) -> None`**
   - Load account, verify not deleted, verify EDITOR permission
   - Load parent transaction
   - Verify not deleted
   - Load children via `self._uow.transactions.find_children(cmd.transaction_id)`
   - Call `parent.join_splits(child_count=len(children))`
   - Hard-delete children via `self._uow.transactions.hard_delete_children(cmd.transaction_id)`
   - Save parent
   - Commit

3. **Modify `update_amount()`** — add auto-join for split parents and sum validation for split children:
   - After loading transaction and verifying not deleted:
   - IF `transaction.is_split_parent`:
     - Load children, call `transaction.join_splits(len(children))`, hard-delete children
   - IF `transaction.is_split_child()`:
     - Load parent, load siblings, compute new sum, validate against parent amount
     - Raise `SplitAmountMismatchError` on mismatch
   - Then proceed with existing `update_amount()` logic

4. **Modify `soft_delete_transaction()`** — cascade to children:
   - After existing logic, before calling `transaction.soft_delete()`:
   - IF `transaction.is_split_parent`:
     - Load active children via `find_children(transaction_id)`
     - For each child: `child.soft_delete(cmd.requesting_user_id, retention, cmd.reason)`
     - Save all children
   - Then proceed with parent soft_delete

5. **Modify `recover_transaction()`** — validate parent status and cascade recovery:
   - After loading transaction:
   - IF `transaction.is_split_child()`:
     - Load parent (include_deleted=True)
     - IF parent is deleted: raise `ParentDeletedError`
   - IF `transaction.is_split_parent`:
     - Load deleted children via `find_children(transaction_id, include_deleted=True)`
     - For each deleted child: `child.recover()`
     - Save all children
   - Then proceed with transaction.recover()

**Files:**
- `src/emerald/core_finance/application/services/transaction_management.py` — modify service

**Acceptance Criteria:**
- [ ] `split_transaction()` creates and persists children correctly
- [ ] `join_transaction_splits()` hard-deletes children and updates parent
- [ ] `update_amount()` auto-joins split parents before amount update
- [ ] `update_amount()` validates sum integrity for split children
- [ ] `soft_delete_transaction()` cascades to children
- [ ] `recover_transaction()` validates parent not deleted for children
- [ ] `recover_transaction()` cascades recovery to deleted children
- [ ] All new methods require EDITOR permission (except recovery: OWNER)

**Tests:**
- [ ] `tests/unit/core_finance/application/services/test_transaction_split.py` — new file

Split service tests:
- [ ] Successful split creates children and saves them
- [ ] Split requires EDITOR permission
- [ ] Split raises on deleted account
- [ ] Split raises on non-existent account
- [ ] Split raises on non-existent transaction
- [ ] Split raises on deleted transaction
- [ ] Parent is_split_parent is True after split
- [ ] Children are persisted via save_many
- [ ] UoW is committed

Join service tests:
- [ ] Successful join hard-deletes children and updates parent
- [ ] Join requires EDITOR permission
- [ ] Join raises on deleted account
- [ ] Join raises on non-existent transaction
- [ ] Join raises on non-split parent
- [ ] Parent is_split_parent is False after join
- [ ] Children are hard-deleted
- [ ] UoW is committed

Update amount with split-aware behavior:
- [ ] Auto-joins split parent before updating amount
- [ ] Children hard-deleted during auto-join
- [ ] Validates sum for split child amount update
- [ ] Raises SplitAmountMismatchError when child update breaks sum

Soft delete cascade:
- [ ] Soft-deleting parent cascades to all active children
- [ ] Soft-deleting a single child does not affect parent/siblings

Recovery cascade:
- [ ] Recovering parent recovers all deleted children
- [ ] Recovering child validates parent is not deleted
- [ ] Raises ParentDeletedError when parent is deleted
- [ ] Recovering child does not affect siblings

---

### Phase 3: Test Infrastructure

#### TASK-009: Extend test fakes
**Layer:** Test Infrastructure
**Depends On:** TASK-007

**Description:**
Extend `FakeTransactionRepository` with:

1. **`find_children(parent_transaction_id, include_deleted=False) -> list[Transaction]`**
   - Filter `_transactions` by `parent_transaction_id` matching
   - Respect `include_deleted` flag

2. **`hard_delete_children(parent_transaction_id) -> int`**
   - Remove all transactions with matching `parent_transaction_id` from `_transactions` dict
   - Return count of removed

3. **Fix `sum_amounts()`** to respect `exclude_split_parents` parameter:
   - When `exclude_split_parents=True` (default), skip transactions where `is_split_parent` is True
   - Current implementation ignores this flag

**Files:**
- `tests/unit/core_finance/fakes.py` — extend fake repository

**Acceptance Criteria:**
- [ ] `find_children()` returns correct children
- [ ] `find_children()` respects include_deleted flag
- [ ] `hard_delete_children()` permanently removes children and returns count
- [ ] `sum_amounts()` excludes split parents when flag is True

**Tests:**
- [ ] Tested transitively through service tests

---

### Phase 4: Public API Exports

#### TASK-010: Update all `__init__.py` exports
**Layer:** All
**Depends On:** TASK-002, TASK-003, TASK-004, TASK-006

**Description:**
Update the module export chain to expose all new public types:

**New exports to add:**
- Value objects: `SplitRequest`
- Events: `TransactionSplit`, `TransactionSplitsJoined`
- Exceptions: `MinimumSplitsRequiredError`, `MaxSplitsExceededError`, `SplitAmountMismatchError`, `CannotSplitChildError`, `AlreadySplitError`, `NotSplitParentError`, `ParentDeletedError`
- Commands: `SplitTransaction`, `JoinTransactionSplits`

**Files (full chain):**
- `src/emerald/core_finance/domain/models/value_objects/__init__.py` — add `SplitRequest`
- `src/emerald/core_finance/domain/models/__init__.py` — add `SplitRequest`
- `src/emerald/core_finance/domain/events/__init__.py` — add 2 events
- `src/emerald/core_finance/domain/exceptions/__init__.py` — add 7 exceptions
- `src/emerald/core_finance/domain/__init__.py` — add VO + events + exceptions
- `src/emerald/core_finance/application/dtos/commands/__init__.py` — add 2 commands
- `src/emerald/core_finance/application/dtos/__init__.py` — add 2 commands
- `src/emerald/core_finance/application/__init__.py` — add 2 commands
- `src/emerald/core_finance/__init__.py` — add all new types to `__all__`

**Acceptance Criteria:**
- [ ] All new types importable from `emerald.core_finance`
- [ ] All `__all__` lists updated
- [ ] Import chain verified (no circular imports)

**Tests:**
- [ ] Verified by running full test suite and import checks

---

### Phase 5: Quality Assurance

#### TASK-011: Run full quality checks
**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-010

**Description:**
Run all quality tools and fix any issues:
1. `uv run ruff check --fix .`
2. `uv run ruff format .`
3. `uv run ty check`
4. `uv run pytest -v`

**Acceptance Criteria:**
- [ ] All tests pass (existing + new)
- [ ] Ruff check clean (no lint errors)
- [ ] Ruff format clean (no formatting changes)
- [ ] ty check clean (no type errors)
- [ ] No regressions in existing test suite

---

## 5. Task Dependency Graph

```
TASK-001 (constants) ─────┬──► TASK-005 (entity)
                          │
TASK-002 (split_request) ─┤
                          │
TASK-003 (exceptions) ────┤
                          │
TASK-004 (events) ────────┘
                               │
TASK-006 (commands) ───────────┤
                               │
TASK-007 (repo protocol) ─────┤
                               │
                               ▼
                          TASK-008 (service) ──► TASK-010 (exports)
                               │                      │
                          TASK-009 (fakes)             │
                               │                      ▼
                               └──────────────► TASK-011 (QA)
```

**Parallel work opportunities:**
- TASK-001, TASK-002, TASK-003, TASK-004 can all be done in parallel
- TASK-006, TASK-007 can be done in parallel
- TASK-008, TASK-009 should be done together (service needs fakes for testing)
- TASK-010, TASK-011 are sequential finalization

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `is_split_parent` changing from method to property breaks callers | Medium | Medium | Search all call sites — existing stub is a method `is_split_parent()`, spec wants a property. Update all callers. The test `test_is_split_parent_returns_false` calls `tx.is_split_parent()` with parens — must be updated. |
| `sum_amounts` fake doesn't filter split parents | High | High | Fix in TASK-009 — current fake ignores `exclude_split_parents`. Required for balance tests. |
| Child Transaction `review_status` default mismatch | Medium | Low | `Transaction.create()` defaults to `TO_REVIEW`, but spec requires `REVIEWED` for children. Set explicitly after creation in `split()`. |
| Circular import from SplitRequest → Money | Low | Low | `SplitRequest` uses `Money` from shared kernel — same pattern as other VOs, no risk. |

---

## 7. Definition of Done

- [ ] All 11 tasks completed
- [ ] All acceptance criteria met
- [ ] All new unit tests passing
- [ ] All existing tests still passing (no regressions)
- [ ] `uv run ruff check .` — clean
- [ ] `uv run ruff format .` — clean
- [ ] `uv run ty check` — clean
- [ ] All new types exported from `emerald.core_finance`
- [ ] MEMORY.md updated with spec-010 status
