# Spec 024: Core Finance Persistence Layer

**Status:** Draft
**Bounded Context:** Core Finance (Infrastructure)
**Dependencies:** 021 (Configuration & Database Foundation), 022 (IAM Persistence Layer), 007-012 (Core Finance domain specs)
**Blocks:** 025, 026

---

## 1. Overview

This spec implements ORM models and repositories for the most data-intensive context — accounts with child collections (shares, cards), transactions with splits, and all Core Finance query patterns.

**Key Principle:** Complex domain objects (Account with shares/cards, Transaction with split hierarchy) require careful ORM mapping. Money value objects map to two columns. Soft-delete filtering is applied at the repository level, not globally.

## 2. Scope

### In Scope

- ORM models: `AccountModel`, `AccountShareModel`, `CardModel`, `TransactionModel`
- Repository implementations: `SqlAlchemyAccountRepository`, `SqlAlchemyTransactionRepository`
- `SqlAlchemyCoreFinanceUnitOfWork`
- Alembic migration for all Core Finance tables
- Money VO ↔ two-column mapping
- Soft-delete filtering with `include_deleted` parameter
- Split transaction self-referential FK

### Out of Scope

- Classification persistence (spec 025)
- Integrations persistence (spec 025)
- API layer (specs 028-030)

## 3. ORM Models

### 3.1 AccountModel

**Table:** `cf_accounts`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `Account.id` |
| account_name | VARCHAR(100) | No | — | `Account.account_name.value` |
| account_type_id | UUID | Yes | — | `Account.account_type_id` |
| financial_institution_id | UUID | Yes | — | `Account.financial_institution_id` |
| currency_code | VARCHAR(3) | No | — | `Account.currency.code` |
| opening_balance_amount | DECIMAL(19,4) | No | — | `Account.opening_balance.amount` |
| opening_balance_currency | VARCHAR(3) | No | — | `Account.opening_balance.currency.code` |
| iban | VARCHAR(34) | Yes | — | `Account.iban.full_number` |
| notes | TEXT | Yes | — | `Account.notes` |
| version | INTEGER | No | DEFAULT 1 | `Account.version` |
| created_at | TIMESTAMP(tz) | No | — | `Account.created_at` |
| created_by | UUID | No | — | `Account.created_by` |
| updated_at | TIMESTAMP(tz) | No | — | `Account.updated_at` |
| updated_by | UUID | Yes | — | `Account.updated_by` |
| deleted_at | TIMESTAMP(tz) | Yes | — | `Account.deleted_at` |
| deleted_by | UUID | Yes | — | `Account.deleted_by` |

**Indexes:**
- `ix_cf_accounts_created_by` — on `created_by`
- Functional index for case-insensitive account name uniqueness per owner

### 3.2 AccountShareModel

**Table:** `cf_account_shares`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `AccountShare.id` |
| account_id | UUID | No | FK → cf_accounts.id, INDEX | Parent account |
| user_id | UUID | No | INDEX | `AccountShare.user_id` |
| permission_level | VARCHAR(10) | No | — | `AccountShare.permission_level.value` |
| granted_by | UUID | No | — | `AccountShare.granted_by` |
| granted_at | TIMESTAMP(tz) | No | — | `AccountShare.granted_at` |
| revoked_at | TIMESTAMP(tz) | Yes | — | `AccountShare.revoked_at` |
| revoked_by | UUID | Yes | — | `AccountShare.revoked_by` |

**Constraints:**
- FK `account_id` → `cf_accounts.id` ON DELETE CASCADE
- UNIQUE(`account_id`, `user_id`) WHERE `revoked_at IS NULL` (partial unique — one active share per user per account)

**Indexes:**
- `ix_cf_account_shares_account_id` — on `account_id`
- `ix_cf_account_shares_user_id` — on `user_id`

### 3.3 CardModel

**Table:** `cf_cards`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `Card.id` |
| account_id | UUID | No | FK → cf_accounts.id, INDEX | Parent account |
| card_name | VARCHAR(100) | No | — | `Card.card_name.value` |
| last_four_digits | VARCHAR(4) | No | — | `Card.last_four_digits` |
| card_type | VARCHAR(20) | No | — | `Card.card_type.value` |
| card_network | VARCHAR(20) | Yes | — | `Card.card_network.value` |
| expiration_date | DATE | Yes | — | `Card.expiration_date` |
| is_active | BOOLEAN | No | DEFAULT true | `Card.is_active` |
| created_at | TIMESTAMP(tz) | No | — | `Card.created_at` |
| updated_at | TIMESTAMP(tz) | No | — | `Card.updated_at` |
| deleted_at | TIMESTAMP(tz) | Yes | — | `Card.deleted_at` |
| deleted_by | UUID | Yes | — | `Card.deleted_by` |

**Constraints:**
- FK `account_id` → `cf_accounts.id` ON DELETE CASCADE

### 3.4 TransactionModel

**Table:** `cf_transactions`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `Transaction.id` |
| account_id | UUID | No | FK → cf_accounts.id, INDEX | `Transaction.account_id` |
| amount | DECIMAL(19,4) | No | — | `Transaction.amount.amount` |
| currency_code | VARCHAR(3) | No | — | `Transaction.amount.currency.code` |
| description | VARCHAR(500) | No | — | `Transaction.description` |
| merchant | VARCHAR(200) | Yes | — | `Transaction.merchant` |
| transaction_date | DATE | No | INDEX | `Transaction.transaction_date` |
| value_date | DATE | Yes | — | `Transaction.value_date` |
| external_id | VARCHAR(255) | Yes | INDEX | `Transaction.external_id` |
| comments | TEXT | Yes | — | `Transaction.comments` |
| card_id | UUID | Yes | FK → cf_cards.id | `Transaction.card_id` |
| review_status | VARCHAR(20) | No | DEFAULT 'TO_REVIEW' | `Transaction.review_status.value` |
| import_source_type | VARCHAR(20) | Yes | — | `Transaction.import_source.source_type.value` |
| import_source_id | VARCHAR(255) | Yes | — | `Transaction.import_source.source_id` |
| import_source_imported_at | TIMESTAMP(tz) | Yes | — | `Transaction.import_source.imported_at` |
| is_split_parent | BOOLEAN | No | DEFAULT false | `Transaction._is_split_parent` |
| parent_transaction_id | UUID | Yes | FK → cf_transactions.id | `Transaction.parent_transaction_id` |
| version | INTEGER | No | DEFAULT 1 | `Transaction.version` |
| created_at | TIMESTAMP(tz) | No | — | `Transaction.created_at` |
| created_by | UUID | No | — | `Transaction.created_by` |
| updated_at | TIMESTAMP(tz) | No | — | `Transaction.updated_at` |
| updated_by | UUID | Yes | — | `Transaction.updated_by` |
| deleted_at | TIMESTAMP(tz) | Yes | — | `Transaction.deleted_at` |
| deleted_by | UUID | Yes | — | `Transaction.deleted_by` |

**Constraints:**
- FK `account_id` → `cf_accounts.id`
- FK `card_id` → `cf_cards.id` (nullable)
- FK `parent_transaction_id` → `cf_transactions.id` (self-referential, nullable)

**Indexes:**
- `ix_cf_transactions_account_id` — on `account_id`
- `ix_cf_transactions_transaction_date` — on `transaction_date`
- `ix_cf_transactions_external_id` — on `external_id`
- `ix_cf_transactions_parent_id` — on `parent_transaction_id`
- Composite index on `(account_id, deleted_at)` for soft-delete filtering

## 4. Domain ↔ ORM Mapping

### 4.1 Money Value Object

Money maps to two columns:

```
Domain: Money(amount=Decimal("100.50"), currency=Currency.EUR)
  ↓
ORM: amount=Decimal("100.50"), currency_code="EUR"
  ↓
Domain: Money(amount=Decimal("100.50"), currency=Currency("EUR"))
```

### 4.2 Account with Collections

Account loads shares and cards via SQLAlchemy relationships:

```
AccountModel.to_domain() -> Account:
    1. Create AccountName, Currency, Money, IBAN value objects
    2. Load shares → list[AccountShare] domain objects
    3. Load cards → list[Card] domain objects (if applicable)
    4. Reconstruct Account with shares= and cards= parameters
```

### 4.3 ImportSource Value Object

ImportSource maps to three embedded columns:

```
Domain: ImportSource(source_type=ImportSourceType.BANK_IMPORT, source_id="plaid_123", imported_at=datetime)
  ↓
ORM: import_source_type="BANK_IMPORT", import_source_id="plaid_123", import_source_imported_at=datetime
  ↓
Domain: ImportSource(...) or None (if all three columns are NULL)
```

### 4.4 Split Transactions

- `is_split_parent` boolean flag stored directly
- `parent_transaction_id` FK points to parent transaction
- Children loaded via separate `find_children()` query (not eager relationship)

## 5. Repository Implementations

### 5.1 SqlAlchemyAccountRepository

Implements the `AccountRepository` protocol:

```
SqlAlchemyAccountRepository:
    __init__(session: AsyncSession)

    async save(account: Account) -> None
        Persists account + syncs shares collection

    async find_by_id(
        account_id: UUID, include_deleted: bool = False
    ) -> Account | None
        Eager-loads shares
        Applies soft-delete filter unless include_deleted=True

    async find_by_owner(
        user_id: UUID, include_deleted: bool = False
    ) -> list[Account]
        Accounts where user has OWNER share

    async find_accessible_by_user(
        user_id: UUID, include_deleted: bool = False
    ) -> list[Account]
        JOIN across account_shares WHERE user_id matches and share not revoked

    async exists_by_name_for_user(
        account_name: AccountName, user_id: UUID
    ) -> bool
        Case-insensitive name check for accounts owned by user
```

### 5.2 SqlAlchemyTransactionRepository

Implements the `TransactionRepository` protocol:

```
SqlAlchemyTransactionRepository:
    __init__(session: AsyncSession)

    async save(transaction: Transaction) -> None

    async find_by_id(
        transaction_id: UUID, include_deleted: bool = False
    ) -> Transaction | None

    async find_by_account(
        account_id: UUID, include_deleted: bool = False
    ) -> list[Transaction]
        Excludes split parents from default listing

    async find_by_external_id(
        account_id: UUID, external_id: str
    ) -> Transaction | None

    async find_children(parent_id: UUID) -> list[Transaction]
        All children of a split parent (active only)

    async hard_delete_children(parent_id: UUID) -> None
        Physical delete of split children

    async sum_amounts(account_id: UUID) -> Decimal
        SUM(amount) WHERE account_id = ?
            AND deleted_at IS NULL
            AND is_split_parent = false
```

## 6. Core Finance Unit of Work

### 6.1 SqlAlchemyCoreFinanceUnitOfWork

```
SqlAlchemyCoreFinanceUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    accounts -> SqlAlchemyAccountRepository

    @property
    transactions -> SqlAlchemyTransactionRepository
```

Implements `AbstractCoreFinanceUnitOfWork` protocol.

## 7. Alembic Migration

### 7.1 Tables Created

1. `cf_accounts` — Account aggregate root
2. `cf_account_shares` — Account sharing (FK → cf_accounts)
3. `cf_cards` — Card entities (FK → cf_accounts)
4. `cf_transactions` — Transactions (FK → cf_accounts, self-ref FK, FK → cf_cards)

### 7.2 Migration Dependencies

This migration depends on the IAM migration (spec 022) being applied first, since `created_by` / `deleted_by` UUIDs reference IAM user IDs (no FK constraint, but logical dependency).

## 8. File Structure

```
src/emerald/infrastructure/
    persistence/
        core_finance/
            __init__.py
            models.py               # AccountModel, AccountShareModel, CardModel, TransactionModel
            account_repository.py
            transaction_repository.py
            unit_of_work.py         # SqlAlchemyCoreFinanceUnitOfWork
alembic/
    versions/
        002_core_finance_tables.py
```

## 9. Acceptance Criteria

### ORM Models

- [ ] `AccountModel.to_domain()` reconstructs Account with shares collection
- [ ] `AccountModel.from_domain()` maps all fields including Money → two columns
- [ ] `TransactionModel` maps ImportSource to three embedded columns (or None)
- [ ] Split parent flag and parent_transaction_id mapped correctly
- [ ] Money round-trips through DECIMAL(19,4) without precision loss
- [ ] IBAN stored as full string, reconstructed via IBAN value object

### Account Repository

- [ ] `save()` creates account with initial OWNER share
- [ ] `save()` updates existing account and syncs shares
- [ ] `find_by_id()` eager-loads shares
- [ ] `find_by_id(include_deleted=False)` excludes soft-deleted accounts
- [ ] `find_by_id(include_deleted=True)` includes soft-deleted accounts
- [ ] `find_by_owner()` returns only accounts where user is OWNER
- [ ] `find_accessible_by_user()` returns accounts with any active share for user
- [ ] `exists_by_name_for_user()` is case-insensitive

### Transaction Repository

- [ ] `save()` persists transaction with all fields
- [ ] `find_by_account()` excludes split parents by default
- [ ] `find_by_account(include_deleted=False)` excludes soft-deleted
- [ ] `find_by_external_id()` finds by account + external_id
- [ ] `find_children()` returns children of split parent
- [ ] `hard_delete_children()` physically removes children
- [ ] `sum_amounts()` excludes deleted and split parents
- [ ] `sum_amounts()` returns Decimal(0) for empty account

### Unit of Work

- [ ] `SqlAlchemyCoreFinanceUnitOfWork` creates repos sharing same session
- [ ] Implements `AbstractCoreFinanceUnitOfWork` protocol
- [ ] Commit persists changes from both repos atomically

### Migration

- [ ] All 4 tables created with correct columns and types
- [ ] Foreign keys between shares/cards/transactions → accounts
- [ ] Self-referential FK on transactions for split hierarchy
- [ ] Indexes created for performance
- [ ] Migration is reversible
