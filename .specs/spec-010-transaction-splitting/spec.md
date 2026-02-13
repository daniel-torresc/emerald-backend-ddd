# Spec 010: Transaction Splitting

**Version:** 1.0
**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 009 (Transaction Management)
**Date:** 2025-02-13

---

## 1. Overview

This spec defines the transaction splitting capability — dividing a single transaction into multiple sub-transactions that sum exactly to the parent amount. Splitting enables users to categorize portions of a transaction differently (e.g., a grocery receipt with food, cleaning supplies, and pharmacy items) or to attribute portions to different purposes.

**Key Principle:** Split amounts must sum exactly to the parent transaction's amount. The parent is excluded from balance calculation when split children exist (to prevent double-counting). Splits are all-or-nothing for lifecycle operations — they move together during delete and recovery.

---

## 2. Background & Context

### Problem Statement

A single financial transaction often covers multiple expense categories. Without splitting, users cannot accurately categorize portions of a transaction (e.g., a $85 supermarket receipt that includes $50 food, $25 cleaning, and $10 pharmacy).

### Business Goals

- Enable granular categorization of multi-purpose transactions
- Maintain accurate balance calculations despite parent/child relationships
- Preserve data integrity through exact-sum validation
- Support undo (join) for user flexibility

### Success Metrics

- Split amounts always sum exactly to parent amount (zero tolerance)
- Balance calculations remain consistent before and after splitting
- Cascade operations (delete/recover) maintain parent-child integrity

---

## 3. Scope

### In Scope

- Split operation (parent → children)
- Join operation (undo split, hard-delete children)
- SplitRequest value object
- Split validation rules (sum, minimum count, maximum count, nesting prohibition)
- Balance calculation impact (parent exclusion)
- Split cascade behavior (soft delete, recovery, hard delete)
- Split child transaction creation
- Split child amount updates with sum re-validation
- Auto-join on parent amount update

### Out of Scope

- Transaction categorization on split children (Spec 014 — each child can be categorized independently)
- Bulk split operations (not specified in requirements)
- UI/UX for split interaction

---

## 4. Users & Personas

### Primary Users

Users with EDITOR or OWNER permission on an account who need to break down a transaction into categorizable portions.

### User Goals

- Split a transaction into 2–50 sub-transactions that sum exactly to the original
- Undo a split (join) to restore the parent to a regular transaction
- Update individual split child amounts while maintaining sum integrity
- Update split parent metadata (description, merchant, comments) without affecting children

---

## 5. Split Model

### 5.1 Parent-Child Relationship

```
┌──────────────────────────────────────────┐
│        Transaction (Parent)              │
│        amount: -85.00 EUR                │
│        description: "Supermarket"        │
│        _is_split_parent: True            │
│        parent_transaction_id: None       │
│                                          │
│  ► EXCLUDED from balance when split      │
└────────────────┬─────────────────────────┘
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ Child 1 │ │ Child 2 │ │ Child 3 │
   │ -50.00  │ │ -25.00  │ │ -10.00  │
   │ "Food"  │ │"Cleaning│ │"Pharmacy│
   │         │ │ stuff"  │ │  items" │
   └─────────┘ └─────────┘ └─────────┘
   parent_id    parent_id    parent_id
   = parent     = parent     = parent

   ► INCLUDED in balance (sum = -85.00)
```

### 5.2 Balance Calculation Impact

```
Without split:
  balance += parent.amount (-85.00)

With split:
  balance += child1.amount (-50.00)
           + child2.amount (-25.00)
           + child3.amount (-10.00)
           = -85.00 (same total)

  parent.amount is EXCLUDED (sum_amounts excludes split parents)
```

**Rule:** The balance calculation excludes transactions that are split parents. The `TransactionRepository.sum_amounts(exclude_split_parents=True)` already supports this. The exclusion is determined by the `_is_split_parent` flag on the entity, hydrated by the repository during load.

---

## 6. Value Objects

### 6.1 SplitRequest

**Value Object** — represents a single portion of a split operation.

| Attribute | Type | Validation | Description |
|-----------|------|------------|-------------|
| amount | Money | Required, same currency as parent | Amount for this split portion |
| description | str | Required, 1–500 chars, trimmed | Description for the child transaction |
| merchant | str \| None | Optional, max 200 chars, trimmed | Optional merchant for the child |
| comments | str \| None | Optional, max 1000 chars, trimmed | Optional comments for the child |

**Validation:** Uses same length constants as Transaction entity (`MAX_ORIGINAL_DESCRIPTION_LENGTH`, `MAX_MERCHANT_LENGTH`, `MAX_COMMENTS_LENGTH`).

---

## 7. Entity Changes

### 7.1 Transaction Entity Extensions

The Transaction entity gains a `_is_split_parent` flag and new domain methods:

**New field:**
- `_is_split_parent: bool` — defaults to `False`, hydrated by repository/service based on existence of active children

**New/modified methods:**

```
Transaction:
  // Split — creates child transactions
  + split(splits: list[SplitRequest], split_by: UUID) -> list[Transaction]
      Validates:
        1. Transaction is not deleted
           Raises: TransactionDeletedError
        2. Transaction is NOT a split child (parent_transaction_id is not None)
           Raises: CannotSplitChildError
        3. Transaction is NOT already a split parent (_is_split_parent is True)
           Raises: AlreadySplitError
        4. At least 2 splits provided
           Raises: MinimumSplitsRequiredError
        5. No more than MAX_SPLITS_PER_TRANSACTION (50) splits
           Raises: MaxSplitsExceededError
        6. All split amounts have same currency as this transaction
           Raises: CurrencyMismatchError (from shared kernel)
        7. Split amounts sum exactly to this.amount
           Raises: SplitAmountMismatchError
      Creates:
        - One child Transaction per split, with:
            - account_id = this.account_id
            - parent_transaction_id = this.id
            - transaction_date = this.transaction_date
            - value_date = this.value_date
            - amount = split.amount
            - original_description = split.description
            - merchant = split.merchant
            - comments = split.comments
            - review_status = REVIEWED
            - import_source = this.import_source (inherit)
            - external_id = None
            - card_id = this.card_id (inherit)
            - created_by = split_by
      Sets: _is_split_parent = True
      Emits: TransactionSplit
      Returns: list of created child transactions

  // Join (undo split) — marks parent as unsplit
  + join_splits(child_count: int) -> None
      Validates:
        1. Transaction is not deleted
           Raises: TransactionDeletedError
        2. Transaction IS a split parent (_is_split_parent is True)
           Raises: NotSplitParentError
      Sets: _is_split_parent = False
      Emits: TransactionSplitsJoined(removed_child_count=child_count)
      Note: Service is responsible for hard-deleting children from repository

  // Query helpers
  + is_split_parent -> bool (property)
      Returns: _is_split_parent flag value

  + is_split_child() -> bool (already exists)
      Returns: parent_transaction_id is not None
```

**Hydration:** The `_is_split_parent` flag is passed during entity reconstitution by the repository. When loading a transaction, the repository determines whether it has active children and sets the flag accordingly. The `Transaction.create()` factory always sets `_is_split_parent=False`.

### 7.2 Transaction Entity — Split-Aware Update Behavior

The existing `update_amount()` method on the Transaction entity does NOT change. The auto-join-on-amount-update behavior is handled by the service layer (see section 9).

Non-amount fields (description, merchant, comments, dates) can be freely updated on split parents without triggering auto-join.

---

## 8. Domain Constants

Add to `core_finance/domain/constants.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_SPLITS_PER_TRANSACTION` | 50 | Maximum number of children per split |
| `MIN_SPLITS_PER_TRANSACTION` | 2 | Minimum number of children per split |

---

## 9. Application Service

### 9.1 TransactionManagementService Extensions

Splitting is orchestrated by `TransactionManagementService`, consistent with all other transaction operations from spec-009.

**New methods:**

```
TransactionManagementService:

  + split_transaction(command: SplitTransaction) -> list[Transaction]
      1. Load account, verify not deleted
      2. Verify EDITOR permission for command.user_id
      3. Load parent transaction by command.transaction_id
      4. Validate parent belongs to account
      5. Call parent.split(command.splits, command.user_id)
         → Returns child transactions
      6. Save parent (updated _is_split_parent flag)
      7. Save all children via repository.save_many()
      8. Collect events from parent
      9. Commit UoW
      Returns: list of created child transactions

  + join_transaction_splits(command: JoinTransactionSplits) -> None
      1. Load account, verify not deleted
      2. Verify EDITOR permission for command.user_id
      3. Load parent transaction by command.transaction_id
      4. Load all children via repository.find_children(parent_id)
      5. Call parent.join_splits(child_count=len(children))
      6. Hard-delete all children from repository
      7. Save parent (updated _is_split_parent flag)
      8. Collect events from parent
      9. Commit UoW
```

### 9.2 Split-Aware Amount Update

The existing `update_transaction_amount()` method is extended with auto-join behavior:

```
  update_transaction_amount(command: UpdateTransactionAmount):
      1. Load account, verify not deleted
      2. Verify EDITOR permission
      3. Load transaction
      4. IF transaction.is_split_parent:
         a. Load all children via repository.find_children(transaction_id)
         b. Call transaction.join_splits(child_count=len(children))
         c. Hard-delete children from repository
      5. Call transaction.update_amount(command.amount)
      6. Save transaction
      7. Commit UoW
```

### 9.3 Split Child Amount Update with Sum Validation

When updating a split child's amount, the service validates that the new sum of all siblings still equals the parent amount:

```
  update_transaction_amount(command: UpdateTransactionAmount):
      ... (existing load/permission logic)
      3. Load transaction
      4. IF transaction.is_split_child():
         a. Load parent via repository.find_by_id(transaction.parent_transaction_id)
         b. Load all siblings via repository.find_children(parent_id)
         c. Compute new_sum = sum(sibling.amount for sibling in siblings
                                  if sibling.id != transaction.id) + command.amount
         d. IF new_sum != parent.amount:
            Raise SplitAmountMismatchError(expected=parent.amount, actual=new_sum)
      5. Call transaction.update_amount(command.amount)
      6. Save, commit
```

### 9.4 Split-Aware Soft Delete Cascade

Extend `soft_delete_transaction()`:

```
  soft_delete_transaction(command: SoftDeleteTransaction):
      ... (existing load/permission logic)
      IF transaction.is_split_parent:
        1. Load all active children via repository.find_children(transaction_id)
        2. For each child: child.soft_delete(command.user_id)
        3. Save all children
      transaction.soft_delete(command.user_id)
      Save, commit
```

### 9.5 Split-Aware Recovery Cascade

Extend `recover_transaction()`:

```
  recover_transaction(command: RecoverTransaction):
      ... (existing load/permission logic)
      IF transaction.is_split_child():
        1. Load parent (include_deleted=True)
        2. IF parent is deleted: Raise ParentDeletedError
      IF transaction.is_split_parent:
        1. Load all soft-deleted children via repository.find_children(
               transaction_id, include_deleted=True)
        2. For each deleted child: child.recover()
        3. Save all children
      transaction.recover()
      Save, commit
```

### 9.6 Split-Aware Balance Calculation

The existing `calculate_balance()` method requires no changes — it already uses `repository.sum_amounts(account_id, exclude_split_parents=True)`. The repository implementation will use the `_is_split_parent` flag to exclude split parents.

---

## 10. Repository Extensions

### 10.1 TransactionRepository Protocol

Add new method:

```
TransactionRepository:
  + find_children(
        parent_transaction_id: UUID,
        include_deleted: bool = False
    ) -> list[Transaction]
      Returns all child transactions for a given parent.
      If include_deleted=False (default), returns only active children.
      If include_deleted=True, returns both active and soft-deleted children.

  + hard_delete_children(parent_transaction_id: UUID) -> int
      Permanently removes all child transactions for a parent.
      Returns: count of deleted children.
```

---

## 11. Split Validation Rules

| Rule ID | Rule | Enforcement |
|---------|------|-------------|
| TXN-003 | Split amounts must sum exactly to parent amount | `transaction.split()` |
| TXN-004 | Minimum 2 splits required | `transaction.split()` |
| TXN-005 | Cannot split a split child (no nesting) | `transaction.split()` |
| TXN-006 | Maximum 50 splits per transaction | `transaction.split()` |
| TXN-007 | Child amount update must maintain sum = parent | `service.update_transaction_amount()` |

### 11.1 Exact Sum Validation

```
validate_split_sum(parent_amount: Money, splits: list[SplitRequest]):
    total = Money.zero(parent_amount.currency)
    for split in splits:
        total = total + split.amount
    if total != parent_amount:
        raise SplitAmountMismatchError(
            expected=parent_amount,
            actual=total
        )
```

**Rules:**
- Sum must be **exact** — no rounding tolerance
- All split amounts must be in the same currency as the parent
- Individual split amounts can be positive, negative, or zero (as long as they sum correctly)

### 11.2 Nesting Prohibition

Splits are limited to one level of depth:

```
✓ Transaction → Split Children        (one level)
✗ Transaction → Split Child → Split   (two levels — forbidden)
```

A split child cannot itself be split. This prevents unbounded nesting complexity.

---

## 12. Cascade Behavior

### 12.1 Soft Delete Cascade

**When a split parent is soft deleted:**
1. All active children are soft deleted first
2. Parent is soft deleted
3. `TransactionSoftDeleted` event emitted for parent and each child

**When a single split child is soft deleted:**
1. Only the child is soft deleted
2. Parent remains active, siblings unaffected
3. Balance reflects remaining active children only (parent still excluded because other active children may exist)

**Important:** Deleting a single child changes the effective balance because the parent is still excluded (it still has other active children) but the deleted child no longer contributes.

### 12.2 Recovery Cascade

**Recovering a split parent:**
1. Parent is recovered
2. All soft-deleted children are also recovered
3. Balance restored to original split state

**Recovering a single split child:**
1. Validate parent is NOT deleted → raises `ParentDeletedError` if deleted
2. Child is recovered
3. Parent and other children unaffected

### 12.3 Hard Delete Cascade

**When a split parent is hard deleted:**
1. Hard delete ALL children first (depth-first)
2. Hard delete parent
3. `EntityHardDeleted` emitted for each

---

## 13. Edge Cases

### 13.1 Auto-Join on Parent Amount Update

If a split parent's amount is updated, the split children become inconsistent. The service automatically joins the splits before applying the update:

```
service.update_transaction_amount(split_parent_id, new_amount):
    → auto-join (hard-delete children)
    → update parent amount
    → user must re-split if desired
```

### 13.2 Deleting All Children Individually

If a user deletes every child of a split parent one by one:
- When the last active child is deleted, the parent's `_is_split_parent` flag is stale until next repository load
- On next load from repository, `_is_split_parent` is `False` (no active children detected)
- Parent re-enters balance calculation naturally
- The deleted children are in trash and can be recovered individually (which would re-establish split state)

### 13.3 Zero-Amount Splits

- Individual split amounts can be zero (e.g., memo/categorization entries)
- The only requirement is that they sum to the parent amount
- A split where all children are zero is valid only if the parent amount is zero

### 13.4 Negative-Amount Splits

- Individual split amounts can be negative even if parent is positive (and vice versa)
- The only requirement is exact sum match
- This supports scenarios like rebates within a larger transaction

### 13.5 Updating Non-Amount Fields on Split Parents

- Description, merchant, comments, and dates can be updated on split parents without triggering auto-join
- Only amount updates trigger the auto-join behavior

### 13.6 Split Child Card Association

- Split children inherit the parent's `card_id` at creation time
- If the parent has no card_id, children also have no card_id
- The card_id on children is immutable after creation (consistent with parent)

---

## 14. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `TransactionSplit` | `split()` | parent_transaction_id, account_id, child_count, child_ids |
| `TransactionSplitsJoined` | `join_splits()` | parent_transaction_id, account_id, removed_child_count |

### 14.1 Event Definitions

```
@dataclass(frozen=True)
TransactionSplit(DomainEvent):
    aggregate_type = "Transaction"
    parent_transaction_id: UUID
    account_id: UUID
    child_count: int
    child_ids: tuple[UUID, ...]

@dataclass(frozen=True)
TransactionSplitsJoined(DomainEvent):
    aggregate_type = "Transaction"
    parent_transaction_id: UUID
    account_id: UUID
    removed_child_count: int
```

---

## 15. Domain Errors

| Error | Code | Parent | Trigger | Description |
|-------|------|--------|---------|-------------|
| `MinimumSplitsRequiredError` | `MINIMUM_SPLITS_REQUIRED` | `InvariantViolationError` | Less than 2 splits provided | At least 2 splits required |
| `MaxSplitsExceededError` | `MAX_SPLITS_EXCEEDED` | `InvariantViolationError` | More than 50 splits provided | Maximum 50 splits per transaction |
| `SplitAmountMismatchError` | `SPLIT_AMOUNT_MISMATCH` | `InvariantViolationError` | Split amounts don't sum to parent | Includes expected and actual amounts |
| `CannotSplitChildError` | `CANNOT_SPLIT_CHILD` | `InvariantViolationError` | Attempting to split a split child | Nesting not allowed |
| `AlreadySplitError` | `ALREADY_SPLIT` | `InvariantViolationError` | Attempting to split an already-split parent | Must join first |
| `NotSplitParentError` | `NOT_SPLIT_PARENT` | `InvariantViolationError` | `join_splits()` on non-split transaction | Nothing to join |
| `ParentDeletedError` | `PARENT_DELETED` | `InvariantViolationError` | Recovering a child whose parent is deleted | Parent must be recovered first |

**Note:** `TransactionDeletedError` and `CurrencyMismatchError` are reused from existing specs (009 and shared kernel respectively).

---

## 16. Commands

```
@dataclass(frozen=True)
SplitTransaction(Command):
    account_id: UUID
    transaction_id: UUID
    splits: tuple[SplitRequest, ...]
    user_id: UUID

@dataclass(frozen=True)
JoinTransactionSplits(Command):
    account_id: UUID
    transaction_id: UUID
    user_id: UUID
```

**Note:** Split child amount updates use the existing `UpdateTransactionAmount` command from spec-009. The service detects split child status and applies sum re-validation.

---

## 17. Authorization

| Operation | Required Permission |
|-----------|-------------------|
| Split transaction | EDITOR or above |
| Join transaction splits | EDITOR or above |
| Update split child amount | EDITOR or above |
| Soft delete split parent (cascade) | EDITOR or above |
| Recover split parent (cascade) | OWNER only (consistent with spec-009) |

---

## 18. Acceptance Criteria

### Split Operation

- [ ] Splitting creates child transactions with `parent_transaction_id` set to parent ID
- [ ] Split amounts must sum exactly to parent amount — raises `SplitAmountMismatchError` on mismatch
- [ ] Minimum 2 splits required — raises `MinimumSplitsRequiredError` for fewer
- [ ] Maximum 50 splits — raises `MaxSplitsExceededError` for more
- [ ] Cannot split a split child — raises `CannotSplitChildError`
- [ ] Cannot split an already-split parent — raises `AlreadySplitError`
- [ ] Cannot split a deleted transaction — raises `TransactionDeletedError`
- [ ] All split amounts must have same currency as parent — raises `CurrencyMismatchError`
- [ ] All split children inherit parent's `account_id`, `transaction_date`, `value_date`
- [ ] Split children inherit parent's `import_source`
- [ ] Split children inherit parent's `card_id`
- [ ] Split children have `external_id = None`
- [ ] Split children have `review_status = REVIEWED`
- [ ] `TransactionSplit` event emitted with parent ID, account ID, child count, and child IDs
- [ ] Parent `_is_split_parent` flag set to True after split

### Join Operation

- [ ] Joining hard deletes all child transactions (permanent, not soft delete)
- [ ] Parent becomes a regular transaction after join (`_is_split_parent = False`)
- [ ] Parent re-enters balance calculation
- [ ] Cannot join a non-split transaction — raises `NotSplitParentError`
- [ ] Cannot join a deleted transaction — raises `TransactionDeletedError`
- [ ] `TransactionSplitsJoined` event emitted with removed child count

### Balance Calculation

- [ ] Split parent is excluded from balance when `_is_split_parent` is True
- [ ] Split children's amounts are included in balance
- [ ] Total balance is unchanged by splitting (children sum = parent amount)
- [ ] Deleting a single child affects balance (parent still excluded, child removed)
- [ ] Deleting all children individually causes parent to re-enter balance on next load

### Split Child Amount Updates

- [ ] Split child amount can be updated individually
- [ ] Service validates that new sum of all siblings equals parent amount
- [ ] Raises `SplitAmountMismatchError` if sum mismatch after update
- [ ] Non-amount fields on split children can be updated without sum validation

### Cascade Behavior

- [ ] Soft deleting parent soft deletes all active children
- [ ] Soft deleting a single child does NOT affect parent or siblings
- [ ] Recovering parent recovers all soft-deleted children
- [ ] Recovering a child requires parent to be active — raises `ParentDeletedError` if deleted
- [ ] Hard deleting parent hard deletes all children first (depth-first)

### Edge Cases

- [ ] Updating a split parent's amount auto-joins splits first, then applies update
- [ ] Non-amount fields on split parents can be updated without auto-join
- [ ] Zero-amount splits are valid if they sum to parent (which must also be zero)
- [ ] Individual split amounts can be negative (as long as sum is correct)
- [ ] Split children inherit parent's card_id at creation time
- [ ] Split children can be categorized independently (Spec 014)

### Authorization

- [ ] Splitting requires EDITOR permission on account
- [ ] Joining requires EDITOR permission on account
- [ ] Recovery cascade requires OWNER permission (consistent with spec-009)

---

## 19. Dependencies

### Internal Dependencies
- **Spec 001** (Shared Kernel): DomainEvent, Command, Money, CurrencyMismatchError, InvariantViolationError
- **Spec 006** (Data Lifecycle): SoftDeletableMixin, EntityHardDeleted event
- **Spec 007** (Account Management): Account aggregate, AccountRepository
- **Spec 008** (Account Sharing): PermissionLevel for authorization checks
- **Spec 009** (Transaction Management): Transaction entity, TransactionRepository, TransactionManagementService

### Blocked By
- None (all dependencies already implemented)

### Blocks
- **Spec 014** (Transaction Categorization): Split children can be categorized independently

---

## 20. Glossary

- **Split Parent**: A transaction that has been divided into child transactions. Excluded from balance calculation.
- **Split Child**: A transaction created as part of a split, linked to its parent via `parent_transaction_id`.
- **Join**: The operation of undoing a split by hard-deleting all children and restoring the parent to a regular transaction.
- **Auto-Join**: Automatic joining triggered when a split parent's amount is updated, since children become inconsistent.
- **Sum Validation**: The invariant that all split children's amounts must sum exactly to the parent's amount.
