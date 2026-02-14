# Spec 013: Classification & Taxonomies — Implementation Plan

**Spec:** `.specs/spec-013-classification-and-taxonomies/spec.md`
**Version:** 1.0
**Date:** 2026-02-14

---

## 1. Overview

This plan implements the Classification bounded context — a new context (`src/emerald/classification/`) containing the **Taxonomy aggregate** and its child **TaxonomyTerm** entities. The Taxonomy is a user-owned hierarchical tree for organizing financial data (e.g., "Food > Restaurants > Italian"). Key complexity lies in the aggregate managing its internal term collection with cycle detection, cascade operations, and sort ordering.

**Approach:** Inside-out — domain layer first (value objects → entity → aggregate → events → exceptions), then application layer (commands → ports → service), then tests at each phase.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|---|---|---|
| Value objects (TaxonomyName, TermName, TaxonomyPath) | Domain | `domain/models/value_objects/` |
| TaxonomyTerm child entity | Domain | `domain/models/entities/taxonomy_term.py` |
| Taxonomy aggregate (hierarchy, cycle detection, cascade) | Domain | `domain/models/aggregates/taxonomy.py` |
| Domain events (12 events) | Domain | `domain/events/taxonomy_events.py` |
| Domain exceptions (14 errors) | Domain | `domain/exceptions/taxonomy_exceptions.py` |
| Domain constants | Domain | `domain/constants.py` |
| Commands (12 commands) | Application | `application/dtos/commands/taxonomy_commands.py` |
| TaxonomyRepository protocol | Application | `application/ports/outbound/taxonomy_repository.py` |
| AbstractClassificationUnitOfWork | Application | `application/ports/outbound/unit_of_work.py` |
| TaxonomyManagementService | Application | `application/services/taxonomy_management.py` |

### 2.2 Directory Structure

```
src/emerald/classification/
├── __init__.py                          # Public API re-exports
├── domain/
│   ├── __init__.py
│   ├── constants.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── aggregates/
│   │   │   ├── __init__.py
│   │   │   └── taxonomy.py
│   │   ├── entities/
│   │   │   ├── __init__.py
│   │   │   └── taxonomy_term.py
│   │   └── value_objects/
│   │       ├── __init__.py
│   │       ├── taxonomy_name.py
│   │       ├── term_name.py
│   │       └── taxonomy_path.py
│   ├── events/
│   │   ├── __init__.py
│   │   └── taxonomy_events.py
│   └── exceptions/
│       ├── __init__.py
│       └── taxonomy_exceptions.py
├── application/
│   ├── __init__.py
│   ├── dtos/
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── taxonomy_commands.py
│   ├── ports/
│   │   ├── __init__.py
│   │   └── outbound/
│   │       ├── __init__.py
│   │       ├── taxonomy_repository.py
│   │       └── unit_of_work.py
│   └── services/
│       ├── __init__.py
│       └── taxonomy_management.py

tests/unit/classification/
├── __init__.py
├── fakes.py
├── domain/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── aggregates/
│   │   │   ├── __init__.py
│   │   │   └── test_taxonomy.py
│   │   ├── entities/
│   │   │   ├── __init__.py
│   │   │   └── test_taxonomy_term.py
│   │   └── value_objects/
│   │       ├── __init__.py
│   │       ├── test_taxonomy_name.py
│   │       ├── test_term_name.py
│   │       └── test_taxonomy_path.py
│   ├── events/
│   │   ├── __init__.py
│   │   └── test_taxonomy_events.py
│   └── exceptions/
│       ├── __init__.py
│       └── test_taxonomy_exceptions.py
├── application/
│   ├── __init__.py
│   ├── dtos/
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── test_taxonomy_commands.py
│   └── services/
│       ├── __init__.py
│       ├── test_taxonomy_create.py
│       ├── test_taxonomy_update.py
│       ├── test_taxonomy_lifecycle.py
│       ├── test_term_add.py
│       ├── test_term_update.py
│       ├── test_term_move.py
│       ├── test_term_lifecycle.py
│       └── test_term_reorder.py
```

### 2.3 Ports and Adapters

| Port (Interface) | Purpose | Layer |
|---|---|---|
| `TaxonomyRepository` (Protocol) | Taxonomy persistence (aggregate + terms) | Application |
| `AbstractClassificationUnitOfWork` | Transaction boundary for classification context | Application |

### 2.4 Key Design Decisions

**Decision 1: TaxonomyTerm as a simpler child entity than Transaction**
- TaxonomyTerm extends `SoftDeletableMixin + TimestampedMixin + Entity` (per spec)
- Does NOT have AuditableMixin (no created_by/updated_by on terms — tracked via Taxonomy aggregate)
- Does NOT manage own events (unlike Transaction) — all events emitted by Taxonomy aggregate
- Internal mutation methods prefixed with `_` (called only by Taxonomy aggregate methods)

**Decision 2: Taxonomy soft_delete/recover overrides**
- Taxonomy.soft_delete() must cascade to all active terms
- Both Taxonomy and TaxonomyTerm use SoftDeletableMixin which requires `RetentionPeriod`
- The aggregate's `soft_delete(deleted_by, retention)` cascades: calls `term.soft_delete(deleted_by, retention)` on each active term
- The aggregate's `recover()` only recovers the taxonomy — terms remain deleted

**Decision 3: Term name uniqueness is global within taxonomy**
- Uniqueness is among ALL active terms in the taxonomy (not just siblings)
- Checked via case-insensitive comparison using `TermName.normalized()`
- Both `add_term` and `rename_term` check this invariant

**Decision 4: DeletableEntityType already has TAXONOMY and TAXONOMY_TERM**
- Confirmed these values exist in the shared kernel enum — no changes needed there

---

## 3. Implementation Tasks

### Phase 1: Domain Layer — Value Objects, Constants, Exceptions, Events

#### TASK-001: Create domain constants and package structure
**Layer:** Domain
**Depends On:** None

**Description:**
Create the full directory structure for `src/emerald/classification/` and `tests/unit/classification/` with all `__init__.py` files. Create `domain/constants.py` with the 5 classification constants.

**Files to Create:**
- All directory `__init__.py` stubs (empty for now)
- `src/emerald/classification/domain/constants.py`

**Acceptance Criteria:**
- [ ] All directories and `__init__.py` files created
- [ ] Constants match spec section 4 values

---

#### TASK-002: Create domain exceptions
**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Create all 14 domain exceptions in `taxonomy_exceptions.py`. Follow the pattern from `core_finance/domain/exceptions/account_exceptions.py`:
- 4 value object errors extending `InvalidValueError`: InvalidTaxonomyNameError, InvalidTermNameError, TaxonomyDescriptionTooLongError, TermDescriptionTooLongError
- 10 invariant errors extending `InvariantViolationError`: TaxonomyNameAlreadyExistsError, TermNameAlreadyExistsError, TermNotFoundError, ParentTermNotFoundError, ParentTermDeletedError, CannotBeOwnParentError, CircularReferenceError, TaxonomyNotActiveError, MaxTermsExceededError, IncompleteReorderError
- 1 not found error extending `NotFoundError`: TaxonomyNotFoundError

Each exception gets a unique `code` string matching spec section 10.

**Files to Create:**
- `src/emerald/classification/domain/exceptions/__init__.py` (re-exports)
- `src/emerald/classification/domain/exceptions/taxonomy_exceptions.py`

**Tests:**
- `tests/unit/classification/domain/exceptions/test_taxonomy_exceptions.py`
- [ ] Each exception has correct code, message defaults, and inheritance

---

#### TASK-003: Create value objects (TaxonomyName, TermName, TaxonomyPath)
**Layer:** Domain
**Depends On:** TASK-001, TASK-002

**Description:**
Implement the 3 value objects following established patterns:

1. **TaxonomyName** — `@dataclass(frozen=True, eq=False)` with case-insensitive equality (identical pattern to `AccountName`). Trim in `__post_init__`, validate non-empty and max length from constants. Custom `__eq__`, `__hash__`, `normalized()`.

2. **TermName** — Same pattern as TaxonomyName but with `MAX_TERM_NAME_LENGTH` and `InvalidTermNameError`.

3. **TaxonomyPath** — `@dataclass(frozen=True)` with `segments: tuple[str, ...]`. Validate at least one segment in `__post_init__`. Properties: `depth` (len-1), `parent_path()` (None for single segment), `__str__()` formatted as `"A > B > C"`.

**Files to Create:**
- `src/emerald/classification/domain/models/value_objects/taxonomy_name.py`
- `src/emerald/classification/domain/models/value_objects/term_name.py`
- `src/emerald/classification/domain/models/value_objects/taxonomy_path.py`
- `src/emerald/classification/domain/models/value_objects/__init__.py` (re-exports)

**Tests:**
- `tests/unit/classification/domain/models/value_objects/test_taxonomy_name.py`
- `tests/unit/classification/domain/models/value_objects/test_term_name.py`
- `tests/unit/classification/domain/models/value_objects/test_taxonomy_path.py`
- [ ] TaxonomyName: empty raises, too long raises, trimming works, case-insensitive eq/hash, normalized()
- [ ] TermName: same as TaxonomyName but with term-specific error
- [ ] TaxonomyPath: empty segments raises, depth correct, parent_path works, str formatting

---

#### TASK-004: Create domain events
**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Create all 12 domain events as `@dataclass(frozen=True)` extending `DomainEvent` with `aggregate_type: ClassVar[str] = "Taxonomy"`. All fields use defaults (UUID default = `uuid.UUID(int=0)`, str default = `""`, etc.) following the established pattern from `account_events.py`.

Events:
- TaxonomyCreated (taxonomy_id via aggregate_id, owner_id, name)
- TaxonomyRenamed (old_name, new_name)
- TaxonomyDescriptionUpdated (taxonomy_id)
- TaxonomySoftDeleted (deleted_by, term_count)
- TaxonomyRecovered (taxonomy_id)
- TermAdded (term_id, taxonomy_id, name, parent_term_id)
- TermRenamed (term_id, old_name, new_name)
- TermDescriptionUpdated (term_id)
- TermMoved (term_id, old_parent_id, new_parent_id)
- TermDeleted (term_id, deleted_by, descendants_deleted)
- TermRecovered (term_id)
- TermsReordered (parent_id, ordered_term_ids)

**Files to Create:**
- `src/emerald/classification/domain/events/__init__.py` (re-exports)
- `src/emerald/classification/domain/events/taxonomy_events.py`

**Tests:**
- `tests/unit/classification/domain/events/test_taxonomy_events.py`
- [ ] Each event instantiates with defaults, has correct aggregate_type

---

### Phase 2: Domain Layer — Entities and Aggregate

#### TASK-005: Create TaxonomyTerm entity
**Layer:** Domain
**Depends On:** TASK-003

**Description:**
Create `TaxonomyTerm` extending `SoftDeletableMixin + TimestampedMixin + Entity` (MRO: SoftDeletable → Timestamped → Entity). Uses cooperative `super().__init__(**kwargs)`.

Attributes (per spec 6.1):
- `taxonomy_id: UUID` (immutable via property)
- `name: TermName` (mutable)
- `description: str | None` (mutable)
- `parent_term_id: UUID | None` (mutable)
- `sort_order: int` (mutable)

Internal mutation methods (prefixed `_`, called by Taxonomy aggregate only):
- `_rename(new_name: TermName)` — update name, `_touch()`
- `_update_description(description: str | None)` — update description, `_touch()`
- `_move(new_parent_id: UUID | None)` — update parent_term_id, `_touch()`
- `_set_sort_order(order: int)` — update sort_order (no _touch, set in batch)

Construction via `__init__` only (no factory classmethod — created by Taxonomy.add_term()).

**Files to Create:**
- `src/emerald/classification/domain/models/entities/taxonomy_term.py`
- `src/emerald/classification/domain/models/entities/__init__.py` (re-exports)

**Tests:**
- `tests/unit/classification/domain/models/entities/test_taxonomy_term.py`
- [ ] Construction with all fields
- [ ] Immutable taxonomy_id via property
- [ ] `_rename()` updates name and touches timestamp
- [ ] `_update_description()` updates description and touches timestamp
- [ ] `_move()` updates parent_term_id and touches timestamp
- [ ] `_set_sort_order()` updates sort_order
- [ ] SoftDeletableMixin: soft_delete, recover, is_deleted, is_active
- [ ] TimestampedMixin: created_at, updated_at

---

#### TASK-006: Create Taxonomy aggregate
**Layer:** Domain
**Depends On:** TASK-002, TASK-003, TASK-004, TASK-005

**Description:**
Create the Taxonomy aggregate root extending `SoftDeletableMixin + AuditableMixin + AggregateRoot` (same MRO as Account). This is the most complex task — the aggregate manages its internal `_terms` collection with full hierarchy operations.

**Sections to implement (per spec):**

1. **Constructor** (`__init__`): owner_id (immutable property), name, description, terms (list for hydration), plus **kwargs for MRO.

2. **Factory** (`create` classmethod): Creates taxonomy with empty terms, validates description length, sets created_by=owner_id, emits TaxonomyCreated.

3. **Taxonomy updates**: `rename()`, `update_description()` — both check TaxonomyNotActiveError. Emit events.

4. **Lifecycle overrides**:
   - `soft_delete(deleted_by, retention)`: cascade soft_delete to ALL active terms, then call super().soft_delete(). Emit TaxonomySoftDeleted with term_count.
   - `recover()`: recover taxonomy only (terms stay deleted). Emit TaxonomyRecovered.

5. **Term operations** (the core complexity):
   - `add_term()`: validate active, max terms, name uniqueness (global, case-insensitive), parent exists/active, description length. Create TaxonomyTerm with auto sort_order. Emit TermAdded.
   - `rename_term()`: find active term, check name uniqueness. Emit TermRenamed.
   - `update_term_description()`: find active term, validate length. Emit TermDescriptionUpdated.
   - `move_term()`: find active term, validate new parent (exists, active, not self, no cycle via `_would_create_cycle`). No-op if same parent. Assign sort_order at end of new siblings. Emit TermMoved.
   - `delete_term()`: find term (not deleted), cascade soft_delete to all descendants. Emit TermDeleted with descendants count.
   - `recover_term()`: find deleted term, check taxonomy active, check parent active. Recover term only. Emit TermRecovered.
   - `reorder_terms()`: validate all term_ids exist and active, all share same parent_id, complete set (no missing, no dups). Update sort_orders. Emit TermsReordered.

6. **Cycle detection**: `_would_create_cycle(term_id, new_parent_id)` — walk parent chain from new_parent_id upward; if we reach term_id, it's a cycle.

7. **Query methods**: `find_term()`, `get_term()`, `get_root_terms()`, `get_children()`, `get_descendants()`, `get_term_path()`, `get_term_depth()`, `active_term_count`, `terms`.

8. **Private helpers**: `_get_active_term(term_id)`, `_next_sort_order(parent_id)`, `_get_all_descendants(term_id)`, `_find_term_parent(term_id)`.

**Files to Create:**
- `src/emerald/classification/domain/models/aggregates/taxonomy.py`
- `src/emerald/classification/domain/models/aggregates/__init__.py` (re-exports)

**Tests:**
- `tests/unit/classification/domain/models/aggregates/test_taxonomy.py`
- [ ] **Creation**: create() with valid data, description too long error, TaxonomyCreated event
- [ ] **Updates**: rename, update_description, not-active errors, events
- [ ] **Lifecycle**: soft_delete cascades terms, recover does NOT recover terms, events with cascade counts
- [ ] **add_term**: root term, child term, with description, name uniqueness (case-insensitive), max terms, parent not found, parent deleted, taxonomy not active, auto sort_order, event
- [ ] **rename_term**: success, not found, name conflict, event
- [ ] **update_term_description**: success, too long, event
- [ ] **move_term**: to new parent, to root, same parent no-op, self-parent error, cycle detection (multi-depth), parent not found, parent deleted, sort_order at end, event
- [ ] **delete_term**: success, cascade to descendants, already deleted, count in event
- [ ] **recover_term**: success, not deleted, taxonomy not active, parent deleted, no child recovery
- [ ] **reorder_terms**: success, incomplete set, duplicates, wrong parent, event
- [ ] **Query methods**: get_root_terms sorted, get_children sorted, get_descendants recursive, get_term_path, get_term_depth, active_term_count
- [ ] **Cycle detection**: deep tree, move root under grandchild = cycle, move sibling = ok

---

### Phase 3: Application Layer

#### TASK-007: Create commands
**Layer:** Application
**Depends On:** TASK-001

**Description:**
Create all 12 commands as `@dataclass(frozen=True)` extending `Command`. Follow pattern from `core_finance/application/dtos/commands/account_commands.py`. All fields have defaults for ty compatibility.

5 taxonomy commands: CreateTaxonomy, RenameTaxonomy, UpdateTaxonomyDescription, SoftDeleteTaxonomy, RecoverTaxonomy.
7 term commands: AddTerm, RenameTerm, UpdateTermDescription, MoveTerm, DeleteTerm, RecoverTerm, ReorderTerms.

**Files to Create:**
- `src/emerald/classification/application/dtos/commands/taxonomy_commands.py`
- `src/emerald/classification/application/dtos/commands/__init__.py` (re-exports)
- `src/emerald/classification/application/dtos/__init__.py` (re-exports)

**Tests:**
- `tests/unit/classification/application/dtos/commands/test_taxonomy_commands.py`
- [ ] Each command instantiates with defaults and with explicit values

---

#### TASK-008: Create repository protocol and unit of work
**Layer:** Application
**Depends On:** TASK-006

**Description:**
Create the `TaxonomyRepository` protocol and `AbstractClassificationUnitOfWork`.

**TaxonomyRepository** (Protocol):
- `save(taxonomy: Taxonomy) -> None`
- `find_by_id(taxonomy_id: UUID, include_deleted: bool = False) -> Taxonomy | None`
- `find_by_owner(owner_id: UUID, include_deleted: bool = False) -> list[Taxonomy]`
- `exists_by_name_for_owner(name: TaxonomyName, owner_id: UUID, exclude_taxonomy_id: UUID | None = None) -> bool`

**AbstractClassificationUnitOfWork** (extends `AbstractUnitOfWork`):
- `taxonomies: TaxonomyRepository`
- Abstract `commit()`, `rollback()`

**Files to Create:**
- `src/emerald/classification/application/ports/outbound/taxonomy_repository.py`
- `src/emerald/classification/application/ports/outbound/unit_of_work.py`
- `src/emerald/classification/application/ports/outbound/__init__.py` (re-exports)
- `src/emerald/classification/application/ports/__init__.py`

---

#### TASK-009: Create test fakes
**Layer:** Tests
**Depends On:** TASK-008

**Description:**
Create `FakeTaxonomyRepository` and `FakeClassificationUnitOfWork` in `tests/unit/classification/fakes.py`. Follow the exact pattern from `tests/unit/core_finance/fakes.py`.

**FakeTaxonomyRepository:**
- `_taxonomies: dict[UUID, Taxonomy]` in-memory store
- `seen: set[Taxonomy]` for event collection
- `save()`: store by id
- `find_by_id()`: handle include_deleted
- `find_by_owner()`: filter by owner_id
- `exists_by_name_for_owner()`: case-insensitive name check with exclude_taxonomy_id

**FakeClassificationUnitOfWork:**
- `taxonomies: FakeTaxonomyRepository`
- `committed: bool`
- `collect_new_events()`: yield from seen taxonomy events

**Files to Create:**
- `tests/unit/classification/fakes.py`

---

#### TASK-010: Create TaxonomyManagementService
**Layer:** Application
**Depends On:** TASK-006, TASK-007, TASK-008

**Description:**
Implement the application service following the pattern from `AccountManagementService`. Inject `AbstractClassificationUnitOfWork` and `RetentionPolicyService`.

**Taxonomy operations:**
- `create_taxonomy(cmd)`: construct TaxonomyName, check uniqueness, Taxonomy.create(), save, commit
- `rename_taxonomy(cmd)`: load, verify ownership, construct TaxonomyName, check uniqueness (exclude self), taxonomy.rename(), commit
- `update_taxonomy_description(cmd)`: load, verify ownership, taxonomy.update_description(), commit
- `soft_delete_taxonomy(cmd)`: load (include_deleted=True), verify ownership, get retention, taxonomy.soft_delete(), commit
- `recover_taxonomy(cmd)`: load (include_deleted=True), verify ownership, taxonomy.recover(), commit

**Term operations:**
- `add_term(cmd)`: load, verify ownership, construct TermName, taxonomy.add_term(), commit, return term
- `rename_term(cmd)`: load, verify ownership, construct TermName, taxonomy.rename_term(), commit
- `update_term_description(cmd)`: load, verify ownership, taxonomy.update_term_description(), commit
- `move_term(cmd)`: load, verify ownership, taxonomy.move_term(), commit
- `delete_term(cmd)`: load, verify ownership, taxonomy.delete_term(), commit
- `recover_term(cmd)`: load, verify ownership, taxonomy.recover_term(), commit
- `reorder_terms(cmd)`: load, verify ownership, taxonomy.reorder_terms(), commit

**Queries:**
- `get_taxonomy(taxonomy_id, owner_id)`: load, verify ownership, return
- `list_taxonomies(owner_id)`: find_by_owner, return

**Private helpers:**
- `_load_taxonomy(taxonomy_id, include_deleted=False)`: find or raise TaxonomyNotFoundError
- `_verify_ownership(taxonomy, owner_id)`: raise TaxonomyNotFoundError if mismatch (no existence leak)

**Files to Create:**
- `src/emerald/classification/application/services/taxonomy_management.py`
- `src/emerald/classification/application/services/__init__.py` (re-exports)

**Tests** (split by operation area):
- `tests/unit/classification/application/services/test_taxonomy_create.py`
- `tests/unit/classification/application/services/test_taxonomy_update.py`
- `tests/unit/classification/application/services/test_taxonomy_lifecycle.py`
- `tests/unit/classification/application/services/test_term_add.py`
- `tests/unit/classification/application/services/test_term_update.py`
- `tests/unit/classification/application/services/test_term_move.py`
- `tests/unit/classification/application/services/test_term_lifecycle.py`
- `tests/unit/classification/application/services/test_term_reorder.py`
- [ ] **create**: success, duplicate name raises, event emitted, committed
- [ ] **rename**: success, not found, wrong owner gets not found, duplicate name raises
- [ ] **update_description**: success, not found, too long
- [ ] **soft_delete**: success with cascade, already deleted, retention used
- [ ] **recover**: success, not deleted
- [ ] **add_term**: success root and child, uniqueness, max terms, parent checks, description length
- [ ] **rename_term**: success, uniqueness
- [ ] **update_term_description**: success, too long
- [ ] **move_term**: success, cycle, self-parent, no-op
- [ ] **delete_term**: success, cascade
- [ ] **recover_term**: success, parent deleted
- [ ] **reorder_terms**: success, incomplete
- [ ] **get_taxonomy / list_taxonomies**: returns correctly, ownership check

---

### Phase 4: Public API & Integration

#### TASK-011: Create public `__init__.py` re-exports
**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-010

**Description:**
Wire up all `__init__.py` files with proper re-exports following the pattern from `core_finance/__init__.py`:

1. `src/emerald/classification/domain/__init__.py` — re-export all domain types
2. `src/emerald/classification/application/__init__.py` — re-export all application types
3. `src/emerald/classification/__init__.py` — top-level re-export with `__all__`

Organize `__all__` in sections: Aggregates, Entities, Value Objects, Events, Exceptions, Commands, Ports, Services.

**Acceptance Criteria:**
- [ ] All public types accessible via `from emerald.classification import X`
- [ ] `__all__` is complete and organized

---

#### TASK-012: Run quality checks and finalize
**Layer:** Cross-cutting
**Depends On:** TASK-011

**Description:**
Run the full quality pipeline and fix any issues:
1. `uv run ruff check --fix .`
2. `uv run ruff format .`
3. `uv run ty check`
4. `uv run pytest` (all tests pass)

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] ruff check clean
- [ ] ruff format clean
- [ ] ty check clean

---

## 4. Task Dependency Graph

```
TASK-001 (structure + constants)
   │
   ├──► TASK-002 (exceptions) ─────────────────────────┐
   │                                                    │
   ├──► TASK-003 (value objects) ──┐                    │
   │       depends on: 001, 002   │                    │
   │                               │                    │
   ├──► TASK-004 (events) ────────┐│                    │
   │                              ││                    │
   │    TASK-005 (term entity) ◄──┘│                    │
   │       depends on: 003        ││                    │
   │                              ││                    │
   │    TASK-006 (aggregate) ◄────┘┘◄───────────────────┘
   │       depends on: 002, 003, 004, 005
   │                              │
   ├──► TASK-007 (commands) ──────┤
   │       depends on: 001        │
   │                              │
   │    TASK-008 (ports) ◄────────┘
   │       depends on: 006        │
   │                              │
   │    TASK-009 (fakes) ◄────────┘
   │       depends on: 008        │
   │                              │
   │    TASK-010 (service) ◄──────┘◄── TASK-007
   │       depends on: 006, 007, 008
   │                              │
   │    TASK-011 (__init__.py) ◄──┘
   │       depends on: all above
   │                              │
   │    TASK-012 (quality) ◄──────┘
   │       depends on: 011
```

**Parallelizable groups:**
- TASK-002, TASK-003, TASK-004, TASK-007 can start in parallel after TASK-001
- TASK-005 starts after TASK-003
- TASK-006 waits for TASK-002, 003, 004, 005
- TASK-008 waits for TASK-006
- TASK-010 waits for TASK-006, 007, 008, 009

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Cycle detection bugs | Medium | High | Extensive tree test fixtures with 3+ depth levels |
| Cascade soft-delete correctness | Medium | Medium | Test deep hierarchy cascade with multiple branches |
| SoftDeletableMixin RetentionPeriod in cascade | Low | Medium | Follow Account.soft_delete pattern — pass retention through to terms |
| Term sort_order consistency | Low | Low | Test reorder with complete sibling sets |
| ty type checking issues with MRO kwargs | Medium | Low | Use `**kwargs: Any` pattern from existing codebase |

---

## 6. Definition of Done

- [ ] All 12 tasks completed
- [ ] All acceptance criteria from spec section 15 met
- [ ] All tests passing (`uv run pytest`)
- [ ] Code quality checks clean (`ruff check`, `ruff format`, `ty check`)
- [ ] Public API re-exports complete
- [ ] No cross-context runtime imports in domain layer
