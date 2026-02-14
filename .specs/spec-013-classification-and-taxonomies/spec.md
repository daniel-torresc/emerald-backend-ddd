# Spec 013: Classification & Taxonomies

**Version:** 1.0
**Status:** Draft
**Bounded Context:** Classification (Supporting Domain)
**Dependencies:** 001 (Shared Kernel), 002 (User Registration & Identity), 006 (Data Lifecycle Management)
**Blocks:** 014 (Transaction Categorization)

---

## 1. Overview

This spec defines the Taxonomy aggregate — a user-defined hierarchical classification system. Taxonomies provide flexible, unlimited-depth tree structures for organizing financial data. The primary use case is transaction categorization (e.g., "Food > Restaurants > Italian"), but the model is generic enough to support other classification needs.

**Key Principles:**

- Taxonomies are user-owned and hierarchical with unlimited depth
- Term names are unique within a taxonomy (case-insensitive, globally — not just among siblings)
- The hierarchy must never contain circular references
- Terms are child entities managed inside the Taxonomy aggregate (no separate repository)
- All users create their own taxonomies — there are no system-provided defaults

---

## 2. Background & Context

### Problem Statement

Users need a flexible way to classify and organize their financial transactions. Rigid, flat category lists are insufficient for users who want granular control (e.g., separating "Food > Groceries" from "Food > Restaurants > Italian"). The taxonomy system provides hierarchical tree structures that users own and customize.

### Business Goals

- Enable users to create custom classification hierarchies of any depth
- Support transaction categorization (spec 014) with user-defined terms
- Provide a foundation for future auto-categorization and reporting features

---

## 3. Scope

### In Scope

- Taxonomy aggregate with terms as internal child entities
- TaxonomyTerm entity (hierarchical tree nodes within the aggregate)
- `TaxonomyName`, `TermName`, `TaxonomyPath` value objects
- Hierarchy operations: add, move, rename, delete, recover, reorder terms
- Cycle detection algorithm
- Sort ordering among sibling terms
- TaxonomyManagementService covering all operations
- AbstractClassificationUnitOfWork

### Out of Scope

- Transaction-term association (Spec 014)
- Auto-categorization rules and ML (future — Phase 2)
- Sharing taxonomies between users
- System/platform-provided default taxonomies

---

## 4. Domain Constants

```
# classification/domain/constants.py

MAX_TAXONOMY_NAME_LENGTH: int = 100
MAX_TERM_NAME_LENGTH: int = 100
MAX_TAXONOMY_DESCRIPTION_LENGTH: int = 500
MAX_TERM_DESCRIPTION_LENGTH: int = 500
MAX_TERMS_PER_TAXONOMY: int = 500
```

---

## 5. Value Objects

### 5.1 TaxonomyName

`@dataclass(frozen=True, eq=False)` — case-insensitive equality (like AccountName).

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Taxonomy display name (trimmed) |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__post_init__()` | Trim, validate non-empty, validate max length | `InvalidTaxonomyNameError` |
| `__eq__` / `__hash__` | Case-insensitive comparison | — |
| `normalized() -> str` | Lowercase, trimmed — for uniqueness checks | — |

**Business Rules:**

- Must be non-empty after trimming
- Maximum length: `MAX_TAXONOMY_NAME_LENGTH` (100) characters
- Equality is case-insensitive (e.g., `TaxonomyName("Budget") == TaxonomyName("budget")`)
- Uniqueness per user enforced by domain service

### 5.2 TermName

`@dataclass(frozen=True, eq=False)` — case-insensitive equality.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Term display name (trimmed) |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__post_init__()` | Trim, validate non-empty, validate max length | `InvalidTermNameError` |
| `__eq__` / `__hash__` | Case-insensitive comparison | — |
| `normalized() -> str` | Lowercase, trimmed — for uniqueness checks | — |

**Business Rules:**

- Must be non-empty after trimming
- Maximum length: `MAX_TERM_NAME_LENGTH` (100) characters
- Equality is case-insensitive
- Uniqueness within a taxonomy (globally, not just among siblings) enforced by aggregate

### 5.3 TaxonomyPath

`@dataclass(frozen=True)` — represents the full hierarchy path from root to a term.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| segments | tuple[str, ...] | Ordered term names from root to leaf (immutable) |

**Behavior:**

| Method | Description |
|--------|-------------|
| `__post_init__()` | Validate at least one segment |
| `depth -> int` | Property: number of segments minus 1 (root=0, child=1, etc.) |
| `parent_path() -> TaxonomyPath \| None` | Path without the last segment (None for root-level terms) |
| `__str__() -> str` | Formatted as `"Food > Restaurants > Italian"` |

**Construction:**

```
TaxonomyPath(segments=("Food", "Restaurants", "Italian"))
str(path) → "Food > Restaurants > Italian"
path.depth → 2  (root=0, child=1, grandchild=2)
path.parent_path() → TaxonomyPath(segments=("Food", "Restaurants"))
```

---

## 6. TaxonomyTerm Entity

Child entity managed inside the Taxonomy aggregate. Extends `SoftDeletableMixin + TimestampedMixin + Entity` (like Transaction).

### 6.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| term_id | UUID | No | Unique identifier (Entity.id) |
| taxonomy_id | UUID | No | Parent taxonomy reference |
| name | TermName | Yes | Display name |
| description | str \| None | Yes | Optional description |
| parent_term_id | UUID \| None | Yes | Parent term (None = root level) |
| sort_order | int | Yes | Display order among siblings |
| created_at | datetime | No | Via TimestampedMixin |
| updated_at | datetime | Auto | Via TimestampedMixin |
| deleted_at | datetime \| None | Yes | Via SoftDeletableMixin |
| deleted_by | UUID \| None | Yes | Via SoftDeletableMixin |

### 6.2 Construction

```
TaxonomyTerm(
    id=uuid,
    taxonomy_id=uuid,
    name=TermName("Food"),
    description=None,
    parent_term_id=None,
    sort_order=0,
)
```

- Created only via `Taxonomy.add_term()` — never directly by external code
- No factory classmethod on TaxonomyTerm itself

### 6.3 Internal Mutation Methods

These are called by the Taxonomy aggregate's operations, not directly by external code:

| Method | Description |
|--------|-------------|
| `_rename(new_name: TermName)` | Update name, touch updated_at |
| `_update_description(description: str \| None)` | Update description, touch updated_at |
| `_move(new_parent_id: UUID \| None)` | Update parent_term_id, touch updated_at |
| `_set_sort_order(order: int)` | Update sort_order |

---

## 7. Taxonomy Aggregate

Extends `SoftDeletableMixin + AuditableMixin + AggregateRoot` (like Account).

Terms are managed as an internal collection — the Taxonomy is the aggregate root, terms are child entities.

### 7.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| taxonomy_id | UUID | No | Unique identifier (Entity.id) |
| owner_id | UUID | No | User who owns this taxonomy |
| name | TaxonomyName | Yes | Display name (unique per user) |
| description | str \| None | Yes | Optional description |
| _terms | list[TaxonomyTerm] | Internal | Child entities collection |
| version | int | Auto | Via AggregateRoot (optimistic concurrency) |
| created_at | datetime | No | Via TimestampedMixin |
| updated_at | datetime | Auto | Via TimestampedMixin |
| created_by | UUID | No | Via AuditableMixin |
| updated_by | UUID \| None | Auto | Via AuditableMixin |
| deleted_at | datetime \| None | Yes | Via SoftDeletableMixin |
| deleted_by | UUID \| None | Yes | Via SoftDeletableMixin |

### 7.2 Hydration Constructor

```
Taxonomy(
    id=uuid,
    owner_id=uuid,
    name=TaxonomyName("Categories"),
    description="My spending categories",
    terms=[...],  # list[TaxonomyTerm] for repository hydration
    version=1,
    created_by=uuid,
    created_at=datetime,
    updated_at=datetime,
)
```

### 7.3 Creation

```
Taxonomy:
  + create(
      owner_id: UUID,
      name: TaxonomyName,
      description: str | None = None,
    ) -> Taxonomy                                      [class method]
      Creates: Taxonomy with empty terms collection
      Sets: created_by = owner_id
      Validates: description length <= MAX_TAXONOMY_DESCRIPTION_LENGTH
      Raises: TaxonomyDescriptionTooLongError
      Emits: TaxonomyCreated
```

### 7.4 Taxonomy Updates

```
Taxonomy:
  + rename(new_name: TaxonomyName) -> None
      Validates: taxonomy is active (not deleted)
      Raises: TaxonomyNotActiveError
      Updates: name, _touch()
      Note: Name uniqueness checked by domain service
      Emits: TaxonomyRenamed

  + update_description(description: str | None) -> None
      Validates:
        1. Taxonomy is active
           Raises: TaxonomyNotActiveError
        2. If not None, length <= MAX_TAXONOMY_DESCRIPTION_LENGTH
           Raises: TaxonomyDescriptionTooLongError
      Updates: description, _touch()
      Emits: TaxonomyDescriptionUpdated
```

### 7.5 Taxonomy Lifecycle

```
Taxonomy:
  + soft_delete(deleted_by: UUID) -> None
      Validates:
        - Not already deleted (via SoftDeletableMixin)
      Cascades: soft deletes ALL active terms (with deleted_by)
      Emits: TaxonomySoftDeleted
      Raises: AlreadyDeletedError

  + recover() -> None
      Validates: is soft deleted (via SoftDeletableMixin)
      Clears: deletion fields on taxonomy only
      Note: Terms remain in trash — recovered individually
      Emits: TaxonomyRecovered
      Raises: NotDeletedError
```

### 7.6 Term Operations

All term operations are methods on the Taxonomy aggregate to enforce invariants.

#### Add Term

```
Taxonomy:
  + add_term(
      name: TermName,
      parent_term_id: UUID | None = None,
      description: str | None = None,
    ) -> TaxonomyTerm
      Validates:
        1. Taxonomy is active (not deleted)
           Raises: TaxonomyNotActiveError
        2. Term count < MAX_TERMS_PER_TAXONOMY
           Raises: MaxTermsExceededError
        3. Name is unique within this taxonomy (case-insensitive, global)
           Raises: TermNameAlreadyExistsError
        4. If description provided, length <= MAX_TERM_DESCRIPTION_LENGTH
           Raises: TermDescriptionTooLongError
        5. If parent_term_id provided:
           a. Parent exists in this taxonomy
              Raises: ParentTermNotFoundError
           b. Parent is not deleted
              Raises: ParentTermDeletedError
      Creates:
        - TaxonomyTerm with next sort_order among siblings
      Emits: TermAdded
      Returns: the created term
```

#### Rename Term

```
Taxonomy:
  + rename_term(term_id: UUID, new_name: TermName) -> None
      Validates:
        1. Term exists in this taxonomy and is active
           Raises: TermNotFoundError
        2. New name is unique within this taxonomy (case-insensitive, global)
           Raises: TermNameAlreadyExistsError
      Updates: term._rename(new_name), _touch()
      Emits: TermRenamed
```

#### Update Term Description

```
Taxonomy:
  + update_term_description(term_id: UUID, description: str | None) -> None
      Validates:
        1. Term exists in this taxonomy and is active
           Raises: TermNotFoundError
        2. If not None, length <= MAX_TERM_DESCRIPTION_LENGTH
           Raises: TermDescriptionTooLongError
      Updates: term._update_description(description), _touch()
      Emits: TermDescriptionUpdated
```

#### Move Term

```
Taxonomy:
  + move_term(term_id: UUID, new_parent_id: UUID | None) -> None
      Validates:
        1. Term exists in this taxonomy and is active
           Raises: TermNotFoundError
        2. If new_parent_id is not None:
           a. New parent exists in this taxonomy and is active
              Raises: ParentTermNotFoundError
           b. New parent is not the term itself
              Raises: CannotBeOwnParentError
           c. New parent is not a descendant of term (no cycles)
              Raises: CircularReferenceError
        3. new_parent_id differs from current parent
           (no-op: return early without event)
      Updates:
        - term._move(new_parent_id)
        - Assign sort_order = next among new siblings
        - _touch()
      Emits: TermMoved
```

#### Delete Term

```
Taxonomy:
  + delete_term(term_id: UUID, deleted_by: UUID) -> None
      Validates:
        1. Term exists in this taxonomy
           Raises: TermNotFoundError
        2. Term is not already deleted
           Raises: AlreadyDeletedError
      Effect:
        - Soft delete the term (via SoftDeletableMixin)
        - Cascade: soft delete all descendant terms (children, grandchildren, etc.)
        - _touch()
      Emits: TermDeleted (one event, includes cascade info)
```

#### Recover Term

```
Taxonomy:
  + recover_term(term_id: UUID) -> None
      Validates:
        1. Term exists and is deleted
           Raises: TermNotFoundError (if not found), NotDeletedError (if active)
        2. Taxonomy is active
           Raises: TaxonomyNotActiveError
        3. If term has a parent: parent is active
           Raises: ParentTermDeletedError
      Effect:
        - Recover the term (clear deletion fields)
        - Children remain in trash — recovered individually
        - _touch()
      Emits: TermRecovered
```

#### Reorder Terms

```
Taxonomy:
  + reorder_terms(term_ids: list[UUID], parent_id: UUID | None = None) -> None
      Validates:
        1. All term_ids exist in this taxonomy and are active
           Raises: TermNotFoundError
        2. All term_ids share the same parent (parent_id)
           Raises: TermNotFoundError
        3. term_ids contains ALL active siblings under parent_id (complete set)
           Raises: IncompleteReorderError
        4. No duplicates in term_ids
           Raises: IncompleteReorderError
      Effect:
        - Updates sort_order to match the provided order (0-indexed)
        - _touch()
      Emits: TermsReordered
```

### 7.7 Query Methods

Methods on the aggregate for reading term hierarchy state:

```
Taxonomy:
  + find_term(term_id: UUID) -> TaxonomyTerm | None
      Returns term by ID (active or deleted), or None

  + get_term(term_id: UUID) -> TaxonomyTerm
      Returns term by ID or raises TermNotFoundError

  + get_root_terms() -> list[TaxonomyTerm]
      Active terms with parent_term_id = None, sorted by sort_order

  + get_children(term_id: UUID) -> list[TaxonomyTerm]
      Active direct children of term_id, sorted by sort_order

  + get_descendants(term_id: UUID) -> list[TaxonomyTerm]
      All active descendants (recursive), depth-first

  + get_term_path(term_id: UUID) -> TaxonomyPath
      Full path from root to term (walks parent chain)
      Raises: TermNotFoundError

  + get_term_depth(term_id: UUID) -> int
      Level in tree: root=0, child=1, etc.
      Raises: TermNotFoundError

  + active_term_count -> int
      Property: number of active (non-deleted) terms

  + terms -> list[TaxonomyTerm]
      Property: all terms (active and deleted) — for repository persistence
```

---

## 8. Cycle Detection

The cycle detection algorithm prevents circular references when moving terms. Implemented as a private method on the Taxonomy aggregate.

### 8.1 Algorithm

```
_would_create_cycle(term_id: UUID, new_parent_id: UUID | None) -> bool:
    """Returns True if moving term_id under new_parent_id would create a cycle."""
    if new_parent_id is None:
        return False  # Moving to root — no cycle possible

    current = new_parent_id
    while current is not None:
        if current == term_id:
            return True  # Cycle detected!
        current = self._find_term_parent(current)
    return False
```

### 8.2 Examples

```
Tree:
  A
  +-- B
  |   +-- C
  |   +-- D
  +-- E

move_term(A, new_parent=C):
  Check: C.parent = B, B.parent = A, A == A -> CYCLE!

move_term(C, new_parent=E):
  Check: E.parent = A, A.parent = None -> no cycle

move_term(B, new_parent=B):
  Check: B == B -> CYCLE! (caught by separate CannotBeOwnParentError check first)

move_term(D, new_parent=None):
  new_parent is None -> no cycle (moving to root)
```

---

## 9. Domain Events

All events extend `DomainEvent` with `aggregate_type: ClassVar[str] = "Taxonomy"`.

| Event | Trigger | Key Data |
|-------|---------|----------|
| `TaxonomyCreated` | `Taxonomy.create()` | taxonomy_id, owner_id, name |
| `TaxonomyRenamed` | `rename()` | taxonomy_id, old_name, new_name |
| `TaxonomyDescriptionUpdated` | `update_description()` | taxonomy_id |
| `TaxonomySoftDeleted` | `soft_delete()` | taxonomy_id, deleted_by, term_count (cascade) |
| `TaxonomyRecovered` | `recover()` | taxonomy_id |
| `TermAdded` | `add_term()` | term_id, taxonomy_id, name, parent_term_id |
| `TermRenamed` | `rename_term()` | term_id, taxonomy_id, old_name, new_name |
| `TermDescriptionUpdated` | `update_term_description()` | term_id, taxonomy_id |
| `TermMoved` | `move_term()` | term_id, taxonomy_id, old_parent_id, new_parent_id |
| `TermDeleted` | `delete_term()` | term_id, taxonomy_id, deleted_by, descendants_deleted (count) |
| `TermRecovered` | `recover_term()` | term_id, taxonomy_id |
| `TermsReordered` | `reorder_terms()` | taxonomy_id, parent_id, ordered_term_ids |

---

## 10. Domain Errors

### Value Object Errors (extend `InvalidValueError`)

| Error | Code | Trigger |
|-------|------|---------|
| `InvalidTaxonomyNameError` | `INVALID_TAXONOMY_NAME` | Empty or exceeds max length |
| `InvalidTermNameError` | `INVALID_TERM_NAME` | Empty or exceeds max length |
| `TaxonomyDescriptionTooLongError` | `TAXONOMY_DESCRIPTION_TOO_LONG` | Exceeds MAX_TAXONOMY_DESCRIPTION_LENGTH |
| `TermDescriptionTooLongError` | `TERM_DESCRIPTION_TOO_LONG` | Exceeds MAX_TERM_DESCRIPTION_LENGTH |

### Invariant Errors (extend `InvariantViolationError`)

| Error | Code | Trigger |
|-------|------|---------|
| `TaxonomyNameAlreadyExistsError` | `TAXONOMY_NAME_ALREADY_EXISTS` | Duplicate name for same user |
| `TermNameAlreadyExistsError` | `TERM_NAME_ALREADY_EXISTS` | Duplicate name within taxonomy (global) |
| `TermNotFoundError` | `TERM_NOT_FOUND` | Term doesn't exist or is deleted (context-dependent) |
| `ParentTermNotFoundError` | `PARENT_TERM_NOT_FOUND` | Parent term doesn't exist in taxonomy |
| `ParentTermDeletedError` | `PARENT_TERM_DELETED` | Parent term is soft deleted |
| `CannotBeOwnParentError` | `CANNOT_BE_OWN_PARENT` | Moving term under itself |
| `CircularReferenceError` | `CIRCULAR_REFERENCE` | Move would create a cycle |
| `TaxonomyNotActiveError` | `TAXONOMY_NOT_ACTIVE` | Operation on deleted taxonomy |
| `MaxTermsExceededError` | `MAX_TERMS_EXCEEDED` | Term count >= MAX_TERMS_PER_TAXONOMY |
| `IncompleteReorderError` | `INCOMPLETE_REORDER` | Reorder doesn't include all siblings or has duplicates |

### Not Found Error (extends `NotFoundError`)

| Error | Code | Trigger |
|-------|------|---------|
| `TaxonomyNotFoundError` | `TAXONOMY_NOT_FOUND` | Service-level: taxonomy ID not in repository |

---

## 11. Commands

All commands are `@dataclass(frozen=True)` extending `Command`.

### Taxonomy Commands

```
CreateTaxonomy:
  owner_id: UUID
  name: str
  description: str | None = None

RenameTaxonomy:
  taxonomy_id: UUID
  owner_id: UUID      # for ownership verification
  new_name: str

UpdateTaxonomyDescription:
  taxonomy_id: UUID
  owner_id: UUID
  description: str | None

SoftDeleteTaxonomy:
  taxonomy_id: UUID
  owner_id: UUID

RecoverTaxonomy:
  taxonomy_id: UUID
  owner_id: UUID
```

### Term Commands

```
AddTerm:
  taxonomy_id: UUID
  owner_id: UUID
  name: str
  parent_term_id: UUID | None = None
  description: str | None = None

RenameTerm:
  taxonomy_id: UUID
  owner_id: UUID
  term_id: UUID
  new_name: str

UpdateTermDescription:
  taxonomy_id: UUID
  owner_id: UUID
  term_id: UUID
  description: str | None

MoveTerm:
  taxonomy_id: UUID
  owner_id: UUID
  term_id: UUID
  new_parent_id: UUID | None

DeleteTerm:
  taxonomy_id: UUID
  owner_id: UUID
  term_id: UUID

RecoverTerm:
  taxonomy_id: UUID
  owner_id: UUID
  term_id: UUID

ReorderTerms:
  taxonomy_id: UUID
  owner_id: UUID
  term_ids: list[UUID]
  parent_id: UUID | None = None
```

---

## 12. Repository Interface

Single repository for the aggregate — terms are loaded/saved with the taxonomy.

```
TaxonomyRepository (Protocol):
  + save(taxonomy: Taxonomy) -> None
      Persists taxonomy and all its terms (upsert semantics)

  + find_by_id(
      taxonomy_id: UUID,
      include_deleted: bool = False
    ) -> Taxonomy | None
      Loads taxonomy with all terms. Returns None if not found.
      If include_deleted=False, returns None for deleted taxonomies.

  + find_by_owner(
      owner_id: UUID,
      include_deleted: bool = False
    ) -> list[Taxonomy]
      All taxonomies for a user (each loaded with terms).

  + exists_by_name_for_owner(
      name: TaxonomyName,
      owner_id: UUID,
      exclude_taxonomy_id: UUID | None = None
    ) -> bool
      Case-insensitive name uniqueness check.
      exclude_taxonomy_id: for rename operations (exclude self).
```

---

## 13. Unit of Work

```
AbstractClassificationUnitOfWork (extends AbstractUnitOfWork):
  taxonomies: TaxonomyRepository

  + commit() -> None     [abstract]
  + rollback() -> None   [abstract]
```

---

## 14. TaxonomyManagementService

Application service covering all taxonomy and term operations. Uses UoW pattern.

```
TaxonomyManagementService:
  __init__(uow: AbstractClassificationUnitOfWork)

  # --- Taxonomy operations ---

  + create_taxonomy(cmd: CreateTaxonomy) -> Taxonomy
      1. Create TaxonomyName (validates format)
      2. Check name uniqueness for owner
         Raises: TaxonomyNameAlreadyExistsError
      3. Taxonomy.create(...)
      4. Persist via uow, commit, return

  + rename_taxonomy(cmd: RenameTaxonomy) -> None
      1. Load taxonomy, verify ownership
      2. Create TaxonomyName (validates format)
      3. Check name uniqueness (exclude self)
         Raises: TaxonomyNameAlreadyExistsError
      4. taxonomy.rename(new_name)
      5. Persist via uow, commit

  + update_taxonomy_description(cmd: UpdateTaxonomyDescription) -> None
      1. Load taxonomy, verify ownership
      2. taxonomy.update_description(description)
      3. Persist via uow, commit

  + soft_delete_taxonomy(cmd: SoftDeleteTaxonomy) -> None
      1. Load taxonomy (include_deleted=True), verify ownership
      2. taxonomy.soft_delete(deleted_by=cmd.owner_id)
      3. Persist via uow, commit

  + recover_taxonomy(cmd: RecoverTaxonomy) -> None
      1. Load taxonomy (include_deleted=True), verify ownership
      2. taxonomy.recover()
      3. Persist via uow, commit

  # --- Term operations ---

  + add_term(cmd: AddTerm) -> TaxonomyTerm
      1. Load taxonomy, verify ownership
      2. Create TermName (validates format)
      3. taxonomy.add_term(name, parent_term_id, description)
         (Aggregate enforces: active, max terms, uniqueness, parent checks)
      4. Persist via uow, commit, return term

  + rename_term(cmd: RenameTerm) -> None
      1. Load taxonomy, verify ownership
      2. Create TermName (validates format)
      3. taxonomy.rename_term(term_id, new_name)
      4. Persist via uow, commit

  + update_term_description(cmd: UpdateTermDescription) -> None
      1. Load taxonomy, verify ownership
      2. taxonomy.update_term_description(term_id, description)
      3. Persist via uow, commit

  + move_term(cmd: MoveTerm) -> None
      1. Load taxonomy, verify ownership
      2. taxonomy.move_term(term_id, new_parent_id)
         (Aggregate enforces: cycle detection, parent checks)
      3. Persist via uow, commit

  + delete_term(cmd: DeleteTerm) -> None
      1. Load taxonomy, verify ownership
      2. taxonomy.delete_term(term_id, deleted_by=cmd.owner_id)
         (Aggregate handles cascade to descendants)
      3. Persist via uow, commit

  + recover_term(cmd: RecoverTerm) -> None
      1. Load taxonomy, verify ownership
      2. taxonomy.recover_term(term_id)
         (Aggregate checks parent is active)
      3. Persist via uow, commit

  + reorder_terms(cmd: ReorderTerms) -> None
      1. Load taxonomy, verify ownership
      2. taxonomy.reorder_terms(term_ids, parent_id)
      3. Persist via uow, commit

  # --- Queries ---

  + get_taxonomy(taxonomy_id: UUID, owner_id: UUID) -> Taxonomy
      Load and verify ownership. Raises TaxonomyNotFoundError.

  + list_taxonomies(owner_id: UUID) -> list[Taxonomy]
      Return all active taxonomies for user.

  # --- Private helpers ---

  - _load_taxonomy(taxonomy_id: UUID, include_deleted: bool = False) -> Taxonomy
      Load taxonomy or raise TaxonomyNotFoundError

  - _verify_ownership(taxonomy: Taxonomy, owner_id: UUID) -> None
      Raise TaxonomyNotFoundError if owner_id doesn't match
      (Don't leak existence of other users' taxonomies)
```

---

## 15. Acceptance Criteria

### Taxonomy CRUD

- [ ] User can create a taxonomy with a unique name
- [ ] Duplicate taxonomy name for same user raises `TaxonomyNameAlreadyExistsError`
- [ ] Taxonomy name is case-insensitive for uniqueness
- [ ] User can rename a taxonomy with uniqueness check (excluding self)
- [ ] User can update taxonomy description (or set to None)
- [ ] Description exceeding max length raises `TaxonomyDescriptionTooLongError`
- [ ] `TaxonomyCreated` event emitted on creation
- [ ] `TaxonomyRenamed` event emitted on rename
- [ ] `TaxonomyDescriptionUpdated` event emitted on description change
- [ ] Ownership is verified for all operations
- [ ] Non-owner gets `TaxonomyNotFoundError` (no existence leak)

### Term Management

- [ ] Can add a root term (parent_term_id = None)
- [ ] Can add a child term with valid parent_term_id
- [ ] Can add term with optional description
- [ ] Term name must be unique within taxonomy (globally) — raises `TermNameAlreadyExistsError`
- [ ] Term name uniqueness is case-insensitive
- [ ] Cannot add term to deleted taxonomy — raises `TaxonomyNotActiveError`
- [ ] Cannot add child to deleted parent — raises `ParentTermDeletedError`
- [ ] Cannot exceed MAX_TERMS_PER_TAXONOMY — raises `MaxTermsExceededError`
- [ ] Sort order is automatically assigned among siblings
- [ ] `TermAdded` event emitted
- [ ] Can rename a term with uniqueness check
- [ ] Can update term description (or set to None)
- [ ] Term description exceeding max length raises `TermDescriptionTooLongError`

### Hierarchy Operations

- [ ] Moving a term changes its parent_term_id
- [ ] Moving to root sets parent_term_id = None
- [ ] Cannot move term under itself — raises `CannotBeOwnParentError`
- [ ] Cannot create circular reference — raises `CircularReferenceError`
- [ ] Cycle detection works at arbitrary depth
- [ ] Moving to same parent is a no-op (no event emitted)
- [ ] Sort order assigned to end of new siblings after move
- [ ] `TermMoved` event emitted
- [ ] Reordering updates sort_order for all specified siblings
- [ ] Reorder requires complete active sibling set — raises `IncompleteReorderError`
- [ ] Duplicate term_ids in reorder raises `IncompleteReorderError`
- [ ] `TermsReordered` event emitted

### Query Methods

- [ ] `get_term_path()` returns full hierarchy (e.g., "Food > Restaurants > Italian")
- [ ] `get_term_depth()` returns correct level (root = 0)
- [ ] `get_children()` returns active direct children sorted by sort_order
- [ ] `get_descendants()` returns all active descendants recursively
- [ ] `get_root_terms()` returns active root-level terms sorted by sort_order
- [ ] `active_term_count` returns number of active terms

### Lifecycle

- [ ] Soft deleting taxonomy cascades to all active terms
- [ ] `TaxonomySoftDeleted` event includes cascade term count
- [ ] Recovering taxonomy does NOT auto-recover terms
- [ ] Soft deleting a term cascades to all descendant terms
- [ ] `TermDeleted` event includes descendants_deleted count
- [ ] Recovering a term requires taxonomy to be active
- [ ] Recovering a term requires parent to be active — raises `ParentTermDeletedError`
- [ ] Recovering a term does NOT auto-recover children

### Aggregate Boundary

- [ ] Terms are loaded/saved with the taxonomy (single repository)
- [ ] No separate TaxonomyTermRepository
- [ ] All term invariants enforced by Taxonomy aggregate methods
- [ ] Version incremented on every mutation (_touch via AggregateRoot)
