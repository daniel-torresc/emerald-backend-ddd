# Spec 013: Classification & Taxonomies

**Status:** Draft
**Bounded Context:** Classification (Supporting Domain)
**Dependencies:** 001 (Shared Kernel), 002 (User Registration & Identity), 006 (Data Lifecycle Management)
**Blocks:** 014 (Transaction Categorization)

---

## 1. Overview

This spec defines the Taxonomy aggregate — a user-defined hierarchical classification system. Taxonomies provide flexible, unlimited-depth tree structures for organizing financial data. The primary use case is transaction categorization (e.g., "Food > Restaurants > Italian"), but the model is generic enough to support other classification needs.

**Key Principle:** Taxonomies are user-owned, hierarchical, and unlimited in depth. Term names are unique within a taxonomy (case-insensitive). The hierarchy must never contain circular references. System taxonomies are platform-provided and cannot be deleted by users.

## 2. Scope

### In Scope

- Taxonomy aggregate with all invariants
- Taxonomy entity (root)
- TaxonomyTerm entity (hierarchical tree nodes)
- `TaxonomyName`, `TermName`, `TaxonomyPath` value objects
- Hierarchy operations: add term, move term, rename term, delete term
- Cycle detection algorithm
- System taxonomies (platform-provided defaults)
- Sort ordering among sibling terms

### Out of Scope

- Transaction-term association (Spec 014)
- Auto-categorization rules and ML (future — Phase 2)
- Sharing taxonomies between users (not specified in requirements)

## 3. Value Objects

### 3.1 TaxonomyName

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Taxonomy display name |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Validate and normalize | `InvalidTaxonomyNameError` |
| `__eq__` / `__hash__` | Case-insensitive comparison | - |
| `normalized() -> str` | Lowercase, trimmed for uniqueness | - |

**Business Rules:**

- Must be non-empty after trimming
- Maximum length: 100 characters
- Uniqueness is per-user, case-insensitive (enforced by domain service)

### 3.2 TermName

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | Term display name |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Validate and normalize | `InvalidTermNameError` |
| `__eq__` / `__hash__` | Case-insensitive comparison | - |
| `normalized() -> str` | Lowercase, trimmed for uniqueness | - |

**Business Rules:**

- Must be non-empty after trimming
- Maximum length: 100 characters
- Uniqueness is within a single taxonomy, case-insensitive

### 3.3 TaxonomyPath

Represents the full hierarchy path from root to a term.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| segments | list[str] | Ordered term names from root to leaf |

**Behavior:**

| Method | Description |
|--------|-------------|
| `depth() -> int` | Number of segments (0 for root terms) |
| `parent_path() -> TaxonomyPath?` | Path without the last segment (None for root) |
| `__str__() -> str` | Formatted as "Food > Restaurants > Italian" |

**Construction:**

```
TaxonomyPath(segments=["Food", "Restaurants", "Italian"])
str(path) → "Food > Restaurants > Italian"
path.depth() → 2  (zero-indexed: root=0, child=1, grandchild=2)
```

## 4. Taxonomy Entity

### 4.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| taxonomy_id | UUID | No | Unique identifier |
| owner_id | UUID | No | User who owns this taxonomy |
| name | TaxonomyName | Yes | Display name (unique per user) |
| description | str? | Yes | Optional description |
| is_system | bool | No | System-provided (immutable, not deletable) |
| created_at | datetime | No | Creation time |
| updated_at | datetime | Auto | Last update time |
| deleted_at | datetime? | Yes | Soft delete timestamp |

### 4.2 Domain Methods

```
Taxonomy:
  // Creation
  + create(
      owner_id: UUID,
      name: TaxonomyName,
      description: str? = None,
      is_system: bool = False
    ) -> Taxonomy                                      [class method]
      Creates: Taxonomy entity with empty terms collection
      Note: Name uniqueness checked by domain service
      Emits: TaxonomyCreated

  // Updates
  + rename(new_name: TaxonomyName) -> None
      Validates: not a system taxonomy (system taxonomies can't be renamed by users)
      Updates: name, updated_at
      Note: Uniqueness checked by domain service
      Raises: SystemTaxonomyNotModifiableError

  + update_description(description: str?) -> None
      Updates: description, updated_at

  // Lifecycle
  + soft_delete(deleted_by: UUID) -> None
      Validates:
        - Not a system taxonomy
        - Not already deleted
      Cascades: soft deletes all terms
      Emits: TaxonomySoftDeleted
      Raises: SystemTaxonomyNotDeletableError, AlreadyDeletedError

  + recover() -> None
      Validates: is soft deleted
      Clears: deletion fields
      Note: Terms remain in trash (recovered individually)
      Emits: TaxonomyRecovered
      Raises: NotDeletedError
```

## 5. TaxonomyTerm Entity

### 5.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| term_id | UUID | No | Unique identifier |
| taxonomy_id | UUID | No | Parent taxonomy |
| name | TermName | Yes | Display name |
| description | str? | Yes | Optional description |
| parent_term_id | UUID? | Yes | Parent term (None = root level) |
| sort_order | int | Yes | Display order among siblings |
| created_at | datetime | No | Creation time |
| updated_at | datetime | Auto | Last update time |
| deleted_at | datetime? | Yes | Soft delete timestamp |

### 5.2 Computed Properties

| Property | Type | Description |
|----------|------|-------------|
| path | TaxonomyPath | Full path from root to this term |
| depth | int | Level in tree (0 = root) |
| has_children | bool | Whether this term has active child terms |
| child_count | int | Number of direct active children |

## 6. Taxonomy Aggregate — Term Operations

Terms are managed through the Taxonomy aggregate to enforce invariants:

### 6.1 Add Term

```
Taxonomy:
  + add_term(
      name: TermName,
      parent_term_id: UUID? = None
    ) -> TaxonomyTerm
      Validates:
        1. Taxonomy is active (not deleted)
           Raises: TaxonomyNotActiveError
        2. Name is unique within this taxonomy (case-insensitive)
           Raises: TermNameAlreadyExistsError
        3. If parent_term_id provided:
           a. Parent exists in this taxonomy
              Raises: ParentTermNotFoundError
           b. Parent is not deleted
              Raises: ParentTermDeletedError
      Creates:
        - TaxonomyTerm with next sort_order among siblings
      Emits: TermAdded
      Returns: the created term
```

### 6.2 Move Term

```
Taxonomy:
  + move_term(term_id: UUID, new_parent_id: UUID?) -> None
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
        3. new_parent_id differs from current parent (no-op check)
      Updates:
        - term.parent_term_id = new_parent_id
        - Recalculate sort_order for new siblings
        - updated_at
      Emits: TermMoved
```

### 6.3 Rename Term

```
Taxonomy:
  + rename_term(term_id: UUID, new_name: TermName) -> None
      Validates:
        1. Term exists in this taxonomy and is active
           Raises: TermNotFoundError
        2. New name is unique within this taxonomy (case-insensitive)
           Raises: TermNameAlreadyExistsError
      Updates: term.name, term.updated_at
      Emits: TermRenamed
```

### 6.4 Delete Term

```
Taxonomy:
  + delete_term(term_id: UUID, deleted_by: UUID) -> None
      Validates:
        1. Term exists in this taxonomy
           Raises: TermNotFoundError
        2. Term is not already deleted
           Raises: AlreadyDeletedError
      Effect:
        - Soft delete the term
        - Cascade: soft delete all descendant terms (children, grandchildren, etc.)
        - Recalculate sort_order for remaining siblings
      Emits: TermDeleted (for each affected term)
```

### 6.5 Recover Term

```
Taxonomy:
  + recover_term(term_id: UUID) -> None
      Validates:
        1. Term exists and is deleted
           Raises: NotDeletedError
        2. Taxonomy is active
           Raises: TaxonomyNotActiveError
        3. If term has a parent: parent is active
           Raises: ParentTermDeletedError
      Effect:
        - Recover the term (clear deletion fields)
        - Children remain in trash
      Emits: TermRecovered
```

### 6.6 Reorder Terms

```
Taxonomy:
  + reorder_terms(term_ids: list[UUID], parent_id: UUID? = None) -> None
      Validates:
        1. All term_ids exist in this taxonomy and are active
        2. All term_ids share the same parent (parent_id)
        3. term_ids contains all siblings under parent_id (complete set)
           Raises: IncompleteReorderError
      Effect:
        - Updates sort_order to match the provided order
      Emits: TermsReordered
```

## 7. Cycle Detection

The cycle detection algorithm prevents circular references when moving terms.

### 7.1 Algorithm

```
detect_cycle(term_id: UUID, new_parent_id: UUID?) -> bool:
    """Returns True if moving term_id under new_parent_id would create a cycle."""
    if new_parent_id is None:
        return False  # Moving to root — no cycle possible

    current = new_parent_id
    while current is not None:
        if current == term_id:
            return True  # Cycle detected!
        current = terms[current].parent_term_id
    return False
```

### 7.2 Examples

```
Tree:
  A
  ├── B
  │   ├── C
  │   └── D
  └── E

move_term(A, new_parent=C):
  Check: C.parent = B, B.parent = A, A == A → CYCLE! ✗

move_term(C, new_parent=E):
  Check: E.parent = A, A.parent = None → no cycle ✓

move_term(B, new_parent=B):
  Check: B == B → CYCLE! ✗ (self-reference, caught by separate validation)

move_term(D, new_parent=None):
  new_parent is None → no cycle ✓ (moving to root)
```

## 8. System Taxonomies

### 8.1 Definition

System taxonomies are platform-provided, pre-populated classification systems. They serve as sensible defaults that users can use immediately.

| System Taxonomy | Description | Default Terms |
|-----------------|-------------|---------------|
| Categories | Standard spending categories | Food, Transport, Shopping, Entertainment, Bills, Health, etc. |

### 8.2 System Taxonomy Rules

| Rule | Description |
|------|-------------|
| Cannot be deleted | `soft_delete()` raises `SystemTaxonomyNotDeletableError` |
| Cannot be renamed by user | `rename()` raises `SystemTaxonomyNotModifiableError` |
| Terms are modifiable | Users CAN add, rename, move, and delete terms within system taxonomies |
| Created per user | Each user gets their own copy of system taxonomies at registration |
| `is_system = True` | Immutable flag set at creation |

### 8.3 System Taxonomy Provisioning

```
TaxonomyProvisioningService:
  + provision_default_taxonomies(user_id: UUID) -> list[Taxonomy]
      Creates default system taxonomies for a new user:
        1. Create "Categories" taxonomy (is_system=True)
        2. Populate with default category terms
        3. Return created taxonomies
      Triggered by: UserRegistered event (or during registration flow)
```

## 9. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `TaxonomyCreated` | `Taxonomy.create()` | taxonomy_id, owner_id, name, is_system |
| `TaxonomyRenamed` | `Taxonomy.rename()` | taxonomy_id, old_name, new_name |
| `TaxonomySoftDeleted` | `soft_delete()` | taxonomy_id, deleted_by |
| `TaxonomyRecovered` | `recover()` | taxonomy_id |
| `TermAdded` | `add_term()` | term_id, taxonomy_id, name, parent_term_id |
| `TermMoved` | `move_term()` | term_id, old_parent_id, new_parent_id |
| `TermRenamed` | `rename_term()` | term_id, old_name, new_name |
| `TermDeleted` | `delete_term()` | term_id, taxonomy_id, deleted_by |
| `TermRecovered` | `recover_term()` | term_id, taxonomy_id |
| `TermsReordered` | `reorder_terms()` | taxonomy_id, parent_id, new_order |

## 10. Domain Errors

| Error | Trigger | Description |
|-------|---------|-------------|
| `InvalidTaxonomyNameError` | TaxonomyName construction | Empty or too long |
| `InvalidTermNameError` | TermName construction | Empty or too long |
| `TaxonomyNameAlreadyExistsError` | Duplicate name for same user | Case-insensitive uniqueness |
| `TermNameAlreadyExistsError` | Duplicate name within taxonomy | Case-insensitive uniqueness |
| `TermNotFoundError` | Term doesn't exist in taxonomy | Wrong ID or wrong taxonomy |
| `ParentTermNotFoundError` | Parent term doesn't exist | Invalid parent_term_id |
| `ParentTermDeletedError` | Parent term is soft deleted | Cannot add child to deleted parent |
| `CannotBeOwnParentError` | Moving term under itself | Self-reference |
| `CircularReferenceError` | Move would create a cycle | Detected by cycle detection |
| `SystemTaxonomyNotDeletableError` | Deleting system taxonomy | System taxonomies are permanent |
| `SystemTaxonomyNotModifiableError` | Renaming system taxonomy | System taxonomy name is fixed |
| `TaxonomyNotActiveError` | Operation on deleted taxonomy | Taxonomy is soft deleted |
| `IncompleteReorderError` | Reorder doesn't include all siblings | Must reorder complete set |

## 11. Domain Service

```
TaxonomyManagementService:
  + create_taxonomy(
      owner_id: UUID,
      name: str,
      description: str? = None
    ) -> Taxonomy
      1. Create TaxonomyName (validates format)
      2. Check name uniqueness for this user
         Raises: TaxonomyNameAlreadyExistsError
      3. Taxonomy.create(...)
      4. Persist and return

  + rename_taxonomy(
      taxonomy_id: UUID,
      owner_id: UUID,
      new_name: str
    ) -> None
      1. Load taxonomy, verify ownership
      2. Create TaxonomyName (validates format)
      3. Check uniqueness for this user
         Raises: TaxonomyNameAlreadyExistsError
      4. taxonomy.rename(new_name)
      5. Persist
```

## 12. Repository Interface

```
TaxonomyRepository (Protocol):
  + save(taxonomy: Taxonomy) -> None
  + find_by_id(taxonomy_id: UUID) -> Taxonomy?
  + find_by_owner(owner_id: UUID, include_deleted: bool = False) -> list[Taxonomy]
  + exists_by_name_for_owner(name: TaxonomyName, owner_id: UUID) -> bool

TaxonomyTermRepository (Protocol):
  + save(term: TaxonomyTerm) -> None
  + save_many(terms: list[TaxonomyTerm]) -> None
  + find_by_id(term_id: UUID) -> TaxonomyTerm?
  + find_by_taxonomy(
      taxonomy_id: UUID,
      include_deleted: bool = False
    ) -> list[TaxonomyTerm]
  + find_children(
      parent_term_id: UUID?,
      taxonomy_id: UUID,
      include_deleted: bool = False
    ) -> list[TaxonomyTerm]
  + find_descendants(term_id: UUID) -> list[TaxonomyTerm]
      All descendants (for cascade operations)
  + exists_by_name_in_taxonomy(name: TermName, taxonomy_id: UUID) -> bool
```

## 13. Acceptance Criteria

### Taxonomy CRUD

- [ ] User can create a taxonomy with a unique name
- [ ] Duplicate taxonomy name for same user raises `TaxonomyNameAlreadyExistsError`
- [ ] Taxonomy name is case-insensitive for uniqueness
- [ ] User can rename a non-system taxonomy
- [ ] Renaming a system taxonomy raises `SystemTaxonomyNotModifiableError`
- [ ] `TaxonomyCreated` event emitted on creation

### Term Management

- [ ] Can add a root term (parent_term_id = None) to a taxonomy
- [ ] Can add a child term with valid parent_term_id
- [ ] Term name must be unique within taxonomy — raises `TermNameAlreadyExistsError`
- [ ] Term name uniqueness is case-insensitive
- [ ] Cannot add term to deleted taxonomy — raises `TaxonomyNotActiveError`
- [ ] Cannot add child to deleted parent — raises `ParentTermDeletedError`
- [ ] Sort order is automatically assigned among siblings
- [ ] `TermAdded` event emitted

### Hierarchy Operations

- [ ] Moving a term changes its parent_term_id
- [ ] Moving to root sets parent_term_id = None
- [ ] Cannot move term under itself — raises `CannotBeOwnParentError`
- [ ] Cannot create circular reference — raises `CircularReferenceError`
- [ ] Cycle detection works at arbitrary depth
- [ ] Parent must belong to same taxonomy — raises `ParentTermNotFoundError`
- [ ] Reordering updates sort_order for all specified siblings
- [ ] Reorder requires complete sibling set — raises `IncompleteReorderError`

### Computed Properties

- [ ] `path` returns full hierarchy from root (e.g., "Food > Restaurants > Italian")
- [ ] `depth` returns correct level (root = 0)
- [ ] `has_children` returns True when active children exist
- [ ] `child_count` returns number of direct active children

### System Taxonomies

- [ ] System taxonomies are created per user on registration
- [ ] System taxonomies have `is_system = True`
- [ ] Cannot delete system taxonomy — raises `SystemTaxonomyNotDeletableError`
- [ ] CAN add, rename, move, and delete terms within system taxonomies
- [ ] Default "Categories" taxonomy created with standard spending terms

### Lifecycle

- [ ] Soft deleting taxonomy cascades to all terms
- [ ] Cannot delete system taxonomy
- [ ] Recovering taxonomy does not auto-recover terms
- [ ] Soft deleting a term cascades to all descendant terms
- [ ] Recovering a term requires parent to be active
- [ ] Recovering a term does not auto-recover children
