# Spec 007: Account Management

**Version:** 1.0
**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 001 (Shared Kernel), 002 (User Registration & Identity), 006 (Data Lifecycle Management)
**Blocks:** 008, 009, 011, 015

---

## 1. Overview

This specification defines the **Account aggregate** — the central consistency boundary for financial data in the Emerald Finance Platform. It covers the Anti-Corruption Layer that translates IAM identity into the Core Finance domain's `UserReference`, the `AccountName` and `IBAN` value objects, the Account aggregate root with creation/update/lifecycle operations, and the `AccountManagementService` application service that orchestrates these operations.

**Key Principles:**

- The Account aggregate owns the consistency boundary for all financial data
- Currency is immutable after creation
- Balance is always calculated (never stored) — signature defined here, implementation deferred to Spec 009
- The Core Finance context has zero dependency on IAM internals
- Account ownership is determined by `created_by` until Spec 008 introduces share-based authorization

---

## 2. Background & Context

### Problem Statement

Users need a way to create and manage financial accounts (bank accounts, credit cards, cash, investments, etc.) that serve as containers for transactions. Each account has a fixed currency, an opening balance, and metadata. The account is the root aggregate that transactions, cards, and shares belong to.

### Business Goals

- Provide users with a flexible account structure supporting any currency and account type
- Enforce financial integrity (immutable currency, calculated balances)
- Maintain clean bounded context separation between IAM and Core Finance
- Establish the aggregate root that all subsequent Core Finance specs build upon

### Success Metrics

- Users can create accounts with any supported currency
- Account invariants are never violated (currency immutability, balance consistency)
- No IAM types leak into the Core Finance domain layer

---

## 3. Scope

### In Scope

- Anti-Corruption Layer: `UserReference` value object (IAM → Core Finance translation)
- `AccountName` value object with validation and case-insensitive equality
- `IBAN` value object with MOD-97 validation
- Account aggregate root with all attributes, invariants, and domain methods
- Account creation with currency/opening-balance validation
- Account updates (name, type, institution, notes) with ownership authorization
- Account soft delete and recovery (delegates to Shared Kernel `SoftDeletableMixin`)
- Balance calculation method (signature only — returns `opening_balance` until Spec 009)
- Domain events: `AccountCreated`, `AccountUpdated`, `AccountSoftDeleted`, `AccountRecovered`
- `AccountManagementService` (application service)
- `AccountRepository` protocol (port)
- 7 commands for all account operations

### Out of Scope

- Account sharing and permission management (Spec 008) — **owner share creation is deferred**
- Transaction management and balance implementation (Spec 009)
- Card management (Spec 011)
- Bulk operations (Spec 012)
- Bank connections (Spec 015)
- Multi-currency conversion and reporting (Spec 017)
- Account type and financial institution master data catalogs (future reference data spec)
- `find_accessible_by_user` repository method (deferred to Spec 008 when shares exist)

---

## 4. Anti-Corruption Layer

### 4.1 UserReference (Value Object)

The Core Finance context does **not** work with the full `User` aggregate or `AuthenticatedIdentity` from IAM. Instead, it uses a minimal `UserReference` that contains only what the finance domain needs: identity and display.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `user_id` | `UUID` | User identifier (from `AuthenticatedIdentity.user_id`) |
| `display_name` | `str` | Display name (from `AuthenticatedIdentity.display_name`) |

**Validation (`__post_init__`):**

- `user_id` must not be `None`
- `display_name` must not be empty after stripping whitespace

**Translation mapping:**

```
AuthenticatedIdentity (IAM)           UserReference (Core Finance)
  .user_id              ──────────►     .user_id
  .display_name         ──────────►     .display_name
  .email                ──── X (discarded)
  .system_role          ──── X (discarded)
```

**Construction:** `UserReference.from_identity(identity: AuthenticatedIdentity) -> UserReference` — class method that performs the translation.

**Design rules:**

- No roles, no email, no credentials — the finance domain only needs to know WHO
- Domain authorization is handled by `AccountShare` (Spec 008), not by system roles
- A SUPERADMIN has no special financial access — they must be explicitly shared on an account like any other user
- No IAM types (`User`, `SystemRole`, `EmailAddress`, etc.) are imported into Core Finance **domain layer**
- `AuthenticatedIdentity` is imported only at the **application layer** for translation

**Raises:** `InvalidUserReferenceError` if `user_id` is `None` or `display_name` is blank.

---

## 5. Value Objects

### 5.1 AccountName

`@dataclass(frozen=True)` with `__post_init__` validation.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `value` | `str` | User-defined account name (stored as-is after trimming) |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Trim whitespace, validate non-empty and length | `InvalidAccountNameError` |
| `__eq__` / `__hash__` | Case-insensitive comparison (use `normalized()`) | — |
| `normalized() -> str` | Lowercase, trimmed version for uniqueness checks | — |

**Business Rules:**

- Must be non-empty after stripping whitespace
- Maximum length: 100 characters (after trimming)
- Equality and hashing are **case-insensitive** (via `normalized()`)
- Uniqueness is per-user, case-insensitive — enforced by the application service, not the value object

**Raises:** `InvalidAccountNameError` with code `INVALID_ACCOUNT_NAME`.

### 5.2 IBAN

`@dataclass(frozen=True)` with `__post_init__` validation.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `value` | `str` | Complete IBAN, stored uppercase without spaces |
| `last_four` | `str` | Last 4 characters, derived at construction |

**Behavior:**

| Method | Description | Raises |
|--------|-------------|--------|
| `__init__(value: str)` | Normalize (uppercase, strip spaces), validate format + checksum | `InvalidIBANError` |
| `masked() -> str` | Returns masked display (e.g., `"****1234"`) | — |

**Validation steps (in `__post_init__`):**

1. Strip all whitespace, convert to uppercase
2. Validate minimum length (>= 15 characters) and maximum length (<= 34 characters)
3. Validate first two characters are letters (country code)
4. Validate characters 3-4 are digits (check digits)
5. Validate remaining characters are alphanumeric
6. Validate MOD-97 checksum per ISO 13616:
   - Move first 4 characters to end
   - Convert letters to numbers (A=10, B=11, ..., Z=35)
   - Compute mod 97 — result must equal 1
7. Derive `last_four` from the last 4 characters of the normalized value

**Business Rules:**

- IBAN format follows ISO 13616
- `last_four` is read-only, derived at construction
- `masked()` returns stars followed by `last_four` (e.g., `"****1234"`)

**Raises:** `InvalidIBANError` with code `INVALID_IBAN`.

---

## 6. Account Aggregate

### 6.1 Composition

```python
class Account(SoftDeletableMixin, AuditableMixin, AggregateRoot):
    ...
```

The Account aggregate root composes the following mixins (cooperative MRO with `**kwargs: Any`):

| Mixin | Provides |
|-------|----------|
| `Entity` (via `AggregateRoot`) | `_id` (UUID identity), `__eq__`, `__hash__` |
| `TimestampedMixin` (via `AggregateRoot`) | `created_at`, `updated_at`, `_touch()` |
| `AggregateRoot` | `version`, `_events`, `_increment_version()`, `collect_events()`, `_register_event()` |
| `AuditableMixin` | `created_by`, `updated_by`, `_set_updated_by()` |
| `SoftDeletableMixin` | `deleted_at`, `deleted_by`, `deletion_reason`, `hard_delete_scheduled_at`, `soft_delete()`, `recover()`, `is_deleted()`, `is_active()` |

### 6.2 Account-Specific Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| `account_name` | `AccountName` | Yes | User-defined name |
| `account_type_id` | `UUID` | Yes | Opaque reference to account type master data |
| `financial_institution_id` | `UUID` | Yes | Opaque reference to institution master data |
| `currency` | `Currency` | **No** | Account currency (immutable after creation) |
| `opening_balance` | `Money` | **No** | Initial balance (immutable after creation) |
| `iban` | `IBAN \| None` | **No** | Bank account number, optional (immutable after creation) |
| `notes` | `str \| None` | Yes | User notes, max 500 characters |

### 6.3 Immutable Fields Rationale

| Field | Rationale |
|-------|-----------|
| `currency` | Changing currency would invalidate all transactions |
| `opening_balance` | Historical accuracy — initial state must be preserved |
| `iban` | Bank account numbers don't change |

### 6.4 Aggregate Boundary

```
┌──────────────────────────────────────────────┐
│            ACCOUNT AGGREGATE                  │
│                                               │
│  Account (ROOT)  ◄── this spec                │
│    │                                          │
│    ├── Transactions (many) ── Spec 009        │
│    ├── Cards (many) ── Spec 011               │
│    └── AccountShares (many) ── Spec 008       │
│                                               │
│  INVARIANTS:                                  │
│    - Currency immutable after creation         │
│    - opening_balance.currency == currency      │
│    - Account name unique per owner (app svc)   │
│    - Notes max 500 characters                  │
│    - Balance always calculable                 │
│                                               │
│  DEFERRED INVARIANTS (future specs):           │
│    - Exactly ONE owner share (Spec 008)        │
│    - All transactions match account currency   │
│      (Spec 009)                                │
│    - One active share per user max (Spec 008)  │
└──────────────────────────────────────────────┘
```

### 6.5 Factory Method

```
Account.create(
    owner: UserReference,
    account_name: AccountName,
    currency: Currency,
    opening_balance: Money,
    account_type_id: UUID,
    financial_institution_id: UUID,
    iban: IBAN | None = None,
    notes: str | None = None,
) -> Account                                      [class method]

  Validates:
    - opening_balance.currency == currency → raises CurrencyMismatchError
    - notes length <= 500 → raises InvalidAccountNotesError

  Sets:
    - _id = new UUID
    - account_name, currency, opening_balance, iban, notes
    - account_type_id, financial_institution_id
    - created_by = owner.user_id
    - created_at = utcnow()
    - updated_at = utcnow()
    - version = 1

  Emits: AccountCreated

  Note: Account name uniqueness is validated by the application service
        BEFORE calling this factory method.
  Note: Owner AccountShare creation is deferred to Spec 008.
        Until then, account.created_by identifies the owner.
```

### 6.6 Update Methods

All update methods:
- Accept `updated_by: UUID` to track who made the change
- Call `self._touch()` to update `updated_at` and increment `version`
- Call `self._set_updated_by(updated_by)` to track the actor
- Emit `AccountUpdated` with the changed field name

```
+ update_name(new_name: AccountName, updated_by: UUID) -> None
    Updates: account_name, updated_at, updated_by, version
    Emits: AccountUpdated(changed_fields=frozenset({"account_name"}))
    Note: Uniqueness checked by application service before calling

+ update_account_type(account_type_id: UUID, updated_by: UUID) -> None
    Updates: account_type_id, updated_at, updated_by, version
    Emits: AccountUpdated(changed_fields=frozenset({"account_type_id"}))

+ update_financial_institution(institution_id: UUID, updated_by: UUID) -> None
    Updates: financial_institution_id, updated_at, updated_by, version
    Emits: AccountUpdated(changed_fields=frozenset({"financial_institution_id"}))

+ update_notes(notes: str | None, updated_by: UUID) -> None
    Validates: notes length <= 500 if not None → raises InvalidAccountNotesError
    Updates: notes, updated_at, updated_by, version
    Emits: AccountUpdated(changed_fields=frozenset({"notes"}))
```

### 6.7 Balance Calculation (Signature Only)

```
+ calculate_balance() -> Money
    Returns: opening_balance
    Note: Full implementation deferred to Spec 009.
          When transactions exist, returns:
          opening_balance + Σ(transaction.amount)
            WHERE transaction.deleted_at IS NULL
            AND transaction.parent_transaction_id IS NULL

+ transaction_count -> int (property)
    Returns: 0
    Note: Full implementation deferred to Spec 009.
```

**Why calculated, not stored:**
- Single source of truth (transactions)
- No sync issues between stored balance and actual transactions
- Audit trail is automatic
- Easier recovery from errors
- Caching is an infrastructure concern (application layer), not a domain concept

### 6.8 Lifecycle Methods

```
+ soft_delete(deleted_by: UUID, retention_period: RetentionPeriod, reason: str | None = None) -> None
    Delegates to: SoftDeletableMixin.soft_delete()
    Validates: entity is active (not already deleted) → raises AlreadyDeletedError
    Sets: deleted_at, deleted_by, deletion_reason, hard_delete_scheduled_at
    Emits: AccountSoftDeleted
    Note: Cascade to children (transactions, cards, shares) deferred to
          Specs 008/009/011. Currently only the account itself is soft-deleted.

+ recover() -> None
    Delegates to: SoftDeletableMixin.recover()
    Validates: entity is soft-deleted → raises NotDeletedError
    Clears: deleted_at, deleted_by, deletion_reason, hard_delete_scheduled_at
    Emits: AccountRecovered
    Note: When children exist (future specs), they remain in trash
          and are recovered individually per Spec 006 patterns.
```

---

## 7. Domain Events

All events are `@dataclass(frozen=True)` extending `DomainEvent` with `aggregate_type = "account"`.

### 7.1 AccountCreated

| Field | Type | Description |
|-------|------|-------------|
| `aggregate_id` | `UUID` | Account ID |
| `owner_user_id` | `UUID` | User who created the account |
| `currency_code` | `str` | Currency code (e.g., "USD") |
| `account_name` | `str` | Account name value |
| `opening_balance` | `Decimal` | Opening balance amount |

### 7.2 AccountUpdated

| Field | Type | Description |
|-------|------|-------------|
| `aggregate_id` | `UUID` | Account ID |
| `updated_by` | `UUID` | User who made the update |
| `changed_fields` | `frozenset[str]` | Set of changed field names |

### 7.3 AccountSoftDeleted

| Field | Type | Description |
|-------|------|-------------|
| `aggregate_id` | `UUID` | Account ID |
| `deleted_by` | `UUID` | User who deleted the account |
| `reason` | `str \| None` | Deletion reason |

### 7.4 AccountRecovered

| Field | Type | Description |
|-------|------|-------------|
| `aggregate_id` | `UUID` | Account ID |
| `recovered_by` | `UUID` | User who recovered the account |

---

## 8. Exceptions

All exceptions follow the shared kernel hierarchy. Each has a unique `code`.

| Exception | Extends | Code | When Raised |
|-----------|---------|------|-------------|
| `InvalidAccountNameError` | `InvalidValueError` | `INVALID_ACCOUNT_NAME` | Name empty or > 100 chars |
| `InvalidIBANError` | `InvalidValueError` | `INVALID_IBAN` | IBAN fails format or MOD-97 checksum |
| `InvalidAccountNotesError` | `InvalidValueError` | `INVALID_ACCOUNT_NOTES` | Notes exceed 500 characters |
| `InvalidUserReferenceError` | `InvalidValueError` | `INVALID_USER_REFERENCE` | UserReference has None user_id or blank display_name |
| `AccountNameAlreadyExistsError` | `AlreadyExistsError` | `ACCOUNT_NAME_ALREADY_EXISTS` | Duplicate name for same user |
| `AccountNotFoundError` | `NotFoundError` | `ACCOUNT_NOT_FOUND` | Account ID not found in repository |
| `NotAccountOwnerError` | `AuthorizationError` | `NOT_ACCOUNT_OWNER` | Non-owner attempts mutation (pre-Spec 008) |

**Shared kernel exceptions reused directly (no subclass needed):**
- `CurrencyMismatchError` — opening balance currency != account currency
- `AlreadyDeletedError` — soft-deleting an already-deleted account
- `NotDeletedError` — recovering a non-deleted account

---

## 9. Commands

All commands are `@dataclass(frozen=True)` extending `Command`.

### 9.1 CreateAccount

| Field | Type | Description |
|-------|------|-------------|
| `owner_user_id` | `UUID` | ID of the user creating the account |
| `owner_display_name` | `str` | Display name for UserReference construction |
| `account_name` | `str` | Raw account name (validated by service) |
| `currency_code` | `str` | Currency code string (e.g., "USD") |
| `opening_balance` | `Decimal` | Opening balance amount |
| `account_type_id` | `UUID` | Account type reference |
| `financial_institution_id` | `UUID` | Financial institution reference |
| `iban` | `str \| None` | Raw IBAN string, optional |
| `notes` | `str \| None` | Account notes, optional |

### 9.2 RenameAccount

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | `UUID` | Target account |
| `requesting_user_id` | `UUID` | User requesting the rename |
| `new_name` | `str` | New raw account name |

### 9.3 UpdateAccountType

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | `UUID` | Target account |
| `requesting_user_id` | `UUID` | User requesting the update |
| `account_type_id` | `UUID` | New account type reference |

### 9.4 UpdateFinancialInstitution

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | `UUID` | Target account |
| `requesting_user_id` | `UUID` | User requesting the update |
| `financial_institution_id` | `UUID` | New institution reference |

### 9.5 UpdateAccountNotes

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | `UUID` | Target account |
| `requesting_user_id` | `UUID` | User requesting the update |
| `notes` | `str \| None` | New notes (or None to clear) |

### 9.6 SoftDeleteAccount

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | `UUID` | Target account |
| `requesting_user_id` | `UUID` | User requesting deletion |
| `reason` | `str \| None` | Optional deletion reason |

### 9.7 RecoverAccount

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | `UUID` | Target account |
| `requesting_user_id` | `UUID` | User requesting recovery |

---

## 10. Application Service: AccountManagementService

This is an **application service** (not a domain service) because it coordinates persistence, validation, and aggregate creation. It depends on `AbstractCoreFinanceUnitOfWork` and `RetentionPolicyService`.

### 10.1 Constructor Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `uow` | `AbstractCoreFinanceUnitOfWork` | Transaction/persistence boundary |
| `retention_policy_service` | `RetentionPolicyService` | Calculate retention for soft delete |

### 10.2 Service Methods

```
+ create_account(cmd: CreateAccount) -> Account
    1. Build UserReference(user_id=cmd.owner_user_id, display_name=cmd.owner_display_name)
    2. Build Currency from cmd.currency_code → raises InvalidValueError if invalid
    3. Build AccountName(cmd.account_name) → raises InvalidAccountNameError
    4. Build Money(cmd.opening_balance, currency) → raises InvalidValueError
    5. Build IBAN(cmd.iban) if provided → raises InvalidIBANError
    6. Check uow.accounts.exists_by_name_for_user(account_name, cmd.owner_user_id)
       → raises AccountNameAlreadyExistsError if duplicate
    7. Account.create(owner, account_name, currency, money, account_type_id,
                      financial_institution_id, iban, notes)
       → raises CurrencyMismatchError if mismatch
    8. uow.accounts.save(account)
    9. uow.commit()
    10. Return account

+ rename_account(cmd: RenameAccount) -> None
    1. Load account: uow.accounts.find_by_id(cmd.account_id)
       → raises AccountNotFoundError if not found
    2. Verify ownership: account.created_by == cmd.requesting_user_id
       → raises NotAccountOwnerError if not owner
    3. Build AccountName(cmd.new_name) → raises InvalidAccountNameError
    4. Check uow.accounts.exists_by_name_for_user(new_name, account.created_by)
       → raises AccountNameAlreadyExistsError if duplicate
    5. account.update_name(new_name, cmd.requesting_user_id)
    6. uow.commit()

+ update_account_type(cmd: UpdateAccountType) -> None
    1. Load account → raises AccountNotFoundError
    2. Verify ownership → raises NotAccountOwnerError
    3. account.update_account_type(cmd.account_type_id, cmd.requesting_user_id)
    4. uow.commit()

+ update_financial_institution(cmd: UpdateFinancialInstitution) -> None
    1. Load account → raises AccountNotFoundError
    2. Verify ownership → raises NotAccountOwnerError
    3. account.update_financial_institution(cmd.financial_institution_id, cmd.requesting_user_id)
    4. uow.commit()

+ update_account_notes(cmd: UpdateAccountNotes) -> None
    1. Load account → raises AccountNotFoundError
    2. Verify ownership → raises NotAccountOwnerError
    3. account.update_notes(cmd.notes, cmd.requesting_user_id)
       → raises InvalidAccountNotesError if notes > 500 chars
    4. uow.commit()

+ soft_delete_account(cmd: SoftDeleteAccount) -> None
    1. Load account → raises AccountNotFoundError
    2. Verify ownership → raises NotAccountOwnerError
    3. Calculate retention period via retention_policy_service.get_effective_retention(
         DeletableEntityType.FINANCIAL_ACCOUNT, cmd.requesting_user_id)
    4. account.soft_delete(cmd.requesting_user_id, retention_period, cmd.reason)
       → raises AlreadyDeletedError if already deleted
    5. uow.commit()

+ recover_account(cmd: RecoverAccount) -> None
    1. Load account (include_deleted=True) → raises AccountNotFoundError
    2. Verify ownership → raises NotAccountOwnerError
    3. account.recover()
       → raises NotDeletedError if not deleted
    4. uow.commit()
```

### 10.3 Authorization Model (Pre-Spec 008)

Until Spec 008 introduces share-based authorization, all mutations are gated by a simple ownership check:

```
if account.created_by != requesting_user_id:
    raise NotAccountOwnerError(account_id=account.id)
```

When Spec 008 is implemented, this check evolves into share-based permission validation where different operations require different permission levels (OWNER, EDITOR, VIEWER).

---

## 11. Repository Protocol

### 11.1 AccountRepository

```python
class AccountRepository(Protocol):
    def save(self, account: Account) -> None: ...
    def find_by_id(self, account_id: UUID, include_deleted: bool = False) -> Account | None: ...
    def find_by_owner(self, user_id: UUID, include_deleted: bool = False) -> list[Account]: ...
    def exists_by_name_for_user(self, account_name: AccountName, user_id: UUID) -> bool: ...
```

**Method details:**

| Method | Description |
|--------|-------------|
| `save` | Persist new or updated account |
| `find_by_id` | Find by primary key. Excludes soft-deleted by default. |
| `find_by_owner` | All accounts where `created_by == user_id`. Excludes soft-deleted by default. |
| `exists_by_name_for_user` | For uniqueness validation. Uses `AccountName.normalized()` for case-insensitive comparison. Always excludes soft-deleted accounts (deleted names can be reused). |

**Deferred to Spec 008:**
- `find_accessible_by_user(user_id, include_deleted)` — returns accounts where user has any share

### 11.2 AbstractCoreFinanceUnitOfWork

```python
class AbstractCoreFinanceUnitOfWork(AbstractUnitOfWork):
    accounts: AccountRepository
```

Extends the shared kernel `AbstractUnitOfWork` with the `accounts` repository. Future specs will add `transactions`, `cards`, `shares`, etc.

---

## 12. Acceptance Criteria

### AC-01: Anti-Corruption Layer

- [ ] `UserReference` contains only `user_id` and `display_name`
- [ ] `UserReference.from_identity()` correctly translates `AuthenticatedIdentity`
- [ ] Email, system role, and admin permissions are discarded during translation
- [ ] No IAM domain types (`User`, `SystemRole`, `EmailAddress`) are imported into Core Finance domain layer
- [ ] `AuthenticatedIdentity` import is restricted to the Core Finance application layer
- [ ] `InvalidUserReferenceError` raised for `None` user_id or blank display_name

### AC-02: AccountName Value Object

- [ ] Rejects empty strings (after trimming whitespace) → `InvalidAccountNameError`
- [ ] Rejects strings longer than 100 characters → `InvalidAccountNameError`
- [ ] Stores the trimmed (but original-case) value
- [ ] Equality and hashing are case-insensitive (`"My Account" == "my account"`)
- [ ] `normalized()` returns lowercase, trimmed version

### AC-03: IBAN Value Object

- [ ] Normalizes input: strips whitespace, converts to uppercase
- [ ] Rejects IBANs shorter than 15 or longer than 34 characters → `InvalidIBANError`
- [ ] Rejects IBANs with invalid country code format → `InvalidIBANError`
- [ ] Validates MOD-97 checksum per ISO 13616 → `InvalidIBANError` if check fails
- [ ] `last_four` is derived from the last 4 characters at construction
- [ ] `masked()` returns `"****"` + `last_four` (e.g., `"****1234"`)
- [ ] Valid IBAN examples pass: `GB29 NWBK 6016 1331 9268 19`, `DE89 3704 0044 0532 0130 00`
- [ ] Invalid IBAN examples fail: `GB00 NWBK 6016 1331 9268 19` (bad checksum), `XX12345` (too short)

### AC-04: Account Creation

- [ ] `Account.create()` produces a valid Account with all attributes set
- [ ] `created_by` is set to `owner.user_id`
- [ ] `currency` and `opening_balance` are immutable after creation (no setter/update method)
- [ ] `iban` is immutable after creation
- [ ] `opening_balance.currency` must match `currency` → `CurrencyMismatchError` if different
- [ ] Opening balance can be negative (credit card debt), zero, or positive
- [ ] Notes validated: max 500 characters → `InvalidAccountNotesError`
- [ ] `AccountCreated` event emitted with correct data (account_id, owner_user_id, currency_code, name, balance)
- [ ] Version starts at 1

### AC-05: Account Name Uniqueness

- [ ] `AccountManagementService.create_account()` checks name uniqueness for the owner
- [ ] `AccountManagementService.rename_account()` checks name uniqueness for the owner
- [ ] Uniqueness is case-insensitive (via `AccountName.normalized()`)
- [ ] Soft-deleted accounts' names can be reused (excluded from uniqueness check)
- [ ] Raises `AccountNameAlreadyExistsError` on duplicate

### AC-06: Account Updates

- [ ] `update_name` changes `account_name`, sets `updated_at`, `updated_by`, increments `version`
- [ ] `update_account_type` changes `account_type_id`, sets `updated_at`, `updated_by`, increments `version`
- [ ] `update_financial_institution` changes `financial_institution_id`, sets `updated_at`, `updated_by`, increments `version`
- [ ] `update_notes` changes `notes` (including to `None`), sets `updated_at`, `updated_by`, increments `version`
- [ ] `update_notes` validates max 500 characters → `InvalidAccountNotesError`
- [ ] Each update emits `AccountUpdated` with correct `changed_fields` frozenset
- [ ] All update service methods verify ownership → `NotAccountOwnerError` if not owner

### AC-07: Balance Calculation

- [ ] `calculate_balance()` returns `opening_balance` (stub until Spec 009)
- [ ] `transaction_count` property returns 0 (stub until Spec 009)
- [ ] Balance currency always matches account currency

### AC-08: Soft Delete

- [ ] `soft_delete()` sets `deleted_at`, `deleted_by`, `deletion_reason`, `hard_delete_scheduled_at`
- [ ] `hard_delete_scheduled_at` is calculated via `RetentionPolicyService`
- [ ] Emits `AccountSoftDeleted` event
- [ ] Raises `AlreadyDeletedError` when soft-deleting an already-deleted account
- [ ] Service verifies ownership before deletion
- [ ] No cascade to children (deferred to Specs 008/009/011)

### AC-09: Account Recovery

- [ ] `recover()` clears all deletion fields (`deleted_at`, `deleted_by`, `deletion_reason`, `hard_delete_scheduled_at`)
- [ ] Emits `AccountRecovered` event
- [ ] Raises `NotDeletedError` when recovering a non-deleted account
- [ ] Service verifies ownership before recovery
- [ ] Service loads account with `include_deleted=True` to find soft-deleted accounts

### AC-10: Repository

- [ ] `save()` persists new and updated accounts
- [ ] `find_by_id()` returns `None` for non-existent accounts
- [ ] `find_by_id()` excludes soft-deleted by default, includes with `include_deleted=True`
- [ ] `find_by_owner()` returns only accounts where `created_by == user_id`
- [ ] `find_by_owner()` excludes soft-deleted by default, includes with `include_deleted=True`
- [ ] `exists_by_name_for_user()` uses case-insensitive comparison
- [ ] `exists_by_name_for_user()` always excludes soft-deleted accounts

---

## 13. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Create account with empty name | `InvalidAccountNameError` |
| Create account with 101-character name | `InvalidAccountNameError` |
| Create account with USD currency but EUR opening balance | `CurrencyMismatchError` |
| Create account with negative opening balance | Allowed (e.g., credit card) |
| Create account with zero opening balance | Allowed |
| Create account with duplicate name for same user | `AccountNameAlreadyExistsError` |
| Create account with same name as a soft-deleted account | Allowed (deleted names can be reused) |
| Create account with invalid IBAN | `InvalidIBANError` |
| Create account without IBAN | Allowed (`iban=None`) |
| Create account with notes > 500 chars | `InvalidAccountNotesError` |
| Rename to a name already used by same user | `AccountNameAlreadyExistsError` |
| Rename to same name with different case | Rejected (case-insensitive uniqueness) |
| Update account by non-owner | `NotAccountOwnerError` |
| Update account that doesn't exist | `AccountNotFoundError` |
| Soft-delete account that's already deleted | `AlreadyDeletedError` |
| Recover account that's not deleted | `NotDeletedError` |
| Recover soft-deleted account | Success — deletion fields cleared |
| Find account by ID when soft-deleted (default) | Returns `None` |
| Find account by ID when soft-deleted (`include_deleted=True`) | Returns the account |
| UserReference with blank display_name | `InvalidUserReferenceError` |
| IBAN with spaces and lowercase | Normalized to uppercase, spaces stripped, then validated |

---

## 14. Dependencies

### Internal Dependencies

| Dependency | Source | What's Used |
|------------|--------|-------------|
| Shared Kernel (Spec 001) | `emerald.shared_kernel` | `Entity`, `AggregateRoot`, `SoftDeletableMixin`, `AuditableMixin`, `TimestampedMixin`, `Currency`, `Money`, `DomainEvent`, `Command`, `RetentionPeriod`, exception hierarchy |
| Data Lifecycle (Spec 006) | `emerald.shared_kernel` | `DeletableEntityType.FINANCIAL_ACCOUNT`, `RetentionPolicyService`, retention constants |
| IAM (Spec 002/003) | `emerald.iam` | `AuthenticatedIdentity` (application layer import only) |

### External Dependencies

None — this spec is pure domain logic with no external service dependencies.

---

## 15. Constraints

- **No IAM leakage:** Core Finance domain layer must not import any IAM types. Only the application layer may import `AuthenticatedIdentity` for translation to `UserReference`.
- **Immutability enforcement:** `currency`, `opening_balance`, and `iban` have no update methods. Attempting to change them is a programming error caught at the type level, not a runtime check.
- **Opaque references:** `account_type_id` and `financial_institution_id` are opaque UUIDs. No domain-level validation that they point to real entities. Infrastructure/application layer may validate against master data catalogs.
- **Pre-Spec 008 authorization:** All mutations require `account.created_by == requesting_user_id`. This is a temporary model replaced by share-based authorization in Spec 008.

---

## 16. Glossary

| Term | Definition |
|------|------------|
| **Account** | The aggregate root for financial data — holds a fixed currency, opening balance, and is the parent of transactions, cards, and shares |
| **UserReference** | An Anti-Corruption Layer value object that translates IAM identity into the minimal information the Core Finance domain needs |
| **AccountName** | A value object for user-defined account names with case-insensitive equality |
| **IBAN** | International Bank Account Number — a value object validated per ISO 13616 (MOD-97) |
| **Opening Balance** | The initial balance of an account at creation time, immutable, of the same currency as the account |
| **ACL (Anti-Corruption Layer)** | A DDD pattern that prevents one bounded context's model from leaking into another |
| **Opaque UUID** | A UUID reference to an entity in another system or catalog, with no domain-level validation of its existence |
