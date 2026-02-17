# Spec 014: Transaction Categorization

**Version:** 1.0
**Status:** Draft
**Date:** 2026-02-14
**Bounded Context:** Classification (Supporting Domain)
**Dependencies:** 009 (Transaction Management), 013 (Classification & Taxonomies)

---

## 1. Overview

This spec defines the association between transactions and taxonomy terms — the mechanism by which users classify their financial activity. A transaction can be tagged with terms from multiple taxonomies (e.g., a "Category" and a "Project"), but only one term per taxonomy. Phase 1 supports manual categorization only; auto-categorization (rules, ML) is deferred to Phase 2.

**Key Principle:** Categorization is a cross-context concern connecting Core Finance (transactions) with Classification (taxonomies). The `TransactionTermAssignment` entity lives in the Classification bounded context. Cross-context validation (transaction existence, account permissions) is handled via protocol ports following the Anti-Corruption Layer pattern.

---

## 2. Background & Context

### Problem Statement

Users need to classify transactions into meaningful categories (e.g., "Food > Restaurants", "Transport > Fuel") to understand spending patterns, generate reports, and track budgets. Without categorization, transactions are just raw financial data with no semantic meaning.

### Business Goals

- Enable manual transaction categorization using user-defined taxonomies (Spec 013)
- Support multi-taxonomy classification (e.g., "Category" + "Project" simultaneously)
- Maintain data integrity when terms, taxonomies, or transactions are deleted
- Lay the foundation for Phase 2 auto-categorization

### Success Metrics

- Users can assign terms to transactions and see categorized views
- One-term-per-taxonomy constraint is enforced at the domain level
- Cleanup cascades correctly on entity deletion (no orphaned assignments)

---

## 3. Scope

### In Scope

- `TransactionTermAssignment` entity (simple Entity, not AggregateRoot)
- Assign a term to a transaction (manual, by user with EDITOR permission)
- Replace within same taxonomy (reassignment handled transparently by assign)
- Remove a term assignment (hard delete)
- One term per taxonomy per transaction constraint
- Multi-taxonomy support
- Split child independent categorization
- Cross-context validation via `TransactionAccessPort` protocol
- Event handler protocol for lifecycle cascades (term/taxonomy/transaction deletion)
- Query capabilities (by transaction, by term, uncategorized)
- Commands, domain events, exceptions

### Out of Scope

- Auto-categorization rules (Phase 2)
- ML-based categorization (Phase 2)
- Suggestion mode (Phase 2)
- Bulk categorization (future extension of Spec 012)
- `AssignmentSource` value object with source types (Phase 2 — YAGNI for Phase 1)
- Confidence scores (Phase 2)
- Taxonomy sharing / cross-user taxonomy visibility (future spec)

---

## 4. Architecture

### Context Placement

The `TransactionTermAssignment` entity, its repository, and the `TransactionCategorizationService` live in the **Classification** bounded context. Cross-context checks are abstracted via protocol ports.

```
Classification Context
├── domain/
│   ├── models/
│   │   └── entities/
│   │       └── transaction_term_assignment.py
│   ├── events/
│   │   └── categorization_events.py
│   ├── exceptions/
│   │   └── categorization_errors.py
│   └── constants.py  (extended)
├── application/
│   ├── dtos/
│   │   └── commands/
│   │       └── categorization_commands.py
│   ├── ports/
│   │   ├── transaction_access_port.py      ← NEW: cross-context validation
│   │   ├── transaction_term_assignment_repository.py
│   │   └── unit_of_work.py                 ← EXTENDED: add assignments
│   └── services/
│       └── transaction_categorization_service.py
```

### Cross-Context Communication

```
┌────────────────────────┐         ┌──────────────────────────┐
│     Core Finance       │         │     Classification        │
│                        │         │                            │
│  Transaction           │◄────────│  TransactionAccessPort     │
│  Account + Shares      │ (port)  │  (verify active, editor)   │
│                        │         │                            │
│  TransactionSoftDeleted│────────►│  CategorizationEventHandler│
│  (domain event)        │ (event) │  (cleanup assignments)     │
└────────────────────────┘         └──────────────────────────┘
```

- **Classification → Core Finance:** Via `TransactionAccessPort` protocol (structural subtyping). Classification defines the port; infrastructure provides the adapter that delegates to Core Finance repositories.
- **Core Finance → Classification:** Via `CategorizationEventHandler` protocol. Classification defines the handler interface; infrastructure wires it to react to Core Finance domain events. Phase 1: synchronous call at composition root after UoW commit.

---

## 5. TransactionTermAssignment Entity

### 5.1 Design

Simple `Entity` (not AggregateRoot). Immutable after creation — no mutation methods. Created via factory method, deleted via hard-delete. No mixins needed. No own event collection (events are emitted by the service).

### 5.2 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| `id` | `UUID` | No | Unique assignment identifier (inherited from Entity) |
| `transaction_id` | `UUID` | No | Transaction being categorized |
| `term_id` | `UUID` | No | Term being applied |
| `taxonomy_id` | `UUID` | No | Denormalized — which taxonomy the term belongs to |
| `assigned_at` | `datetime` (UTC) | No | When the assignment was made |
| `assigned_by` | `UUID` | No | User who assigned the term |

**Design Notes:**

- `taxonomy_id` is denormalized for efficient one-per-taxonomy constraint enforcement and taxonomy-level queries without joining through terms.
- `assigned_by` is a simple UUID (not a VO). Phase 1 only supports manual assignment, so the assigner is always a user. When Phase 2 adds auto-categorization, an `AssignmentSource` VO can be introduced.
- Entity is effectively immutable — once created, it is only read or deleted. No update paths.

### 5.3 Factory Method

```
TransactionTermAssignment.create(
    transaction_id: UUID,
    term_id: UUID,
    taxonomy_id: UUID,
    assigned_by: UUID
) -> TransactionTermAssignment
```

Generates `id` and `assigned_at` internally.

### 5.4 Validation

- All UUIDs must be non-nil (not `UUID(int=0)`)
- `assigned_at` must be timezone-aware (UTC)
- `assigned_by` must be non-nil

---

## 6. Assignment Rules

### 6.1 One Term Per Taxonomy

A transaction can have at most **one** term from each taxonomy, but can have terms from **multiple** different taxonomies simultaneously.

```
Transaction "Coffee at Starbucks" (-4.50):
  ├── Categories taxonomy: "Food > Coffee"          OK
  ├── Projects taxonomy: "Personal"                  OK
  └── Categories taxonomy: "Dining > Restaurants"    REJECTED (already has a Categories term)
```

### 6.2 Assignment Behavior

When assigning term T from taxonomy X to a transaction:

```
1. Check if transaction already has a term from taxonomy X
   ├── Yes → REASSIGNMENT: delete old assignment, create new one
   └── No  → NEW assignment: create directly
```

The `assign_term` operation handles both cases transparently. A single service method — no separate "reassign" method.

### 6.3 Split Child Independence

| Rule | Description |
|------|-------------|
| Independent | Assigning a term to a split child does NOT affect the parent |
| Independent | Assigning a term to a parent does NOT affect split children |
| No inheritance | Children do not inherit parent's categorization |
| Each categorized separately | Each split child can have its own terms |

```
Transaction "Supermarket" (-85.00):
  ├── Category: (none — parent is split, categorize children instead)
  │
  ├── Split Child "Food" (-50.00):
  │   └── Category: "Food > Groceries"
  │
  ├── Split Child "Cleaning" (-25.00):
  │   └── Category: "Home > Cleaning Supplies"
  │
  └── Split Child "Medicine" (-10.00):
      └── Category: "Health > Pharmacy"
```

### 6.4 Permission Requirement

Assigning or removing a categorization requires **EDITOR** permission (or above) on the transaction's account. This is validated via `TransactionAccessPort`.

### 6.5 Term Validity

The term must exist and be active (not soft-deleted). The taxonomy must also be active. These checks happen via the `TaxonomyRepository` (same bounded context).

---

## 7. Ports (Protocol Interfaces)

### 7.1 TransactionAccessPort

Cross-context port for validating transaction state and account permissions. Defined in Classification, implemented by infrastructure (delegates to Core Finance).

```
TransactionAccessPort (Protocol):

  + verify_transaction_active(transaction_id: UUID) -> UUID
      Verifies the transaction exists and is active (not soft-deleted).
      Returns: the transaction's account_id (needed for permission check)
      Raises: TransactionNotActiveError if not found or deleted

  + verify_editor_permission(account_id: UUID, user_id: UUID) -> None
      Verifies the user has at least EDITOR permission on the account.
      Raises: InsufficientPermissionError if permission is insufficient
```

**Why combined port:** Both checks are needed together for every categorization operation. Grouping them reduces port proliferation.

### 7.2 CategorizationEventHandler

Event handler protocol for lifecycle cascades. Defined in Classification. Implemented by the `TransactionCategorizationService` (or a dedicated handler class). Called by other contexts/composition root when relevant events occur.

```
CategorizationEventHandler (Protocol):

  + handle_term_deleted(term_id: UUID) -> int
      Remove all assignments referencing the deleted term.
      Emit TransactionUncategorized for each affected transaction.
      Returns: count of removed assignments

  + handle_taxonomy_soft_deleted(taxonomy_id: UUID) -> int
      Remove all assignments for any term in the deleted taxonomy.
      Emit TransactionUncategorized for each affected transaction.
      Returns: count of removed assignments

  + handle_transaction_soft_deleted(transaction_id: UUID) -> int
      Remove all assignments for the deleted transaction.
      Emit TransactionUncategorized for each affected transaction.
      Returns: count of removed assignments
```

**Phase 1 Wiring:**
- **Term/taxonomy deletion (intra-context):** `TaxonomyManagementService` receives `CategorizationEventHandler` as a dependency. After deleting a term or taxonomy, calls the handler synchronously.
- **Transaction deletion (inter-context):** Composition root wires the handler to be called after `TransactionManagementService.soft_delete_transaction()` commits. Classification context has no dependency on Core Finance.

### 7.3 TransactionTermAssignmentRepository

```
TransactionTermAssignmentRepository (Protocol):

  + save(assignment: TransactionTermAssignment) -> None
      Persist a new assignment.

  + delete(assignment_id: UUID) -> None
      Hard delete a single assignment by ID.

  + delete_by_term(term_id: UUID) -> list[TransactionTermAssignment]
      Remove all assignments for a specific term.
      Returns: the deleted assignments (for event emission).

  + delete_by_taxonomy(taxonomy_id: UUID) -> list[TransactionTermAssignment]
      Remove all assignments for an entire taxonomy.
      Returns: the deleted assignments (for event emission).

  + delete_by_transaction(transaction_id: UUID) -> list[TransactionTermAssignment]
      Remove all assignments for a specific transaction.
      Returns: the deleted assignments (for event emission).

  + find_by_transaction(transaction_id: UUID) -> list[TransactionTermAssignment]
      All assignments for a transaction (one per taxonomy).

  + find_by_transaction_and_taxonomy(
      transaction_id: UUID,
      taxonomy_id: UUID
    ) -> TransactionTermAssignment | None
      Assignment for a specific transaction + taxonomy pair.

  + find_by_term(term_id: UUID) -> list[TransactionTermAssignment]
      All assignments referencing a specific term.

  + find_transaction_ids_by_term(term_id: UUID) -> list[UUID]
      Transaction IDs with a specific term assigned.
      Used for hierarchical queries (term + descendants).

  + find_uncategorized_transaction_ids(
      account_id: UUID,
      taxonomy_id: UUID
    ) -> list[UUID]
      Transaction IDs in the account WITHOUT an assignment in the given taxonomy.
      Note: Cross-context query — implementation is an infrastructure concern.
```

**Design Note:** Bulk delete methods (`delete_by_term`, `delete_by_taxonomy`, `delete_by_transaction`) return the deleted assignments so the service/handler can emit `TransactionUncategorized` events with full context (transaction_id, taxonomy_id).

### 7.4 Unit of Work (Extended)

Extend the existing `AbstractClassificationUnitOfWork`:

```
AbstractClassificationUnitOfWork:
  taxonomies: TaxonomyRepository           ← existing
  assignments: TransactionTermAssignmentRepository  ← NEW
```

---

## 8. Service

### TransactionCategorizationService

Application service that orchestrates categorization operations. Lives in Classification bounded context.

**Dependencies:**
- `AbstractClassificationUnitOfWork` (for assignments + taxonomies)
- `TransactionAccessPort` (for cross-context validation)

**Service-level events:** The service maintains its own `_events` list with `collect_events()` method (same pattern as `AuthenticationService` in IAM context).

```
TransactionCategorizationService:

  + assign_term(command: AssignTerm) -> TransactionTermAssignment
      1. Verify transaction is active via TransactionAccessPort
         → gets account_id
         Raises: TransactionNotActiveError
      2. Verify user has EDITOR permission via TransactionAccessPort
         Raises: InsufficientPermissionError
      3. Load taxonomy containing the term via TaxonomyRepository
         Raises: TaxonomyNotFoundError (if taxonomy deleted)
      4. Verify term exists and is active within taxonomy
         Raises: TermNotFoundError (if term doesn't exist or is deleted)
      5. Check for existing assignment for this transaction + taxonomy
         ├── Exists → Delete old assignment (hard delete)
         └── None   → Continue
      6. Create TransactionTermAssignment via factory
      7. Persist via repository
      8. Emit TransactionCategorized event
         (with is_reassignment=True if step 5 found existing)
      Returns: the created assignment

  + remove_assignment(command: RemoveAssignment) -> None
      1. Verify transaction is active via TransactionAccessPort
         → gets account_id
      2. Verify user has EDITOR permission via TransactionAccessPort
      3. Find assignment for transaction + taxonomy
         Raises: AssignmentNotFoundError
      4. Delete assignment (hard delete)
      5. Emit TransactionUncategorized event (reason=MANUAL)

  + get_assignments(transaction_id: UUID) -> list[TransactionTermAssignment]
      Returns all active assignments for a transaction (one per taxonomy).

  + get_assignment_for_taxonomy(
      transaction_id: UUID,
      taxonomy_id: UUID
    ) -> TransactionTermAssignment | None
      Returns assignment for specific transaction + taxonomy, or None.

  + get_transactions_by_term(
      term_id: UUID,
      include_descendants: bool = False
    ) -> list[UUID]
      Returns transaction IDs with the given term assigned.
      If include_descendants=True:
        1. Load taxonomy containing the term
        2. Get all descendant term IDs
        3. Query assignments for all term IDs (parent + descendants)
      If include_descendants=False:
        1. Query assignments for the single term_id

  + get_uncategorized_transactions(
      account_id: UUID,
      taxonomy_id: UUID
    ) -> list[UUID]
      Returns transaction IDs in the account without an assignment
      in the given taxonomy.
```

### CategorizationEventHandler Implementation

The `TransactionCategorizationService` also implements the `CategorizationEventHandler` protocol:

```
  + handle_term_deleted(term_id: UUID) -> int
      1. Delete all assignments for the term → get deleted list
      2. Emit TransactionUncategorized for each (reason=TERM_DELETED)
      3. Return count

  + handle_taxonomy_soft_deleted(taxonomy_id: UUID) -> int
      1. Delete all assignments for the taxonomy → get deleted list
      2. Emit TransactionUncategorized for each (reason=TAXONOMY_DELETED)
      3. Return count

  + handle_transaction_soft_deleted(transaction_id: UUID) -> int
      1. Delete all assignments for the transaction → get deleted list
      2. Emit TransactionUncategorized for each (reason=TRANSACTION_DELETED)
      3. Return count
```

---

## 9. Domain Events

All events are `@dataclass(frozen=True)` extending `DomainEvent`.

| Event | aggregate_type | aggregate_id | Key Data |
|-------|---------------|--------------|----------|
| `TransactionCategorized` | `"transaction"` | `transaction_id` | `term_id`, `taxonomy_id`, `assignment_id`, `assigned_by`, `is_reassignment` |
| `TransactionUncategorized` | `"transaction"` | `transaction_id` | `taxonomy_id`, `term_id`, `reason: UncategorizationReason` |

### UncategorizationReason

Value object enum:

| Value | Description |
|-------|-------------|
| `MANUAL` | User explicitly removed the assignment |
| `TERM_DELETED` | The assigned term was soft-deleted |
| `TAXONOMY_DELETED` | The term's taxonomy was soft-deleted |
| `TRANSACTION_DELETED` | The transaction was soft-deleted |

---

## 10. Commands

All commands are `@dataclass(frozen=True)` extending `Command`.

| Command | Fields | Description |
|---------|--------|-------------|
| `AssignTerm` | `transaction_id`, `term_id`, `user_id` | Assign a term to a transaction (handles reassignment) |
| `RemoveAssignment` | `transaction_id`, `taxonomy_id`, `user_id` | Remove the term assignment for a taxonomy |

**Note:** No commands for event-driven cleanup (term/taxonomy/transaction deletion). Those are handled by the `CategorizationEventHandler` protocol, not initiated by user commands.

---

## 11. Domain Exceptions

All exceptions extend the shared kernel hierarchy. Each has a unique `code`.

| Exception | Parent | Code | Trigger |
|-----------|--------|------|---------|
| `TransactionNotActiveError` | `NotFoundError` | `"TRANSACTION_NOT_ACTIVE"` | Transaction doesn't exist or is soft-deleted |
| `AssignmentNotFoundError` | `NotFoundError` | `"ASSIGNMENT_NOT_FOUND"` | No assignment for transaction + taxonomy pair |

**Reused from existing contexts (not redefined):**
- `TermNotFoundError` — already in Classification (Spec 013)
- `TaxonomyNotFoundError` — already in Classification (Spec 013)
- `InsufficientPermissionError` — already in Core Finance (Spec 008)
- `TaxonomyNotActiveError` — already in Classification (Spec 013)

**Note on `InsufficientPermissionError`:** The `TransactionAccessPort` raises this error. Since it's a port, the Classification context needs its own definition or re-imports from shared kernel. Given that `AuthorizationError` exists in the shared kernel, `InsufficientPermissionError` could be defined there if not already. The implementation adapter translates Core Finance errors to this shared exception.

---

## 12. Domain Constants

Added to `classification/domain/constants.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| (none needed for Phase 1) | — | No limits on assignments per transaction — bounded naturally by taxonomy count |

---

## 13. Lifecycle Cascades

### 13.1 Term Soft-Deleted (Spec 013)

When a taxonomy term is soft-deleted via `TaxonomyManagementService.delete_term()`:

1. `CategorizationEventHandler.handle_term_deleted(term_id)` is called
2. All assignments referencing `term_id` are hard-deleted
3. `TransactionUncategorized` event emitted per affected transaction (reason=`TERM_DELETED`)

**Rationale:** A deleted term is no longer a valid classification. Assignments are removed rather than preserved with a dangling reference.

### 13.2 Taxonomy Soft-Deleted (Spec 013)

When an entire taxonomy is soft-deleted via `TaxonomyManagementService.soft_delete_taxonomy()`:

1. `CategorizationEventHandler.handle_taxonomy_soft_deleted(taxonomy_id)` is called
2. All assignments where `taxonomy_id` matches are hard-deleted
3. `TransactionUncategorized` event emitted per affected transaction (reason=`TAXONOMY_DELETED`)

### 13.3 Transaction Soft-Deleted (Spec 009)

When a transaction is soft-deleted via Core Finance:

1. `CategorizationEventHandler.handle_transaction_soft_deleted(transaction_id)` is called
2. All assignments where `transaction_id` matches are hard-deleted
3. `TransactionUncategorized` event emitted per affected assignment (reason=`TRANSACTION_DELETED`)

**Wiring (Phase 1):** Synchronous call at composition root after Core Finance UoW commits. Classification has no compile-time dependency on Core Finance.

### 13.4 Recovery Does NOT Restore

Recovering a deleted term, taxonomy, or transaction does **not** restore previously removed assignments. Users must re-categorize manually. This is consistent with the project-wide recovery principle (Spec 006, 013).

### 13.5 Account Soft-Deleted

When an account is soft-deleted, its transactions are cascade-deleted (Spec 007/009). Each transaction's deletion triggers the cascade in 13.3 above. No special account-level handling needed.

---

## 14. Acceptance Criteria

### Assignment

- [ ] User can assign a term to a transaction
- [ ] Assignment records `transaction_id`, `term_id`, `taxonomy_id`, `assigned_at`, `assigned_by`
- [ ] `assigned_by` is the user's UUID
- [ ] Assigning requires EDITOR permission on the transaction's account (via `TransactionAccessPort`)
- [ ] Transaction must be active (not soft-deleted)
- [ ] Term must exist and be active within an active taxonomy
- [ ] `TransactionCategorized` event emitted on assignment

### One Per Taxonomy Constraint

- [ ] Transaction can have terms from multiple different taxonomies simultaneously
- [ ] Transaction can have at most one term per taxonomy
- [ ] Assigning a new term from the same taxonomy replaces the existing assignment (hard-deletes old, creates new)
- [ ] Reassignment emits `TransactionCategorized` with `is_reassignment=True`

### Removal

- [ ] User can remove a term assignment from a transaction (by taxonomy)
- [ ] Removal is a hard delete (no soft delete for assignments)
- [ ] Removing a non-existent assignment raises `AssignmentNotFoundError`
- [ ] Removal requires EDITOR permission on the transaction's account
- [ ] `TransactionUncategorized` event emitted with `reason=MANUAL`

### Split Child Independence

- [ ] Assigning a term to a split child does not affect the parent transaction
- [ ] Assigning a term to a parent does not affect split children
- [ ] Each split child can have its own independent term assignments
- [ ] Split children do not inherit categorization from parent

### Lifecycle Cascades

- [ ] Deleting a term removes all assignments referencing that term
- [ ] Deleting a taxonomy removes all assignments for any term in that taxonomy
- [ ] Deleting a transaction removes all assignments for that transaction
- [ ] All cascade removals emit `TransactionUncategorized` events with appropriate `reason`
- [ ] Recovering a term/taxonomy/transaction does NOT restore removed assignments
- [ ] Account deletion cascades through transactions to assignments

### Cross-Context Ports

- [ ] `TransactionAccessPort` protocol defined in Classification
- [ ] `CategorizationEventHandler` protocol defined in Classification
- [ ] Service uses ports for all cross-context validation (no direct imports from Core Finance domain)

### Queries

- [ ] Can retrieve all assignments for a transaction
- [ ] Can retrieve assignment for a specific transaction + taxonomy
- [ ] Can retrieve all transaction IDs for a specific term
- [ ] Can retrieve transaction IDs for a term and its descendants (hierarchical)
- [ ] Can find uncategorized transaction IDs for a given account + taxonomy

---

## 15. Public API Exports

Added to `classification/__init__.py`:

**Entities:** `TransactionTermAssignment`
**Events:** `TransactionCategorized`, `TransactionUncategorized`
**Value Objects:** `UncategorizationReason`
**Exceptions:** `TransactionNotActiveError`, `AssignmentNotFoundError`
**Commands:** `AssignTerm`, `RemoveAssignment`
**Ports:** `TransactionAccessPort`, `CategorizationEventHandler`, `TransactionTermAssignmentRepository`
**Services:** `TransactionCategorizationService`

---

## 16. Open Questions

None — all ambiguities resolved during clarification.

---

## 17. Glossary

- **Assignment:** A `TransactionTermAssignment` — the link between a transaction and a taxonomy term
- **Reassignment:** Replacing an existing assignment within the same taxonomy with a different term
- **Cascade:** Automatic removal of assignments when a related entity (term, taxonomy, transaction) is deleted
- **TransactionAccessPort:** Protocol for cross-context validation of transaction state and account permissions
- **CategorizationEventHandler:** Protocol for reacting to lifecycle events from other contexts
