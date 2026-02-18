# Spec 025: Classification & Integrations Persistence Layer

**Status:** Draft
**Bounded Context:** Classification + Integrations (Infrastructure)
**Dependencies:** 021 (Configuration & Database Foundation), 022 (IAM Persistence), 024 (Core Finance Persistence), 013 (Classification & Taxonomies), 014 (Transaction Categorization), 015 (Bank Connections & Sync), 006 (Data Lifecycle Management)
**Blocks:** 026

---

## 1. Overview

This spec implements the remaining persistence layers — taxonomies with hierarchical terms, categorization assignments, bank connections with encrypted credentials, sync history, pending transactions, and the shared kernel's cross-table trash/deletion ports.

**Key Principle:** Hierarchical data (taxonomy terms with parent references) requires careful query design. Bank connection credentials must be encrypted at rest. Trash and scheduled deletion ports query across multiple bounded-context tables.

## 2. Scope

### In Scope

- **Classification ORM:** `TaxonomyModel`, `TaxonomyTermModel`, `TransactionTermAssignmentModel`
- **Integrations ORM:** `BankConnectionModel`, `SyncHistoryModel`, `PendingTransactionModel`
- Repository implementations for all above
- Context-specific Unit of Work implementations
- **Shared kernel ports:** `SqlAlchemyScheduledDeletionPort`, `SqlAlchemyTrashQueryPort`
- Alembic migration for Classification and Integrations tables

### Out of Scope

- Credential encryption implementation details (uses Fernet or similar — infrastructure concern)
- Specific bank provider adapters (spec 026 stubs)
- API endpoints (specs 028-030)

## 3. Classification ORM Models

### 3.1 TaxonomyModel

**Table:** `cls_taxonomies`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `Taxonomy.id` |
| name | VARCHAR(100) | No | — | `Taxonomy.name.value` |
| description | TEXT | Yes | — | `Taxonomy.description` |
| owner_id | UUID | No | INDEX | `Taxonomy.owner_id` |
| is_system | BOOLEAN | No | DEFAULT false | `Taxonomy.is_system` |
| version | INTEGER | No | DEFAULT 1 | `Taxonomy.version` |
| created_at | TIMESTAMP(tz) | No | — | `Taxonomy.created_at` |
| created_by | UUID | No | — | `Taxonomy.created_by` |
| updated_at | TIMESTAMP(tz) | No | — | `Taxonomy.updated_at` |
| updated_by | UUID | Yes | — | `Taxonomy.updated_by` |
| deleted_at | TIMESTAMP(tz) | Yes | — | `Taxonomy.deleted_at` |
| deleted_by | UUID | Yes | — | `Taxonomy.deleted_by` |

**Indexes:**
- `ix_cls_taxonomies_owner_id` — on `owner_id`
- Functional index for case-insensitive name uniqueness per owner

### 3.2 TaxonomyTermModel

**Table:** `cls_taxonomy_terms`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `TaxonomyTerm.id` |
| taxonomy_id | UUID | No | FK → cls_taxonomies.id, INDEX | Parent taxonomy |
| name | VARCHAR(100) | No | — | `TaxonomyTerm.name.value` |
| description | TEXT | Yes | — | `TaxonomyTerm.description` |
| parent_id | UUID | Yes | FK → cls_taxonomy_terms.id | `TaxonomyTerm.parent_id` |
| sort_order | INTEGER | No | DEFAULT 0 | `TaxonomyTerm.sort_order` |
| created_at | TIMESTAMP(tz) | No | — | `TaxonomyTerm.created_at` |
| updated_at | TIMESTAMP(tz) | No | — | `TaxonomyTerm.updated_at` |
| deleted_at | TIMESTAMP(tz) | Yes | — | `TaxonomyTerm.deleted_at` |
| deleted_by | UUID | Yes | — | `TaxonomyTerm.deleted_by` |

**Constraints:**
- FK `taxonomy_id` → `cls_taxonomies.id` ON DELETE CASCADE
- FK `parent_id` → `cls_taxonomy_terms.id` (self-referential, nullable)

**Indexes:**
- `ix_cls_taxonomy_terms_taxonomy_id` — on `taxonomy_id`
- `ix_cls_taxonomy_terms_parent_id` — on `parent_id`

### 3.3 TransactionTermAssignmentModel

**Table:** `cls_transaction_term_assignments`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `TransactionTermAssignment.id` |
| transaction_id | UUID | No | INDEX | `TransactionTermAssignment.transaction_id` |
| term_id | UUID | No | FK → cls_taxonomy_terms.id, INDEX | `TransactionTermAssignment.term_id` |
| taxonomy_id | UUID | No | FK → cls_taxonomies.id, INDEX | `TransactionTermAssignment.taxonomy_id` |
| assigned_by | UUID | No | — | `TransactionTermAssignment.assigned_by` |
| assigned_at | TIMESTAMP(tz) | No | — | `TransactionTermAssignment.assigned_at` |

**Constraints:**
- UNIQUE(`transaction_id`, `taxonomy_id`) — one assignment per taxonomy per transaction
- FK `term_id` → `cls_taxonomy_terms.id` ON DELETE CASCADE
- FK `taxonomy_id` → `cls_taxonomies.id` ON DELETE CASCADE
- No FK to `cf_transactions` (cross-context — logical reference only)

## 4. Integrations ORM Models

### 4.1 BankConnectionModel

**Table:** `int_bank_connections`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `BankConnection.id` |
| user_id | UUID | No | INDEX | `BankConnection.user_id` |
| account_id | UUID | No | INDEX | `BankConnection.account_id` |
| provider | VARCHAR(20) | No | — | `BankConnection.provider.value` |
| status | VARCHAR(20) | No | — | `BankConnection.status.value` |
| external_account_id | VARCHAR(255) | No | — | `BankConnection.external_account_id` |
| institution_id | UUID | No | — | `BankConnection.institution_id` |
| encrypted_access_token | BYTEA | Yes | — | `BankConnection.access_token` (encrypted) |
| last_sync_at | TIMESTAMP(tz) | Yes | — | `BankConnection.last_sync_at` |
| last_sync_error | TEXT | Yes | — | `BankConnection.last_sync_error` |
| next_sync_scheduled_at | TIMESTAMP(tz) | Yes | INDEX | `BankConnection.next_sync_scheduled_at` |
| sync_frequency_seconds | INTEGER | No | DEFAULT 21600 | `BankConnection.sync_frequency` (timedelta) |
| consecutive_failures | INTEGER | No | DEFAULT 0 | `BankConnection.consecutive_failures` |
| created_at | TIMESTAMP(tz) | No | — | `BankConnection.created_at` |
| updated_at | TIMESTAMP(tz) | No | — | `BankConnection.updated_at` |
| deleted_at | TIMESTAMP(tz) | Yes | — | `BankConnection.deleted_at` |
| deleted_by | UUID | Yes | — | `BankConnection.deleted_by` |

**Constraints:**
- UNIQUE(`account_id`, `provider`) WHERE `deleted_at IS NULL` — one active connection per account per provider

**Indexes:**
- `ix_int_bank_connections_user_id` — on `user_id`
- `ix_int_bank_connections_account_id` — on `account_id`
- `ix_int_bank_connections_next_sync` — on `next_sync_scheduled_at`

### 4.2 SyncHistoryModel

**Table:** `int_sync_history`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `SyncHistory.sync_id` |
| connection_id | UUID | No | FK → int_bank_connections.id, INDEX | `SyncHistory.connection_id` |
| started_at | TIMESTAMP(tz) | No | — | `SyncHistory.started_at` |
| completed_at | TIMESTAMP(tz) | Yes | — | `SyncHistory.completed_at` |
| status | VARCHAR(20) | No | — | `SyncHistory.status.value` |
| transactions_found | INTEGER | No | DEFAULT 0 | `SyncHistory.transactions_found` |
| transactions_imported | INTEGER | No | DEFAULT 0 | `SyncHistory.transactions_imported` |
| transactions_duplicate | INTEGER | No | DEFAULT 0 | `SyncHistory.transactions_duplicate` |
| transactions_updated | INTEGER | No | DEFAULT 0 | `SyncHistory.transactions_updated` |
| error_message | TEXT | Yes | — | `SyncHistory.error_message` |

**Constraints:**
- FK `connection_id` → `int_bank_connections.id` ON DELETE CASCADE

### 4.3 PendingTransactionModel

**Table:** `int_pending_transactions`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `PendingTransaction.pending_id` |
| connection_id | UUID | No | FK → int_bank_connections.id, INDEX | `PendingTransaction.connection_id` |
| sync_id | UUID | No | FK → int_sync_history.id | `PendingTransaction.sync_id` |
| external_id | VARCHAR(255) | No | — | `PendingTransaction.external_id` |
| raw_data | JSONB | No | — | `PendingTransaction.raw_data` |
| normalized_date | DATE | No | — | `PendingTransaction.normalized_data.transaction_date` |
| normalized_amount | DECIMAL(19,4) | No | — | `PendingTransaction.normalized_data.amount` |
| normalized_currency | VARCHAR(3) | No | — | `PendingTransaction.normalized_data.currency_code` |
| normalized_description | VARCHAR(500) | No | — | `PendingTransaction.normalized_data.description` |
| normalized_merchant | VARCHAR(200) | Yes | — | `PendingTransaction.normalized_data.merchant` |
| match_status | VARCHAR(20) | No | — | `PendingTransaction.match_status.value` |
| matched_transaction_id | UUID | Yes | — | `PendingTransaction.matched_transaction_id` |
| created_at | TIMESTAMP(tz) | No | — | `PendingTransaction.created_at` |

**Constraints:**
- FK `connection_id` → `int_bank_connections.id` ON DELETE CASCADE
- FK `sync_id` → `int_sync_history.id`

## 5. Repository Implementations

### 5.1 SqlAlchemyTaxonomyRepository

Implements `TaxonomyRepository` protocol:

```
SqlAlchemyTaxonomyRepository:
    async save(taxonomy: Taxonomy) -> None
        Persists taxonomy + syncs terms collection

    async find_by_id(
        taxonomy_id: UUID, include_deleted: bool = False
    ) -> Taxonomy | None
        Eager-loads terms

    async find_by_owner(
        owner_id: UUID, include_deleted: bool = False
    ) -> list[Taxonomy]

    async find_by_term_id(term_id: UUID) -> Taxonomy | None
        Join through terms to find parent taxonomy

    async exists_by_name_for_owner(
        name: TaxonomyName, owner_id: UUID
    ) -> bool
        Case-insensitive check
```

### 5.2 SqlAlchemyAssignmentRepository

Implements `TransactionTermAssignmentRepository` protocol:

```
SqlAlchemyAssignmentRepository:
    async save(assignment: TransactionTermAssignment) -> None
    async find_by_id(assignment_id: UUID) -> TransactionTermAssignment | None
    async find_by_transaction(transaction_id: UUID) -> list[TransactionTermAssignment]
    async find_by_transaction_and_taxonomy(
        transaction_id: UUID, taxonomy_id: UUID
    ) -> TransactionTermAssignment | None
    async find_by_term(term_id: UUID) -> list[TransactionTermAssignment]
    async delete(assignment_id: UUID) -> None
    async delete_by_term(term_id: UUID) -> None
    async delete_by_taxonomy(taxonomy_id: UUID) -> None
    async delete_by_transaction(transaction_id: UUID) -> None
```

### 5.3 SqlAlchemyBankConnectionRepository

Implements `BankConnectionRepository` protocol:

```
SqlAlchemyBankConnectionRepository:
    async save(connection: BankConnection) -> None
    async find_by_id(connection_id: UUID) -> BankConnection | None
    async find_by_user(user_id: UUID, include_deleted: bool = False) -> list[BankConnection]
    async find_by_account(account_id: UUID) -> list[BankConnection]
    async find_by_account_and_provider(
        account_id: UUID, provider: BankProvider
    ) -> BankConnection | None
    async find_due_for_sync(as_of: datetime) -> list[BankConnection]
        WHERE next_sync_scheduled_at <= as_of AND status = 'ACTIVE'
```

### 5.4 SqlAlchemySyncHistoryRepository

Implements `SyncHistoryRepository` protocol:

```
SqlAlchemySyncHistoryRepository:
    async save(history: SyncHistory) -> None
    async find_by_connection(connection_id: UUID, limit: int = 10) -> list[SyncHistory]
    async find_latest_by_connection(connection_id: UUID) -> SyncHistory | None
```

### 5.5 SqlAlchemyPendingTransactionRepository

Implements `PendingTransactionRepository` protocol:

```
SqlAlchemyPendingTransactionRepository:
    async save(pending: PendingTransaction) -> None
    async save_many(pendings: list[PendingTransaction]) -> None
    async find_by_connection(connection_id: UUID) -> list[PendingTransaction]
    async find_needs_review(connection_id: UUID) -> list[PendingTransaction]
    async find_by_id(pending_id: UUID) -> PendingTransaction | None
    async delete_by_connection(connection_id: UUID) -> None
```

### 5.6 Shared Kernel Ports

**SqlAlchemyScheduledDeletionPort:**

Implements `ScheduledDeletionPort` (spec 006):

```
SqlAlchemyScheduledDeletionPort:
    async find_due_for_hard_delete(as_of: datetime) -> list[HardDeleteConfirmation]
        Queries across all soft-deletable tables:
            - iam_users, cf_accounts, cf_transactions, cf_cards,
              cls_taxonomies, cls_taxonomy_terms, int_bank_connections
        WHERE deleted_at IS NOT NULL
            AND hard_delete_scheduled_at IS NOT NULL
            AND hard_delete_scheduled_at <= as_of
        Returns entity_type + entity_id for each
```

**SqlAlchemyTrashQueryPort:**

Implements `TrashQueryPort` (spec 006):

```
SqlAlchemyTrashQueryPort:
    async find_trash_items(
        user_id: UUID, entity_type: DeletableEntityType | None = None,
        page: int = 1, page_size: int = 20
    ) -> PaginatedResult[TrashItem]
        UNION query across soft-deletable tables
        Returns TrashItem with entity_type, entity_id, name, deleted_at, scheduled_hard_delete_at

    async get_cascade_summary(
        entity_type: DeletableEntityType, entity_id: UUID
    ) -> CascadeSummary
        Counts child entities that would be affected by recovery or hard delete
```

## 6. Units of Work

### 6.1 SqlAlchemyClassificationUnitOfWork

```
SqlAlchemyClassificationUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    taxonomies -> SqlAlchemyTaxonomyRepository

    @property
    assignments -> SqlAlchemyAssignmentRepository
```

### 6.2 SqlAlchemyIntegrationsUnitOfWork

```
SqlAlchemyIntegrationsUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    bank_connections -> SqlAlchemyBankConnectionRepository

    @property
    sync_history -> SqlAlchemySyncHistoryRepository

    @property
    pending_transactions -> SqlAlchemyPendingTransactionRepository
```

## 7. Credential Encryption

### 7.1 EncryptedToken Handling

Bank connection access tokens are encrypted at rest:

```
Token Encryption:
    - Algorithm: Fernet (AES-128-CBC with HMAC-SHA256)
    - Key: derived from app secret or separate encryption key
    - Stored as: BYTEA column (encrypted bytes)
    - to_domain(): decrypt bytes → EncryptedToken value object
    - from_domain(): encrypt token → bytes for storage
```

**Rules:**
- Encryption key is a separate setting (`ENCRYPTION_KEY`), not the JWT secret
- Key rotation is supported (try current key, fall back to previous)
- Decryption failure raises clear error (corrupted data, wrong key)

## 8. Alembic Migration

### 8.1 Tables Created

**Classification:**
1. `cls_taxonomies` — Taxonomy aggregate
2. `cls_taxonomy_terms` — Terms (FK → taxonomies, self-ref FK)
3. `cls_transaction_term_assignments` — Categorization (FK → terms, taxonomies)

**Integrations:**
4. `int_bank_connections` — Bank connections
5. `int_sync_history` — Sync records (FK → bank_connections)
6. `int_pending_transactions` — Staging area (FK → bank_connections, sync_history)

## 9. File Structure

```
src/emerald/infrastructure/
    persistence/
        classification/
            __init__.py
            models.py                # TaxonomyModel, TaxonomyTermModel, AssignmentModel
            taxonomy_repository.py
            assignment_repository.py
            unit_of_work.py
        integrations/
            __init__.py
            models.py                # BankConnectionModel, SyncHistoryModel, PendingTransactionModel
            bank_connection_repository.py
            sync_history_repository.py
            pending_transaction_repository.py
            unit_of_work.py
        shared_kernel/
            scheduled_deletion_port.py
            trash_query_port.py
alembic/
    versions/
        003_classification_tables.py
        004_integrations_tables.py
```

## 10. Acceptance Criteria

### Classification Persistence

- [ ] `TaxonomyModel.to_domain()` reconstructs Taxonomy with full terms hierarchy
- [ ] `TaxonomyModel.from_domain()` maps terms with parent references
- [ ] `find_by_id()` eager-loads terms
- [ ] `find_by_term_id()` finds taxonomy containing a specific term
- [ ] `exists_by_name_for_owner()` is case-insensitive
- [ ] Term self-referential parent_id correctly stored
- [ ] Assignment unique constraint on (transaction_id, taxonomy_id)
- [ ] `delete_by_term()` removes all assignments for a term
- [ ] `delete_by_taxonomy()` removes all assignments for a taxonomy
- [ ] `delete_by_transaction()` removes all assignments for a transaction

### Integrations Persistence

- [ ] `BankConnectionModel` encrypts access_token at rest
- [ ] `to_domain()` decrypts access_token
- [ ] `find_due_for_sync()` returns only ACTIVE connections past sync schedule
- [ ] `find_by_account_and_provider()` respects soft-delete filter
- [ ] `SyncHistoryModel` maps all count fields correctly
- [ ] `PendingTransactionModel` stores raw_data as JSONB
- [ ] `PendingTransactionModel` stores normalized fields in separate columns
- [ ] `save_many()` batch inserts pending transactions efficiently
- [ ] `delete_by_connection()` removes all pending for a connection

### Shared Kernel Ports

- [ ] `ScheduledDeletionPort` queries across all soft-deletable tables
- [ ] Returns only entities past their hard_delete_scheduled_at
- [ ] `TrashQueryPort` UNION query returns items from all contexts
- [ ] Trash items include entity name/description for display
- [ ] `get_cascade_summary()` counts affected children
- [ ] Paginated results return correct totals

### Credential Encryption

- [ ] Access tokens encrypted before storage
- [ ] Access tokens decrypted on domain reconstruction
- [ ] Different connections have different ciphertext (random IV)
- [ ] Wrong encryption key raises clear error

### Migrations

- [ ] All 6 tables created with correct schemas
- [ ] Foreign keys between related tables
- [ ] Self-referential FK on taxonomy_terms
- [ ] No cross-context foreign keys (assignments don't FK to cf_transactions)
- [ ] Migrations are reversible
