# Spec 009: Transaction Management

**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 007 (Account Management), 008 (Account Sharing & Domain Authorization)
**Blocks:** 010, 012, 014, 015, 018, 020

---

## 1. Overview

This spec defines the Transaction entity — the fundamental unit of financial activity in the Emerald Finance Platform. Transactions record debits and credits against an account, carry immutable import metadata, support a review workflow, and participate in the Account aggregate's balance calculation.

**Key Principle:** Transactions always belong to an Account and must match its currency. The original description from an import is immutable (audit trail), while users can overlay their own description, merchant, and comments.

## 2. Scope

### In Scope

- Transaction entity with all attributes and invariants
- Transaction creation (manual and via import)
- Transaction update (mutable fields only)
- Review workflow (To Review / Reviewed)
- Transaction soft delete with split-child cascade
- `ImportSource` value object
- `ReviewStatus` enum
- Transaction querying within an account (date range, filtering)
- Transaction creation through the Account aggregate

### Out of Scope

- Transaction splitting (Spec 010)
- Bulk transaction operations (Spec 012)
- Transaction categorization (Spec 014)
- Bank import ingestion (Spec 015 — this spec defines how imported transactions are stored)
- Card linking behavior (Spec 011)
- Search and filtering across accounts (Spec 018)

## 3. Value Objects

### 3.1 ImportSource

Tracks where a transaction originated. Immutable.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| source_type | ImportSourceType | How the transaction was created |
| source_id | str? | Identifier of import batch or connection |
| imported_at | datetime | When imported |

**Enum — ImportSourceType:**

| Value | Description |
|-------|-------------|
| MANUAL | Created by user directly |
| BANK_IMPORT | Imported from bank connection sync |
| BULK_IMPORT | Imported via bulk create operation |
| API | Created via external API |

### 3.2 ReviewStatus

**Enum:**

| Value | Description |
|-------|-------------|
| TO_REVIEW | Transaction needs user review (default for imports) |
| REVIEWED | User has reviewed and confirmed |

## 4. Transaction Entity

### 4.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| transaction_id | UUID | No | Unique identifier |
| account_id | UUID | No | Parent account |
| transaction_date | date | Yes | When transaction occurred |
| value_date | date? | Yes | When value applied (settlement date) |
| amount | Money | Yes | Amount (currency must match account) |
| original_description | str | No | Immutable original description |
| user_description | str? | Yes | User-edited description overlay |
| merchant | str? | Yes | Merchant name |
| comments | str? | Yes | User notes |
| review_status | ReviewStatus | Yes | To Review / Reviewed |
| card_id | UUID? | Yes | Card used (optional, linked in Spec 011) |
| parent_transaction_id | UUID? | No | Parent if this is a split child (Spec 010) |
| import_source | ImportSource? | No | Where transaction came from |
| external_id | str? | No | ID from external system (imports) |
| created_at | datetime | No | Creation time |
| created_by | UUID | No | Who created (user_id) |
| updated_at | datetime | Auto | Last modification time |
| deleted_at | datetime? | Yes | Soft delete timestamp |
| deleted_by | UUID? | Yes | Who performed deletion |

### 4.2 Immutable Fields

| Field | Rationale |
|-------|-----------|
| original_description | Preserves import/creation audit trail |
| import_source | Historical record of origin |
| external_id | Deduplication key for imports |
| parent_transaction_id | Split relationship is structural |
| account_id | Transactions don't move between accounts |
| created_by | Audit integrity |

### 4.3 Effective Description

The display description follows a fallback chain:

```
effective_description:
  if user_description is not None:
      return user_description
  return original_description
```

This allows users to override the original description while preserving the immutable import data.

## 5. Domain Methods

```
Transaction:
  // Creation
  + create(
      account_id: UUID,
      transaction_date: date,
      amount: Money,
      original_description: str,
      created_by: UUID,
      value_date: date? = None,
      merchant: str? = None,
      comments: str? = None,
      review_status: ReviewStatus = TO_REVIEW,
      import_source: ImportSource? = None,
      external_id: str? = None
    ) -> Transaction                                   [class method]
      Validates:
        - original_description is non-empty
        - amount.currency will be validated by Account aggregate
      Sets:
        - transaction_id = new UUID
        - created_at = now
        - review_status = TO_REVIEW (or REVIEWED for manual creation)
      Returns: Transaction entity (not yet added to account)

  // Updates
  + update_description(user_description: str?) -> None
      Updates: user_description, updated_at
      Note: original_description remains unchanged

  + update_merchant(merchant: str?) -> None
      Updates: merchant, updated_at

  + update_comments(comments: str?) -> None
      Updates: comments, updated_at

  + update_dates(transaction_date: date?, value_date: date?) -> None
      Updates: whichever dates are provided, updated_at
      Validates: transaction_date not None (required field)

  + update_amount(amount: Money) -> None
      Validates: currency matches account currency (checked by aggregate)
      Updates: amount, updated_at
      Note: If this is a split parent, split children become invalid
            (handled by Spec 010)

  // Review workflow
  + mark_as_reviewed() -> None
      Sets: review_status = REVIEWED, updated_at
      Emits: TransactionReviewed

  + mark_for_review() -> None
      Sets: review_status = TO_REVIEW, updated_at

  // Lifecycle
  + soft_delete(deleted_by: UUID) -> None
      Validates: not already deleted
      Sets: deleted_at, deleted_by
      Note: If this is a split parent, cascade to children (Spec 010)
      Emits: TransactionSoftDeleted
      Raises: AlreadyDeletedError

  + recover() -> None
      Validates: is soft deleted, parent account is active
      Clears: deleted_at, deleted_by
      Emits: TransactionRecovered
      Raises: NotDeletedError, ParentDeletedError

  // Query helpers
  + is_split_parent() -> bool
      Returns: has child transactions (Spec 010)

  + is_split_child() -> bool
      Returns: parent_transaction_id is not None

  + effective_description() -> str
      Returns: user_description or original_description
```

## 6. Account Aggregate — Transaction Operations

Transactions are created and managed **through** the Account aggregate to enforce invariants:

```
Account:
  // Add single transaction
  + add_transaction(transaction: Transaction) -> None
      Validates:
        1. Account is active (not deleted)
           Raises: AccountNotActiveError
        2. Transaction currency matches account currency
           Raises: CurrencyMismatchError
        3. If external_id provided, unique within this account
           Raises: DuplicateExternalIdError
      Effect:
        - Transaction added to account's collection
        - Balance recalculated
      Emits: TransactionCreated

  // Get transactions in date range
  + get_transactions_in_range(
      date_range: DateRange,
      include_deleted: bool = False
    ) -> list[Transaction]
      Returns: transactions where transaction_date falls within range
      Filters: excludes deleted unless include_deleted=True

  // Update transaction
  + update_transaction(
      transaction_id: UUID,
      requesting_user_id: UUID,
      **updates
    ) -> None
      Validates:
        1. Transaction exists and belongs to this account
           Raises: TransactionNotFoundError
        2. Transaction is not deleted
           Raises: TransactionDeletedError
        3. If amount changed, currency still matches
           Raises: CurrencyMismatchError
      Effect:
        - Applies updates to transaction
        - If amount changed, balance recalculated
      Emits: TransactionUpdated

  // Delete transaction
  + delete_transaction(transaction_id: UUID, deleted_by: UUID) -> None
      Validates:
        1. Transaction exists and belongs to this account
        2. Transaction is not already deleted
      Effect:
        - Soft deletes transaction
        - If split parent, cascades to children (Spec 010)
        - Balance recalculated
      Emits: TransactionSoftDeleted

  // Recover transaction
  + recover_transaction(transaction_id: UUID) -> None
      Validates:
        1. Transaction exists, belongs to this account, and is deleted
        2. Account is active
      Effect:
        - Recovers transaction
        - Balance recalculated
      Emits: TransactionRecovered
```

## 7. Transaction Creation Flows

### 7.1 Manual Creation

```
User creates transaction via UI/API:
     │
     ▼
  1. Authorization: account.has_permission(user_id, EDITOR)
     Raises: InsufficientPermissionError
     │
     ▼
  2. Create Transaction entity:
     - import_source = ImportSource(MANUAL, None, now)
     - review_status = REVIEWED (manual = already reviewed by user)
     - original_description = user-provided description
     │
     ▼
  3. account.add_transaction(transaction)
     Validates: currency match, account active
     │
     ▼
  4. Emit TransactionCreated
```

### 7.2 Import Creation (from Bank Sync)

```
Bank sync produces normalized transaction data:
     │
     ▼
  1. Create Transaction entity:
     - import_source = ImportSource(BANK_IMPORT, connection_id, now)
     - review_status = TO_REVIEW (imports need user review)
     - original_description = bank-provided description (immutable)
     - external_id = bank's transaction ID (for deduplication)
     │
     ▼
  2. account.add_transaction(transaction)
     Validates: currency match, external_id unique, account active
     │
     ▼
  3. Emit TransactionCreated (with import_source info)
```

### 7.3 External ID Deduplication

| Rule | Description |
|------|-------------|
| Scope | External ID uniqueness is per-account (not globally) |
| Match | Exact string match |
| Import only | Only relevant for transactions with `import_source` |
| Deleted included | Deduplication checks include soft-deleted transactions |

```
Deduplication on add_transaction:
  if transaction.external_id is not None:
      existing = find transaction in this account
                 where external_id == transaction.external_id
                 (including soft-deleted)
      if existing:
          raise DuplicateExternalIdError(existing_transaction_id)
```

## 8. Amount Semantics

Transaction amounts follow a sign convention:

| Amount | Meaning | Example |
|--------|---------|---------|
| Positive | Credit (money in) | Salary deposit: +2000.00 |
| Negative | Debit (money out) | Coffee purchase: -4.50 |
| Zero | Zero-amount transaction | Fee waiver, memo entry |

**Rules:**

- Zero-amount transactions are explicitly allowed (TXN-007)
- Currency of the amount must always match the account's currency
- Amount uses the `Money` value object for arbitrary-precision arithmetic

## 9. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `TransactionCreated` | `account.add_transaction()` | transaction_id, account_id, amount, import_source? |
| `TransactionUpdated` | `account.update_transaction()` | transaction_id, changed_fields |
| `TransactionReviewed` | `mark_as_reviewed()` | transaction_id, reviewed_by |
| `TransactionSoftDeleted` | `soft_delete()` | transaction_id, account_id, deleted_by |
| `TransactionRecovered` | `recover()` | transaction_id, account_id |

## 10. Domain Errors

| Error | Trigger | Description |
|-------|---------|-------------|
| `CurrencyMismatchError` | Transaction currency != account currency | Currency must match |
| `DuplicateExternalIdError` | External ID already exists in account | Import deduplication |
| `AccountNotActiveError` | Operation on deleted account | Account is soft deleted |
| `TransactionNotFoundError` | Transaction ID not in account | Transaction doesn't exist or wrong account |
| `TransactionDeletedError` | Update on deleted transaction | Must recover first |
| `EmptyDescriptionError` | Empty original_description | Description is required |

## 11. Repository Interface

```
TransactionRepository (Protocol):
  + save(transaction: Transaction) -> None
  + save_many(transactions: list[Transaction]) -> None
  + find_by_id(transaction_id: UUID) -> Transaction?
  + find_by_account(
      account_id: UUID,
      include_deleted: bool = False
    ) -> list[Transaction]
  + find_by_account_in_range(
      account_id: UUID,
      date_range: DateRange,
      include_deleted: bool = False
    ) -> list[Transaction]
  + find_by_external_id(
      account_id: UUID,
      external_id: str
    ) -> Transaction?
      Includes soft-deleted (for deduplication)
  + sum_amounts(
      account_id: UUID,
      exclude_split_parents: bool = True
    ) -> Money
      For efficient balance calculation
      Excludes soft-deleted transactions
```

## 12. Acceptance Criteria

### Transaction Creation

- [ ] Manual transaction created with `import_source = MANUAL` and `review_status = REVIEWED`
- [ ] Import transaction created with `import_source = BANK_IMPORT` and `review_status = TO_REVIEW`
- [ ] Transaction currency must match account currency — raises `CurrencyMismatchError`
- [ ] Transaction on deleted account raises `AccountNotActiveError`
- [ ] Duplicate `external_id` within same account raises `DuplicateExternalIdError`
- [ ] Duplicate check includes soft-deleted transactions
- [ ] `original_description` is required (non-empty)
- [ ] `TransactionCreated` event emitted with correct data

### Immutable Fields

- [ ] `original_description` cannot be changed after creation
- [ ] `import_source` cannot be changed after creation
- [ ] `external_id` cannot be changed after creation
- [ ] `parent_transaction_id` cannot be changed after creation
- [ ] `account_id` cannot be changed after creation
- [ ] `created_by` cannot be changed after creation

### Transaction Updates

- [ ] `user_description`, `merchant`, `comments` can be updated
- [ ] `transaction_date` and `value_date` can be updated
- [ ] `amount` can be updated (currency must still match account)
- [ ] Updating amount triggers balance recalculation
- [ ] `updated_at` is set on every update
- [ ] Updating a deleted transaction raises `TransactionDeletedError`
- [ ] `TransactionUpdated` event emitted

### Effective Description

- [ ] Returns `user_description` when set
- [ ] Falls back to `original_description` when `user_description` is None
- [ ] `original_description` is never affected by description updates

### Review Workflow

- [ ] `mark_as_reviewed()` sets `review_status = REVIEWED`
- [ ] `mark_for_review()` sets `review_status = TO_REVIEW`
- [ ] `TransactionReviewed` event emitted on review

### Amount Semantics

- [ ] Positive amounts represent credits (money in)
- [ ] Negative amounts represent debits (money out)
- [ ] Zero-amount transactions are allowed
- [ ] Amount uses `Money` value object (arbitrary-precision decimal)

### Lifecycle

- [ ] Soft delete sets `deleted_at` and `deleted_by`
- [ ] Soft deleting already-deleted transaction raises `AlreadyDeletedError`
- [ ] Soft deleted transactions excluded from balance calculation
- [ ] Recovery clears deletion fields
- [ ] Cannot recover if parent account is deleted — raises `ParentDeletedError`
- [ ] Recovery of non-deleted transaction raises `NotDeletedError`

### Authorization

- [ ] Creating transaction requires EDITOR permission on account
- [ ] Updating transaction requires EDITOR permission
- [ ] Deleting transaction requires EDITOR permission
- [ ] Viewing transactions requires VIEWER permission
- [ ] Recovering requires OWNER permission
