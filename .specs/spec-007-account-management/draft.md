# Spec 007: Account Management

**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 001 (Shared Kernel), 002 (User Registration & Identity), 006 (Data Lifecycle Management)
**Blocks:** 008, 009, 011, 015

---

## 1. Overview

This spec defines the Account aggregate — the central consistency boundary for financial data in the Emerald Finance Platform. It covers account creation, updates, balance calculation, and the Anti-Corruption Layer that translates IAM identity into the Core Finance domain's `UserReference`.

**Key Principle:** The Account aggregate owns the consistency boundary for all financial data. Currency is immutable after creation. Balance is always calculated (never stored). The Core Finance context has zero dependency on IAM internals.

## 2. Scope

### In Scope

- Anti-Corruption Layer: `UserReference` value object
- `AccountName` value object
- Account entity with all attributes and invariants
- Account creation with owner share auto-creation
- Balance calculation (opening balance + sum of transactions)
- Account update (mutable fields only)
- Account soft delete (delegates to Spec 006 lifecycle)
- Account recovery
- Account repository interface

### Out of Scope

- Account sharing and permission management (Spec 008)
- Transaction management (Spec 009)
- Card management (Spec 011)
- Bulk operations (Spec 012)
- Bank connections (Spec 015)
- Multi-currency conversion and reporting (Spec 017)

## 3. Anti-Corruption Layer

### 3.1 UserReference (Value Object)

The Core Finance context does not work with the full User entity from IAM. Instead, it receives an `AuthenticatedIdentity` (Spec 003) and translates it to a minimal `UserReference`.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| user_id | UUID | User identifier |
| display_name | str | Username or full name for display |

**Rules:**

- No roles, no email, no credentials — the finance domain only needs to know WHO is performing an action
- Domain authorization is handled by `AccountShare` (Spec 008), not by system roles
- A SUPERADMIN has no special financial access — they must be explicitly shared on an account like any other user

**Translation:**

```
AuthenticatedIdentity (from IAM)     UserReference (Core Finance)
  - user_id              ──────────►   - user_id
  - display_name         ──────────►   - display_name
  - email                ──── X (discarded)
  - system_role          ──── X (discarded)
  - admin_permissions    ──── X (discarded)
```

## 4. Value Objects

### 4.1 AccountName

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| value | str | User-defined account name |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Validate and normalize | `InvalidAccountNameError` |
| `__eq__` / `__hash__` | Case-insensitive comparison | - |
| `normalized() -> str` | Lowercase, trimmed version for uniqueness checks | - |

**Business Rules:**

- Must be non-empty after trimming
- Maximum length: 100 characters
- Uniqueness is per-user, case-insensitive (enforced by domain service, not the value object)

### 4.2 IBAN (Value Object)

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| full_number | str | Complete IBAN |
| last_four | str | Last 4 characters for display |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Validate checksum and format | `InvalidIBANError` |
| `masked() -> str` | Returns masked version (e.g., "****1234") | - |

**Business Rules:**

- Validated using MOD-97 checksum (ISO 13616)
- Country-specific length validation
- `last_four` derived from `full_number` at construction

## 5. Account Entity

### 5.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| account_id | UUID | No | Unique identifier |
| account_name | AccountName | Yes | User-defined name |
| account_type_id | UUID | Yes | Reference to account type master data |
| financial_institution_id | UUID | Yes | Reference to institution master data |
| currency | Currency | No | Account currency (immutable after creation) |
| opening_balance | Money | No | Initial balance (immutable after creation) |
| iban | IBAN? | No | Bank account number (immutable after creation) |
| notes | str? | Yes | User notes |
| created_at | datetime | No | Creation time |
| created_by | UUID | No | User who created this account |
| updated_at | datetime | Auto | Last update time |
| deleted_at | datetime? | Yes | Soft delete timestamp |
| deleted_by | UUID? | Yes | Who performed deletion |
| hard_delete_scheduled_at | datetime? | Yes | When automatic hard delete occurs |

### 5.2 Immutable Fields

These fields are set at creation and can never change:

| Field | Rationale |
|-------|-----------|
| currency | Changing currency would invalidate all transactions |
| opening_balance | Historical accuracy — initial state must be preserved |
| iban | Bank account numbers don't change |

### 5.3 Computed Properties

| Property | Type | Derivation |
|----------|------|------------|
| current_balance | Money | `opening_balance + sum(active_transactions)` |
| transaction_count | int | Count of active (non-deleted) transactions |

**Balance Calculation Rule:**

```
current_balance = opening_balance
  + Σ(transaction.amount)
    WHERE transaction.deleted_at IS NULL
    AND transaction.parent_transaction_id IS NULL  (exclude split parents)

Note: When a transaction is split, the parent amount is excluded
and only the split children's amounts are counted. This prevents
double-counting.
```

**Why calculated, not stored:**

- Single source of truth (transactions)
- No sync issues between stored balance and actual transactions
- Audit trail is automatic
- Easier recovery from errors

**Performance:** Balance may be cached in the application layer with invalidation on transaction changes. The cache is an infrastructure concern, not a domain concept.

## 6. Account Aggregate

The Account is the aggregate root. It enforces all invariants across its children (Transactions, Cards, AccountShares).

### 6.1 Aggregate Boundary

```
┌─────────────────────────────────────────────────┐
│              ACCOUNT AGGREGATE                   │
│                                                  │
│  Account (ROOT)                                  │
│    │                                             │
│    ├── Transactions (many) ── Spec 009           │
│    ├── Cards (many) ── Spec 011                  │
│    └── AccountShares (many) ── Spec 008          │
│                                                  │
│  INVARIANTS:                                     │
│    • Exactly ONE owner share at all times         │
│    • All transaction currencies match account     │
│    • Balance is always calculable                 │
│    • One active share per user maximum            │
│    • Account name unique per user                 │
└─────────────────────────────────────────────────┘
```

**Note:** Transactions, Cards, and Shares are part of the aggregate but are specified in their own specs (009, 011, 008). This spec defines the root entity and aggregate-level invariants.

### 6.2 Domain Methods

```
Account:
  // Creation
  + create(
      owner: UserReference,
      account_name: AccountName,
      currency: Currency,
      opening_balance: Money,
      account_type_id: UUID,
      financial_institution_id: UUID,
      iban: IBAN? = None,
      notes: str? = None
    ) -> Account                                      [class method]
      Validates:
        - opening_balance.currency matches currency
      Creates:
        - Account entity
        - Owner AccountShare (permission_level=OWNER) automatically
      Emits: AccountCreated
      Raises: CurrencyMismatchError
      Note: Account name uniqueness checked by domain service

  // Updates
  + update_name(new_name: AccountName) -> None
      Updates: account_name, updated_at
      Note: Uniqueness checked by domain service

  + update_account_type(account_type_id: UUID) -> None
      Updates: account_type_id, updated_at

  + update_financial_institution(institution_id: UUID) -> None
      Updates: financial_institution_id, updated_at

  + update_notes(notes: str?) -> None
      Updates: notes, updated_at

  // Balance
  + calculate_balance() -> Money
      Returns: opening_balance + sum of all active, non-split-parent transactions

  // Lifecycle
  + soft_delete(deleted_by: UUID, reason: str?) -> None
      Validates: entity is active
      Cascades: soft deletes all transactions, cards, and non-owner shares
      Emits: AccountSoftDeleted
      Raises: AlreadyDeletedError

  + recover() -> None
      Validates: entity is soft deleted
      Clears: deletion fields
      Note: Children remain in trash (recovered individually per Spec 006)
      Emits: AccountRecovered
      Raises: NotDeletedError
```

## 7. Account Creation Flow

```
User requests account creation:
     │
     ▼
  1. Translate AuthenticatedIdentity → UserReference
     │
     ▼
  2. Validate account name unique per user (domain service)
     Raises: AccountNameAlreadyExistsError
     │
     ▼
  3. Validate opening_balance currency matches account currency
     Raises: CurrencyMismatchError
     │
     ▼
  4. Create Account entity
     │
     ▼
  5. Auto-create Owner AccountShare:
     - user_id = creator's user_id
     - permission_level = OWNER
     - granted_by = creator's user_id
     │
     ▼
  6. Emit AccountCreated event
     │
     ▼
  7. Persist via repository
```

**Critical Invariant:** An Account can never exist without exactly one OWNER share. The owner share is created atomically with the account.

## 8. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `AccountCreated` | `Account.create()` | account_id, owner_user_id, currency, account_name |
| `AccountUpdated` | Any update method | account_id, changed_fields |
| `AccountSoftDeleted` | `soft_delete()` | account_id, deleted_by, reason |
| `AccountRecovered` | `recover()` | account_id, recovered_by |

## 9. Domain Service: Account Management Service

```
AccountManagementService:
  + create_account(
      owner: UserReference,
      account_name: str,
      currency: Currency,
      opening_balance: Decimal,
      account_type_id: UUID,
      financial_institution_id: UUID,
      iban: str? = None,
      notes: str? = None
    ) -> Account
      1. Create AccountName value object (validates format)
      2. Create Money value object for opening balance
      3. Check account name uniqueness for this user
         Raises: AccountNameAlreadyExistsError
      4. Account.create(...)
      5. Persist and return

  + rename_account(
      account_id: UUID,
      requesting_user: UserReference,
      new_name: str
    ) -> None
      1. Load account
      2. Verify requesting_user is OWNER (Spec 008)
      3. Create AccountName value object
      4. Check uniqueness for owner's user_id
         Raises: AccountNameAlreadyExistsError
      5. account.update_name(new_name)
      6. Persist
```

## 10. Repository Interface

```
AccountRepository (Protocol):
  + save(account: Account) -> None
  + find_by_id(account_id: UUID) -> Account?
  + find_by_owner(user_id: UUID, include_deleted: bool = False) -> list[Account]
  + find_accessible_by_user(user_id: UUID, include_deleted: bool = False) -> list[Account]
      Returns all accounts where user has any share (owner, editor, or viewer)
  + exists_by_name_for_user(account_name: AccountName, user_id: UUID) -> bool
      For uniqueness validation (excludes soft-deleted accounts)
```

## 11. Acceptance Criteria

### Anti-Corruption Layer

- [ ] `UserReference` contains only `user_id` and `display_name`
- [ ] `AuthenticatedIdentity` is correctly translated to `UserReference` (email, role, permissions discarded)
- [ ] No IAM types (User, SystemRole, etc.) are imported into Core Finance domain

### Value Objects

- [ ] `AccountName` rejects empty strings and strings over 100 characters
- [ ] `AccountName` equality is case-insensitive
- [ ] `IBAN` validates MOD-97 checksum
- [ ] `IBAN` provides masked display (e.g., "****1234")

### Account Creation

- [ ] Creating an account automatically creates an OWNER share for the creator
- [ ] Account and owner share are created atomically
- [ ] `opening_balance` currency must match `currency` — raises `CurrencyMismatchError` if different
- [ ] Account name must be unique per user — raises `AccountNameAlreadyExistsError` on duplicate
- [ ] `AccountCreated` event is emitted with correct data
- [ ] `currency`, `opening_balance`, and `iban` are immutable after creation

### Account Updates

- [ ] `account_name` can be updated (with uniqueness re-validation)
- [ ] `account_type_id` and `financial_institution_id` can be updated
- [ ] `notes` can be updated or set to None
- [ ] `currency`, `opening_balance`, `iban` cannot be changed — immutable
- [ ] `updated_at` is set on every update

### Balance Calculation

- [ ] Balance = `opening_balance` + sum of all active transactions
- [ ] Soft-deleted transactions are excluded from balance
- [ ] Split parent transactions are excluded when split children exist (no double-counting)
- [ ] Account with no transactions returns `opening_balance`
- [ ] Balance currency always matches account currency

### Lifecycle

- [ ] Soft delete sets `deleted_at`, `deleted_by`, `hard_delete_scheduled_at`
- [ ] Soft delete cascades to transactions, cards, and non-owner shares
- [ ] Soft deleting an already-deleted account raises `AlreadyDeletedError`
- [ ] Recovery clears all deletion fields
- [ ] Recovery does NOT auto-recover children (they stay in trash)
- [ ] Recovering a non-deleted account raises `NotDeletedError`

### Query

- [ ] `find_by_owner` returns only accounts where user is owner
- [ ] `find_accessible_by_user` returns all accounts where user has any share level
- [ ] Soft-deleted accounts excluded by default, included with `include_deleted=True`
