# Spec 010: Transaction Splitting

**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 009 (Transaction Management)
**Blocks:** None

---

## 1. Overview

This spec defines the transaction splitting capability — dividing a single transaction into multiple sub-transactions that sum exactly to the parent amount. Splitting enables users to categorize portions of a transaction differently (e.g., a grocery receipt with food, cleaning supplies, and pharmacy items) or to attribute portions to different purposes.

**Key Principle:** Split amounts must sum exactly to the parent transaction's amount. The parent is excluded from balance calculation when split children exist (to prevent double-counting). Splits are all-or-nothing — they move together during delete and recovery.

## 2. Scope

### In Scope

- Split operation (parent -> children)
- Join operation (undo split, remove children)
- Split validation rules (sum, minimum count, nesting prohibition)
- Balance calculation impact (parent exclusion)
- Split cascade behavior (soft delete, recovery)
- Split child transaction creation

### Out of Scope

- Transaction categorization on split children (Spec 014 — each child can be categorized independently)
- Bulk split operations (not specified in requirements)

## 3. Split Model

### 3.1 Parent-Child Relationship

```
┌──────────────────────────────────────────┐
│        Transaction (Parent)              │
│        amount: -85.00 EUR                │
│        description: "Supermarket"        │
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

### 3.2 Balance Calculation Impact

```
Without split:
  balance += parent.amount (-85.00)

With split:
  balance += child1.amount (-50.00)
           + child2.amount (-25.00)
           + child3.amount (-10.00)
           = -85.00 (same total)

  parent.amount is EXCLUDED (parent_transaction_id IS NULL check
  filters split parents by detecting they have children)
```

**Rule:** The balance calculation (Spec 007) excludes transactions that are split parents. The exclusion is based on detecting whether a transaction has active (non-deleted) child transactions, not on a flag.

## 4. Split Request

**Value Object — SplitRequest:**

| Attribute | Type | Description |
|-----------|------|-------------|
| amount | Money | Amount for this split portion |
| description | str | Description for the child transaction |
| merchant | str? | Optional merchant for the child |
| comments | str? | Optional comments for the child |

## 5. Domain Methods

### 5.1 Transaction Methods

```
Transaction:
  // Split
  + split(splits: list[SplitRequest], split_by: UUID) -> list[Transaction]
      Validates:
        1. At least 2 splits
           Raises: MinimumSplitsRequiredError
        2. Split amounts sum exactly to this.amount
           Raises: SplitAmountMismatchError
        3. All split amounts have same currency as this transaction
           Raises: CurrencyMismatchError
        4. This is NOT already a split child
           Raises: CannotSplitChildError
        5. This is NOT already a split parent (already has children)
           Raises: AlreadySplitError
        6. This transaction is not deleted
           Raises: TransactionDeletedError
      Creates:
        - One child Transaction per split, with:
            - account_id = this.account_id
            - parent_transaction_id = this.transaction_id
            - transaction_date = this.transaction_date
            - value_date = this.value_date
            - amount = split.amount
            - original_description = split.description
            - merchant = split.merchant
            - comments = split.comments
            - review_status = REVIEWED (user just created them)
            - import_source = this.import_source (inherit parent's source)
            - external_id = None (children don't have external IDs)
            - created_by = split_by
      Emits: TransactionSplit
      Returns: list of created child transactions

  // Join (undo split)
  + join_splits() -> None
      Validates:
        1. This IS a split parent (has children)
           Raises: NotSplitParentError
        2. This transaction is not deleted
           Raises: TransactionDeletedError
      Effect:
        - Hard deletes ALL child transactions (permanent, not soft delete)
        - Parent becomes a regular transaction again
        - Parent re-enters balance calculation
      Emits: TransactionSplitsJoined

  // Query helpers
  + is_split_parent() -> bool
      Returns: True if this transaction has active child transactions

  + is_split_child() -> bool
      Returns: parent_transaction_id is not None

  + get_split_children() -> list[Transaction]
      Returns: child transactions (non-deleted)
      Note: Requires repository lookup (not stored in entity)
```

### 5.2 Account Aggregate Methods

```
Account:
  // Split a transaction
  + split_transaction(
      transaction_id: UUID,
      splits: list[SplitRequest],
      split_by: UUID
    ) -> list[Transaction]
      Validates:
        1. Transaction exists and belongs to this account
           Raises: TransactionNotFoundError
        2. Delegates to transaction.split() for domain validation
      Effect:
        - Creates child transactions
        - Balance unaffected (parent excluded, children sum to same amount)
      Returns: created child transactions

  // Join splits
  + join_transaction_splits(transaction_id: UUID) -> None
      Validates:
        1. Transaction exists and belongs to this account
        2. Delegates to transaction.join_splits() for domain validation
      Effect:
        - Children hard deleted
        - Parent re-enters balance calculation
```

## 6. Split Validation Rules

| Rule ID | Rule | Enforcement |
|---------|------|-------------|
| TXN-003 | Split amounts must sum exactly to parent amount | `transaction.split()` |
| TXN-004 | Minimum 2 splits required | `transaction.split()` |
| TXN-005 | Cannot split a split child | `transaction.split()` |

### 6.1 Exact Sum Validation

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

### 6.2 Nesting Prohibition

Splits are limited to one level of depth:

```
✓ Transaction → Split Children        (one level)
✗ Transaction → Split Child → Split   (two levels — forbidden)
```

A split child cannot itself be split. This prevents unbounded nesting complexity.

## 7. Cascade Behavior

### 7.1 Soft Delete Cascade

When a split parent is soft deleted, ALL children are soft deleted too:

```
Soft deleting a split parent:
  1. parent.soft_delete(deleted_by)
  2. For each active child:
     child.soft_delete(deleted_by)
  3. Emit TransactionSoftDeleted for parent
  4. Emit TransactionSoftDeleted for each child
```

When a split child is soft deleted individually:

```
Soft deleting a single split child:
  1. child.soft_delete(deleted_by)
  2. Parent remains active
  3. Remaining children stay active
  4. NOTE: Balance now reflects remaining children only
     (parent still excluded because other children exist)
```

**Important:** Deleting a single child changes the effective balance because the parent is still excluded (it still has other active children) but the deleted child no longer contributes.

### 7.2 Recovery Cascade

Split transactions recover together (exception to the general rule in Spec 006):

```
Recovering a split parent:
  1. parent.recover()
  2. ALL soft-deleted children also recovered
  3. Balance restored to original split state

Recovering a split child:
  1. Validate parent is not deleted
     Raises: ParentDeletedError
  2. child.recover()
  3. Parent and other children unaffected
```

### 7.3 Hard Delete Cascade

When a split parent is hard deleted:

```
Hard deleting a split parent:
  1. Hard delete ALL children first (depth-first)
  2. Hard delete parent
  3. Emit EntityHardDeleted for each
```

## 8. Edge Cases

### 8.1 Splitting and Amount Updates

If a split parent's amount is updated after splitting (via Spec 009 `update_amount`):

- The split children become inconsistent (their sum no longer matches parent)
- **Resolution:** Updating a split parent's amount automatically joins the splits first, then applies the update. The user must re-split if desired.

```
account.update_transaction(split_parent_id, amount=new_amount):
  if transaction.is_split_parent():
      transaction.join_splits()  # removes children
  transaction.update_amount(new_amount)
```

### 8.2 Deleting All Children Individually

If a user deletes every child of a split parent one by one:

- Parent has no active children remaining
- Parent is no longer a "split parent" (`is_split_parent()` returns False)
- Parent re-enters balance calculation naturally
- The deleted children are in trash and can be recovered individually

### 8.3 Zero-Amount Splits

- Individual split amounts can be zero (e.g., memo/categorization entries)
- The only requirement is that they sum to the parent amount
- A split where all children are zero is valid only if the parent amount is zero

## 9. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `TransactionSplit` | `split()` | parent_transaction_id, child_count, child_ids |
| `TransactionSplitsJoined` | `join_splits()` | parent_transaction_id, removed_child_count |

## 10. Domain Errors

| Error | Trigger | Description |
|-------|---------|-------------|
| `MinimumSplitsRequiredError` | Less than 2 splits provided | At least 2 splits required |
| `SplitAmountMismatchError` | Split amounts don't sum to parent | Includes expected and actual amounts |
| `CannotSplitChildError` | Attempting to split a split child | Nesting not allowed |
| `AlreadySplitError` | Attempting to split an already-split parent | Must join first |
| `NotSplitParentError` | `join_splits()` on non-split transaction | Nothing to join |

## 11. Acceptance Criteria

### Split Operation

- [ ] Splitting creates child transactions with `parent_transaction_id` set to parent
- [ ] Split amounts must sum exactly to parent amount — raises `SplitAmountMismatchError` on mismatch
- [ ] Minimum 2 splits required — raises `MinimumSplitsRequiredError` for fewer
- [ ] Cannot split a split child — raises `CannotSplitChildError`
- [ ] Cannot split an already-split parent — raises `AlreadySplitError`
- [ ] Cannot split a deleted transaction — raises `TransactionDeletedError`
- [ ] All split children inherit parent's `account_id`, `transaction_date`, `value_date`
- [ ] Split children inherit parent's `import_source`
- [ ] Split children have `external_id = None`
- [ ] Split children have `review_status = REVIEWED`
- [ ] `TransactionSplit` event emitted with parent and child IDs

### Join Operation

- [ ] Joining hard deletes all child transactions (not soft delete)
- [ ] Parent becomes a regular transaction after join
- [ ] Parent re-enters balance calculation
- [ ] Cannot join a non-split transaction — raises `NotSplitParentError`
- [ ] Cannot join a deleted transaction — raises `TransactionDeletedError`
- [ ] `TransactionSplitsJoined` event emitted

### Balance Calculation

- [ ] Split parent is excluded from balance when active children exist
- [ ] Split children's amounts are included in balance
- [ ] Total balance is unchanged by splitting (children sum = parent amount)
- [ ] Deleting a single child affects balance (parent still excluded, child removed)
- [ ] Deleting all children individually causes parent to re-enter balance

### Cascade Behavior

- [ ] Soft deleting parent soft deletes all children
- [ ] Soft deleting a single child does NOT affect parent or siblings
- [ ] Recovering parent recovers all soft-deleted children (exception to general rule)
- [ ] Recovering a child requires parent to be active — raises `ParentDeletedError` if deleted
- [ ] Hard deleting parent hard deletes all children first (depth-first)

### Edge Cases

- [ ] Updating a split parent's amount auto-joins splits first, then applies update
- [ ] Zero-amount splits are valid if they sum to parent (which must also be zero)
- [ ] Individual split amounts can be negative (as long as sum is correct)
- [ ] Split children can be categorized independently (Spec 014)

### Authorization

- [ ] Splitting requires EDITOR permission on account
- [ ] Joining requires EDITOR permission on account
