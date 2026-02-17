# Transaction Categorization — Implementation Plan

**Spec:** `.specs/spec-014-transaction-categorization/spec.md`
**Version:** 1.0
**Date:** 2026-02-14

---

## 1. Overview

Implement manual transaction categorization within the **Classification** bounded context. A `TransactionTermAssignment` entity links Core Finance transactions to Classification taxonomy terms. Cross-context validation uses a `TransactionAccessPort` protocol (ACL pattern). Lifecycle cascades are handled via a `CategorizationEventHandler` protocol.

All new code lives in the Classification context — no modifications to Core Finance or Shared Kernel domain layers.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| Assignment entity | Domain | `TransactionTermAssignment` entity |
| Uncategorization reasons | Domain | `UncategorizationReason` enum VO |
| Domain events | Domain | `TransactionCategorized`, `TransactionUncategorized` |
| Domain exceptions | Domain | `TransactionNotActiveError`, `AssignmentNotFoundError` |
| Cross-context port | Application | `TransactionAccessPort` protocol |
| Event handler port | Application | `CategorizationEventHandler` protocol |
| Assignment repository | Application | `TransactionTermAssignmentRepository` protocol |
| Unit of Work extension | Application | `AbstractClassificationUnitOfWork` extended |
| Categorization commands | Application | `AssignTerm`, `RemoveAssignment` |
| Service | Application | `TransactionCategorizationService` |

### 2.2 File Structure

```
classification/
├── domain/
│   ├── models/
│   │   ├── entities/
│   │   │   ├── __init__.py               (EXTENDED: add TransactionTermAssignment)
│   │   │   └── transaction_term_assignment.py  (NEW)
│   │   ├── value_objects/
│   │   │   ├── __init__.py               (EXTENDED: add UncategorizationReason)
│   │   │   └── uncategorization_reason.py (NEW)
│   │   └── __init__.py                   (EXTENDED)
│   ├── events/
│   │   ├── __init__.py                   (EXTENDED)
│   │   └── categorization_events.py      (NEW)
│   ├── exceptions/
│   │   ├── __init__.py                   (EXTENDED)
│   │   └── categorization_exceptions.py  (NEW)
│   └── __init__.py                       (EXTENDED)
├── application/
│   ├── dtos/
│   │   ├── commands/
│   │   │   ├── __init__.py               (EXTENDED)
│   │   │   └── categorization_commands.py (NEW)
│   │   └── __init__.py                   (EXTENDED)
│   ├── ports/
│   │   ├── outbound/
│   │   │   ├── __init__.py               (EXTENDED)
│   │   │   ├── transaction_access_port.py (NEW)
│   │   │   ├── categorization_event_handler.py (NEW)
│   │   │   ├── transaction_term_assignment_repository.py (NEW)
│   │   │   └── unit_of_work.py           (EXTENDED)
│   │   └── __init__.py                   (EXTENDED)
│   ├── services/
│   │   ├── __init__.py                   (EXTENDED)
│   │   └── transaction_categorization.py  (NEW)
│   └── __init__.py                       (EXTENDED)
└── __init__.py                           (EXTENDED)
```

### 2.3 Ports and Adapters

| Port | Purpose | Layer |
|------|---------|-------|
| `TransactionAccessPort` | Cross-context: verify transaction active + editor permission | Application (Classification) |
| `CategorizationEventHandler` | Cross-context: cleanup on term/taxonomy/transaction deletion | Application (Classification) |
| `TransactionTermAssignmentRepository` | Persist/query assignments | Application (Classification) |

---

## 3. Technical Decisions

### 3.1 InsufficientPermissionError Placement
**Decision:** The `TransactionAccessPort` raises `InsufficientPermissionError`. Since this port lives in Classification but the error is defined in Core Finance (`core_finance/domain/exceptions/sharing_exceptions.py`), we define a **new** `CategorizationPermissionError` in Classification that extends `AuthorizationError` from the shared kernel. The infrastructure adapter translates Core Finance's `InsufficientPermissionError` → Classification's `CategorizationPermissionError`. However, per the spec's note: "InsufficientPermissionError could be defined [in shared kernel] if not already" — since `AuthorizationError` is already in shared kernel, we'll actually define `InsufficientCategorizationPermissionError` in Classification's own exceptions with its own code. **UPDATE:** Re-reading the spec more carefully — it says the port raises `InsufficientPermissionError`. The simplest approach: define the port to raise `AuthorizationError` (from shared kernel) since that's context-neutral. The infrastructure adapter catches Core Finance's `InsufficientPermissionError` and re-raises as shared `AuthorizationError`. The service layer doesn't need to know about Core Finance exceptions at all.

**Final Decision:** The `TransactionAccessPort.verify_editor_permission()` raises `AuthorizationError` from shared kernel. Test fakes do the same. The spec names it `InsufficientPermissionError` — we define a Classification-specific `InsufficientCategorizationPermissionError(AuthorizationError)` with code `"INSUFFICIENT_CATEGORIZATION_PERMISSION"`. This keeps Classification independent of Core Finance while matching the spec's intent.

**Simplification:** Actually, re-reading the spec once more — it explicitly says to reuse `InsufficientPermissionError` from Core Finance (Spec 008). Since this is a *port* definition and the spec explicitly calls it out as "reused from existing contexts (not redefined)", the port protocol just declares the type hint. The actual raising happens in the infrastructure adapter. For the test fakes in Classification, we can just raise a plain `AuthorizationError` or define a minimal stub. The cleanest approach: **define nothing new** — the port's docstring says it raises `InsufficientPermissionError` but the protocol method signature just returns `None`. The adapter raises Core Finance's error. Test fakes raise `AuthorizationError` from shared kernel. No new exception needed for this.

### 3.2 Entity Design
**Decision:** `TransactionTermAssignment` is a plain `Entity` with no mixins (no soft-delete, no audit, no timestamps beyond `assigned_at`). Immutable after creation — only created and hard-deleted. No `_events` list (events emitted by service).

### 3.3 Service-Level Events
**Decision:** Follow `AuthenticationService` pattern — `TransactionCategorizationService` has `_events: list[object]` and `collect_events()`. Events are `DomainEvent` subclasses but emitted by service, not aggregate.

### 3.4 CategorizationEventHandler as Service
**Decision:** `TransactionCategorizationService` implements the `CategorizationEventHandler` protocol (structural subtyping). The three `handle_*` methods are on the service class itself.

---

## 4. Implementation Tasks

### Phase 1: Domain Layer

#### TASK-001: Create UncategorizationReason value object
**Layer:** Domain
**Depends On:** None

**Description:**
Create the `UncategorizationReason` enum value object with four members: `MANUAL`, `TERM_DELETED`, `TAXONOMY_DELETED`, `TRANSACTION_DELETED`.

**Files:**
- `src/emerald/classification/domain/models/value_objects/uncategorization_reason.py` — NEW
- `src/emerald/classification/domain/models/value_objects/__init__.py` — EXTEND (add export)
- `src/emerald/classification/domain/models/__init__.py` — EXTEND (add export)

**Tests:**
- `tests/unit/classification/domain/value_objects/test_uncategorization_reason.py` — enum membership, str values

**Acceptance Criteria:**
- [ ] Enum with 4 members
- [ ] Extends `enum.StrEnum` (consistent with other enums like `ReviewStatus`)
- [ ] Each member has descriptive string value

---

#### TASK-002: Create TransactionTermAssignment entity
**Layer:** Domain
**Depends On:** None

**Description:**
Create the `TransactionTermAssignment` entity. Simple `Entity` subclass, no mixins. Factory method `create()` generates `id` and `assigned_at`. Validation: all UUIDs non-nil, `assigned_at` timezone-aware.

**Files:**
- `src/emerald/classification/domain/models/entities/transaction_term_assignment.py` — NEW
- `src/emerald/classification/domain/models/entities/__init__.py` — EXTEND (add export)
- `src/emerald/classification/domain/models/__init__.py` — EXTEND (add export)

**Tests:**
- `tests/unit/classification/domain/entities/test_transaction_term_assignment.py`
  - Factory method creates with generated id and assigned_at
  - All UUID fields validated non-nil
  - assigned_at is timezone-aware
  - Entity equality by id
  - Immutability (no mutation methods)

**Acceptance Criteria:**
- [ ] Extends `Entity` (not `AggregateRoot`)
- [ ] No mixins
- [ ] `create()` factory method with `transaction_id`, `term_id`, `taxonomy_id`, `assigned_by`
- [ ] Hydration `__init__` with all fields for repository reconstruction
- [ ] All UUID fields non-nil validated
- [ ] `assigned_at` is UTC-aware datetime

---

#### TASK-003: Create categorization domain events
**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Create `TransactionCategorized` and `TransactionUncategorized` domain events. Both are `@dataclass(frozen=True)` extending `DomainEvent` with `aggregate_type = "transaction"`.

**Files:**
- `src/emerald/classification/domain/events/categorization_events.py` — NEW
- `src/emerald/classification/domain/events/__init__.py` — EXTEND
- `src/emerald/classification/domain/__init__.py` — EXTEND

**Tests:**
- `tests/unit/classification/domain/events/test_categorization_events.py`
  - Event creation with all fields
  - aggregate_type is "transaction"
  - Frozen (immutable)
  - Default values for event_id and occurred_at

**Acceptance Criteria:**
- [ ] `TransactionCategorized`: `transaction_id` (aggregate_id), `term_id`, `taxonomy_id`, `assignment_id`, `assigned_by`, `is_reassignment`
- [ ] `TransactionUncategorized`: `transaction_id` (aggregate_id), `taxonomy_id`, `term_id`, `reason: UncategorizationReason`
- [ ] Both have `aggregate_type: ClassVar[str] = "transaction"`

---

#### TASK-004: Create categorization domain exceptions
**Layer:** Domain
**Depends On:** None

**Description:**
Create `TransactionNotActiveError` (extends `NotFoundError`) and `AssignmentNotFoundError` (extends `NotFoundError`), each with unique error codes.

**Files:**
- `src/emerald/classification/domain/exceptions/categorization_exceptions.py` — NEW
- `src/emerald/classification/domain/exceptions/__init__.py` — EXTEND
- `src/emerald/classification/domain/__init__.py` — EXTEND

**Tests:**
- `tests/unit/classification/domain/exceptions/test_categorization_exceptions.py`
  - Each exception has correct code
  - Inherits correct parent
  - Message is preserved

**Acceptance Criteria:**
- [ ] `TransactionNotActiveError(NotFoundError)` with code `"TRANSACTION_NOT_ACTIVE"`
- [ ] `AssignmentNotFoundError(NotFoundError)` with code `"ASSIGNMENT_NOT_FOUND"`

---

### Phase 2: Application Layer — Ports & Commands

#### TASK-005: Create TransactionAccessPort protocol
**Layer:** Application
**Depends On:** TASK-004

**Description:**
Define the `TransactionAccessPort` protocol with two methods: `verify_transaction_active(transaction_id) -> UUID` and `verify_editor_permission(account_id, user_id) -> None`. This is the ACL port — Classification defines it, infrastructure implements it.

**Files:**
- `src/emerald/classification/application/ports/outbound/transaction_access_port.py` — NEW
- `src/emerald/classification/application/ports/outbound/__init__.py` — EXTEND
- `src/emerald/classification/application/ports/__init__.py` — EXTEND

**Tests:**
- No unit tests for protocol definition itself (tested via service tests with fakes)

**Acceptance Criteria:**
- [ ] `typing.Protocol` with `verify_transaction_active(transaction_id: UUID) -> UUID`
- [ ] `typing.Protocol` with `verify_editor_permission(account_id: UUID, user_id: UUID) -> None`
- [ ] Docstrings describe raise behavior

---

#### TASK-006: Create CategorizationEventHandler protocol
**Layer:** Application
**Depends On:** None

**Description:**
Define the `CategorizationEventHandler` protocol with three methods: `handle_term_deleted`, `handle_taxonomy_soft_deleted`, `handle_transaction_soft_deleted`. Each returns `int` (count of removed assignments).

**Files:**
- `src/emerald/classification/application/ports/outbound/categorization_event_handler.py` — NEW
- `src/emerald/classification/application/ports/outbound/__init__.py` — EXTEND (if not already done in TASK-005)
- `src/emerald/classification/application/ports/__init__.py` — EXTEND

**Tests:**
- No unit tests for protocol definition itself

**Acceptance Criteria:**
- [ ] `typing.Protocol`
- [ ] `handle_term_deleted(term_id: UUID) -> int`
- [ ] `handle_taxonomy_soft_deleted(taxonomy_id: UUID) -> int`
- [ ] `handle_transaction_soft_deleted(transaction_id: UUID) -> int`

---

#### TASK-007: Create TransactionTermAssignmentRepository protocol
**Layer:** Application
**Depends On:** TASK-002

**Description:**
Define the `TransactionTermAssignmentRepository` protocol with all methods specified in Section 7.3 of the spec.

**Files:**
- `src/emerald/classification/application/ports/outbound/transaction_term_assignment_repository.py` — NEW
- `src/emerald/classification/application/ports/outbound/__init__.py` — EXTEND
- `src/emerald/classification/application/ports/__init__.py` — EXTEND

**Tests:**
- No unit tests for protocol definition

**Acceptance Criteria:**
- [ ] `save(assignment) -> None`
- [ ] `delete(assignment_id) -> None`
- [ ] `delete_by_term(term_id) -> list[TransactionTermAssignment]`
- [ ] `delete_by_taxonomy(taxonomy_id) -> list[TransactionTermAssignment]`
- [ ] `delete_by_transaction(transaction_id) -> list[TransactionTermAssignment]`
- [ ] `find_by_transaction(transaction_id) -> list[TransactionTermAssignment]`
- [ ] `find_by_transaction_and_taxonomy(transaction_id, taxonomy_id) -> TransactionTermAssignment | None`
- [ ] `find_by_term(term_id) -> list[TransactionTermAssignment]`
- [ ] `find_transaction_ids_by_term(term_id) -> list[UUID]`
- [ ] `find_uncategorized_transaction_ids(account_id, taxonomy_id) -> list[UUID]`

---

#### TASK-008: Extend AbstractClassificationUnitOfWork
**Layer:** Application
**Depends On:** TASK-007

**Description:**
Add `assignments: TransactionTermAssignmentRepository` attribute to the existing `AbstractClassificationUnitOfWork`.

**Files:**
- `src/emerald/classification/application/ports/outbound/unit_of_work.py` — MODIFY

**Tests:**
- Tested implicitly via service tests with FakeUnitOfWork

**Acceptance Criteria:**
- [ ] `assignments: TransactionTermAssignmentRepository` attribute added
- [ ] Import added for the repository type

---

#### TASK-009: Create categorization commands
**Layer:** Application
**Depends On:** None

**Description:**
Create `AssignTerm` and `RemoveAssignment` command DTOs.

**Files:**
- `src/emerald/classification/application/dtos/commands/categorization_commands.py` — NEW
- `src/emerald/classification/application/dtos/commands/__init__.py` — EXTEND
- `src/emerald/classification/application/dtos/__init__.py` — EXTEND

**Tests:**
- Tested implicitly via service tests

**Acceptance Criteria:**
- [ ] `AssignTerm(Command)`: `transaction_id: UUID`, `term_id: UUID`, `user_id: UUID` (with defaults)
- [ ] `RemoveAssignment(Command)`: `transaction_id: UUID`, `taxonomy_id: UUID`, `user_id: UUID` (with defaults)
- [ ] `@dataclass(frozen=True)`

---

### Phase 3: Application Layer — Service & Test Fakes

#### TASK-010: Create test fakes
**Layer:** Test Infrastructure
**Depends On:** TASK-005, TASK-007, TASK-008

**Description:**
Create `FakeTransactionAccessPort`, `FakeTransactionTermAssignmentRepository`, and extend `FakeClassificationUnitOfWork` with `assignments`. These are needed before writing service tests.

**Files:**
- `tests/unit/classification/fakes.py` — EXTEND with new fakes

**Acceptance Criteria:**
- [ ] `FakeTransactionAccessPort`: configurable active transactions (returns account_id), configurable permissions, raises `TransactionNotActiveError` / `AuthorizationError`
- [ ] `FakeTransactionTermAssignmentRepository`: in-memory dict, all protocol methods implemented
- [ ] `FakeClassificationUnitOfWork` extended with `assignments` attribute
- [ ] `collect_new_events()` unchanged (assignments don't have aggregate events)

---

#### TASK-011: Create TransactionCategorizationService
**Layer:** Application
**Depends On:** TASK-002, TASK-003, TASK-004, TASK-005, TASK-006, TASK-007, TASK-008, TASK-009

**Description:**
Implement the `TransactionCategorizationService` with all methods from Section 8 of the spec. The service also implements the `CategorizationEventHandler` protocol (structural subtyping — no explicit inheritance needed).

Service-level events: `_events: list[object]` with `collect_events()` method.

**Files:**
- `src/emerald/classification/application/services/transaction_categorization.py` — NEW
- `src/emerald/classification/application/services/__init__.py` — EXTEND

**Methods:**
1. `assign_term(cmd: AssignTerm) -> TransactionTermAssignment`
2. `remove_assignment(cmd: RemoveAssignment) -> None`
3. `get_assignments(transaction_id: UUID) -> list[TransactionTermAssignment]`
4. `get_assignment_for_taxonomy(transaction_id, taxonomy_id) -> TransactionTermAssignment | None`
5. `get_transactions_by_term(term_id, include_descendants=False) -> list[UUID]`
6. `get_uncategorized_transactions(account_id, taxonomy_id) -> list[UUID]`
7. `handle_term_deleted(term_id: UUID) -> int`
8. `handle_taxonomy_soft_deleted(taxonomy_id: UUID) -> int`
9. `handle_transaction_soft_deleted(transaction_id: UUID) -> int`

**Tests:** (in Phase 4)

**Acceptance Criteria:**
- [ ] `assign_term`: validates transaction active, editor permission, taxonomy active, term active; handles reassignment transparently
- [ ] `remove_assignment`: validates transaction active, editor permission; hard-deletes; raises `AssignmentNotFoundError` if missing
- [ ] Query methods: delegate to repository
- [ ] `get_transactions_by_term` with `include_descendants=True`: loads taxonomy, collects descendant term IDs, queries all
- [ ] Handler methods: bulk delete via repository, emit `TransactionUncategorized` per deleted assignment
- [ ] Service-level `collect_events()` returns and clears `_events`

---

### Phase 4: Tests

#### TASK-012: Unit tests for TransactionCategorizationService — assign_term
**Layer:** Tests
**Depends On:** TASK-010, TASK-011

**Description:**
Test the `assign_term` flow including: happy path (new assignment), reassignment (same taxonomy replaces), cross-context validation errors, term/taxonomy not found, term/taxonomy deleted.

**Files:**
- `tests/unit/classification/application/services/test_categorization_assign.py` — NEW

**Tests:**
- [ ] Assign term to transaction → assignment created, `TransactionCategorized` event emitted
- [ ] Reassignment (same taxonomy, different term) → old deleted, new created, event with `is_reassignment=True`
- [ ] Transaction not active → `TransactionNotActiveError`
- [ ] User lacks EDITOR permission → `AuthorizationError`
- [ ] Taxonomy not found → `TaxonomyNotFoundError`
- [ ] Taxonomy soft-deleted → `TaxonomyNotFoundError` (repository returns None with `include_deleted=False`)
- [ ] Term not found in taxonomy → `TermNotFoundError`
- [ ] Term soft-deleted → `TermNotFoundError`
- [ ] Multi-taxonomy: assign terms from 2 different taxonomies → both coexist
- [ ] Split child independence: assign to parent and child independently

---

#### TASK-013: Unit tests for TransactionCategorizationService — remove_assignment
**Layer:** Tests
**Depends On:** TASK-010, TASK-011

**Description:**
Test the `remove_assignment` flow.

**Files:**
- `tests/unit/classification/application/services/test_categorization_remove.py` — NEW

**Tests:**
- [ ] Remove existing assignment → hard-deleted, `TransactionUncategorized` event with `reason=MANUAL`
- [ ] Remove non-existent assignment → `AssignmentNotFoundError`
- [ ] Transaction not active → `TransactionNotActiveError`
- [ ] User lacks EDITOR permission → `AuthorizationError`

---

#### TASK-014: Unit tests for TransactionCategorizationService — queries
**Layer:** Tests
**Depends On:** TASK-010, TASK-011

**Description:**
Test query methods.

**Files:**
- `tests/unit/classification/application/services/test_categorization_queries.py` — NEW

**Tests:**
- [ ] `get_assignments` returns all for a transaction
- [ ] `get_assignment_for_taxonomy` returns specific or None
- [ ] `get_transactions_by_term` single term
- [ ] `get_transactions_by_term` with `include_descendants=True` (hierarchical)
- [ ] `get_uncategorized_transactions` delegates to repository

---

#### TASK-015: Unit tests for TransactionCategorizationService — event handlers (cascades)
**Layer:** Tests
**Depends On:** TASK-010, TASK-011

**Description:**
Test lifecycle cascade handler methods.

**Files:**
- `tests/unit/classification/application/services/test_categorization_cascades.py` — NEW

**Tests:**
- [ ] `handle_term_deleted` → removes all assignments for term, emits events with `TERM_DELETED`
- [ ] `handle_taxonomy_soft_deleted` → removes all for taxonomy, emits events with `TAXONOMY_DELETED`
- [ ] `handle_transaction_soft_deleted` → removes all for transaction, emits events with `TRANSACTION_DELETED`
- [ ] Handler returns correct count
- [ ] No assignments to remove → returns 0, no events
- [ ] Multiple assignments removed → correct count, one event per assignment

---

### Phase 5: Public API & Integration

#### TASK-016: Update all __init__.py exports
**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-011

**Description:**
Update all `__init__.py` files in the Classification context to re-export the new public types. Follow the existing pattern.

**Files (all EXTEND):**
- `src/emerald/classification/domain/models/entities/__init__.py`
- `src/emerald/classification/domain/models/value_objects/__init__.py`
- `src/emerald/classification/domain/models/__init__.py`
- `src/emerald/classification/domain/events/__init__.py`
- `src/emerald/classification/domain/exceptions/__init__.py`
- `src/emerald/classification/domain/__init__.py`
- `src/emerald/classification/application/dtos/commands/__init__.py`
- `src/emerald/classification/application/dtos/__init__.py`
- `src/emerald/classification/application/ports/outbound/__init__.py`
- `src/emerald/classification/application/ports/__init__.py`
- `src/emerald/classification/application/services/__init__.py`
- `src/emerald/classification/application/__init__.py`
- `src/emerald/classification/__init__.py`

**Acceptance Criteria:**
- [ ] All new public types exported in `classification/__init__.py`
- [ ] `__all__` lists updated at every level
- [ ] Exports match spec Section 15: `TransactionTermAssignment`, `TransactionCategorized`, `TransactionUncategorized`, `UncategorizationReason`, `TransactionNotActiveError`, `AssignmentNotFoundError`, `AssignTerm`, `RemoveAssignment`, `TransactionAccessPort`, `CategorizationEventHandler`, `TransactionTermAssignmentRepository`, `TransactionCategorizationService`

---

#### TASK-017: Run full quality checks
**Layer:** Cross-cutting
**Depends On:** All previous tasks

**Description:**
Run all quality checks to ensure everything passes.

**Commands:**
```bash
uv run pytest -v
uv run ruff check --fix .
uv run ruff format .
uv run ty check
```

**Acceptance Criteria:**
- [ ] All tests pass (existing + new)
- [ ] `ruff check` clean
- [ ] `ruff format` clean
- [ ] `ty check` clean

---

## 5. Task Dependency Graph

```
TASK-001 (VO) ─────────────────────────┐
                                        │
TASK-002 (Entity) ──────────────────────┤
                                        │
TASK-003 (Events) ──────────────────────┤
  depends on TASK-001                   │
                                        │
TASK-004 (Exceptions) ──────────────────┤
                                        │
TASK-005 (TransactionAccessPort) ───────┤
  depends on TASK-004                   │
                                        │
TASK-006 (EventHandler protocol) ───────┤
                                        │
TASK-007 (AssignmentRepo protocol) ─────┤
  depends on TASK-002                   │
                                        │
TASK-008 (UoW extension) ──────────────┤
  depends on TASK-007                   │
                                        │
TASK-009 (Commands) ────────────────────┤
                                        │
                                        ▼
TASK-010 (Test Fakes) ──────────► TASK-011 (Service) ──────► TASK-016 (Exports)
  depends on 005, 007, 008          depends on all above         │
                                        │                        ▼
                                        ├────► TASK-012 (assign tests)
                                        ├────► TASK-013 (remove tests)  ──► TASK-017 (Quality)
                                        ├────► TASK-014 (query tests)
                                        └────► TASK-015 (cascade tests)
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `InsufficientPermissionError` cross-context | Med | Low | Port docstrings document raises; fakes use `AuthorizationError` from shared kernel |
| `ty` strict checks on Protocol ports | Med | Low | Follow established patterns (Protocol methods with explicit return types) |
| UoW `collect_new_events()` confusion | Low | Med | Service-level events separate from aggregate events; document clearly |
| Taxonomy loading for `include_descendants` | Low | Low | Reuse existing `TaxonomyRepository.find_by_id()` + taxonomy term traversal |

---

## 7. Definition of Done

- [ ] All 17 tasks completed
- [ ] All acceptance criteria met per spec Section 14
- [ ] Unit tests passing (all new + all existing)
- [ ] `ruff check` clean
- [ ] `ruff format` clean
- [ ] `ty check` clean
- [ ] Public API exports match spec Section 15
- [ ] No modifications to Core Finance or Shared Kernel domains
