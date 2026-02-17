# Spec 015: Bank Connections & Sync

**Version:** 1.0
**Status:** Draft
**Bounded Context:** External Integrations (Supporting Domain)
**Dependencies:** 007 (Account Management), 009 (Transaction Management)
**Date:** 2026-02-17

---

## 1. Overview

This spec defines the **BankConnection aggregate** and the supporting infrastructure for automatic transaction import from external banking providers. Users link external bank accounts to Emerald for automated transaction synchronization. The Integrations context normalizes external data, detects duplicates, stages ambiguous transactions for user review, and delegates final transaction creation to Core Finance via a port interface.

**Key Principle:** The Integrations context imports data INTO Core Finance but does **not** own accounts or transactions. It normalizes, deduplicates, and stages — then delegates creation via `TransactionImportPort`.

---

## 2. Scope

### In Scope

- BankConnection aggregate (root entity with lifecycle state machine)
- Connection lifecycle (PENDING → ACTIVE → NEEDS_REAUTH / ERROR / DISCONNECTED)
- SyncHistory entity (separate from aggregate, own repository)
- PendingTransaction entity (ephemeral staging area)
- TransactionNormalizer domain service (pure transformation)
- DeduplicationService application service (queries existing transactions)
- BankConnectionService (connection lifecycle orchestration)
- BankSyncService (sync execution orchestration)
- TransactionImportPort (ACL boundary to Core Finance)
- BankProviderAdapter protocol (outbound port for provider APIs)
- Domain events, exceptions, commands, and repository protocols

### Out of Scope

- Specific provider API implementations (Plaid, Teller, etc. — infrastructure adapters)
- Credential encryption/storage details (infrastructure concern)
- Real-time sync / webhooks (future enhancement)
- Open Banking protocol support (future enhancement)
- UI for reviewing pending transactions (presentation layer)
- Updating already-imported transactions on re-sync (transactions are immutable after import)

---

## 3. Domain Layer

### 3.1 Value Objects

#### ProviderName

Validated provider identifier. Domain-agnostic — specific providers (Plaid, Teller) are infrastructure configuration.

| Attribute | Type | Validation |
|-----------|------|------------|
| value | str | Non-empty, trimmed, max 50 chars, lowercase normalized |

```
ProviderName("plaid")  ✓
ProviderName("")       ✗ EmptyProviderNameError
ProviderName("  ")     ✗ EmptyProviderNameError
```

#### ProviderCredentials

Opaque credential token. The domain treats this as an opaque string — encryption/decryption happens in the infrastructure adapter layer.

| Attribute | Type | Validation |
|-----------|------|------------|
| token | str | Non-empty, trimmed |

#### NormalizedTransaction

Provider-agnostic representation of a bank transaction. Immutable value object.

| Attribute | Type | Validation |
|-----------|------|------------|
| transaction_date | date | Required |
| value_date | date \| None | Optional |
| amount | Decimal | Required (non-zero) |
| currency_code | str | ISO 4217, 3 chars uppercase |
| description | str | Required, trimmed, max 500 chars |
| merchant | str \| None | Optional, trimmed, max 200 chars |
| external_id | str | Required, trimmed, non-empty |

#### DeduplicationResult

Output of the deduplication check.

| Attribute | Type | Description |
|-----------|------|-------------|
| match_status | MatchStatus | NEW, DUPLICATE, or NEEDS_REVIEW |
| matched_transaction_id | UUID \| None | If DUPLICATE or NEEDS_REVIEW |
| confidence | float | 0.0 - 1.0 |
| match_reason | str | Human-readable explanation |

#### SyncResult

Summary counts for a completed sync.

| Attribute | Type | Description |
|-----------|------|-------------|
| transactions_found | int | Total fetched from provider (>= 0) |
| transactions_imported | int | New transactions created (>= 0) |
| transactions_duplicate | int | Skipped as duplicates (>= 0) |
| transactions_staged | int | Staged for user review (>= 0) |

**Invariant:** `transactions_imported + transactions_duplicate + transactions_staged == transactions_found`

### 3.2 Enums

#### ConnectionStatus

| Value | Description |
|-------|-------------|
| PENDING | Awaiting user authentication at provider |
| ACTIVE | Connected and syncing |
| NEEDS_REAUTH | Credentials expired, user must re-authenticate |
| ERROR | Sync failing repeatedly (3+ consecutive failures) |
| DISCONNECTED | User intentionally disconnected |

#### SyncStatus

| Value | Description |
|-------|-------------|
| IN_PROGRESS | Sync currently running |
| SUCCESS | Completed successfully |
| PARTIAL | Completed with some items staged for review |
| FAILED | Completely failed |

#### MatchStatus

| Value | Description |
|-------|-------------|
| NEW | No matching transaction found — will be auto-imported |
| DUPLICATE | Exact match found — will be skipped |
| NEEDS_REVIEW | Possible match — staged for user verification |
| USER_APPROVED | User confirmed as new (override from NEEDS_REVIEW) |
| USER_REJECTED | User confirmed as duplicate (override from NEEDS_REVIEW) |

### 3.3 Domain Constants

```python
# Bank connection limits
MIN_SYNC_FREQUENCY_HOURS = 1
MAX_SYNC_FREQUENCY_HOURS = 24
DEFAULT_SYNC_FREQUENCY_HOURS = 6

# Failure thresholds
MAX_CONSECUTIVE_FAILURES = 3

# Retry backoff
RETRY_BASE_MINUTES = 15        # 15min, 30min, 60min
RETRY_MAX_MINUTES = 60

# Provider name limits
MAX_PROVIDER_NAME_LENGTH = 50

# Normalized transaction limits
MAX_DESCRIPTION_LENGTH = 500
MAX_MERCHANT_LENGTH = 200

# Deduplication
AMOUNT_TOLERANCE = Decimal("0.01")  # ±0.01 for fuzzy matching
```

### 3.4 BankConnection Aggregate

**Composition:** `SoftDeletableMixin + AuditableMixin + AggregateRoot`

#### Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| id | UUID | No | Unique identifier (connection_id) |
| user_id | UUID | No | User who owns this connection |
| account_id | UUID | No | Emerald account to sync into |
| provider_name | ProviderName | No | Which aggregation provider |
| status | ConnectionStatus | Yes | Current lifecycle state |
| external_account_id | str | No | Account ID at provider |
| institution_id | str | No | Financial institution reference |
| credentials | ProviderCredentials \| None | Yes | Provider access credentials (opaque) |
| last_sync_at | datetime \| None | Yes | Last successful sync timestamp |
| last_sync_error | str \| None | Yes | Last error message |
| next_sync_scheduled_at | datetime \| None | Yes | Next scheduled sync time |
| sync_frequency_hours | int | Yes | Hours between syncs (default: 6) |
| consecutive_failures | int | Yes | Count of consecutive sync failures |
| created_at | datetime | No | Via TimestampedMixin |
| updated_at | datetime | Auto | Via TimestampedMixin |
| created_by | UUID | No | Via AuditableMixin |
| updated_by | UUID \| None | Auto | Via AuditableMixin |

#### Connection Status State Machine

```
                    ┌──────────────┐
      User starts   │   PENDING    │
      connection    └──────┬───────┘
                           │ activate(credentials)
                           ▼
                    ┌──────────────┐
                    │    ACTIVE    │◄──────────────────┐
                    └──────┬───────┘                    │
                           │                            │
              ┌────────────┼────────────┐               │
              │            │            │               │
    3+ sync   │  Provider  │   User     │               │
    failures  │  auth err  │ disconnects│    reconnect  │
              ▼            ▼            ▼   (success)   │
       ┌──────────┐ ┌───────────┐ ┌──────────────┐     │
       │  ERROR   │ │NEEDS_     │ │ DISCONNECTED │     │
       │          │ │  REAUTH   │ │ (terminal)   │     │
       └────┬─────┘ └─────┬─────┘ └──────────────┘     │
            │              │                            │
            └──────────────┴────────────────────────────┘
                      reconnect(credentials)
```

**Terminal state:** DISCONNECTED — no reconnect from DISCONNECTED. User must create a new connection.

#### Domain Methods

```
BankConnection:

  // Factory
  + create(
      user_id: UUID,
      account_id: UUID,
      provider_name: ProviderName,
      institution_id: str,
      external_account_id: str,
      created_by: UUID
    ) -> BankConnection                                [class method]
      Creates: connection in PENDING status, no credentials
      Emits: BankConnectionInitiated

  // Activation
  + activate(credentials: ProviderCredentials) -> None
      Validates: status is PENDING or NEEDS_REAUTH
      Sets: status = ACTIVE, credentials, consecutive_failures = 0
      Schedules: next_sync_scheduled_at = now (immediate sync)
      Emits: BankConnectionActivated
      Raises: InvalidConnectionStateError

  // Sync lifecycle markers (aggregate only tracks state, not history)
  + record_sync_success(synced_at: datetime) -> None
      Validates: status is ACTIVE
      Sets: last_sync_at = synced_at, last_sync_error = None, consecutive_failures = 0
      Schedules: next_sync_scheduled_at = synced_at + sync_frequency
      Raises: ConnectionNotActiveError

  + record_sync_failure(error: str) -> None
      Validates: status is ACTIVE
      Sets: last_sync_error = error
      Increments: consecutive_failures
      If consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        Sets: status = ERROR, next_sync_scheduled_at = None
        Emits: BankConnectionErrored
      Else:
        Schedules: next retry with exponential backoff
      Raises: ConnectionNotActiveError

  // Status transitions
  + mark_needs_reauth() -> None
      Validates: status is ACTIVE
      Sets: status = NEEDS_REAUTH, credentials = None, next_sync_scheduled_at = None
      Emits: BankConnectionNeedsReauth
      Raises: InvalidConnectionStateError

  + disconnect(disconnected_by: UUID) -> None
      Validates: status is not DISCONNECTED, not deleted
      Sets: status = DISCONNECTED, credentials = None, next_sync_scheduled_at = None
      Emits: BankConnectionDisconnected
      Raises: InvalidConnectionStateError (if already DISCONNECTED)

  + reconnect(credentials: ProviderCredentials) -> None
      Validates: status is NEEDS_REAUTH or ERROR
      Sets: status = ACTIVE, credentials, consecutive_failures = 0
      Schedules: next_sync_scheduled_at = now (immediate sync)
      Emits: BankConnectionReconnected
      Raises: InvalidConnectionStateError

  // Configuration
  + update_sync_frequency(hours: int) -> None
      Validates: MIN_SYNC_FREQUENCY_HOURS <= hours <= MAX_SYNC_FREQUENCY_HOURS
      Updates: sync_frequency_hours, recalculates next_sync_scheduled_at if ACTIVE
      Raises: InvalidSyncFrequencyError

  // Lifecycle (via SoftDeletableMixin)
  + soft_delete(deleted_by: UUID, retention: RetentionPeriod, reason: str?) -> None
      Effect: disconnect first (if not already DISCONNECTED), then soft delete
      Emits: BankConnectionSoftDeleted

  // Query helpers
  + is_syncable() -> bool
      Returns: status == ACTIVE and not is_deleted()

  + calculate_next_retry(current_failures: int) -> datetime
      Returns: now + min(RETRY_BASE_MINUTES * 2^(failures-1), RETRY_MAX_MINUTES)
```

### 3.5 SyncHistory Entity

**Extends:** `TimestampedMixin + Entity` (not AggregateRoot — managed by service via its own repository)

Immutable after completion. Created when a sync starts, completed when it ends.

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| id | UUID | No | Unique identifier (sync_id) |
| connection_id | UUID | No | Parent connection |
| status | SyncStatus | Yes | IN_PROGRESS → SUCCESS/PARTIAL/FAILED |
| started_at | datetime | No | Sync start time (tz-aware) |
| completed_at | datetime \| None | Yes | Sync completion time (tz-aware) |
| transactions_found | int | Yes | Total from provider |
| transactions_imported | int | Yes | New transactions auto-created |
| transactions_duplicate | int | Yes | Skipped as duplicates |
| transactions_staged | int | Yes | Staged for user review |
| error_message | str \| None | Yes | If failed, why |

#### Methods

```
SyncHistory:

  + create(connection_id: UUID) -> SyncHistory         [class method]
      Creates: IN_PROGRESS status, started_at = now

  + complete(result: SyncResult) -> None
      Validates: status is IN_PROGRESS
      Sets: status = SUCCESS (or PARTIAL if staged > 0), completed_at = now, counts
      Raises: SyncAlreadyCompletedError

  + fail(error_message: str) -> None
      Validates: status is IN_PROGRESS
      Sets: status = FAILED, completed_at = now, error_message
      Raises: SyncAlreadyCompletedError
```

### 3.6 PendingTransaction Entity

**Extends:** `Entity` (no mixins — ephemeral staging data, hard-deleted when no longer needed)

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| id | UUID | No | Staging record ID |
| connection_id | UUID | No | Source connection |
| sync_id | UUID | No | Which sync produced this |
| account_id | UUID | No | Target Emerald account |
| external_id | str | No | ID from provider |
| raw_data | str | No | Original JSON from provider |
| normalized | NormalizedTransaction | No | Converted to internal format |
| match_status | MatchStatus | Yes | NEW, DUPLICATE, NEEDS_REVIEW, USER_APPROVED, USER_REJECTED |
| matched_transaction_id | UUID \| None | Yes | If DUPLICATE or NEEDS_REVIEW |
| imported_transaction_id | UUID \| None | Yes | Created transaction ID after import |
| created_at | datetime | No | When received |

#### Methods

```
PendingTransaction:

  + create(
      connection_id: UUID,
      sync_id: UUID,
      account_id: UUID,
      external_id: str,
      raw_data: str,
      normalized: NormalizedTransaction,
      match_status: MatchStatus,
      matched_transaction_id: UUID?
    ) -> PendingTransaction                            [class method]
      Validates: match_status is NEW, DUPLICATE, or NEEDS_REVIEW only

  + approve() -> None
      Validates: match_status is NEEDS_REVIEW
      Sets: match_status = USER_APPROVED
      Raises: InvalidPendingStateError

  + reject() -> None
      Validates: match_status is NEEDS_REVIEW
      Sets: match_status = USER_REJECTED
      Raises: InvalidPendingStateError

  + mark_imported(transaction_id: UUID) -> None
      Validates: match_status is NEW or USER_APPROVED
      Sets: imported_transaction_id = transaction_id
      Raises: InvalidPendingStateError

  + is_importable() -> bool
      Returns: match_status in (NEW, USER_APPROVED) and imported_transaction_id is None
```

### 3.7 Domain Services

#### TransactionNormalizer (Protocol — domain port)

Pure transformation logic. Each provider has an infrastructure implementation.

```
TransactionNormalizer (Protocol):
  + normalize(raw_data: str) -> NormalizedTransaction
      Handles:
        - Date format conversion
        - Amount sign normalization
        - Currency code mapping
        - Description cleanup / trimming
        - Merchant extraction
```

**Note:** This is a domain-layer protocol because normalization rules are domain logic (what constitutes a valid normalized transaction). Infrastructure adapters implement it per provider.

### 3.8 Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `BankConnectionInitiated` | `create()` | connection_id, user_id, provider_name, account_id |
| `BankConnectionActivated` | `activate()` | connection_id |
| `BankConnectionNeedsReauth` | `mark_needs_reauth()` | connection_id, user_id |
| `BankConnectionErrored` | 3+ consecutive failures | connection_id, last_error, consecutive_failures |
| `BankConnectionDisconnected` | `disconnect()` | connection_id, disconnected_by |
| `BankConnectionReconnected` | `reconnect()` | connection_id |
| `BankConnectionSoftDeleted` | `soft_delete()` | connection_id, deleted_by |
| `BankSyncStarted` | Sync begins | connection_id, sync_id |
| `BankSyncCompleted` | Sync succeeds | connection_id, sync_id, result counts |
| `BankSyncFailed` | Sync fails | connection_id, sync_id, error |
| `TransactionsImported` | New transactions created | account_id, connection_id, count |
| `PendingTransactionApproved` | User approves | pending_id, connection_id, transaction_id |
| `PendingTransactionRejected` | User rejects | pending_id, connection_id |

**All events:** `@dataclass(frozen=True)` extending `DomainEvent` with `aggregate_type = "BankConnection"`.

### 3.9 Domain Exceptions

| Exception | Base Class | Code | Trigger |
|-----------|-----------|------|---------|
| `EmptyProviderNameError` | `InvalidValueError` | `EMPTY_PROVIDER_NAME` | Empty/blank provider name |
| `ProviderNameTooLongError` | `InvalidValueError` | `PROVIDER_NAME_TOO_LONG` | Exceeds max length |
| `InvalidNormalizedTransactionError` | `InvalidValueError` | `INVALID_NORMALIZED_TRANSACTION` | Invalid normalized data |
| `ConnectionNotActiveError` | `InvariantViolationError` | `CONNECTION_NOT_ACTIVE` | Sync on non-ACTIVE connection |
| `InvalidConnectionStateError` | `InvariantViolationError` | `INVALID_CONNECTION_STATE` | Invalid state transition |
| `DuplicateConnectionError` | `InvariantViolationError` | `DUPLICATE_CONNECTION` | Same account + provider exists |
| `SyncAlreadyInProgressError` | `InvariantViolationError` | `SYNC_ALREADY_IN_PROGRESS` | Starting sync while one runs |
| `SyncAlreadyCompletedError` | `InvariantViolationError` | `SYNC_ALREADY_COMPLETED` | Completing an already-finished sync |
| `InvalidSyncFrequencyError` | `InvalidValueError` | `INVALID_SYNC_FREQUENCY` | Frequency outside allowed range |
| `InvalidPendingStateError` | `InvariantViolationError` | `INVALID_PENDING_STATE` | Invalid pending transaction transition |
| `PendingTransactionNotFoundError` | `NotFoundError` | `PENDING_TRANSACTION_NOT_FOUND` | Non-existent pending_id |
| `BankConnectionNotFoundError` | `NotFoundError` | `BANK_CONNECTION_NOT_FOUND` | Non-existent connection_id |
| `SyncHistoryNotFoundError` | `NotFoundError` | `SYNC_HISTORY_NOT_FOUND` | Non-existent sync_id |
| `InvalidProviderCredentialsError` | `InvalidValueError` | `INVALID_PROVIDER_CREDENTIALS` | Empty credentials token |

### 3.10 Commands

| Command | Fields |
|---------|--------|
| `InitiateBankConnection` | user_id, account_id, provider_name, institution_id, external_account_id |
| `ActivateBankConnection` | connection_id, credentials_token, activated_by |
| `DisconnectBankConnection` | connection_id, disconnected_by |
| `ReconnectBankConnection` | connection_id, credentials_token, reconnected_by |
| `UpdateSyncFrequency` | connection_id, hours, updated_by |
| `TriggerSync` | connection_id, triggered_by |
| `ApprovePendingTransaction` | pending_id, approved_by |
| `RejectPendingTransaction` | pending_id, rejected_by |
| `SoftDeleteBankConnection` | connection_id, deleted_by, reason? |

---

## 4. Application Layer

### 4.1 Outbound Ports

#### BankProviderAdapter (Protocol)

Infrastructure contract for communicating with external bank aggregation services.

```
BankProviderAdapter (Protocol):
  + fetch_transactions(
      credentials: ProviderCredentials,
      external_account_id: str,
      since: datetime?
    ) -> list[str]
      Returns: list of raw JSON strings from provider
      Raises: ProviderAuthError (credentials expired/invalid)
      Raises: ProviderError (general provider failure)

  + verify_credentials(credentials: ProviderCredentials) -> bool
      Tests if credentials are still valid

  + get_account_info(
      credentials: ProviderCredentials,
      external_account_id: str
    ) -> dict[str, Any]
      Returns: account metadata from provider (balance, name, etc.)
```

**Note:** The adapter is resolved by provider_name at runtime via a registry/factory pattern in infrastructure.

#### TransactionImportPort (Protocol)

ACL boundary from Integrations → Core Finance. Allows creating transactions without depending on Core Finance application services directly.

```
TransactionImportPort (Protocol):
  + import_transaction(
      account_id: UUID,
      transaction_date: date,
      amount: Decimal,
      currency_code: str,
      original_description: str,
      external_id: str,
      value_date: date?,
      merchant: str?,
      imported_by: UUID
    ) -> UUID
      Returns: created transaction ID
      Raises: AccountNotFoundError, CurrencyMismatchError, DuplicateExternalIdError

  + find_by_external_id(account_id: UUID, external_id: str) -> bool
      Returns: whether a transaction with this external_id exists in the account

  + find_by_date_and_amount(
      account_id: UUID,
      transaction_date: date,
      amount: Decimal,
      description: str?
    ) -> list[TransactionMatch]
      Returns: potential matches for dedup (includes soft-deleted)

TransactionMatch:
  transaction_id: UUID
  transaction_date: date
  amount: Decimal
  description: str
  external_id: str?
```

#### BankProviderAdapterRegistry (Protocol)

Resolves the correct provider adapter for a given provider name.

```
BankProviderAdapterRegistry (Protocol):
  + get_adapter(provider_name: ProviderName) -> BankProviderAdapter
      Raises: UnsupportedProviderError

  + get_normalizer(provider_name: ProviderName) -> TransactionNormalizer
      Raises: UnsupportedProviderError
```

### 4.2 Repository Ports

#### BankConnectionRepository (Protocol)

```
BankConnectionRepository (Protocol):
  + save(connection: BankConnection) -> None
  + find_by_id(connection_id: UUID, include_deleted: bool = False) -> BankConnection?
  + find_by_user(user_id: UUID, include_deleted: bool = False) -> list[BankConnection]
  + find_by_account(account_id: UUID) -> list[BankConnection]
  + find_by_account_and_provider(
      account_id: UUID, provider_name: ProviderName
    ) -> BankConnection?
      For enforcing one-connection-per-account-per-provider invariant
  + find_due_for_sync(as_of: datetime) -> list[BankConnection]
      Connections where next_sync_scheduled_at <= as_of and status == ACTIVE
```

#### SyncHistoryRepository (Protocol)

```
SyncHistoryRepository (Protocol):
  + save(history: SyncHistory) -> None
  + find_by_id(sync_id: UUID) -> SyncHistory?
  + find_by_connection(connection_id: UUID, limit: int = 10) -> list[SyncHistory]
      Ordered by started_at descending
  + find_latest_by_connection(connection_id: UUID) -> SyncHistory?
  + find_in_progress_by_connection(connection_id: UUID) -> SyncHistory?
      For enforcing one-sync-at-a-time invariant
```

#### PendingTransactionRepository (Protocol)

```
PendingTransactionRepository (Protocol):
  + save(pending: PendingTransaction) -> None
  + save_many(pendings: list[PendingTransaction]) -> None
  + find_by_id(pending_id: UUID) -> PendingTransaction?
  + find_by_connection(connection_id: UUID) -> list[PendingTransaction]
  + find_needs_review(connection_id: UUID) -> list[PendingTransaction]
      Where match_status == NEEDS_REVIEW
  + find_by_sync(sync_id: UUID) -> list[PendingTransaction]
  + delete_by_connection(connection_id: UUID) -> int
      Hard-delete all pending for a connection. Returns count deleted.
```

### 4.3 Unit of Work

```
AbstractIntegrationsUnitOfWork (extends AbstractUnitOfWork):
  bank_connections: BankConnectionRepository
  sync_history: SyncHistoryRepository
  pending_transactions: PendingTransactionRepository
```

### 4.4 Application Services

#### BankConnectionService

Orchestrates bank connection lifecycle operations.

```
BankConnectionService:
  __init__(
    uow: AbstractIntegrationsUnitOfWork,
    transaction_import_port: TransactionImportPort,
    provider_registry: BankProviderAdapterRegistry
  )

  + initiate_connection(cmd: InitiateBankConnection) -> BankConnection
      1. Check no existing connection for account+provider (via repository)
      2. BankConnection.create(...)
      3. Save and commit
      Raises: DuplicateConnectionError

  + activate_connection(cmd: ActivateBankConnection) -> None
      1. Load connection
      2. connection.activate(credentials)
      3. Save and commit
      Raises: BankConnectionNotFoundError, InvalidConnectionStateError

  + disconnect_connection(cmd: DisconnectBankConnection) -> None
      1. Load connection
      2. connection.disconnect(disconnected_by)
      3. Hard-delete pending transactions for this connection
      4. Save and commit
      Raises: BankConnectionNotFoundError, InvalidConnectionStateError

  + reconnect_connection(cmd: ReconnectBankConnection) -> None
      1. Load connection
      2. connection.reconnect(credentials)
      3. Save and commit
      Raises: BankConnectionNotFoundError, InvalidConnectionStateError

  + update_sync_frequency(cmd: UpdateSyncFrequency) -> None
      1. Load connection
      2. Verify user owns connection (connection.user_id == cmd.updated_by)
      3. connection.update_sync_frequency(cmd.hours)
      4. Save and commit
      Raises: BankConnectionNotFoundError, InvalidSyncFrequencyError

  + soft_delete_connection(cmd: SoftDeleteBankConnection) -> None
      1. Load connection (include_deleted=True)
      2. connection.soft_delete(...)
      3. Hard-delete pending transactions for this connection
      4. Save and commit

  + get_connections_for_user(user_id: UUID) -> list[BankConnection]
  + get_connections_for_account(account_id: UUID) -> list[BankConnection]
  + get_sync_history(connection_id: UUID, limit: int = 10) -> list[SyncHistory]
  + get_pending_for_review(connection_id: UUID) -> list[PendingTransaction]
```

#### BankSyncService

Orchestrates sync execution and pending transaction review.

```
BankSyncService:
  __init__(
    uow: AbstractIntegrationsUnitOfWork,
    transaction_import_port: TransactionImportPort,
    provider_registry: BankProviderAdapterRegistry
  )

  + execute_sync(cmd: TriggerSync) -> SyncHistory
      Full sync flow (see Section 5 for detailed pipeline):
      1. Load connection, validate ACTIVE
      2. Check no sync IN_PROGRESS (raises SyncAlreadyInProgressError)
      3. Create SyncHistory (IN_PROGRESS)
      4. Fetch raw transactions from provider via adapter
         - On auth error: connection.mark_needs_reauth(), history.fail(), save, return
         - On other error: connection.record_sync_failure(), history.fail(), save, return
      5. Normalize each raw transaction via provider normalizer
      6. Deduplicate each normalized transaction
      7. Create PendingTransaction entities with match_status
      8. Auto-import NEW pending transactions via TransactionImportPort
      9. Update sync history with result counts
      10. connection.record_sync_success()
      11. Save all and commit
      Returns: completed SyncHistory

  + approve_pending(cmd: ApprovePendingTransaction) -> UUID
      1. Load pending transaction
      2. Verify user owns the connection
      3. pending.approve()
      4. Import via TransactionImportPort
      5. pending.mark_imported(transaction_id)
      6. Save and commit
      Returns: created transaction_id
      Raises: PendingTransactionNotFoundError, InvalidPendingStateError

  + reject_pending(cmd: RejectPendingTransaction) -> None
      1. Load pending transaction
      2. Verify user owns the connection
      3. pending.reject()
      4. Save and commit
      Raises: PendingTransactionNotFoundError, InvalidPendingStateError

  + find_connections_due_for_sync(as_of: datetime) -> list[BankConnection]
      Queries repository for connections where next_sync_scheduled_at <= as_of
```

#### DeduplicationService (Application Service)

Checks normalized transactions against existing transactions in Core Finance.

```
DeduplicationService:
  __init__(transaction_import_port: TransactionImportPort)

  + check(
      normalized: NormalizedTransaction,
      account_id: UUID
    ) -> DeduplicationResult

  Algorithm:
    1. Exact external_id match:
       if transaction_import_port.find_by_external_id(account_id, normalized.external_id):
         return DeduplicationResult(DUPLICATE, confidence=1.0, reason="Exact external_id match")

    2. Date + amount + description match:
       matches = transaction_import_port.find_by_date_and_amount(
         account_id, normalized.transaction_date, normalized.amount, normalized.description
       )
       exact_matches = [m for m in matches where m.description == normalized.description]
       if exact_matches:
         return DeduplicationResult(DUPLICATE, matched_id, confidence=0.95,
                                    reason="Exact date + amount + description")

    3. Fuzzy date + approximate amount match:
       fuzzy_matches = [m for m in matches where abs(m.amount - normalized.amount) <= AMOUNT_TOLERANCE]
       if fuzzy_matches:
         return DeduplicationResult(NEEDS_REVIEW, matched_id, confidence=0.6,
                                    reason="Same date + approximate amount")

    4. No match:
       return DeduplicationResult(NEW, confidence=0.0, reason="No matching transaction found")
```

---

## 5. Sync Execution Pipeline (Detailed)

```
Scheduled or manual sync trigger
     │
     ▼
  1. Load connection, validate ACTIVE
     │
     ▼
  2. Check no IN_PROGRESS sync exists
     │
     ▼
  3. Create SyncHistory(IN_PROGRESS)
     │
     ▼
  4. Resolve adapter + normalizer from provider_registry
     │
     ▼
  5. adapter.fetch_transactions(credentials, external_account_id, since=last_sync_at)
     │
     ├── ProviderAuthError → mark_needs_reauth() + history.fail() → DONE
     ├── ProviderError → record_sync_failure() + history.fail() → DONE
     │
     ▼
  6. For each raw transaction string:
     a. normalizer.normalize(raw) → NormalizedTransaction
     b. dedup_service.check(normalized, account_id) → DeduplicationResult
     c. Create PendingTransaction with match_status
     │
     ├── DUPLICATE → count, don't persist pending (just count)
     │
     ├── NEW → persist pending, auto-import via TransactionImportPort
     │         pending.mark_imported(transaction_id)
     │
     └── NEEDS_REVIEW → persist pending for user review
     │
     ▼
  7. history.complete(SyncResult(found, imported, duplicate, staged))
     │
     ▼
  8. connection.record_sync_success(synced_at=now)
     │
     ▼
  9. Commit all changes
     │
     ▼
  10. Events emitted: BankSyncCompleted, TransactionsImported (if any)
```

---

## 6. Deduplication Rules

| Priority | Rule | Confidence | Result |
|----------|------|------------|--------|
| 1 | Same `external_id` in same account | 1.0 (definite) | DUPLICATE |
| 2 | Same date + same amount + same description | 0.95 (high) | DUPLICATE |
| 3 | Same date + amount within ±0.01 | 0.6 (medium) | NEEDS_REVIEW |
| 4 | No match | 0.0 | NEW |

**Deduplication scope:**
- Per account (not per connection — prevents cross-connection duplicates)
- Includes soft-deleted transactions (prevents re-import of deleted transactions)
- External ID uniqueness is account-scoped (consistent with existing Transaction behavior)

---

## 7. Invariants

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| BNK-001 | One active connection per account per provider | BankConnectionService checks repository before creation |
| BNK-002 | Sync requires ACTIVE connection status | `record_sync_success/failure` validate status |
| BNK-003 | One sync at a time per connection | BankSyncService checks for IN_PROGRESS sync |
| BNK-004 | Disconnecting hard-deletes pending transactions | BankConnectionService cascades |
| BNK-005 | Sync frequency between 1-24 hours | `update_sync_frequency()` validates range |
| BNK-006 | 3+ consecutive failures → ERROR status | `record_sync_failure()` transitions |
| BNK-007 | DISCONNECTED is terminal | No reconnect from DISCONNECTED |
| BNK-008 | Credentials cleared on NEEDS_REAUTH and DISCONNECTED | State transitions null out credentials |

---

## 8. Imported Transaction Properties

Transactions created via bank sync have:

| Property | Value |
|----------|-------|
| `import_source.source_type` | `ImportSourceType.BANK_IMPORT` |
| `import_source.source_id` | Connection ID (string) |
| `import_source.imported_at` | UTC timestamp of import |
| `external_id` | Provider's transaction ID |
| `review_status` | `ReviewStatus.TO_REVIEW` |
| `original_description` | Bank's transaction description |
| `merchant` | Extracted merchant (if available) |
| `created_by` | Connection owner's user_id |

---

## 9. Context Map

```
┌──────────────────────────────────────────────────────┐
│                 Integrations Context                  │
│                                                       │
│  BankConnection ──── BankSyncService                 │
│  SyncHistory         DeduplicationService            │
│  PendingTransaction  BankConnectionService           │
│                                                       │
│  Outbound Ports:                                     │
│  ├── TransactionImportPort ──→ Core Finance          │
│  ├── BankProviderAdapter ──→ Infrastructure          │
│  └── BankProviderAdapterRegistry ──→ Infrastructure  │
│                                                       │
│  Domain Ports:                                        │
│  └── TransactionNormalizer ──→ Infrastructure         │
└──────────────────────────────────────────────────────┘
          │
          │ TransactionImportPort (ACL)
          ▼
┌──────────────────────────────────────────────────────┐
│                Core Finance Context                   │
│                                                       │
│  Account, Transaction, TransactionManagementService  │
│  (Implementation of TransactionImportPort wraps      │
│   TransactionManagementService)                      │
└──────────────────────────────────────────────────────┘
```

---

## 10. Acceptance Criteria

### Connection Lifecycle

- [ ] User can initiate a bank connection → PENDING status, `BankConnectionInitiated` event
- [ ] Activating with credentials transitions PENDING → ACTIVE, schedules immediate sync
- [ ] Activating from NEEDS_REAUTH → ACTIVE (reauth flow)
- [ ] ACTIVE connection can trigger sync
- [ ] 3+ consecutive sync failures transition to ERROR, `BankConnectionErrored` event
- [ ] Auth error during sync triggers NEEDS_REAUTH, `BankConnectionNeedsReauth` event
- [ ] User can disconnect (DISCONNECTED status), pending transactions hard-deleted
- [ ] User can reconnect from NEEDS_REAUTH or ERROR → ACTIVE
- [ ] DISCONNECTED is terminal — cannot reconnect (must create new connection)
- [ ] One connection per account per provider — raises `DuplicateConnectionError`
- [ ] Soft-delete disconnects first, then soft-deletes, hard-deletes pending

### Sync Execution

- [ ] Sync fetches transactions from provider since `last_sync_at`
- [ ] First sync (last_sync_at is None) fetches all available history
- [ ] Sync creates SyncHistory record (IN_PROGRESS → SUCCESS/PARTIAL/FAILED)
- [ ] Only one sync at a time per connection (`SyncAlreadyInProgressError`)
- [ ] Auth errors during sync trigger NEEDS_REAUTH
- [ ] Other errors increment failure count and schedule retry with exponential backoff
- [ ] `BankSyncCompleted` event emitted on success with result counts
- [ ] `BankSyncFailed` event emitted on failure

### Import Pipeline

- [ ] Raw transactions normalized via provider-specific TransactionNormalizer
- [ ] Normalized transactions checked by DeduplicationService
- [ ] Exact external_id match → DUPLICATE (skipped, not persisted as pending)
- [ ] Exact date + amount + description → DUPLICATE (skipped)
- [ ] Same date + approximate amount (±0.01) → NEEDS_REVIEW (staged)
- [ ] No match → NEW (auto-imported via TransactionImportPort)
- [ ] Deduplication checks include soft-deleted transactions
- [ ] `TransactionsImported` event emitted when new transactions created

### Pending Transaction Review

- [ ] User can approve a NEEDS_REVIEW pending → USER_APPROVED, creates transaction
- [ ] User can reject a NEEDS_REVIEW pending → USER_REJECTED, no transaction created
- [ ] Approved pending linked to created transaction via `imported_transaction_id`
- [ ] Only NEEDS_REVIEW items can be approved/rejected

### Scheduling

- [ ] Sync frequency configurable between 1 and 24 hours (default: 6)
- [ ] Next sync auto-scheduled after successful completion
- [ ] Failed syncs retry with exponential backoff (15min base, 60min max)
- [ ] DISCONNECTED/ERROR/NEEDS_REAUTH connections have no scheduled syncs

### Imported Transactions

- [ ] `import_source.source_type = BANK_IMPORT`
- [ ] `import_source.source_id = connection_id`
- [ ] `review_status = TO_REVIEW`
- [ ] `external_id` set from provider's transaction ID
- [ ] Transactions are immutable after import (no re-sync updates)

---

## 11. Dependencies

### Internal Dependencies

- **Spec 007 (Account Management):** Account aggregate, AccountRepository (for verifying account exists)
- **Spec 009 (Transaction Management):** Transaction entity, TransactionRepository (for dedup queries via port)
- **Spec 001 (Shared Kernel):** DomainEvent, Entity, AggregateRoot, mixins, RetentionPeriod, Money, Currency
- **Spec 006 (Data Lifecycle):** SoftDeletableMixin, DeletableEntityType (add BANK_CONNECTION)

### External Dependencies

- Bank aggregation providers (Plaid, Teller, etc.) — infrastructure adapters, not domain

---

## 12. Glossary

- **BankConnection:** Aggregate root representing a link between an Emerald account and an external bank account
- **SyncHistory:** Record of a single sync execution attempt
- **PendingTransaction:** Ephemeral staging entity for imported transactions awaiting dedup resolution or user review
- **NormalizedTransaction:** Provider-agnostic representation of a bank transaction
- **TransactionImportPort:** ACL boundary allowing Integrations to create transactions in Core Finance without direct service dependency
- **ProviderCredentials:** Opaque token representing access to a bank provider API
- **Deduplication:** Process of checking incoming bank transactions against existing transactions to prevent duplicates
