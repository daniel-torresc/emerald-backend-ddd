# Spec 009: Transaction Management

**Version:** 1.0
**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 007 (Account Management), 008 (Account Sharing & Domain Authorization)
**Blocks:** 010, 012, 014, 015, 018, 020

---

## 1. Overview

This spec defines the **Transaction entity** — the fundamental unit of financial activity in the Emerald Finance Platform. Transactions record debits and credits against an account, carry immutable import metadata, support a review workflow, and participate in balance calculation. Transaction is a **standalone Entity** with its own repository, persisted and queried independently of the Account aggregate.

**Key Principles:**

- Transactions always belong to an Account and must match its currency
- The original description from an import is immutable (audit trail); users can overlay their own description, merchant, and comments
- All transactions start as `TO_REVIEW`; users explicitly mark them `REVIEWED`
- Balance is computed at the application service level: `opening_balance + sum_amounts()`

---

## 2. Background & Context

### Problem Statement

Users need to record individual financial transactions against their accounts — both manually and from bank imports. Each transaction must preserve its original import data while allowing user edits. A review workflow helps users track which imported transactions they've already examined.

### Business Goals

- Enable manual transaction creation and editing for any account
- Preserve immutable audit trail for imported transaction data
- Provide a review status workflow so users can track processing of transactions
- Support deduplication of imported transactions via external IDs
- Calculate accurate account balances from transaction data

### Success Metrics

- Transactions can be created, updated, soft-deleted, and recovered
- Balance calculation returns `opening_balance + sum of active transaction amounts`
- External ID deduplication prevents duplicate imports
- All string fields are validated with length constraints
- Authorization enforced: EDITOR+ for mutations, VIEWER+ for reads, OWNER for recovery

---

## 3. Scope

### In Scope

- Transaction entity with all attributes and invariants
- Transaction creation (manual and via import)
- Transaction update (mutable fields only, explicit methods per field)
- Review workflow (TO_REVIEW / REVIEWED)
- Transaction soft delete using SoftDeletableMixin
- `ImportSource` value object
- `ImportSourceType` enum
- `ReviewStatus` enum
- Transaction querying (by account, date range, external ID) with pagination
- Balance calculation at the application service level
- Stub fields for future specs (card_id, parent_transaction_id)
- TransactionRepository protocol
- TransactionManagementService (application layer)
- Transaction commands
- UoW extension with TransactionRepository

### Out of Scope

- Transaction splitting (Spec 010)
- Bulk transaction operations (Spec 012)
- Transaction categorization (Spec 014)
- Bank import ingestion (Spec 015 — this spec defines how imported transactions are **stored**)
- Card linking behavior (Spec 011)
- Search and filtering across accounts (Spec 018)

---

## 4. Users & Personas

### Primary Users

- **Account holders** who manually enter transactions or review imported ones
- **Shared account members** (EDITOR+) who create/edit transactions on shared accounts
- **Viewers** who can see transactions but not modify them

### User Goals

- Record financial transactions with correct amounts and descriptions
- Review imported transactions and mark them as processed
- Edit transaction details (description, merchant, comments, dates, amount)
- Delete and recover transactions
- See accurate account balance based on transaction history

---

## 5. Requirements

### 5.1 Value Objects

#### REQ-VO-001: ImportSource

**Priority:** Must Have

Tracks where a transaction originated. Immutable after creation.

| Attribute     | Type             | Description                              |
|---------------|------------------|------------------------------------------|
| source_type   | ImportSourceType | How the transaction was created          |
| source_id     | str \| None      | Identifier of import batch or connection |
| imported_at   | datetime         | When the import/creation occurred        |

**Validation:**
- `imported_at` must be timezone-aware
- `source_id` if provided must be non-empty after trimming

#### REQ-VO-002: ImportSourceType (Enum)

**Priority:** Must Have

| Value        | Description                        |
|--------------|------------------------------------|
| MANUAL       | Created by user directly           |
| BANK_IMPORT  | Imported from bank connection sync |
| BULK_IMPORT  | Imported via bulk create operation |
| API          | Created via external API           |

#### REQ-VO-003: ReviewStatus (Enum)

**Priority:** Must Have

| Value      | Description                                            |
|------------|--------------------------------------------------------|
| TO_REVIEW  | Transaction needs user review (default for all new)    |
| REVIEWED   | User has reviewed and confirmed                        |

**Note:** All transactions start as `TO_REVIEW` regardless of creation source. Users explicitly set `REVIEWED`. This supports future extension with additional statuses (e.g., WAITING_OTHERS).

---

### 5.2 Transaction Entity

#### REQ-TX-001: Transaction Attributes

**Priority:** Must Have

Transaction extends `Entity` and uses `SoftDeletableMixin` and `AuditableMixin` for lifecycle and audit tracking. It is **not** an `AggregateRoot` — it is a standalone entity persisted through its own repository.

| Attribute             | Type             | Mutable   | Constraints                   | Description                                |
|-----------------------|------------------|-----------|-------------------------------|--------------------------------------------|
| id (entity)           | UUID             | No        | Generated on create           | Unique identifier (from Entity base)       |
| account_id            | UUID             | No        | Required                      | Parent account                             |
| transaction_date      | date             | Yes       | Required                      | When transaction occurred                  |
| value_date            | date \| None     | Yes       | Optional                      | Settlement/value date                      |
| amount                | Money            | Yes       | Currency validated by service | Transaction amount                         |
| original_description  | str              | No        | 1-500 chars, trimmed          | Immutable original description             |
| user_description      | str \| None      | Yes       | 1-500 chars if set, trimmed   | User-edited description overlay            |
| merchant              | str \| None      | Yes       | 1-200 chars if set, trimmed   | Merchant name                              |
| comments              | str \| None      | Yes       | 1-1000 chars if set, trimmed  | User notes                                 |
| review_status         | ReviewStatus     | Yes       | Defaults TO_REVIEW            | Review workflow status                     |
| card_id               | UUID \| None     | Yes       | Stub for Spec 011             | Card used (optional, linked in Spec 011)   |
| parent_transaction_id | UUID \| None     | No        | Stub for Spec 010             | Parent if this is a split child            |
| import_source         | ImportSource     | No        | Required                      | Where transaction came from                |
| external_id           | str \| None      | No        | Unique per account if set     | ID from external system (imports)          |
| created_by            | UUID             | No        | Required                      | Who created (from AuditableMixin)          |
| updated_by            | UUID             | Auto      | Set on every mutation         | Who last modified (from AuditableMixin)    |
| created_at            | datetime         | No        | Set on create                 | Creation timestamp (from TimestampedMixin) |
| updated_at            | datetime         | Auto      | Set on every mutation         | Last modification (from TimestampedMixin)  |
| deleted_at            | datetime \| None | Via mixin | SoftDeletableMixin            | Soft delete timestamp                      |
| deleted_by            | UUID \| None     | Via mixin | SoftDeletableMixin            | Who performed deletion                     |

**Mixin composition:**
```
class Transaction(SoftDeletableMixin, AuditableMixin, Entity)
```

**Note:** `AuditableMixin` provides `created_by` (immutable) and `updated_by` (mutable). Since shared accounts allow multiple EDITORs to modify the same transactions, tracking who last edited is important for accountability. All update methods call `_set_updated_by(actor_id)` alongside `_touch()`.

#### REQ-TX-002: Immutable Fields

**Priority:** Must Have

| Field                   | Rationale                                    |
|-------------------------|----------------------------------------------|
| original_description    | Preserves import/creation audit trail        |
| import_source           | Historical record of origin                  |
| external_id             | Deduplication key for imports                |
| parent_transaction_id   | Split relationship is structural             |
| account_id              | Transactions don't move between accounts     |
| created_by              | Audit integrity                              |

These fields are exposed as read-only properties. No update methods exist for them.

#### REQ-TX-003: Effective Description

**Priority:** Must Have

The display description follows a fallback chain:

```
effective_description:
    if user_description is not None:
        return user_description
    return original_description
```

Exposed as a read-only property on Transaction.

#### REQ-TX-004: String Field Validation

**Priority:** Must Have

| Field                 | Min | Max  | Trimmed | Notes                           |
|-----------------------|-----|------|---------|---------------------------------|
| original_description  | 1   | 500  | Yes     | Required, non-empty after trim  |
| user_description      | 1   | 500  | Yes     | Optional; if set, non-empty     |
| merchant              | 1   | 200  | Yes     | Optional; if set, non-empty     |
| comments              | 1   | 1000 | Yes     | Optional; if set, non-empty     |

Validation happens in entity methods. Setting an optional field to `None` clears it; setting it to `""` or whitespace-only raises an error.

---

### 5.3 Transaction Domain Methods

#### REQ-TX-010: Factory — create()

**Priority:** Must Have

```python
@classmethod
def create(
    cls,
    account_id: UUID,
    transaction_date: date,
    amount: Money,
    original_description: str,
    created_by: UUID,
    import_source: ImportSource,
    value_date: date | None = None,
    merchant: str | None = None,
    comments: str | None = None,
    external_id: str | None = None,
    parent_transaction_id: UUID | None = None,  # Stub for Spec 010
    card_id: UUID | None = None,                 # Stub for Spec 011
) -> Transaction
```

**Behavior:**
- Validates `original_description` is non-empty (1-500 chars, trimmed)
- Validates `merchant`, `comments` if provided (length constraints)
- Sets `review_status = TO_REVIEW` always
- Sets `created_at = now`, `updated_at = now`
- Generates `id = uuid4()`
- Returns new Transaction entity

**Note:** Currency validation (amount.currency must match account.currency) is NOT performed here — it is enforced by the application service which has access to the Account aggregate.

#### REQ-TX-011: update_description()

**Priority:** Must Have

```python
def update_description(self, user_description: str | None, updated_by: UUID) -> None
```

- If `None`: clears user_description
- If string: validates 1-500 chars after trim, raises `EmptyDescriptionError` if blank
- Calls `_set_updated_by(updated_by)` and `_touch()`
- `original_description` remains unchanged

#### REQ-TX-012: update_merchant()

**Priority:** Must Have

```python
def update_merchant(self, merchant: str | None, updated_by: UUID) -> None
```

- If `None`: clears merchant
- If string: validates 1-200 chars after trim, raises `InvalidMerchantError` if blank
- Calls `_set_updated_by(updated_by)` and `_touch()`

#### REQ-TX-013: update_comments()

**Priority:** Must Have

```python
def update_comments(self, comments: str | None, updated_by: UUID) -> None
```

- If `None`: clears comments
- If string: validates 1-1000 chars after trim, raises `InvalidCommentsError` if blank
- Calls `_set_updated_by(updated_by)` and `_touch()`

#### REQ-TX-014: update_dates()

**Priority:** Must Have

```python
def update_dates(
    self,
    updated_by: UUID,
    transaction_date: date | None = None,
    value_date: date | None = _SENTINEL,
) -> None
```

- `transaction_date`: if provided, replaces current; if `None`, no change (required field, cannot be cleared)
- `value_date`: uses sentinel pattern — if not passed, no change; if `None`, clears; if date, sets
- At least one parameter must differ from current state
- Calls `_set_updated_by(updated_by)` and `_touch()`

#### REQ-TX-015: update_amount()

**Priority:** Must Have

```python
def update_amount(self, amount: Money, updated_by: UUID) -> None
```

- Replaces current amount
- Calls `_set_updated_by(updated_by)` and `_touch()`
- **Note:** Currency validation is enforced by the application service, not by the entity

#### REQ-TX-016: mark_as_reviewed()

**Priority:** Must Have

```python
def mark_as_reviewed(self, reviewed_by: UUID) -> None
```

- Sets `review_status = REVIEWED`
- Calls `_set_updated_by(reviewed_by)` and `_touch()`
- Emits `TransactionReviewed` event
- No-op if already REVIEWED (idempotent)

#### REQ-TX-017: mark_for_review()

**Priority:** Must Have

```python
def mark_for_review(self, updated_by: UUID) -> None
```

- Sets `review_status = TO_REVIEW`
- Calls `_set_updated_by(updated_by)` and `_touch()`
- No-op if already TO_REVIEW (idempotent)

#### REQ-TX-018: Soft Delete

**Priority:** Must Have

```python
def soft_delete(self, deleted_by: UUID, retention: RetentionPeriod, reason: str | None = None) -> None
```

Uses `SoftDeletableMixin.soft_delete()` — validates not already deleted, sets `deleted_at`, `deleted_by`, `deletion_reason`, schedules hard delete via retention.

- Raises `AlreadyDeletedError` if already deleted
- Emits `TransactionSoftDeleted`

#### REQ-TX-019: Recover

**Priority:** Must Have

```python
def recover(self) -> None
```

Uses `SoftDeletableMixin.recover()` — validates is deleted, clears deletion fields.

- Raises `NotDeletedError` if not deleted
- Emits `TransactionRecovered`
- **Note:** The application service validates that the parent account is active before calling this

#### REQ-TX-020: Stub Methods (Spec 010)

**Priority:** Should Have

```python
def is_split_parent(self) -> bool
    # Stub: returns False (Spec 010 will implement)

def is_split_child(self) -> bool
    return self.parent_transaction_id is not None
```

---

### 5.4 Amount Semantics

#### REQ-AMT-001: Sign Convention

**Priority:** Must Have

| Amount   | Meaning                    | Example                     |
|----------|----------------------------|-----------------------------|
| Positive | Credit (money in)          | Salary deposit: +2000.00    |
| Negative | Debit (money out)          | Coffee purchase: -4.50      |
| Zero     | Zero-amount transaction    | Fee waiver, memo entry      |

**Rules:**
- Zero-amount transactions are explicitly allowed
- Currency of the amount must always match the account's currency
- Amount uses the `Money` value object for arbitrary-precision arithmetic

---

### 5.5 Balance Calculation

#### REQ-BAL-001: Service-Level Balance Computation

**Priority:** Must Have

Balance is computed at the **application service level**, not inside the Account aggregate.

```
account_balance = account.opening_balance + transaction_repository.sum_amounts(account_id)
```

- `sum_amounts()` excludes soft-deleted transactions
- `sum_amounts()` excludes split parents when `exclude_split_parents=True` (Spec 010 — stub: returns total of all non-deleted for now)
- The Account aggregate's `calculate_balance()` stub is **replaced** with a service method

**Account aggregate changes:**
- Remove `calculate_balance()` stub method
- Remove `transaction_count` stub property
- These become service-level concerns

---

### 5.6 External ID Deduplication

#### REQ-DEDUP-001: Deduplication Rules

**Priority:** Must Have

| Rule             | Description                                                |
|------------------|------------------------------------------------------------|
| Scope            | External ID uniqueness is per-account (not globally)       |
| Match            | Exact string match                                         |
| All sources      | Applies to any transaction with an external_id             |
| Deleted included | Deduplication checks include soft-deleted transactions     |

**Deduplication flow (in application service):**
```
if transaction.external_id is not None:
    existing = transaction_repo.find_by_external_id(account_id, external_id)
    if existing is not None:
        raise DuplicateExternalIdError(existing.id)
```

---

### 5.7 Domain Events

#### REQ-EVT-001: Transaction Events

**Priority:** Must Have

All events are frozen dataclasses extending `DomainEvent` with `aggregate_type: ClassVar[str] = "transaction"`.

| Event                    | Trigger                                | Key Data                                          |
|--------------------------|----------------------------------------|---------------------------------------------------|
| `TransactionCreated`     | Service creates and saves transaction  | transaction_id, account_id, amount, import_source  |
| `TransactionUpdated`     | Any mutable field update               | transaction_id, account_id, changed_fields         |
| `TransactionReviewed`    | `mark_as_reviewed()`                   | transaction_id, account_id, reviewed_by            |
| `TransactionSoftDeleted` | `soft_delete()`                        | transaction_id, account_id, deleted_by             |
| `TransactionRecovered`   | `recover()`                            | transaction_id, account_id                         |

**Note:** Since Transaction is not an AggregateRoot, events are collected by the application service (via `collect_events()` method on the service or by direct event registration on Transaction using a lightweight event list pattern).

**Implementation approach:** Transaction holds an internal `_events: list[DomainEvent]` list with `_register_event()` and `collect_events()` methods (same pattern as AggregateRoot but without the version/timestamp overhead). The service collects events after each operation.

---

### 5.8 Domain Exceptions

#### REQ-ERR-001: Transaction Exceptions

**Priority:** Must Have

| Error                     | Extends                  | Code                        | Trigger                                    |
|---------------------------|--------------------------|-----------------------------|--------------------------------------------|
| `CurrencyMismatchError`   | *(already exists)*       | `CURRENCY_MISMATCH`         | Transaction currency != account currency   |
| `DuplicateExternalIdError`| ConflictError            | `DUPLICATE_EXTERNAL_ID`     | External ID already exists in account      |
| `TransactionNotFoundError`| NotFoundError            | `TRANSACTION_NOT_FOUND`     | Transaction ID not found                   |
| `TransactionDeletedError` | InvariantViolationError  | `TRANSACTION_DELETED`       | Update attempted on deleted transaction    |
| `EmptyDescriptionError`   | InvalidValueError        | `EMPTY_DESCRIPTION`         | Empty original_description or user_description |
| `InvalidMerchantError`    | InvalidValueError        | `INVALID_MERCHANT`          | Merchant string too long or whitespace-only|
| `InvalidCommentsError`    | InvalidValueError        | `INVALID_COMMENTS`          | Comments string too long or whitespace-only|
| `ParentAccountDeletedError`| InvariantViolationError | `PARENT_ACCOUNT_DELETED`    | Recover when parent account is deleted     |
| `AccountNotActiveError`   | *(already exists)*       | `ACCOUNT_NOT_ACTIVE`        | Operation on deleted account               |

---

### 5.9 Repository Protocol

#### REQ-REPO-001: TransactionRepository

**Priority:** Must Have

```python
class TransactionRepository(Protocol):
    def save(self, transaction: Transaction) -> None: ...

    def save_many(self, transactions: list[Transaction]) -> None: ...

    def find_by_id(
        self,
        transaction_id: UUID,
        include_deleted: bool = False,
    ) -> Transaction | None: ...

    def find_by_account(
        self,
        account_id: UUID,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[Transaction]: ...

    def find_by_account_in_range(
        self,
        account_id: UUID,
        date_range: DateRange,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[Transaction]: ...

    def find_by_external_id(
        self,
        account_id: UUID,
        external_id: str,
    ) -> Transaction | None: ...
        # Includes soft-deleted (for deduplication)

    def count_by_account(
        self,
        account_id: UUID,
        include_deleted: bool = False,
    ) -> int: ...

    def sum_amounts(
        self,
        account_id: UUID,
        exclude_split_parents: bool = True,
    ) -> Money: ...
        # Excludes soft-deleted transactions
        # Stub: exclude_split_parents has no effect until Spec 010
```

**Pagination:** Uses `PaginatedResult[T]` from Spec 006 shared kernel. Default page size is 50.

#### REQ-REPO-002: UoW Extension

**Priority:** Must Have

`AbstractCoreFinanceUnitOfWork` is extended:

```python
class AbstractCoreFinanceUnitOfWork(AbstractUnitOfWork):
    accounts: AccountRepository
    transactions: TransactionRepository  # NEW
```

---

### 5.10 Application Layer

#### REQ-APP-001: Transaction Commands

**Priority:** Must Have

All commands are `@dataclass(frozen=True)` extending `Command`.

| Command                     | Fields                                                                                                        |
|-----------------------------|---------------------------------------------------------------------------------------------------------------|
| `CreateTransaction`         | account_id, requesting_user_id, transaction_date, amount, currency_code, original_description, value_date?, merchant?, comments?, import_source_type, source_id?, external_id? |
| `UpdateTransactionDescription` | account_id, requesting_user_id, transaction_id, user_description (str \| None)                            |
| `UpdateTransactionMerchant` | account_id, requesting_user_id, transaction_id, merchant (str \| None)                                        |
| `UpdateTransactionComments` | account_id, requesting_user_id, transaction_id, comments (str \| None)                                        |
| `UpdateTransactionDates`    | account_id, requesting_user_id, transaction_id, transaction_date?, value_date?                                |
| `UpdateTransactionAmount`   | account_id, requesting_user_id, transaction_id, amount, currency_code                                         |
| `ReviewTransaction`         | account_id, requesting_user_id, transaction_id                                                                |
| `UnreviewTransaction`       | account_id, requesting_user_id, transaction_id                                                                |
| `SoftDeleteTransaction`     | account_id, requesting_user_id, transaction_id, reason?                                                       |
| `RecoverTransaction`        | account_id, requesting_user_id, transaction_id                                                                |

**Note:** `account_id` is included in all commands to enable authorization checks against the Account aggregate.

#### REQ-APP-002: TransactionManagementService

**Priority:** Must Have

```python
class TransactionManagementService:
    def __init__(
        self,
        uow: AbstractCoreFinanceUnitOfWork,
        retention_policy_service: RetentionPolicyService,
    ) -> None

    # Creation
    def create_transaction(self, cmd: CreateTransaction) -> Transaction

    # Updates (one method per mutable field)
    def update_description(self, cmd: UpdateTransactionDescription) -> None
    def update_merchant(self, cmd: UpdateTransactionMerchant) -> None
    def update_comments(self, cmd: UpdateTransactionComments) -> None
    def update_dates(self, cmd: UpdateTransactionDates) -> None
    def update_amount(self, cmd: UpdateTransactionAmount) -> None

    # Review
    def review_transaction(self, cmd: ReviewTransaction) -> None
    def unreview_transaction(self, cmd: UnreviewTransaction) -> None

    # Lifecycle
    def soft_delete_transaction(self, cmd: SoftDeleteTransaction) -> None
    def recover_transaction(self, cmd: RecoverTransaction) -> None

    # Query
    def get_transaction(self, account_id: UUID, transaction_id: UUID, requesting_user_id: UUID) -> Transaction
    def list_transactions(self, account_id: UUID, requesting_user_id: UUID, page: int = 1, page_size: int = 50) -> PaginatedResult[Transaction]
    def list_transactions_in_range(self, account_id: UUID, requesting_user_id: UUID, date_range: DateRange, page: int = 1, page_size: int = 50) -> PaginatedResult[Transaction]
    def calculate_balance(self, account_id: UUID, requesting_user_id: UUID) -> Money
    def get_transaction_count(self, account_id: UUID, requesting_user_id: UUID) -> int

    # Private helpers
    def _load_account(self, account_id: UUID) -> Account
    def _load_transaction(self, transaction_id: UUID) -> Transaction
    def _verify_permission(self, account: Account, user_id: UUID, required: PermissionLevel) -> None
    def _verify_not_deleted(self, transaction: Transaction) -> None
```

#### REQ-APP-003: Service Method Flows

**Priority:** Must Have

**create_transaction:**
1. Load account via `_load_account()`
2. `_verify_permission(account, user_id, EDITOR)`
3. Verify account is active — raises `AccountNotActiveError`
4. Build `ImportSource` from command fields
5. Build `Money` from amount + currency_code
6. Validate currency matches: `amount.currency == account.currency` — raises `CurrencyMismatchError`
7. If `external_id` provided, check uniqueness via `repo.find_by_external_id()` — raises `DuplicateExternalIdError`
8. Call `Transaction.create(...)` with validated data
9. Save via `uow.transactions.save()`
10. Register `TransactionCreated` event on service
11. Commit UoW

**update_amount:**
1. Load account + transaction
2. `_verify_permission(account, user_id, EDITOR)`
3. `_verify_not_deleted(transaction)`
4. Build `Money` from amount + currency_code
5. Validate currency matches account currency — raises `CurrencyMismatchError`
6. Call `transaction.update_amount(amount)`
7. Save + commit

**soft_delete_transaction:**
1. Load account
2. `_verify_permission(account, user_id, EDITOR)`
3. Load transaction (include_deleted=True so AlreadyDeletedError can fire from entity)
4. Verify transaction.account_id == account.id
5. Get retention period from `retention_policy_service`
6. Call `transaction.soft_delete(deleted_by, retention, reason)`
7. Save + commit

**recover_transaction:**
1. Load account
2. `_verify_permission(account, user_id, OWNER)` — recovery requires OWNER
3. Verify account is active — raises `ParentAccountDeletedError`
4. Load transaction (include_deleted=True)
5. Call `transaction.recover()`
6. Save + commit

**calculate_balance:**
1. Load account
2. `_verify_permission(account, user_id, VIEWER)`
3. `sum = uow.transactions.sum_amounts(account_id)`
4. Return `account.opening_balance + sum`

---

### 5.11 Account Aggregate Changes

#### REQ-AGG-001: Remove Balance Stubs

**Priority:** Must Have

The Account aggregate's existing stubs are removed:
- Remove `calculate_balance()` method (replaced by service-level `TransactionManagementService.calculate_balance()`)
- Remove `transaction_count` property (replaced by service-level `get_transaction_count()`)

These were placeholder stubs introduced in Spec 007 pending this spec's implementation.

---

## 6. Transaction Creation Flows

### 6.1 Manual Creation

```
User creates transaction via UI/API:
    |
    v
  1. Authorization: account.has_permission(user_id, EDITOR)
     Raises: InsufficientPermissionError
    |
    v
  2. Verify account is active
     Raises: AccountNotActiveError
    |
    v
  3. Create Transaction entity:
     - import_source = ImportSource(MANUAL, None, now)
     - review_status = TO_REVIEW
     - original_description = user-provided description
    |
    v
  4. Validate currency match (amount.currency == account.currency)
     Raises: CurrencyMismatchError
    |
    v
  5. Save transaction via repository
    |
    v
  6. Emit TransactionCreated
```

### 6.2 Import Creation (from Bank Sync)

```
Bank sync produces normalized transaction data:
    |
    v
  1. Create Transaction entity:
     - import_source = ImportSource(BANK_IMPORT, connection_id, now)
     - review_status = TO_REVIEW
     - original_description = bank-provided description (immutable)
     - external_id = bank's transaction ID (for deduplication)
    |
    v
  2. Validate currency match + external_id uniqueness
     Raises: CurrencyMismatchError, DuplicateExternalIdError
    |
    v
  3. Save transaction via repository
    |
    v
  4. Emit TransactionCreated (with import_source info)
```

### 6.3 External ID Deduplication

| Rule             | Description                                                |
|------------------|------------------------------------------------------------|
| Scope            | External ID uniqueness is per-account (not globally)       |
| Match            | Exact string match                                         |
| All sources      | Relevant for any transaction with `external_id` set        |
| Deleted included | Deduplication checks include soft-deleted transactions     |

---

## 7. Edge Cases & Error Handling

| Scenario                                        | Expected Behavior                                                     |
|-------------------------------------------------|-----------------------------------------------------------------------|
| Create transaction on deleted account           | Raises `AccountNotActiveError`                                        |
| Create with currency mismatch                   | Raises `CurrencyMismatchError`                                        |
| Create with duplicate external_id               | Raises `DuplicateExternalIdError` (includes soft-deleted in check)    |
| Create with empty original_description          | Raises `EmptyDescriptionError`                                        |
| Create with whitespace-only description         | Raises `EmptyDescriptionError` (trimmed to empty)                     |
| Update deleted transaction                      | Raises `TransactionDeletedError`                                      |
| Update amount with wrong currency               | Raises `CurrencyMismatchError`                                        |
| Set user_description to empty string            | Raises `EmptyDescriptionError` (use None to clear)                    |
| Set merchant to whitespace-only                 | Raises `InvalidMerchantError` (use None to clear)                     |
| Set comments to whitespace-only                 | Raises `InvalidCommentsError` (use None to clear)                     |
| Soft delete already-deleted transaction         | Raises `AlreadyDeletedError`                                          |
| Recover non-deleted transaction                 | Raises `NotDeletedError`                                              |
| Recover when parent account is deleted          | Raises `ParentAccountDeletedError`                                    |
| Zero-amount transaction                         | Allowed — valid for fee waivers, memo entries                         |
| Transaction with no external_id                 | No deduplication check — valid for manual transactions                |
| mark_as_reviewed on already-REVIEWED            | No-op (idempotent)                                                    |
| mark_for_review on already-TO_REVIEW            | No-op (idempotent)                                                    |
| VIEWER tries to create/update/delete            | Raises `InsufficientPermissionError`                                  |
| Non-OWNER tries to recover                      | Raises `InsufficientPermissionError`                                  |
| original_description > 500 chars                | Raises `EmptyDescriptionError` (or dedicated length error)            |
| merchant > 200 chars                            | Raises `InvalidMerchantError`                                         |
| comments > 1000 chars                           | Raises `InvalidCommentsError`                                         |

---

## 8. Dependencies

### Internal Dependencies

- **Spec 001 (Shared Kernel):** Entity, TimestampedMixin, SoftDeletableMixin, DomainEvent, Command, Money, Currency, DateRange, PaginatedResult, RetentionPeriod, exception hierarchy
- **Spec 006 (Data Lifecycle):** SoftDeletableMixin, RetentionPolicyService, PaginatedResult[T]
- **Spec 007 (Account Management):** Account aggregate, AccountRepository, AbstractCoreFinanceUnitOfWork, AccountNotActiveError, CurrencyMismatchError
- **Spec 008 (Account Sharing):** PermissionLevel, has_permission(), InsufficientPermissionError

### External Dependencies

None — this is a pure domain + application layer spec.

---

## 9. Constraints

- **No infrastructure:** This spec covers domain and application layers only. Repository implementations are deferred to infrastructure specs
- **No cross-account operations:** Transactions belong to a single account; cross-account queries are Spec 018
- **No splitting:** Split parent/child behavior is Spec 010; only stub fields included here
- **No card linking:** Card association behavior is Spec 011; only the `card_id` stub field included
- **Pagination defaults:** page=1, page_size=50, max page_size enforcement deferred to infrastructure

---

## 10. Acceptance Criteria

### Transaction Creation

- [ ] Manual transaction created with `import_source.source_type = MANUAL` and `review_status = TO_REVIEW`
- [ ] Import transaction created with `import_source.source_type = BANK_IMPORT` and `review_status = TO_REVIEW`
- [ ] Transaction currency must match account currency — raises `CurrencyMismatchError`
- [ ] Transaction on deleted account raises `AccountNotActiveError`
- [ ] Duplicate `external_id` within same account raises `DuplicateExternalIdError`
- [ ] Duplicate check includes soft-deleted transactions
- [ ] `original_description` is required (non-empty, 1-500 chars trimmed)
- [ ] `TransactionCreated` event emitted with correct data

### Immutable Fields

- [ ] `original_description` cannot be changed after creation
- [ ] `import_source` cannot be changed after creation
- [ ] `external_id` cannot be changed after creation
- [ ] `parent_transaction_id` cannot be changed after creation
- [ ] `account_id` cannot be changed after creation
- [ ] `created_by` cannot be changed after creation

### Transaction Updates

- [ ] `user_description` can be updated (set to string or cleared with None)
- [ ] `merchant` can be updated (set to string or cleared with None)
- [ ] `comments` can be updated (set to string or cleared with None)
- [ ] `transaction_date` and `value_date` can be updated
- [ ] `amount` can be updated (currency must still match account)
- [ ] `updated_at` is set on every update
- [ ] Updating a deleted transaction raises `TransactionDeletedError`
- [ ] `TransactionUpdated` event emitted with changed_fields
- [ ] String field validation: empty/whitespace strings rejected, None accepted for clearing

### Effective Description

- [ ] Returns `user_description` when set
- [ ] Falls back to `original_description` when `user_description` is None
- [ ] `original_description` is never affected by description updates

### Review Workflow

- [ ] `mark_as_reviewed()` sets `review_status = REVIEWED`
- [ ] `mark_for_review()` sets `review_status = TO_REVIEW`
- [ ] `TransactionReviewed` event emitted on review
- [ ] Review transitions are idempotent (no error if already in target state)
- [ ] All new transactions start as `TO_REVIEW` regardless of source

### Amount Semantics

- [ ] Positive amounts represent credits (money in)
- [ ] Negative amounts represent debits (money out)
- [ ] Zero-amount transactions are allowed
- [ ] Amount uses `Money` value object (arbitrary-precision decimal)

### Lifecycle

- [ ] Soft delete sets `deleted_at`, `deleted_by`, and schedules hard delete via retention
- [ ] Soft deleting already-deleted transaction raises `AlreadyDeletedError`
- [ ] Soft deleted transactions excluded from balance calculation
- [ ] Soft deleted transactions excluded from default queries (included with flag)
- [ ] Recovery clears deletion fields
- [ ] Cannot recover if parent account is deleted — raises `ParentAccountDeletedError`
- [ ] Recovery of non-deleted transaction raises `NotDeletedError`

### Balance Calculation

- [ ] Balance = `opening_balance + sum_amounts(account_id)`
- [ ] `sum_amounts()` excludes soft-deleted transactions
- [ ] Account stubs (`calculate_balance()`, `transaction_count`) removed
- [ ] Balance accessible via `TransactionManagementService.calculate_balance()`

### Authorization

- [ ] Creating transaction requires EDITOR permission on account
- [ ] Updating transaction requires EDITOR permission
- [ ] Deleting transaction requires EDITOR permission
- [ ] Viewing transactions requires VIEWER permission
- [ ] Recovering requires OWNER permission
- [ ] `calculate_balance` requires VIEWER permission

### Pagination

- [ ] `find_by_account()` returns `PaginatedResult[Transaction]`
- [ ] `find_by_account_in_range()` returns `PaginatedResult[Transaction]`
- [ ] Default page_size = 50
- [ ] `count_by_account()` returns total count

### Application Service

- [ ] `TransactionManagementService` orchestrates all operations
- [ ] All mutations go through UoW with commit
- [ ] Events collected from Transaction entity and emitted via UoW
- [ ] `AbstractCoreFinanceUnitOfWork` extended with `transactions` attribute

---

## 11. Appendix

### Glossary

- **Transaction:** A single financial activity (debit or credit) recorded against an account
- **Import Source:** Metadata describing how a transaction was created (manual, bank import, bulk, API)
- **Review Status:** Workflow state indicating whether a user has examined a transaction
- **Effective Description:** The display description — user override or original fallback
- **External ID:** An identifier from an external system, used for deduplication during imports
- **Split Parent/Child:** Transaction splitting relationships (Spec 010) — stub fields only in this spec

### Domain Constants (new)

```python
# Transaction string field limits
MAX_ORIGINAL_DESCRIPTION_LENGTH: int = 500
MAX_USER_DESCRIPTION_LENGTH: int = 500
MAX_MERCHANT_LENGTH: int = 200
MAX_COMMENTS_LENGTH: int = 1000

# Pagination defaults
DEFAULT_TRANSACTION_PAGE_SIZE: int = 50
```

### References

- Spec 001: Shared Kernel (base types)
- Spec 006: Data Lifecycle Management (SoftDeletableMixin, PaginatedResult)
- Spec 007: Account Management (Account aggregate, opening_balance)
- Spec 008: Account Sharing (PermissionLevel, authorization)
- Spec 010: Transaction Splitting (future — stub fields included)
- Spec 011: Card Management (future — card_id stub included)
