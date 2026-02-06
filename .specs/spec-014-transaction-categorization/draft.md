# Spec 014: Transaction Categorization

**Status:** Draft
**Bounded Context:** Classification (Supporting Domain)
**Dependencies:** 009 (Transaction Management), 013 (Classification & Taxonomies)
**Blocks:** None

---

## 1. Overview

This spec defines the association between transactions and taxonomy terms — the mechanism by which users classify their financial activity. A transaction can be tagged with terms from multiple taxonomies (e.g., a "Category" and a "Project"), but only one term per taxonomy. Categorization can be done manually by the user or (in the future) automatically via rules or ML.

**Key Principle:** Categorization is a cross-context concern that connects Core Finance (transactions) with Classification (taxonomies). The association is its own entity, not embedded in either the Transaction or TaxonomyTerm. Each split child can be categorized independently from its parent.

## 2. Scope

### In Scope

- `TransactionTermAssignment` entity
- Assign a term to a transaction (manual)
- Reassign a term (replace within same taxonomy)
- Remove a term assignment
- One term per taxonomy per transaction constraint
- Multi-taxonomy support (transaction can have terms from different taxonomies)
- Split child independent categorization
- Assignment query capabilities

### Out of Scope

- Auto-categorization rules (Phase 2 — rule-based: "If merchant contains 'Amazon' → Shopping")
- ML-based categorization (Phase 2)
- Suggestion mode (Phase 2 — suggest but don't auto-apply)
- Bulk categorization (can be built as extension of Spec 012 bulk update)

## 3. TransactionTermAssignment Entity

### 3.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| assignment_id | UUID | No | Unique identifier |
| transaction_id | UUID | No | Transaction being categorized |
| term_id | UUID | No | Term being applied |
| taxonomy_id | UUID | No | Which taxonomy the term belongs to |
| assigned_at | datetime | No | When assigned |
| assigned_by | AssignmentSource | No | Who/what assigned |
| confidence | float? | No | For auto-categorization: confidence score (0.0-1.0) |

### 3.2 AssignmentSource

**Value Object:**

| Attribute | Type | Description |
|-----------|------|-------------|
| source_type | AssignmentSourceType | How the assignment was made |
| user_id | UUID? | User who assigned (if manual) |
| rule_id | UUID? | Rule that triggered (if rule-based, future) |

**Enum — AssignmentSourceType:**

| Value | Description |
|-------|-------------|
| MANUAL | User explicitly assigned |
| RULE | Auto-categorization rule (future) |
| ML | Machine learning model (future) |

**Rules:**

- `user_id` is required for MANUAL, None for RULE/ML
- `confidence` is None for MANUAL, required for RULE/ML
- For Phase 1, only MANUAL assignments are supported

## 4. Assignment Rules

### 4.1 One Term Per Taxonomy

A transaction can have at most **one** term from each taxonomy, but can have terms from **multiple** different taxonomies simultaneously.

```
Transaction "Coffee at Starbucks" (-4.50):
  ├── Categories taxonomy: "Food > Coffee"          ✓
  ├── Projects taxonomy: "Personal"                  ✓
  └── Categories taxonomy: "Dining > Restaurants"    ✗ (already has a Categories term)
```

### 4.2 Assignment Constraint

```
Before assigning term T from taxonomy X to transaction:
  1. Check if transaction already has a term from taxonomy X
     ├── Yes → This is a REASSIGNMENT (replace the existing assignment)
     └── No  → This is a NEW assignment
```

### 4.3 Split Child Independence

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

## 5. Domain Methods

### 5.1 Categorization Service

Categorization spans two bounded contexts (Core Finance and Classification), so it lives in an application-level service that coordinates between them:

```
TransactionCategorizationService:

  + assign_term(
      transaction_id: UUID,
      term_id: UUID,
      assigned_by_user_id: UUID
    ) -> TransactionTermAssignment
      1. Load transaction — verify it exists and is active
         Raises: TransactionNotFoundError
      2. Verify user has EDITOR permission on the transaction's account
         Raises: InsufficientPermissionError
      3. Load term — verify it exists and is active
         Raises: TermNotFoundError
      4. Determine taxonomy_id from term
      5. Check for existing assignment for this transaction + taxonomy
         ├── Exists → Remove old assignment, create new one (reassignment)
         └── None   → Create new assignment
      6. Create TransactionTermAssignment:
         - assigned_by = AssignmentSource(MANUAL, user_id)
         - confidence = None
      7. Persist
      8. Emit TransactionCategorized event
      Returns: the created assignment

  + remove_assignment(
      transaction_id: UUID,
      taxonomy_id: UUID,
      removed_by_user_id: UUID
    ) -> None
      1. Load transaction — verify exists and active
      2. Verify user has EDITOR permission
      3. Find assignment for transaction + taxonomy
         Raises: AssignmentNotFoundError
      4. Delete assignment (hard delete — no soft delete for assignments)
      5. Emit TransactionUncategorized event

  + reassign_term(
      transaction_id: UUID,
      new_term_id: UUID,
      assigned_by_user_id: UUID
    ) -> TransactionTermAssignment
      Convenience method — equivalent to assign_term() which handles
      replacement automatically. Included for semantic clarity.
      Delegates to: assign_term()

  + get_assignments(
      transaction_id: UUID
    ) -> list[TransactionTermAssignment]
      Returns: all active assignments for a transaction
      (one per taxonomy)

  + get_assignment_for_taxonomy(
      transaction_id: UUID,
      taxonomy_id: UUID
    ) -> TransactionTermAssignment?
      Returns: assignment for specific taxonomy, or None
```

### 5.2 Term Deletion Impact

When a taxonomy term is deleted (Spec 013), existing assignments referencing that term must be handled:

```
On TermDeleted event:
  1. Find all TransactionTermAssignments referencing the deleted term
  2. Remove those assignments (hard delete)
  3. Emit TransactionUncategorized for each affected transaction
```

**Rationale:** A deleted term is no longer a valid classification. Assignments are removed rather than preserved with a dangling reference. Users can recategorize affected transactions.

### 5.3 Taxonomy Deletion Impact

When an entire taxonomy is deleted (Spec 013), all assignments using any term from that taxonomy are removed:

```
On TaxonomySoftDeleted event:
  1. Find all TransactionTermAssignments where taxonomy_id matches
  2. Remove those assignments (hard delete)
  3. Emit TransactionUncategorized for each affected transaction
```

## 6. Query Capabilities

### 6.1 By Transaction

```
Find all categories for a transaction:
  SELECT * FROM transaction_term_assignments
  WHERE transaction_id = :id
  → Returns list of (taxonomy_name, term_name, term_path)
```

### 6.2 By Term

```
Find all transactions with a specific term:
  SELECT * FROM transaction_term_assignments
  WHERE term_id = :term_id
  → Used for: "Show me all 'Food > Restaurants' transactions"
```

### 6.3 By Taxonomy (Hierarchical)

```
Find all transactions under a term and its descendants:
  Given term "Food" with children "Groceries", "Restaurants", etc.
  1. Get all descendant term_ids for "Food"
  2. SELECT * FROM transaction_term_assignments
     WHERE term_id IN (:term_ids)
  → Used for: "Show me all Food transactions (including subcategories)"
```

### 6.4 Uncategorized Transactions

```
Find transactions without a term from a specific taxonomy:
  SELECT t.* FROM transactions t
  WHERE t.account_id = :account_id
  AND NOT EXISTS (
    SELECT 1 FROM transaction_term_assignments a
    WHERE a.transaction_id = t.transaction_id
    AND a.taxonomy_id = :taxonomy_id
  )
  → Used for: "Show me uncategorized transactions"
```

## 7. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `TransactionCategorized` | Term assigned to transaction | transaction_id, term_id, taxonomy_id, is_reassignment |
| `TransactionUncategorized` | Term removed from transaction | transaction_id, taxonomy_id, reason (manual/term_deleted/taxonomy_deleted) |

## 8. Domain Errors

| Error | Trigger | Description |
|-------|---------|-------------|
| `TermNotFoundError` | Term doesn't exist or is deleted | Invalid term_id |
| `TransactionNotFoundError` | Transaction doesn't exist or is deleted | Invalid transaction_id |
| `AssignmentNotFoundError` | No assignment for transaction + taxonomy | Nothing to remove |
| `InsufficientPermissionError` | User lacks EDITOR on account | Authorization failure |

## 9. Repository Interface

```
TransactionTermAssignmentRepository (Protocol):
  + save(assignment: TransactionTermAssignment) -> None
  + delete(assignment_id: UUID) -> None
      Hard delete (no soft delete for assignments)
  + delete_by_term(term_id: UUID) -> int
      Remove all assignments for a deleted term
      Returns: count of removed assignments
  + delete_by_taxonomy(taxonomy_id: UUID) -> int
      Remove all assignments for a deleted taxonomy
      Returns: count of removed assignments
  + find_by_transaction(transaction_id: UUID) -> list[TransactionTermAssignment]
  + find_by_transaction_and_taxonomy(
      transaction_id: UUID,
      taxonomy_id: UUID
    ) -> TransactionTermAssignment?
  + find_by_term(
      term_id: UUID,
      include_descendants: bool = False
    ) -> list[TransactionTermAssignment]
  + find_uncategorized_transactions(
      account_id: UUID,
      taxonomy_id: UUID
    ) -> list[UUID]
      Returns transaction_ids without an assignment in the given taxonomy
```

## 10. Acceptance Criteria

### Assignment

- [ ] User can assign a term to a transaction
- [ ] Assignment records transaction_id, term_id, taxonomy_id, assigned_at, assigned_by
- [ ] MANUAL assignment has user_id set and confidence = None
- [ ] Assigning requires EDITOR permission on the transaction's account
- [ ] `TransactionCategorized` event emitted on assignment

### One Per Taxonomy Constraint

- [ ] Transaction can have terms from multiple different taxonomies simultaneously
- [ ] Transaction can have at most one term per taxonomy
- [ ] Assigning a new term from the same taxonomy replaces the existing assignment
- [ ] Reassignment emits `TransactionCategorized` with `is_reassignment=True`
- [ ] Old assignment is removed (hard deleted) on reassignment

### Removal

- [ ] User can remove a term assignment from a transaction
- [ ] Removal is a hard delete (no trash for assignments)
- [ ] Removing a non-existent assignment raises `AssignmentNotFoundError`
- [ ] `TransactionUncategorized` event emitted on removal

### Split Child Independence

- [ ] Assigning a term to a split child does not affect the parent transaction
- [ ] Assigning a term to a parent does not affect split children
- [ ] Each split child can have its own independent term assignments
- [ ] Split children do not inherit categorization from parent

### Term/Taxonomy Deletion Impact

- [ ] Deleting a term removes all assignments referencing that term
- [ ] Deleting a taxonomy removes all assignments for any term in that taxonomy
- [ ] Affected transactions emit `TransactionUncategorized` events
- [ ] Recovering a term does NOT restore previously removed assignments

### Queries

- [ ] Can retrieve all assignments for a transaction
- [ ] Can retrieve all transactions for a specific term
- [ ] Can retrieve all transactions under a term and its descendants (hierarchical)
- [ ] Can find uncategorized transactions for a given taxonomy
