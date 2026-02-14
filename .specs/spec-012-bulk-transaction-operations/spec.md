# Spec 012: Bulk Transaction Operations

**Version:** 1.0
**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 009 (Transaction Management), 010 (Transaction Splitting)
**Blocks:** 015 (Bank Connections & Sync — uses bulk create internally)

---

## 1. Overview

Bulk transaction operations allow creating, updating, deleting, and recovering multiple transactions in a single request. Each item in a batch is validated independently — valid items succeed even when others fail. Detailed per-item error reporting enables callers to fix and retry only the failed items.

This capability serves two primary use cases: (1) efficient manual data entry when users import spreadsheets or paste multiple transactions, and (2) programmatic ingestion by upstream consumers like bank sync (Spec 015) that produce batches of transactions.

---

## 2. Background & Context

### Problem Statement

The current single-transaction API (Spec 009) requires one request per transaction. For batch imports (bank sync, CSV upload, manual multi-entry), this is slow and provides no partial-failure semantics — a single validation error blocks the entire import.

### Business Goals

- Enable efficient batch data entry (up to 1000 transactions per request)
- Provide partial-success semantics so valid items aren't blocked by invalid ones
- Give callers actionable per-item error reports for retry
- Serve as the foundation for bank import ingestion (Spec 015)

---

## 3. Scope

### In Scope

- Bulk create transactions (up to 1000)
- Bulk update (review status, user description, merchant)
- Bulk soft delete
- Bulk recover
- Per-item validation and error reporting via `BulkResult`
- Request-level (fail-fast) and per-item (partial-success) validation phases
- Domain constants for bulk limits

### Out of Scope

- Bulk splitting (not a batch operation pattern)
- Bank import ingestion orchestration (Spec 015 — consumes bulk create)
- Bulk card operations
- Infrastructure-level batch chunking (deferred to infrastructure layer)
- Persisted balance cache (balance remains computed on-demand)

---

## 4. Users & Personas

### Primary Users

- **End users** importing transactions from spreadsheets or performing mass management (mark all as reviewed, delete old transactions)
- **Bank sync subsystem** (Spec 015) that programmatically creates batches of imported transactions

### User Goals

- Create many transactions without N individual requests
- Update a common field (e.g., review status) across many transactions at once
- Clean up or recover transactions in bulk
- Get clear feedback on which items succeeded and which failed, with actionable error details

---

## 5. Value Objects

### 5.1 BulkResult

Non-generic frozen dataclass. Returned by all four bulk operations.

| Attribute | Type | Description |
|-----------|------|-------------|
| `success_count` | `int` | Number of items that succeeded |
| `failure_count` | `int` | Number of items that failed |
| `total_count` | `int` | Total items in request (`success_count + failure_count`) |
| `successes` | `tuple[BulkSuccess, ...]` | Successful item details |
| `failures` | `tuple[BulkFailure, ...]` | Failed item details |

**Invariant:** `success_count + failure_count == total_count`

**Validation in `__post_init__`:**
- `success_count >= 0`
- `failure_count >= 0`
- `total_count == success_count + failure_count`
- `len(successes) == success_count`
- `len(failures) == failure_count`

**Convenience:**
- `is_complete_success` property: `failure_count == 0`
- `is_complete_failure` property: `success_count == 0`
- `has_failures` property: `failure_count > 0`

### 5.2 BulkSuccess

Frozen dataclass representing a single successful item.

| Attribute | Type | Description |
|-----------|------|-------------|
| `index` | `int` | 0-based position in input list |
| `entity_id` | `uuid.UUID` | ID of the created/affected transaction |

### 5.3 BulkFailure

Frozen dataclass representing a single failed item.

| Attribute | Type | Description |
|-----------|------|-------------|
| `index` | `int` | 0-based position in input list |
| `entity_id` | `uuid.UUID \| None` | ID of affected entity (if applicable — e.g., not set for create failures) |
| `error_code` | `str` | Machine-readable error code (from domain exception hierarchy) |
| `error_message` | `str` | Human-readable error description |

### 5.4 TransactionInput

Frozen dataclass representing a single item in a bulk create request. Currency is derived from the target account — not specified per item.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `transaction_date` | `date` | Yes | When transaction occurred |
| `amount` | `Decimal` | Yes | Transaction amount (currency from account) |
| `original_description` | `str` | Yes | Original description |
| `value_date` | `date \| None` | No | Settlement date |
| `merchant` | `str \| None` | No | Merchant name |
| `comments` | `str \| None` | No | User notes |
| `review_status` | `ReviewStatus` | No | Default: `TO_REVIEW` |
| `external_id` | `str \| None` | No | External system ID (for dedup) |
| `card_id` | `uuid.UUID \| None` | No | Card reference |

**Validation in `__post_init__`:** Validates string field lengths against domain constants (`MAX_ORIGINAL_DESCRIPTION_LENGTH`, `MAX_MERCHANT_LENGTH`, `MAX_COMMENTS_LENGTH`). Trims whitespace. Raises `InvalidValueError` subclasses on failure.

### 5.5 BulkUpdateFields

Frozen dataclass specifying which fields to update across all targeted transactions. Uses a sentinel pattern to distinguish "don't change" from "clear to None."

| Attribute | Type | Description |
|-----------|------|-------------|
| `review_status` | `ReviewStatus \| _Unset` | Set review status on all (default: `_UNSET`) |
| `user_description` | `str \| None \| _Unset` | Set/clear user description (default: `_UNSET`) |
| `merchant` | `str \| None \| _Unset` | Set/clear merchant (default: `_UNSET`) |

**Sentinel pattern:** A module-level `_UNSET` sentinel (similar to the existing `_SENTINEL` in Transaction.update_dates). When a field is `_UNSET`, it is not applied. When `None`, the field is cleared. When a value, the field is set.

**Validation in `__post_init__`:**
- At least one field must be set (not `_UNSET`) — raises `EmptyBulkUpdateError`
- String fields (when not `_UNSET` and not `None`) validated against domain constants

---

## 6. Commands

All commands are `@dataclass(frozen=True)` extending `Command`.

### 6.1 BulkCreateTransactions

| Attribute | Type | Description |
|-----------|------|-------------|
| `account_id` | `uuid.UUID` | Target account |
| `requesting_user_id` | `uuid.UUID` | User performing the operation |
| `transactions` | `tuple[TransactionInput, ...]` | Items to create |
| `import_source_type` | `str` | Import source type for all items (e.g., `"BULK_IMPORT"`, `"BANK_IMPORT"`) |
| `source_id` | `str \| None` | Optional source identifier (e.g., file name, sync job ID) |

### 6.2 BulkUpdateTransactions

| Attribute | Type | Description |
|-----------|------|-------------|
| `account_id` | `uuid.UUID` | Target account |
| `requesting_user_id` | `uuid.UUID` | User performing the operation |
| `transaction_ids` | `tuple[uuid.UUID, ...]` | Transactions to update |
| `updates` | `BulkUpdateFields` | Fields to apply |

### 6.3 BulkDeleteTransactions

| Attribute | Type | Description |
|-----------|------|-------------|
| `account_id` | `uuid.UUID` | Target account |
| `requesting_user_id` | `uuid.UUID` | User performing the operation |
| `transaction_ids` | `tuple[uuid.UUID, ...]` | Transactions to soft delete |
| `reason` | `str \| None` | Optional deletion reason |

### 6.4 BulkRecoverTransactions

| Attribute | Type | Description |
|-----------|------|-------------|
| `account_id` | `uuid.UUID` | Target account |
| `requesting_user_id` | `uuid.UUID` | User performing the operation |
| `transaction_ids` | `tuple[uuid.UUID, ...]` | Transactions to recover |

---

## 7. Processing Model

### 7.1 Two-Phase Validation

All four operations follow the same two-phase validation strategy:

**Phase 1 — Request-level validation (fail-fast, entire request rejected):**

1. Load account — raises `AccountNotFoundError` if missing
2. Verify account is not deleted — raises `AccountNotActiveError`
3. Verify user has required permission — raises `InsufficientPermissionError`
   - Create, Update, Delete: `PermissionLevel.EDITOR`
   - Recover: `PermissionLevel.OWNER`
4. Verify item count: at least 1 — raises `EmptyBulkRequestError`
5. Verify item count: at most 1000 — raises `BulkLimitExceededError`

**Phase 2 — Per-item validation (partial success):**

For each item at index `i`:
- **Try:** Validate and process the item. Record `BulkSuccess(index=i, entity_id=...)`.
- **Except DomainError:** Record `BulkFailure(index=i, entity_id=..., error_code=e.code, error_message=str(e))`. Continue to next item.

### 7.2 External ID Deduplication (Bulk Create)

When `external_id` is provided on a TransactionInput:

1. **Within-batch check:** Track seen external_ids during processing. If a later item in the batch has an external_id already seen in an earlier item, the later item fails with `DuplicateExternalIdError`.
2. **Against existing:** Check the account's existing transactions via `find_by_external_id()`. If a match exists, the item fails with `DuplicateExternalIdError`.

Both checks apply. First occurrence (within batch or existing) wins.

### 7.3 Split Parent Cascade (Bulk Delete)

When bulk-deleting a split parent:
- Children are cascaded (soft-deleted with same retention and reason), consistent with Spec 010 single-delete behavior.
- Cascaded children are **not** counted in `BulkResult`. Only explicitly requested IDs appear in `successes`/`failures`.

### 7.4 Split Recovery (Bulk Recover)

When bulk-recovering a split child whose parent is still deleted:
- The item fails with `ParentDeletedError` (consistent with Spec 010 single-recover behavior).
- Callers should recover the parent first (which cascades to children).

When bulk-recovering a split parent:
- Deleted children are cascaded (recovered), consistent with Spec 010.
- Cascaded children are **not** counted in `BulkResult`.

### 7.5 Balance Impact

Balance is computed on-demand via `sum_amounts()` (Spec 009). Bulk operations do not perform any explicit balance recalculation. The next `calculate_balance()` call will reflect all changes from the bulk operation.

### 7.6 Event Collection

Each successfully processed item emits its own individual domain event (`TransactionCreated`, `TransactionSoftDeleted`, etc.) via the entity's `_register_event()`. The service collects events from all processed entities after the loop.

After all items are processed, the service emits one aggregate bulk event (Section 8) with summary counts.

---

## 8. Domain Events

All `@dataclass(frozen=True)` extending `DomainEvent` with `aggregate_type: ClassVar[str] = "transaction"`.

### 8.1 TransactionsBulkCreated

| Attribute | Type | Description |
|-----------|------|-------------|
| `account_id` | `uuid.UUID` | Target account |
| `success_count` | `int` | Items created successfully |
| `failure_count` | `int` | Items that failed |
| `import_source_type` | `str` | Import source type for the batch |
| `created_by` | `uuid.UUID` | User who performed the operation |

### 8.2 TransactionsBulkUpdated

| Attribute | Type | Description |
|-----------|------|-------------|
| `account_id` | `uuid.UUID` | Target account |
| `success_count` | `int` | Items updated successfully |
| `failure_count` | `int` | Items that failed |
| `updated_fields` | `frozenset[str]` | Names of fields that were updated |
| `updated_by` | `uuid.UUID` | User who performed the operation |

### 8.3 TransactionsBulkDeleted

| Attribute | Type | Description |
|-----------|------|-------------|
| `account_id` | `uuid.UUID` | Target account |
| `success_count` | `int` | Items deleted successfully |
| `failure_count` | `int` | Items that failed |
| `deleted_by` | `uuid.UUID` | User who performed the operation |

### 8.4 TransactionsBulkRecovered

| Attribute | Type | Description |
|-----------|------|-------------|
| `account_id` | `uuid.UUID` | Target account |
| `success_count` | `int` | Items recovered successfully |
| `failure_count` | `int` | Items that failed |
| `recovered_by` | `uuid.UUID` | User who performed the operation |

---

## 9. Domain Exceptions

### 9.1 New Exceptions

| Exception | Parent | Code | Description |
|-----------|--------|------|-------------|
| `BulkLimitExceededError` | `InvariantViolationError` | `BULK_LIMIT_EXCEEDED` | More than 1000 items in request |
| `EmptyBulkRequestError` | `InvariantViolationError` | `EMPTY_BULK_REQUEST` | Zero items in request |
| `EmptyBulkUpdateError` | `InvalidValueError` | `EMPTY_BULK_UPDATE` | No fields set in BulkUpdateFields (all `_UNSET`) |

### 9.2 Reused Exceptions (Per-Item)

These existing exceptions are caught per-item and recorded as `BulkFailure` entries rather than raised:

| Exception | Code | When |
|-----------|------|------|
| `DuplicateExternalIdError` | `DUPLICATE_EXTERNAL_ID` | external_id already exists in account or earlier in batch |
| `TransactionNotFoundError` | `TRANSACTION_NOT_FOUND` | Transaction ID not found in repository |
| `TransactionDeletedError` | `TRANSACTION_DELETED` | Update/delete attempted on deleted transaction |
| `EmptyDescriptionError` | `EMPTY_DESCRIPTION` | Blank original_description in create |
| `InvalidMerchantError` | `INVALID_MERCHANT` | Merchant validation failure |
| `InvalidCommentsError` | `INVALID_COMMENTS` | Comments validation failure |
| `ParentDeletedError` | `PARENT_DELETED` | Recovering split child whose parent is deleted |
| `AlreadyDeletedError` | `ALREADY_DELETED` | From SoftDeletableMixin — already soft-deleted |
| `NotDeletedError` | `NOT_DELETED` | From SoftDeletableMixin — recovering a non-deleted entity |

---

## 10. Domain Constants

Added to `core_finance/domain/constants.py`:

```python
# Bulk operation limits
MAX_BULK_ITEMS: int = 1000
DEFAULT_BULK_BATCH_SIZE: int = 100  # Advisory for infrastructure layer
```

---

## 11. Application Service

### 11.1 BulkTransactionService

A new application service in `core_finance/application/services/`. Depends on:
- `AbstractCoreFinanceUnitOfWork`
- `RetentionPolicyService` (for soft-delete retention calculation)

This is a **separate service** from `TransactionManagementService` to keep single-item and bulk-item concerns cleanly separated. It reuses the same UoW, repository, and domain entities.

### 11.2 Methods

#### `bulk_create_transactions(cmd: BulkCreateTransactions) -> BulkResult`

1. **Phase 1:** Load account, verify EDITOR permission, verify count bounds
2. Build `ImportSource` from `cmd.import_source_type` + `cmd.source_id`
3. Track seen `external_id` set for within-batch dedup
4. **Phase 2:** For each `TransactionInput` at index `i`:
   - Check within-batch external_id duplicate
   - Check existing external_id via `repo.find_by_external_id()`
   - Create `Money(input.amount, account.currency)`
   - Create `Transaction.create(...)` with `created_by=cmd.requesting_user_id`
   - Save via `repo.save(transaction)`
   - Record success or catch `DomainError` and record failure
5. Commit UoW
6. Emit `TransactionsBulkCreated` event
7. Return `BulkResult`

#### `bulk_update_transactions(cmd: BulkUpdateTransactions) -> BulkResult`

1. **Phase 1:** Load account, verify EDITOR permission, verify count bounds
2. **Phase 2:** For each `transaction_id` at index `i`:
   - Load transaction via `repo.find_by_id()`
   - Verify not deleted
   - Apply each non-`_UNSET` field:
     - `review_status`: call `mark_as_reviewed()` or `mark_for_review()`
     - `user_description`: call `update_description()`
     - `merchant`: call `update_merchant()`
   - Save via `repo.save(transaction)`
   - Record success or catch `DomainError` and record failure
3. Commit UoW
4. Emit `TransactionsBulkUpdated` event (with `updated_fields` from non-`_UNSET` field names)
5. Return `BulkResult`

#### `bulk_delete_transactions(cmd: BulkDeleteTransactions) -> BulkResult`

1. **Phase 1:** Load account, verify EDITOR permission, verify count bounds
2. Get effective retention via `RetentionPolicyService`
3. **Phase 2:** For each `transaction_id` at index `i`:
   - Load transaction via `repo.find_by_id()`
   - Verify not already deleted
   - If split parent: cascade soft-delete to children (load via `repo.find_children()`)
   - Call `transaction.soft_delete(deleted_by, retention, reason)`
   - Save transaction (and children if cascaded)
   - Record success or catch `DomainError` and record failure
   - **Cascaded children do NOT appear in BulkResult**
4. Commit UoW
5. Emit `TransactionsBulkDeleted` event
6. Return `BulkResult`

#### `bulk_recover_transactions(cmd: BulkRecoverTransactions) -> BulkResult`

1. **Phase 1:** Load account, verify OWNER permission, verify count bounds, verify account not deleted
2. **Phase 2:** For each `transaction_id` at index `i`:
   - Load transaction via `repo.find_by_id(include_deleted=True)`
   - Verify is deleted
   - If split child: verify parent is not deleted (raises `ParentDeletedError`)
   - If split parent: cascade recover to deleted children
   - Call `transaction.recover()`
   - Save transaction (and children if cascaded)
   - Record success or catch `DomainError` and record failure
   - **Cascaded children do NOT appear in BulkResult**
3. Commit UoW
4. Emit `TransactionsBulkRecovered` event
5. Return `BulkResult`

---

## 12. Acceptance Criteria

### Request Validation

- [ ] Account must exist — raises `AccountNotFoundError` for entire batch
- [ ] Account must not be deleted — raises `AccountNotActiveError` for entire batch
- [ ] User must have required permission (EDITOR for create/update/delete, OWNER for recover) — raises `InsufficientPermissionError`
- [ ] At least 1 item required — raises `EmptyBulkRequestError`
- [ ] Maximum 1000 items — raises `BulkLimitExceededError`

### Partial Success Semantics

- [ ] Valid items succeed even when other items in the batch fail
- [ ] Each failed item reported with `index`, `error_code`, `error_message`
- [ ] Each successful item reported with `index` and `entity_id`
- [ ] `BulkResult.total_count == success_count + failure_count`
- [ ] `BulkResult.is_complete_success` is `True` when all items succeed
- [ ] `BulkResult.has_failures` is `True` when any item fails

### Bulk Create

- [ ] Creates up to 1000 transactions in a single request
- [ ] Currency derived from account — not specified per item
- [ ] `ImportSource` built from request-level `import_source_type` + `source_id`
- [ ] Each transaction validates independently (description required, string limits, etc.)
- [ ] External ID dedup: within-batch (later occurrence fails) AND against existing account transactions
- [ ] Created transactions default to `review_status = TO_REVIEW` (unless overridden in input)
- [ ] Individual `TransactionCreated` events emitted per successful item
- [ ] `TransactionsBulkCreated` aggregate event emitted with counts
- [ ] `created_by` set to `requesting_user_id` for all items

### Bulk Update

- [ ] Updates `review_status`, `user_description`, and/or `merchant` across multiple transactions
- [ ] Sentinel pattern: `_UNSET` means "don't change", `None` means "clear field"
- [ ] At least one field must be non-`_UNSET` — raises `EmptyBulkUpdateError` on BulkUpdateFields construction
- [ ] Non-existent transaction IDs fail individually with `TransactionNotFoundError`
- [ ] Deleted transactions fail individually with `TransactionDeletedError`
- [ ] Individual `TransactionUpdated`/`TransactionReviewed` events emitted per successful item
- [ ] `TransactionsBulkUpdated` aggregate event emitted with `updated_fields`

### Bulk Delete

- [ ] Soft deletes multiple transactions in a single request
- [ ] Already-deleted transactions fail individually with `AlreadyDeletedError`
- [ ] Non-existent transactions fail individually with `TransactionNotFoundError`
- [ ] Split parent cascade: children soft-deleted as side-effect (not in BulkResult)
- [ ] Retention period obtained from `RetentionPolicyService`
- [ ] Individual `TransactionSoftDeleted` events emitted per successful item
- [ ] `TransactionsBulkDeleted` aggregate event emitted with counts

### Bulk Recover

- [ ] Recovers multiple soft-deleted transactions in a single request
- [ ] Requires OWNER permission (stricter than delete)
- [ ] Account must not be deleted — raises `ParentAccountDeletedError`
- [ ] Non-deleted transactions fail individually with `NotDeletedError`
- [ ] Non-existent transactions fail individually with `TransactionNotFoundError`
- [ ] Split child with deleted parent fails with `ParentDeletedError`
- [ ] Split parent cascade: deleted children recovered as side-effect (not in BulkResult)
- [ ] Individual `TransactionRecovered` events emitted per successful item
- [ ] `TransactionsBulkRecovered` aggregate event emitted with counts

---

## 13. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Empty transactions list | `EmptyBulkRequestError` (Phase 1 fail-fast) |
| 1001 items | `BulkLimitExceededError` (Phase 1 fail-fast) |
| All items invalid | `BulkResult(success_count=0, failure_count=N)` — not a request-level error |
| All items valid | `BulkResult(success_count=N, failure_count=0)` |
| Mixed valid/invalid | Valid items succeed, invalid items in `failures` list |
| Duplicate external_id within batch | First occurrence succeeds, subsequent fail with `DUPLICATE_EXTERNAL_ID` |
| Duplicate external_id against existing | Item fails with `DUPLICATE_EXTERNAL_ID` |
| Bulk delete split parent | Parent deleted, children cascade-deleted (not in result) |
| Bulk recover split child (parent deleted) | Fails with `PARENT_DELETED` |
| Bulk recover split parent | Parent recovered, children cascade-recovered (not in result) |
| Bulk update with all `_UNSET` fields | `EmptyBulkUpdateError` on BulkUpdateFields construction |
| Bulk update deleted transaction | Fails with `TRANSACTION_DELETED` |
| Bulk delete already-deleted transaction | Fails with `ALREADY_DELETED` |
| Bulk recover non-deleted transaction | Fails with `NOT_DELETED` |
| Deleted account | `AccountNotActiveError` (Phase 1 fail-fast) |
| User lacks permission | `InsufficientPermissionError` (Phase 1 fail-fast) |

---

## 14. Dependencies

### Internal Dependencies

- **Spec 009 (Transaction Management):** Transaction entity, domain events, exceptions, repository protocol
- **Spec 010 (Transaction Splitting):** Split parent/child cascade behavior for delete and recover
- **Spec 008 (Account Sharing):** Permission verification via `Account.has_permission()`
- **Spec 007 (Account Management):** Account aggregate, `AccountRepository`
- **Spec 006 (Data Lifecycle):** `RetentionPolicyService`, `RetentionPeriod`, `SoftDeletableMixin`
- **Spec 001 (Shared Kernel):** `DomainEvent`, `Command`, `DomainError` hierarchy, `Money`

### Consumed By

- **Spec 015 (Bank Connections & Sync):** Will use `BulkCreateTransactions` with `import_source_type="BANK_IMPORT"` for batch import

---

## 15. Constraints

- Domain and application layer only — no infrastructure/API layer
- Python 3.13+ with `uv` tooling
- Follows existing DDD patterns: frozen dataclasses, Protocol-based ports, cooperative mixins
- No new repository methods required — existing `TransactionRepository` already has `save()`, `save_many()`, `find_by_id()`, `find_by_external_id()`, `find_children()`

---

## 16. Glossary

- **Bulk operation:** A single request that processes multiple items with per-item error reporting
- **Partial success:** Processing model where valid items succeed even when others fail
- **Phase 1 validation:** Request-level checks that reject the entire batch on failure
- **Phase 2 validation:** Per-item checks where failures are recorded individually
- **Sentinel (`_UNSET`):** A value indicating "this field was not provided" (distinct from `None`)
- **Cascade:** Automatic application of an operation to related entities (e.g., split children)
