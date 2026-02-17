# Spec 015: Bank Connections & Sync — Implementation Plan

**Spec:** `.specs/spec-015-bank-connections-and-sync/spec.md`
**Version:** 1.0
**Date:** 2026-02-17

---

## 1. Overview

This plan implements the **External Integrations** bounded context — the first new context outside IAM, Core Finance, and Classification. It introduces the `BankConnection` aggregate with a lifecycle state machine, `SyncHistory` and `PendingTransaction` entities, a deduplication service, and an ACL boundary to Core Finance via `TransactionImportPort`.

**Approach:** Inside-out (domain → application → tests), following the same patterns established in `core_finance` and `classification`. The new context lives at `src/emerald/integrations/`.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| Value objects (ProviderName, ProviderCredentials, NormalizedTransaction, etc.) | Domain | `domain/models/value_objects/` |
| Enums (ConnectionStatus, SyncStatus, MatchStatus) | Domain | `domain/models/value_objects/` |
| Domain constants | Domain | `domain/constants.py` |
| BankConnection aggregate | Domain | `domain/models/aggregates/bank_connection.py` |
| SyncHistory entity | Domain | `domain/models/entities/sync_history.py` |
| PendingTransaction entity | Domain | `domain/models/entities/pending_transaction.py` |
| TransactionNormalizer protocol | Domain | `domain/ports/transaction_normalizer.py` |
| Domain events | Domain | `domain/events/` |
| Domain exceptions | Domain | `domain/exceptions/` |
| Repository protocols | Application | `application/ports/outbound/` |
| Outbound ports (BankProviderAdapter, TransactionImportPort, Registry) | Application | `application/ports/outbound/` |
| Commands | Application | `application/dtos/commands/` |
| Unit of Work | Application | `application/ports/outbound/unit_of_work.py` |
| BankConnectionService | Application | `application/services/bank_connection.py` |
| BankSyncService | Application | `application/services/bank_sync.py` |
| DeduplicationService | Application | `application/services/deduplication.py` |
| TransactionMatch DTO | Application | `application/dtos/transaction_match.py` |

### 2.2 Component Diagram

```
integrations/
├── __init__.py                              # public API re-exports
├── application/
│   ├── __init__.py
│   ├── dtos/
│   │   ├── __init__.py
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   └── connection_commands.py       # all 9 commands
│   │   └── transaction_match.py             # TransactionMatch DTO
│   ├── ports/
│   │   └── outbound/
│   │       ├── __init__.py
│   │       ├── bank_connection_repository.py
│   │       ├── sync_history_repository.py
│   │       ├── pending_transaction_repository.py
│   │       ├── bank_provider_adapter.py     # BankProviderAdapter protocol
│   │       ├── provider_registry.py         # BankProviderAdapterRegistry protocol
│   │       ├── transaction_import_port.py   # ACL to Core Finance
│   │       └── unit_of_work.py              # AbstractIntegrationsUnitOfWork
│   └── services/
│       ├── __init__.py
│       ├── bank_connection.py               # BankConnectionService
│       ├── bank_sync.py                     # BankSyncService
│       └── deduplication.py                 # DeduplicationService
└── domain/
    ├── __init__.py
    ├── constants.py
    ├── events/
    │   ├── __init__.py
    │   ├── base.py                          # BankConnectionEvent base
    │   └── connection_events.py             # all 13 events
    ├── exceptions/
    │   ├── __init__.py
    │   └── connection_exceptions.py         # all 14 exceptions
    └── models/
        ├── __init__.py
        ├── aggregates/
        │   ├── __init__.py
        │   └── bank_connection.py
        ├── entities/
        │   ├── __init__.py
        │   ├── sync_history.py
        │   └── pending_transaction.py
        └── value_objects/
            ├── __init__.py
            ├── provider_name.py
            ├── provider_credentials.py
            ├── normalized_transaction.py
            ├── deduplication_result.py
            ├── sync_result.py
            ├── connection_status.py
            ├── sync_status.py
            └── match_status.py
```

### 2.3 Ports and Adapters

| Port (Protocol) | Layer | Purpose |
|-----------------|-------|---------|
| `BankConnectionRepository` | Application | Connection persistence |
| `SyncHistoryRepository` | Application | Sync history persistence |
| `PendingTransactionRepository` | Application | Staging area persistence |
| `BankProviderAdapter` | Application | External bank API communication |
| `BankProviderAdapterRegistry` | Application | Resolves adapter + normalizer by provider |
| `TransactionImportPort` | Application | ACL boundary to Core Finance |
| `TransactionNormalizer` | Domain | Raw → normalized transaction conversion |

---

## 3. Technical Decisions

### 3.1 Context Naming
**Decision:** `integrations` (not `external_integrations`)
**Rationale:** Shorter, consistent with the established short-name convention (e.g., `iam`, `core_finance`, `classification`). The spec calls it "External Integrations" conceptually but the module name should be concise.

### 3.2 TransactionNormalizer Placement
**Decision:** Domain-layer protocol in `domain/ports/transaction_normalizer.py`
**Rationale:** The spec explicitly states normalization rules are domain logic. Infrastructure adapters implement it per provider.

### 3.3 Event Base Class
**Decision:** Single `BankConnectionEvent` base with `aggregate_type = "bank_connection"`
**Rationale:** All 13 events relate to the BankConnection aggregate or its sync operations. Consistent with `AccountEvent`, `TransactionEvent`, `TaxonomyEvent` pattern.

### 3.4 Provider Exceptions
**Decision:** `ProviderAuthError` and `ProviderError` as domain exceptions (not infrastructure)
**Rationale:** The BankSyncService needs to catch these to drive state transitions (NEEDS_REAUTH, ERROR). They must be defined where the domain can reference them. The `BankProviderAdapter` protocol declares them as raisable.

### 3.5 SyncHistory Event Registration
**Decision:** SyncHistory has no own `_events` list — sync events registered on BankConnection aggregate
**Rationale:** SyncHistory is a simple Entity, not an AggregateRoot. Events like `BankSyncStarted/Completed/Failed` are conceptually BankConnection aggregate events. The BankSyncService registers them on the connection aggregate. Same pattern as AccountShare events being registered on Account.

### 3.6 PendingTransaction Event Handling
**Decision:** `PendingTransactionApproved` and `PendingTransactionRejected` registered on BankConnection (loaded by service)
**Rationale:** PendingTransaction is ephemeral and not an aggregate. The service loads the connection to register events there.

---

## 4. Implementation Tasks

### Phase 1: Domain Layer — Value Objects & Enums

#### TASK-001: Create value object enums (ConnectionStatus, SyncStatus, MatchStatus)
**Layer:** Domain
**Depends On:** None

**Description:**
Create three StrEnum value objects for the BankConnection state machine, sync lifecycle, and deduplication match results.

**Files to Create:**
- `src/emerald/integrations/domain/models/value_objects/connection_status.py` — ConnectionStatus enum (PENDING, ACTIVE, NEEDS_REAUTH, ERROR, DISCONNECTED)
- `src/emerald/integrations/domain/models/value_objects/sync_status.py` — SyncStatus enum (IN_PROGRESS, SUCCESS, PARTIAL, FAILED)
- `src/emerald/integrations/domain/models/value_objects/match_status.py` — MatchStatus enum (NEW, DUPLICATE, NEEDS_REVIEW, USER_APPROVED, USER_REJECTED)

**Tests:**
- `tests/unit/integrations/domain/value_objects/test_connection_status.py`
- `tests/unit/integrations/domain/value_objects/test_sync_status.py`
- `tests/unit/integrations/domain/value_objects/test_match_status.py`

---

#### TASK-002: Create ProviderName and ProviderCredentials value objects
**Layer:** Domain
**Depends On:** None

**Description:**
- `ProviderName`: validated string VO — non-empty, trimmed, max 50 chars, lowercase normalized
- `ProviderCredentials`: opaque token VO — non-empty, trimmed

**Files to Create:**
- `src/emerald/integrations/domain/models/value_objects/provider_name.py`
- `src/emerald/integrations/domain/models/value_objects/provider_credentials.py`

**Tests:**
- `tests/unit/integrations/domain/value_objects/test_provider_name.py`
- `tests/unit/integrations/domain/value_objects/test_provider_credentials.py`

---

#### TASK-003: Create NormalizedTransaction, DeduplicationResult, SyncResult value objects
**Layer:** Domain
**Depends On:** None

**Description:**
- `NormalizedTransaction`: frozen dataclass — transaction_date, value_date, amount (Decimal, non-zero), currency_code (3 chars uppercase), description (trimmed, max 500), merchant (optional, trimmed, max 200), external_id (trimmed, non-empty)
- `DeduplicationResult`: frozen dataclass — match_status, matched_transaction_id (optional), confidence (0.0-1.0), match_reason
- `SyncResult`: frozen dataclass — transactions_found, transactions_imported, transactions_duplicate, transactions_staged; invariant: imported + duplicate + staged == found

**Files to Create:**
- `src/emerald/integrations/domain/models/value_objects/normalized_transaction.py`
- `src/emerald/integrations/domain/models/value_objects/deduplication_result.py`
- `src/emerald/integrations/domain/models/value_objects/sync_result.py`

**Tests:**
- `tests/unit/integrations/domain/value_objects/test_normalized_transaction.py`
- `tests/unit/integrations/domain/value_objects/test_deduplication_result.py`
- `tests/unit/integrations/domain/value_objects/test_sync_result.py`

---

#### TASK-004: Create domain constants
**Layer:** Domain
**Depends On:** None

**Description:**
Define all domain constants for the integrations context.

**Files to Create:**
- `src/emerald/integrations/domain/constants.py`

**Tests:**
- `tests/unit/integrations/domain/test_constants.py` — verify values match spec

---

#### TASK-005: Create domain exceptions
**Layer:** Domain
**Depends On:** None

**Description:**
Create all 14 exceptions (+ 2 provider errors) following the established pattern with unique error codes.

Exceptions:
- `EmptyProviderNameError(InvalidValueError)`
- `ProviderNameTooLongError(InvalidValueError)`
- `InvalidNormalizedTransactionError(InvalidValueError)`
- `InvalidProviderCredentialsError(InvalidValueError)`
- `InvalidSyncFrequencyError(InvalidValueError)`
- `ConnectionNotActiveError(InvariantViolationError)`
- `InvalidConnectionStateError(InvariantViolationError)`
- `DuplicateConnectionError(InvariantViolationError)`
- `SyncAlreadyInProgressError(InvariantViolationError)`
- `SyncAlreadyCompletedError(InvariantViolationError)`
- `InvalidPendingStateError(InvariantViolationError)`
- `PendingTransactionNotFoundError(NotFoundError)`
- `BankConnectionNotFoundError(NotFoundError)`
- `SyncHistoryNotFoundError(NotFoundError)`
- `ProviderAuthError(DomainError)` — credentials expired/invalid
- `ProviderError(DomainError)` — general provider failure

**Files to Create:**
- `src/emerald/integrations/domain/exceptions/__init__.py`
- `src/emerald/integrations/domain/exceptions/connection_exceptions.py`

**Tests:**
- `tests/unit/integrations/domain/exceptions/test_connection_exceptions.py`

---

#### TASK-006: Create domain events
**Layer:** Domain
**Depends On:** None

**Description:**
Create `BankConnectionEvent` base class with `aggregate_type = "bank_connection"` and all 13 concrete events as frozen dataclasses.

Events: BankConnectionInitiated, BankConnectionActivated, BankConnectionNeedsReauth, BankConnectionErrored, BankConnectionDisconnected, BankConnectionReconnected, BankConnectionSoftDeleted, BankSyncStarted, BankSyncCompleted, BankSyncFailed, TransactionsImported, PendingTransactionApproved, PendingTransactionRejected

**Files to Create:**
- `src/emerald/integrations/domain/events/base.py` — BankConnectionEvent
- `src/emerald/integrations/domain/events/connection_events.py` — all 13 events

**Tests:**
- `tests/unit/integrations/domain/events/test_connection_events.py`

---

### Phase 2: Domain Layer — Entities & Aggregate

#### TASK-007: Create SyncHistory entity
**Layer:** Domain
**Depends On:** TASK-001, TASK-003

**Description:**
`SyncHistory` extends `TimestampedMixin + Entity`. Immutable after completion. Methods: `create()` factory, `complete(result)`, `fail(error_message)`.

**Files to Create:**
- `src/emerald/integrations/domain/models/entities/sync_history.py`

**Tests:**
- `tests/unit/integrations/domain/entities/test_sync_history.py`

**Acceptance Criteria:**
- [ ] create() sets IN_PROGRESS status, started_at = now
- [ ] complete() transitions to SUCCESS (or PARTIAL if staged > 0)
- [ ] fail() transitions to FAILED with error_message
- [ ] complete()/fail() raise SyncAlreadyCompletedError if not IN_PROGRESS
- [ ] completed_at set on completion/failure

---

#### TASK-008: Create PendingTransaction entity
**Layer:** Domain
**Depends On:** TASK-001, TASK-003

**Description:**
`PendingTransaction` extends `Entity` (no mixins — ephemeral). Methods: `create()` factory, `approve()`, `reject()`, `mark_imported()`, `is_importable()`.

**Files to Create:**
- `src/emerald/integrations/domain/models/entities/pending_transaction.py`

**Tests:**
- `tests/unit/integrations/domain/entities/test_pending_transaction.py`

**Acceptance Criteria:**
- [ ] create() validates match_status is NEW, DUPLICATE, or NEEDS_REVIEW only
- [ ] approve() only from NEEDS_REVIEW → USER_APPROVED
- [ ] reject() only from NEEDS_REVIEW → USER_REJECTED
- [ ] mark_imported() only from NEW or USER_APPROVED, sets imported_transaction_id
- [ ] is_importable() returns True for NEW/USER_APPROVED with no imported_transaction_id
- [ ] Invalid transitions raise InvalidPendingStateError

---

#### TASK-009: Create BankConnection aggregate
**Layer:** Domain
**Depends On:** TASK-001 through TASK-006

**Description:**
`BankConnection` extends `SoftDeletableMixin + AuditableMixin + AggregateRoot`. Implements full state machine with lifecycle methods.

**Files to Create:**
- `src/emerald/integrations/domain/models/aggregates/bank_connection.py`

**Tests:**
- `tests/unit/integrations/domain/aggregates/test_bank_connection_create.py`
- `tests/unit/integrations/domain/aggregates/test_bank_connection_lifecycle.py`
- `tests/unit/integrations/domain/aggregates/test_bank_connection_sync.py`
- `tests/unit/integrations/domain/aggregates/test_bank_connection_config.py`

**Acceptance Criteria:**
- [ ] create() → PENDING status, no credentials, BankConnectionInitiated event
- [ ] activate() from PENDING → ACTIVE, sets credentials, BankConnectionActivated event
- [ ] activate() from other states raises InvalidConnectionStateError
- [ ] record_sync_success() sets last_sync_at, clears errors, schedules next sync
- [ ] record_sync_failure() increments failures, 3+ triggers ERROR + BankConnectionErrored
- [ ] mark_needs_reauth() ACTIVE → NEEDS_REAUTH, clears credentials
- [ ] disconnect() any non-DISCONNECTED → DISCONNECTED, clears credentials
- [ ] disconnect() from DISCONNECTED raises InvalidConnectionStateError
- [ ] reconnect() from NEEDS_REAUTH/ERROR → ACTIVE, sets credentials
- [ ] reconnect() from DISCONNECTED raises InvalidConnectionStateError
- [ ] update_sync_frequency() validates range, recalculates next sync if ACTIVE
- [ ] soft_delete() disconnects first (if not already), then soft deletes
- [ ] is_syncable() returns True only for ACTIVE + not deleted
- [ ] calculate_next_retry() exponential backoff (15, 30, 60 min cap)

---

### Phase 3: Domain Layer — Domain Ports

#### TASK-010: Create TransactionNormalizer protocol
**Layer:** Domain
**Depends On:** TASK-003

**Description:**
Domain-layer protocol for raw data → NormalizedTransaction conversion.

**Files to Create:**
- `src/emerald/integrations/domain/ports/__init__.py`
- `src/emerald/integrations/domain/ports/transaction_normalizer.py`

**Tests:** Protocol-only, no unit tests needed (tested via fakes in service tests).

---

### Phase 4: Application Layer — Ports & DTOs

#### TASK-011: Create commands
**Layer:** Application
**Depends On:** None

**Description:**
9 commands as frozen dataclasses extending `Command`: InitiateBankConnection, ActivateBankConnection, DisconnectBankConnection, ReconnectBankConnection, UpdateSyncFrequency, TriggerSync, ApprovePendingTransaction, RejectPendingTransaction, SoftDeleteBankConnection.

**Files to Create:**
- `src/emerald/integrations/application/dtos/commands/connection_commands.py`

**Tests:**
- `tests/unit/integrations/application/dtos/commands/test_connection_commands.py`

---

#### TASK-012: Create TransactionMatch DTO
**Layer:** Application
**Depends On:** None

**Description:**
Simple frozen dataclass: transaction_id (UUID), transaction_date (date), amount (Decimal), description (str), external_id (str | None).

**Files to Create:**
- `src/emerald/integrations/application/dtos/transaction_match.py`

**Tests:** Trivial frozen dataclass — tested implicitly via service tests.

---

#### TASK-013: Create repository protocols and outbound ports
**Layer:** Application
**Depends On:** TASK-009, TASK-007, TASK-008

**Description:**
Create all 6 protocol ports:
- `BankConnectionRepository` — save, find_by_id, find_by_user, find_by_account, find_by_account_and_provider, find_due_for_sync
- `SyncHistoryRepository` — save, find_by_id, find_by_connection, find_latest_by_connection, find_in_progress_by_connection
- `PendingTransactionRepository` — save, save_many, find_by_id, find_by_connection, find_needs_review, find_by_sync, delete_by_connection
- `BankProviderAdapter` — fetch_transactions, verify_credentials, get_account_info
- `BankProviderAdapterRegistry` — get_adapter, get_normalizer
- `TransactionImportPort` — import_transaction, find_by_external_id, find_by_date_and_amount

**Files to Create:**
- `src/emerald/integrations/application/ports/outbound/bank_connection_repository.py`
- `src/emerald/integrations/application/ports/outbound/sync_history_repository.py`
- `src/emerald/integrations/application/ports/outbound/pending_transaction_repository.py`
- `src/emerald/integrations/application/ports/outbound/bank_provider_adapter.py`
- `src/emerald/integrations/application/ports/outbound/provider_registry.py`
- `src/emerald/integrations/application/ports/outbound/transaction_import_port.py`

**Tests:** Protocols only — no unit tests (tested via fakes).

---

#### TASK-014: Create AbstractIntegrationsUnitOfWork
**Layer:** Application
**Depends On:** TASK-013

**Description:**
Extends `AbstractUnitOfWork`, declares `bank_connections`, `sync_history`, `pending_transactions` typed repo attributes.

**Files to Create:**
- `src/emerald/integrations/application/ports/outbound/unit_of_work.py`

**Tests:** Abstract class — tested via FakeIntegrationsUnitOfWork.

---

### Phase 5: Application Layer — Services

#### TASK-015: Create test fakes
**Layer:** Testing
**Depends On:** TASK-013, TASK-014

**Description:**
Create in-memory fakes for all repositories, the UoW, provider adapter, registry, normalizer, and transaction import port.

**Files to Create:**
- `tests/unit/integrations/fakes.py`

**Acceptance Criteria:**
- [ ] FakeBankConnectionRepository implements all protocol methods
- [ ] FakeSyncHistoryRepository implements all protocol methods
- [ ] FakePendingTransactionRepository implements all protocol methods (including save_many, delete_by_connection)
- [ ] FakeIntegrationsUnitOfWork with seen-based event collection
- [ ] FakeBankProviderAdapter with configurable responses/errors
- [ ] FakeProviderRegistry resolving fake adapter + normalizer
- [ ] FakeTransactionNormalizer with passthrough behavior
- [ ] FakeTransactionImportPort tracking imported transactions

---

#### TASK-016: Create DeduplicationService
**Layer:** Application
**Depends On:** TASK-012, TASK-013

**Description:**
Application service implementing the 4-tier deduplication algorithm: exact external_id → exact date+amount+description → fuzzy date+amount → new.

**Files to Create:**
- `src/emerald/integrations/application/services/deduplication.py`

**Tests:**
- `tests/unit/integrations/application/services/test_deduplication.py`

**Acceptance Criteria:**
- [ ] Exact external_id match returns DUPLICATE (confidence 1.0)
- [ ] Same date + amount + description returns DUPLICATE (confidence 0.95)
- [ ] Same date + approximate amount (±0.01) returns NEEDS_REVIEW (confidence 0.6)
- [ ] No match returns NEW (confidence 0.0)
- [ ] Deduplication scope is per-account (includes soft-deleted via port)

---

#### TASK-017: Create BankConnectionService
**Layer:** Application
**Depends On:** TASK-014, TASK-015

**Description:**
Orchestrates connection lifecycle: initiate, activate, disconnect, reconnect, update frequency, soft delete, and query operations.

**Files to Create:**
- `src/emerald/integrations/application/services/bank_connection.py`

**Tests:**
- `tests/unit/integrations/application/services/test_connection_initiate.py`
- `tests/unit/integrations/application/services/test_connection_lifecycle.py`
- `tests/unit/integrations/application/services/test_connection_config.py`
- `tests/unit/integrations/application/services/test_connection_queries.py`

**Acceptance Criteria:**
- [ ] initiate_connection checks duplicate (account+provider) before creating
- [ ] activate_connection loads and delegates to aggregate
- [ ] disconnect_connection hard-deletes pending transactions
- [ ] reconnect_connection delegates to aggregate
- [ ] update_sync_frequency verifies user owns connection
- [ ] soft_delete_connection hard-deletes pending transactions
- [ ] Query methods delegate to repository

---

#### TASK-018: Create BankSyncService
**Layer:** Application
**Depends On:** TASK-014, TASK-015, TASK-016

**Description:**
Orchestrates the full sync pipeline: fetch → normalize → deduplicate → stage/import. Also handles pending transaction approval/rejection.

**Files to Create:**
- `src/emerald/integrations/application/services/bank_sync.py`

**Tests:**
- `tests/unit/integrations/application/services/test_sync_execute.py`
- `tests/unit/integrations/application/services/test_sync_pending_review.py`
- `tests/unit/integrations/application/services/test_sync_error_handling.py`

**Acceptance Criteria:**
- [ ] execute_sync validates ACTIVE connection
- [ ] Checks no IN_PROGRESS sync exists (SyncAlreadyInProgressError)
- [ ] Creates SyncHistory(IN_PROGRESS)
- [ ] Auth error → mark_needs_reauth() + history.fail()
- [ ] Provider error → record_sync_failure() + history.fail()
- [ ] DUPLICATE items skipped (not persisted as pending)
- [ ] NEW items auto-imported via TransactionImportPort
- [ ] NEEDS_REVIEW items staged as pending
- [ ] SyncResult invariant maintained (found = imported + duplicate + staged)
- [ ] approve_pending: loads pending, approves, imports, marks imported
- [ ] reject_pending: loads pending, rejects
- [ ] User ownership verified for approve/reject
- [ ] find_connections_due_for_sync queries repository

---

### Phase 6: Module Wiring

#### TASK-019: Create package __init__.py files and public API
**Layer:** All
**Depends On:** TASK-001 through TASK-018

**Description:**
Create all `__init__.py` files for the integrations context, with explicit `__all__` re-exports at each level. Wire up the domain and application sub-packages.

**Files to Create/Modify:**
- `src/emerald/integrations/__init__.py` — top-level public API
- `src/emerald/integrations/domain/__init__.py`
- `src/emerald/integrations/domain/models/__init__.py`
- `src/emerald/integrations/domain/models/aggregates/__init__.py`
- `src/emerald/integrations/domain/models/entities/__init__.py`
- `src/emerald/integrations/domain/models/value_objects/__init__.py`
- `src/emerald/integrations/domain/events/__init__.py`
- `src/emerald/integrations/domain/exceptions/__init__.py` (already in TASK-005)
- `src/emerald/integrations/domain/ports/__init__.py` (already in TASK-010)
- `src/emerald/integrations/application/__init__.py`
- `src/emerald/integrations/application/dtos/__init__.py`
- `src/emerald/integrations/application/dtos/commands/__init__.py`
- `src/emerald/integrations/application/ports/__init__.py`
- `src/emerald/integrations/application/ports/outbound/__init__.py`
- `src/emerald/integrations/application/services/__init__.py`
- All `tests/unit/integrations/` `__init__.py` files

**Acceptance Criteria:**
- [ ] `from emerald.integrations import BankConnection, BankConnectionService, ...` works
- [ ] All public types listed in `__all__`

---

### Phase 7: Quality Assurance

#### TASK-020: Run full quality checks
**Layer:** Cross-cutting
**Depends On:** TASK-019

**Description:**
Run all quality checks and fix any issues.

**Acceptance Criteria:**
- [ ] `uv run pytest` — all tests pass (existing + new)
- [ ] `uv run ruff check .` — no lint errors
- [ ] `uv run ruff format .` — no format changes
- [ ] `uv run ty check` — no type errors

---

## 5. Task Dependency Graph

```
TASK-001 (enums) ──────────┐
TASK-002 (provider VOs) ───┤
TASK-003 (transaction VOs) ┼──► TASK-007 (SyncHistory) ────┐
TASK-004 (constants) ──────┤                                │
TASK-005 (exceptions) ─────┤   TASK-008 (PendingTx) ───────┤
TASK-006 (events) ─────────┤                                │
                            └──► TASK-009 (BankConnection) ─┤
                                                            │
TASK-010 (normalizer port) ─────────────────────────────────┤
TASK-011 (commands) ────────────────────────────────────────┤
TASK-012 (TransactionMatch) ────────────────────────────────┤
                                                            │
                            ┌──► TASK-013 (repo protocols) ─┤
                            │                                │
                            └──► TASK-014 (UoW) ────────────┤
                                                            │
                                 TASK-015 (fakes) ──────────┤
                                                            │
                            ┌──► TASK-016 (dedup service) ──┤
                            │                                │
                            ├──► TASK-017 (connection svc) ─┤
                            │                                │
                            └──► TASK-018 (sync service) ───┤
                                                            │
                                 TASK-019 (__init__.py) ────┤
                                                            │
                                 TASK-020 (quality checks) ─┘
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large scope (3 entities, 3 services, 13 events) | Medium | Medium | Strict inside-out ordering; each task is self-contained and testable |
| BankSyncService complexity (10-step pipeline) | Medium | High | Decompose into clear steps; test each error path independently |
| Cross-context ACL (TransactionImportPort) | Low | Medium | Port is a protocol — implementation deferred to infrastructure; tested via fakes |
| Event registration on connection for sync/pending events | Low | Low | Consistent with AccountShare events pattern; service loads aggregate |

---

## 7. Definition of Done

- [ ] All 20 tasks completed
- [ ] All acceptance criteria met
- [ ] All new unit tests passing
- [ ] All existing tests still passing (no regressions)
- [ ] `uv run ruff check .` clean
- [ ] `uv run ruff format .` clean
- [ ] `uv run ty check` clean
- [ ] `integrations/__init__.py` exports all public types with `__all__`
- [ ] Test fakes fully implement all protocol methods

---

## 8. Estimated Test Count

| Phase | Tests (approx) |
|-------|----------------|
| Value objects & enums (TASK-001–003) | ~40 |
| Constants (TASK-004) | ~10 |
| Exceptions (TASK-005) | ~16 |
| Events (TASK-006) | ~15 |
| SyncHistory entity (TASK-007) | ~12 |
| PendingTransaction entity (TASK-008) | ~15 |
| BankConnection aggregate (TASK-009) | ~50 |
| Commands (TASK-011) | ~10 |
| DeduplicationService (TASK-016) | ~12 |
| BankConnectionService (TASK-017) | ~30 |
| BankSyncService (TASK-018) | ~35 |
| **Total new tests** | **~245** |
| **Total with existing** | **~2532** |
