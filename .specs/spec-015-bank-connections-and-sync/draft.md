# Spec 015: Bank Connections & Sync

**Status:** Draft
**Bounded Context:** External Integrations (Supporting Domain)
**Dependencies:** 007 (Account Management), 009 (Transaction Management)
**Blocks:** None

---

## 1. Overview

This spec defines the BankConnection aggregate — the mechanism by which users link external bank accounts to the Emerald platform for automatic transaction import. It covers the connection lifecycle, sync scheduling, import processing pipeline (normalization, deduplication, staging), and provider adapter architecture.

**Key Principle:** The Integrations context imports data INTO Core Finance but does not own accounts or transactions. It normalizes external data, detects duplicates, stages pending transactions for review, and delegates final transaction creation to the Account aggregate in Core Finance.

## 2. Scope

### In Scope

- BankConnection aggregate (root entity, sync history, pending transactions)
- Connection lifecycle (Pending → Active → NeedsReauth / Error / Disconnected)
- Bank provider adapter interface
- Sync execution and scheduling
- SyncHistory entity
- PendingTransaction entity (staging area)
- Import processing pipeline (normalization, deduplication)
- Duplicate detection rules

### Out of Scope

- Specific provider API implementations (Plaid, Teller, etc. — these are infrastructure adapters)
- Bank credential storage encryption details (infrastructure concern)
- Real-time sync / webhooks (Phase 4 enhancement)
- Open Banking protocol support (Phase 4)
- UI for reviewing pending transactions (presentation layer)

## 3. BankConnection Entity

### 3.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| connection_id | UUID | No | Unique identifier |
| user_id | UUID | No | User who owns this connection |
| account_id | UUID | No | Emerald account to sync into |
| provider | BankProvider | No | Which aggregation provider |
| status | ConnectionStatus | Yes | Current state |
| external_account_id | str | No | Account ID at provider |
| institution_id | UUID | No | Financial institution reference |
| access_token | EncryptedToken | Yes | Provider access credentials |
| last_sync_at | datetime? | Yes | Last successful sync |
| last_sync_error | str? | Yes | Last error message |
| next_sync_scheduled_at | datetime? | Yes | Next scheduled sync |
| sync_frequency | timedelta | Yes | How often to sync (default: 6 hours) |
| created_at | datetime | No | When connected |
| updated_at | datetime | Auto | Last update |
| deleted_at | datetime? | Yes | Soft delete timestamp |

### 3.2 Enums

**BankProvider:**

| Value | Description |
|-------|-------------|
| PLAID | Plaid aggregation service |
| TELLER | Teller aggregation service |
| MX | MX aggregation service |
| YODLEE | Yodlee aggregation service |
| MANUAL | Manual file import (CSV/OFX) |

**ConnectionStatus:**

| Value | Description |
|-------|-------------|
| PENDING | Awaiting user authentication at provider |
| ACTIVE | Connected and syncing |
| NEEDS_REAUTH | Credentials expired, user must re-authenticate |
| ERROR | Sync failing repeatedly |
| DISCONNECTED | User intentionally disconnected |

### 3.3 Connection Status Flow

```
                    ┌──────────────┐
      User starts   │   PENDING    │
      connection    └──────┬───────┘
                           │ User completes auth at provider
                           ▼
                    ┌──────────────┐
                    │    ACTIVE    │◄────────────────────┐
                    └──────┬───────┘                     │
                           │                             │
              ┌────────────┼────────────┐                │
              │            │            │                │
    Sync fails│     Creds  │   User     │                │
    3+ times  │     expire │ disconnects│     User       │
              ▼            ▼            ▼     reauths    │
       ┌──────────┐ ┌───────────┐ ┌──────────────┐      │
       │  ERROR   │ │NEEDS_     │ │ DISCONNECTED │      │
       │          │ │  REAUTH   │─┘              │      │
       └────┬─────┘ └─────┬─────┘ └──────────────┘      │
            │              │                             │
            │              └─────────────────────────────┘
            │                      (reauth success)
            │
            └── Manual retry by user or admin → ACTIVE (if succeeds)
```

### 3.4 Domain Methods

```
BankConnection:
  // Creation
  + initiate(
      user_id: UUID,
      account_id: UUID,
      provider: BankProvider,
      institution_id: UUID,
      external_account_id: str
    ) -> BankConnection                                [class method]
      Creates: connection in PENDING status
      Emits: BankConnectionInitiated

  // Activation
  + activate(access_token: EncryptedToken) -> None
      Validates: status is PENDING or NEEDS_REAUTH
      Sets: status = ACTIVE, access_token, schedule next sync
      Emits: BankConnectionEstablished
      Raises: InvalidConnectionStateError

  // Sync lifecycle
  + start_sync() -> UUID
      Validates: status is ACTIVE
      Creates: SyncHistory record (in progress)
      Returns: sync_id
      Raises: ConnectionNotActiveError

  + complete_sync(sync_id: UUID, result: SyncResult) -> None
      Updates: SyncHistory record with results
      Sets: last_sync_at = now, last_sync_error = None
      Schedules: next_sync_scheduled_at = now + sync_frequency
      Emits: BankSyncCompleted

  + fail_sync(sync_id: UUID, error: str) -> None
      Updates: SyncHistory record with error
      Sets: last_sync_error = error
      Increments: consecutive failure count
      If consecutive failures >= 3:
        Sets: status = ERROR
        Emits: BankConnectionErrored
      Else:
        Schedules: retry with backoff
      Emits: BankSyncFailed

  // Status transitions
  + mark_needs_reauth() -> None
      Sets: status = NEEDS_REAUTH
      Emits: BankConnectionNeedsReauth

  + disconnect(disconnected_by: UUID) -> None
      Sets: status = DISCONNECTED
      Cancels: scheduled syncs
      Soft deletes: all pending transactions
      Emits: BankConnectionDisconnected

  + reconnect(access_token: EncryptedToken) -> None
      Validates: status is NEEDS_REAUTH or ERROR
      Sets: status = ACTIVE, access_token, resets failure count
      Schedules: immediate sync
      Emits: BankConnectionReestablished
      Raises: InvalidConnectionStateError

  // Lifecycle
  + soft_delete(deleted_by: UUID) -> None
      Validates: not already deleted
      Effect: disconnect first (if active), then soft delete
      Emits: BankConnectionSoftDeleted

  + update_sync_frequency(frequency: timedelta) -> None
      Validates: minimum 1 hour, maximum 24 hours
      Updates: sync_frequency, recalculates next_sync_scheduled_at
```

## 4. SyncHistory Entity

### 4.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| sync_id | UUID | No | Unique identifier |
| connection_id | UUID | No | Parent connection |
| started_at | datetime | No | Sync start time |
| completed_at | datetime? | Yes | Sync completion time |
| status | SyncStatus | Yes | Success, Failed, Partial |
| transactions_found | int | Yes | Total from provider |
| transactions_imported | int | Yes | New transactions created |
| transactions_duplicate | int | Yes | Skipped as duplicates |
| transactions_updated | int | Yes | Existing updated |
| error_message | str? | Yes | If failed, why |

**SyncStatus Enum:**

| Value | Description |
|-------|-------------|
| IN_PROGRESS | Sync currently running |
| SUCCESS | Completed successfully |
| PARTIAL | Completed with some failures |
| FAILED | Completely failed |

## 5. PendingTransaction Entity (Staging)

### 5.1 Purpose

When transactions are fetched from a bank provider, they go to a staging area first. This allows deduplication, normalization, and user review before they become real transactions in the Account aggregate.

### 5.2 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| pending_id | UUID | No | Staging record ID |
| connection_id | UUID | No | Source connection |
| sync_id | UUID | No | Which sync produced this |
| external_id | str | No | ID from provider |
| raw_data | dict | No | Original data from provider (JSON) |
| normalized_data | NormalizedTransaction | No | Converted to internal format |
| match_status | MatchStatus | Yes | New, Duplicate, NeedsReview |
| matched_transaction_id | UUID? | Yes | If duplicate, which existing one |
| created_at | datetime | No | When received |

**MatchStatus Enum:**

| Value | Description |
|-------|-------------|
| NEW | No matching transaction found — will be imported |
| DUPLICATE | Exact match found — will be skipped |
| NEEDS_REVIEW | Possible match — user should verify |
| USER_APPROVED | User confirmed as new (override) |
| USER_REJECTED | User confirmed as duplicate (override) |

### 5.3 NormalizedTransaction (Value Object)

Provider-agnostic representation of a bank transaction:

| Attribute | Type | Description |
|-----------|------|-------------|
| transaction_date | date | When transaction occurred |
| value_date | date? | Settlement date |
| amount | Decimal | Transaction amount |
| currency_code | str | ISO 4217 currency code |
| description | str | Transaction description |
| merchant | str? | Merchant name (if available) |
| external_id | str | Provider's transaction ID |

## 6. Import Processing Pipeline

### 6.1 Pipeline Overview

```
Provider API → Fetch
     │
     ▼
┌─────────────────┐
│  Raw Transactions│  Provider-specific format
│    from Bank     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Normalizer    │  Convert to NormalizedTransaction
│  (per provider) │  Handle currency, dates, amounts, signs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Deduplication  │  Check for existing transactions
│    Engine       │  in account by external_id, then fuzzy
└────────┬────────┘
         │
    ┌────┴────┬──────────┐
    │         │          │
    ▼         ▼          ▼
┌───────┐ ┌──────────┐ ┌────────────┐
│  NEW  │ │DUPLICATE │ │NEEDS_REVIEW│
└───┬───┘ └────┬─────┘ └──────┬─────┘
    │          │              │
    ▼          ▼              ▼
┌─────────┐ ┌──────────┐ ┌───────────┐
│ Stage as│ │  Skip    │ │ Stage for │
│ pending │ │ (log)    │ │ user      │
│ (NEW)   │ │          │ │ review    │
└────┬────┘ └──────────┘ └─────┬─────┘
     │                         │
     ▼                         ▼
┌─────────────────────────────────────┐
│  Auto-import NEW pending items      │
│  (or wait for user review)          │
└─────────────────────────────────────┘
     │
     ▼
┌─────────────────┐
│  Create real    │  Via Account.add_transaction()
│  Transactions   │  in Core Finance
└─────────────────┘
```

### 6.2 Provider Adapter Interface

Each bank provider has an adapter that implements a common interface:

```
BankProviderAdapter (Protocol):
  + fetch_transactions(
      access_token: EncryptedToken,
      external_account_id: str,
      since: datetime?
    ) -> list[RawBankTransaction]
      Fetches transactions from provider API
      since: only fetch transactions after this date (for incremental sync)

  + verify_credentials(access_token: EncryptedToken) -> bool
      Tests if credentials are still valid

  + get_account_info(
      access_token: EncryptedToken,
      external_account_id: str
    ) -> ExternalAccountInfo
      Returns account metadata from provider
```

**RawBankTransaction:** Provider-specific raw data (dict/JSON). Each adapter converts this to `NormalizedTransaction`.

### 6.3 Normalizer

Each provider has a normalizer that converts raw data to the internal format:

```
TransactionNormalizer (Protocol):
  + normalize(raw: RawBankTransaction) -> NormalizedTransaction
      Handles:
        - Date format conversion
        - Amount sign normalization (some providers use positive for debits)
        - Currency code mapping
        - Description cleanup
        - Merchant extraction
```

## 7. Deduplication Engine

### 7.1 Deduplication Rules (Ordered by Confidence)

| Priority | Rule | Confidence | Result |
|----------|------|------------|--------|
| 1 | Same `external_id` from same provider | Definite | DUPLICATE |
| 2 | Same date + same amount + same description | High | DUPLICATE |
| 3 | Same date + same amount (within ±0.01) | Medium | NEEDS_REVIEW |
| 4 | No match | — | NEW |

### 7.2 Deduplication Logic

```
DeduplicationEngine:
  + check(
      normalized: NormalizedTransaction,
      account_id: UUID,
      connection_id: UUID
    ) -> DeduplicationResult

  DeduplicationResult:
    - match_status: MatchStatus
    - matched_transaction_id: UUID?  (if DUPLICATE or NEEDS_REVIEW)
    - confidence: float              (0.0 - 1.0)
    - match_reason: str              (human-readable explanation)
```

```
Algorithm:
  1. Exact external_id match (same provider):
     existing = find_by_external_id(account_id, normalized.external_id)
     if existing:
       return DUPLICATE, existing.id, confidence=1.0

  2. Exact date + amount + description match:
     existing = find_by_date_amount_description(
       account_id, normalized.date, normalized.amount, normalized.description
     )
     if existing:
       return DUPLICATE, existing.id, confidence=0.95

  3. Fuzzy date + amount match:
     existing = find_by_date_and_approximate_amount(
       account_id, normalized.date, normalized.amount, tolerance=0.01
     )
     if existing:
       return NEEDS_REVIEW, existing.id, confidence=0.6

  4. No match:
     return NEW, None, confidence=0.0
```

### 7.3 Deduplication Scope

| Scope | Description |
|-------|-------------|
| Per account | Deduplication checks within the target account only |
| Includes deleted | Checks against soft-deleted transactions too (prevents re-import) |
| Per connection | External ID uniqueness is scoped to the connection's account |

## 8. Sync Execution Flow

```
Scheduled sync triggers for connection:
     │
     ▼
  1. Validate connection is ACTIVE
     │
     ▼
  2. connection.start_sync() → sync_id
     │
     ▼
  3. Fetch transactions from provider:
     adapter.fetch_transactions(token, external_id, since=last_sync_at)
     │
     ├── Auth error → connection.mark_needs_reauth(), connection.fail_sync()
     ├── Other error → connection.fail_sync(error)
     │
     ▼
  4. For each raw transaction:
     a. Normalize: normalizer.normalize(raw) → normalized
     b. Deduplicate: engine.check(normalized, account_id) → result
     c. Create PendingTransaction with match_status
     │
     ▼
  5. Auto-import NEW pending transactions:
     For each pending where match_status == NEW:
       a. Create Transaction entity from normalized_data
       b. account.add_transaction(transaction)
       c. Mark pending as imported
     │
     ▼
  6. connection.complete_sync(sync_id, result_counts)
     │
     ▼
  7. Emit BankSyncCompleted (with import counts)
     Emit TransactionsImported (notification trigger)
```

## 9. User Review of Pending Transactions

For transactions with `match_status = NEEDS_REVIEW`:

```
User reviews pending transaction:
     │
     ├── "This is new" (approve):
     │   1. pending.match_status = USER_APPROVED
     │   2. Create Transaction from normalized_data
     │   3. account.add_transaction(transaction)
     │   4. Mark pending as imported
     │
     └── "This is a duplicate" (reject):
         1. pending.match_status = USER_REJECTED
         2. Link to matched_transaction_id for reference
         3. No transaction created
```

## 10. Invariants

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| BNK-001 | One connection per account per provider | Domain service checks before creation |
| BNK-002 | Credentials encrypted at rest | EncryptedToken value object (infra) |
| BNK-003 | Sync requires ACTIVE connection status | `start_sync()` validates status |
| BNK-004 | Disconnecting soft deletes pending transactions | `disconnect()` cascades |

## 11. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `BankConnectionInitiated` | `initiate()` | connection_id, user_id, provider, account_id |
| `BankConnectionEstablished` | `activate()` | connection_id, triggers initial sync |
| `BankConnectionNeedsReauth` | `mark_needs_reauth()` | connection_id, user_id |
| `BankConnectionErrored` | 3+ consecutive failures | connection_id, last_error |
| `BankConnectionDisconnected` | `disconnect()` | connection_id, disconnected_by |
| `BankConnectionReestablished` | `reconnect()` | connection_id |
| `BankConnectionSoftDeleted` | `soft_delete()` | connection_id, deleted_by |
| `BankSyncCompleted` | `complete_sync()` | connection_id, sync_id, imported_count, duplicate_count |
| `BankSyncFailed` | `fail_sync()` | connection_id, sync_id, error |
| `TransactionsImported` | New transactions from sync | account_id, count, connection_id |

## 12. Domain Errors

| Error | Trigger | Description |
|-------|---------|-------------|
| `ConnectionNotActiveError` | Sync on non-ACTIVE connection | Must be ACTIVE to sync |
| `InvalidConnectionStateError` | Invalid state transition | e.g., activating an already-active connection |
| `DuplicateConnectionError` | Same account + provider already exists | BNK-001 violation |
| `SyncAlreadyInProgressError` | Starting sync while one is running | One sync at a time per connection |
| `InvalidSyncFrequencyError` | Frequency outside 1h-24h range | Must be within bounds |
| `PendingTransactionNotFoundError` | Review of non-existent pending | Invalid pending_id |

## 13. Repository Interfaces

```
BankConnectionRepository (Protocol):
  + save(connection: BankConnection) -> None
  + find_by_id(connection_id: UUID) -> BankConnection?
  + find_by_user(user_id: UUID, include_deleted: bool = False) -> list[BankConnection]
  + find_by_account(account_id: UUID) -> list[BankConnection]
  + find_by_account_and_provider(account_id: UUID, provider: BankProvider) -> BankConnection?
  + find_due_for_sync(as_of: datetime) -> list[BankConnection]
      Connections where next_sync_scheduled_at <= as_of and status == ACTIVE

SyncHistoryRepository (Protocol):
  + save(history: SyncHistory) -> None
  + find_by_connection(connection_id: UUID, limit: int = 10) -> list[SyncHistory]
  + find_latest_by_connection(connection_id: UUID) -> SyncHistory?

PendingTransactionRepository (Protocol):
  + save(pending: PendingTransaction) -> None
  + save_many(pendings: list[PendingTransaction]) -> None
  + find_by_connection(connection_id: UUID) -> list[PendingTransaction]
  + find_needs_review(connection_id: UUID) -> list[PendingTransaction]
  + find_by_id(pending_id: UUID) -> PendingTransaction?
  + delete_by_connection(connection_id: UUID) -> None
      For disconnect cascade
```

## 14. Acceptance Criteria

### Connection Lifecycle

- [ ] User can initiate a bank connection (PENDING status)
- [ ] Activating with credentials transitions to ACTIVE
- [ ] ACTIVE connection can trigger sync
- [ ] 3+ consecutive sync failures transition to ERROR
- [ ] Expired credentials transition to NEEDS_REAUTH
- [ ] User can disconnect (DISCONNECTED status, pending transactions soft deleted)
- [ ] User can reconnect from NEEDS_REAUTH or ERROR
- [ ] One connection per account per provider — raises `DuplicateConnectionError`

### Sync Execution

- [ ] Sync fetches transactions from provider since last sync
- [ ] First sync fetches all available history
- [ ] Sync creates SyncHistory record with counts
- [ ] Auth errors during sync trigger NEEDS_REAUTH
- [ ] Other errors increment failure count and schedule retry with backoff
- [ ] `BankSyncCompleted` event emitted on success
- [ ] `BankSyncFailed` event emitted on failure

### Import Pipeline

- [ ] Raw transactions are normalized via provider-specific normalizer
- [ ] Normalized transactions are checked against deduplication engine
- [ ] Exact external_id match → DUPLICATE (skipped)
- [ ] Exact date + amount + description → DUPLICATE (skipped)
- [ ] Same date + approximate amount (±0.01) → NEEDS_REVIEW (staged)
- [ ] No match → NEW (auto-imported)
- [ ] Deduplication checks include soft-deleted transactions
- [ ] NEW transactions auto-create real transactions in Core Finance

### Pending Transaction Review

- [ ] User can approve a NEEDS_REVIEW pending (creates transaction)
- [ ] User can reject a NEEDS_REVIEW pending (no transaction created)
- [ ] Approved pending linked to created transaction
- [ ] Rejected pending linked to matched existing transaction

### Scheduling

- [ ] Sync frequency configurable between 1 hour and 24 hours
- [ ] Next sync auto-scheduled after successful completion
- [ ] Failed syncs retry with exponential backoff
- [ ] Disconnected connections have no scheduled syncs

### Imported Transactions

- [ ] Imported transactions have `import_source = BANK_IMPORT`
- [ ] Imported transactions have `review_status = TO_REVIEW`
- [ ] Imported transactions have `external_id` set from provider
- [ ] Imported transactions preserve `original_description` from bank
- [ ] `TransactionsImported` event emitted for notification
