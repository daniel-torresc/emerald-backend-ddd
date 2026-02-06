# Spec 012: Bulk Transaction Operations

**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 009 (Transaction Management)
**Blocks:** None

---

## 1. Overview

This spec defines bulk operations on transactions — creating, updating, deleting, and recovering multiple transactions in a single request. Bulk operations enable efficient data entry, batch imports, and mass management of transactions while providing per-item error reporting so that partial failures don't block the entire batch.

**Key Principle:** Bulk operations are partial-success tolerant. Each item in a batch is validated independently. Valid items succeed even when others fail. Detailed per-item error reporting enables callers to fix and retry only the failed items.

## 2. Scope

### In Scope

- Bulk create (up to 1000 transactions)
- Bulk update (review status, category)
- Bulk soft delete
- Bulk recover
- Per-item validation and error reporting
- Batch processing with configurable batch size
- `BulkResult` response structure

### Out of Scope

- Bulk splitting (not specified in requirements)
- Bank import ingestion (Spec 015 — uses bulk create internally)
- Bulk card operations (not specified)

## 3. Request and Result Types

### 3.1 Bulk Create

**BulkTransactionCreateRequest:**

| Attribute | Type | Description |
|-----------|------|-------------|
| account_id | UUID | Target account for all transactions |
| transactions | list[TransactionInput] | Items to create (max 1000) |

**TransactionInput:**

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| transaction_date | date | Yes | When transaction occurred |
| value_date | date? | No | Settlement date |
| amount | Decimal | Yes | Transaction amount |
| description | str | Yes | Original description |
| merchant | str? | No | Merchant name |
| comments | str? | No | User notes |
| review_status | ReviewStatus | No | Default: TO_REVIEW |
| external_id | str? | No | External system ID (for dedup) |
| card_id | UUID? | No | Card reference |

### 3.2 Bulk Update

**BulkTransactionUpdateRequest:**

| Attribute | Type | Description |
|-----------|------|-------------|
| account_id | UUID | Target account |
| transaction_ids | list[UUID] | Transactions to update (max 1000) |
| updates | BulkUpdateFields | Fields to apply to all |

**BulkUpdateFields:**

| Attribute | Type | Description |
|-----------|------|-------------|
| review_status | ReviewStatus? | Set review status on all |
| user_description | str? | Set description on all |
| merchant | str? | Set merchant on all |

**Note:** Only fields that make sense to apply uniformly across many transactions are supported for bulk update. Per-transaction field updates use the single update endpoint (Spec 009).

### 3.3 Bulk Delete

**BulkTransactionDeleteRequest:**

| Attribute | Type | Description |
|-----------|------|-------------|
| account_id | UUID | Target account |
| transaction_ids | list[UUID] | Transactions to soft delete (max 1000) |
| reason | str? | Optional deletion reason |

### 3.4 Bulk Recover

**BulkTransactionRecoverRequest:**

| Attribute | Type | Description |
|-----------|------|-------------|
| account_id | UUID | Target account |
| transaction_ids | list[UUID] | Transactions to recover (max 1000) |

### 3.5 BulkResult

All bulk operations return the same result structure:

**BulkResult:**

| Attribute | Type | Description |
|-----------|------|-------------|
| success_count | int | Number of items that succeeded |
| failure_count | int | Number of items that failed |
| total_count | int | Total items in request |
| successes | list[BulkSuccess] | Details of successful items |
| failures | list[BulkFailure] | Details of failed items |

**BulkSuccess:**

| Attribute | Type | Description |
|-----------|------|-------------|
| index | int | Position in input list |
| entity_id | UUID | ID of created/affected entity |

**BulkFailure:**

| Attribute | Type | Description |
|-----------|------|-------------|
| index | int | Position in input list |
| entity_id | UUID? | ID of affected entity (if applicable) |
| error_code | str | Machine-readable error code |
| error_message | str | Human-readable description |

## 4. Processing Model

### 4.1 Validation Strategy

Bulk operations use a **two-phase validation** approach:

```
Phase 1 — Request-level validation (fail-fast):
  1. Account exists and is active
     Raises: AccountNotActiveError (entire request fails)
  2. Requesting user has required permission
     Raises: InsufficientPermissionError (entire request fails)
  3. Item count within limit (max 1000)
     Raises: BulkLimitExceededError (entire request fails)

Phase 2 — Per-item validation (partial success):
  For each item:
    Try:
      Validate item (currency match, format, dedup, etc.)
      Process item
      Record success
    Except DomainError:
      Record failure with error details
      Continue to next item
```

**Key Rule:** Request-level validation failures reject the entire batch. Per-item validation failures are recorded individually, and valid items still succeed.

### 4.2 Batch Processing

Large batches are processed in configurable chunks:

| Setting | Default | Description |
|---------|---------|-------------|
| batch_size | 100 | Items processed per batch |
| max_items | 1000 | Maximum items per request |

```
Processing flow:
  items = request.transactions  # up to 1000
  results = []

  for batch in chunk(items, batch_size=100):
      for item in batch:
          result = process_single(item)
          results.append(result)
      # Persist batch (application layer transaction boundary)

  return aggregate_results(results)
```

**Transaction Boundaries:**

- Each batch of 100 items is persisted in a single database transaction
- If a batch fails at the infrastructure level, the entire batch is retried or reported
- Per-item domain validation failures do not affect other items in the same batch

### 4.3 Balance Recalculation

Balance is recalculated **once** after the entire bulk operation completes, not after each individual item. This is a performance optimization.

```
Bulk create 500 transactions:
  1. Process all 500 items (per-item validation)
  2. Persist in batches of 100
  3. Recalculate balance ONCE at the end
  4. Return BulkResult
```

## 5. Bulk Create Flow

```
Bulk create request (account_id, transactions[]):
     │
     ▼
Phase 1 — Request validation:
  1. Load account, verify active
  2. Verify user has EDITOR permission
  3. Verify count <= 1000
     │
     ▼
Phase 2 — Per-item processing:
  For each TransactionInput at index i:
     │
     ├── Create Money(amount, account.currency)
     │   Fail? → record failure (invalid amount)
     │
     ├── Create Transaction entity
     │   Fail? → record failure (validation error)
     │
     ├── account.add_transaction(transaction)
     │   Fail? → record failure (currency mismatch, duplicate external_id)
     │
     └── Success → record BulkSuccess(index, transaction_id)
     │
     ▼
Aggregate and return BulkResult
Emit TransactionsBulkCreated event (with success/failure counts)
```

## 6. Bulk Update Flow

```
Bulk update request (account_id, transaction_ids[], updates):
     │
     ▼
Phase 1 — Request validation:
  1. Load account, verify active
  2. Verify user has EDITOR permission
  3. Verify count <= 1000
     │
     ▼
Phase 2 — Per-item processing:
  For each transaction_id at index i:
     │
     ├── Find transaction in account
     │   Not found? → record failure (TransactionNotFoundError)
     │
     ├── Verify transaction is active (not deleted)
     │   Deleted? → record failure (TransactionDeletedError)
     │
     ├── Apply updates to transaction
     │   Fail? → record failure (validation error)
     │
     └── Success → record BulkSuccess(index, transaction_id)
     │
     ▼
Aggregate and return BulkResult
Emit TransactionsBulkUpdated event
```

## 7. Bulk Delete Flow

```
Bulk delete request (account_id, transaction_ids[], reason?):
     │
     ▼
Phase 1 — Request validation:
  1. Load account, verify active
  2. Verify user has EDITOR permission
  3. Verify count <= 1000
     │
     ▼
Phase 2 — Per-item processing:
  For each transaction_id at index i:
     │
     ├── Find transaction in account
     │   Not found? → record failure
     │
     ├── Verify transaction is active
     │   Already deleted? → record failure (AlreadyDeletedError)
     │
     ├── transaction.soft_delete(deleted_by, reason)
     │   Note: If split parent, cascade to children
     │
     └── Success → record BulkSuccess(index, transaction_id)
     │
     ▼
Recalculate balance once
Aggregate and return BulkResult
Emit TransactionsBulkDeleted event
```

## 8. Bulk Recover Flow

```
Bulk recover request (account_id, transaction_ids[]):
     │
     ▼
Phase 1 — Request validation:
  1. Load account, verify active
  2. Verify user has OWNER permission (recovery requires OWNER)
  3. Verify count <= 1000
     │
     ▼
Phase 2 — Per-item processing:
  For each transaction_id at index i:
     │
     ├── Find transaction in account (include deleted)
     │   Not found? → record failure
     │
     ├── Verify transaction is deleted
     │   Not deleted? → record failure (NotDeletedError)
     │
     ├── transaction.recover()
     │   Note: Split transactions recover together (Spec 010)
     │
     └── Success → record BulkSuccess(index, transaction_id)
     │
     ▼
Recalculate balance once
Aggregate and return BulkResult
Emit TransactionsBulkRecovered event
```

## 9. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `TransactionsBulkCreated` | Bulk create completes | account_id, success_count, failure_count, import_source? |
| `TransactionsBulkUpdated` | Bulk update completes | account_id, success_count, failure_count, updated_fields |
| `TransactionsBulkDeleted` | Bulk delete completes | account_id, success_count, failure_count |
| `TransactionsBulkRecovered` | Bulk recover completes | account_id, success_count, failure_count |

**Note:** Individual `TransactionCreated`, `TransactionSoftDeleted`, etc. events are still emitted per item. The bulk events are aggregate summaries for notification and audit purposes.

## 10. Domain Errors

| Error | Trigger | Description |
|-------|---------|-------------|
| `BulkLimitExceededError` | More than 1000 items | Maximum batch size exceeded |
| `EmptyBulkRequestError` | Zero items in request | At least one item required |

All per-item errors reuse existing domain errors from Spec 009 (`CurrencyMismatchError`, `DuplicateExternalIdError`, `TransactionNotFoundError`, etc.) — they are captured in `BulkFailure` rather than raised.

## 11. Acceptance Criteria

### Request Validation

- [ ] Account must exist and be active — raises `AccountNotActiveError` for entire batch
- [ ] User must have required permission (EDITOR for create/update/delete, OWNER for recover)
- [ ] Maximum 1000 items per request — raises `BulkLimitExceededError`
- [ ] At least 1 item required — raises `EmptyBulkRequestError`

### Partial Success

- [ ] Valid items succeed even when other items in the batch fail
- [ ] Each failed item is reported with index, error_code, and error_message
- [ ] Each successful item is reported with index and entity_id
- [ ] `BulkResult` accurately reports success_count + failure_count = total_count

### Bulk Create

- [ ] Creates up to 1000 transactions in a single request
- [ ] Each transaction validates independently (currency match, description required, dedup)
- [ ] Transactions with duplicate `external_id` fail individually (not entire batch)
- [ ] Created transactions default to `review_status = TO_REVIEW`
- [ ] Balance recalculated once after all items processed
- [ ] `TransactionsBulkCreated` event emitted with counts
- [ ] Individual `TransactionCreated` events emitted per successful item

### Bulk Update

- [ ] Updates review_status, user_description, or merchant across multiple transactions
- [ ] Non-existent transaction IDs fail individually
- [ ] Deleted transactions fail individually
- [ ] `TransactionsBulkUpdated` event emitted

### Bulk Delete

- [ ] Soft deletes multiple transactions in a single request
- [ ] Already-deleted transactions fail individually
- [ ] Split parent cascade applies (children also deleted)
- [ ] Balance recalculated once after all deletes
- [ ] `TransactionsBulkDeleted` event emitted

### Bulk Recover

- [ ] Recovers multiple transactions from trash in a single request
- [ ] Requires OWNER permission (stricter than delete)
- [ ] Non-deleted transactions fail individually
- [ ] Split transaction recovery rules apply (Spec 010)
- [ ] Balance recalculated once after all recoveries
- [ ] `TransactionsBulkRecovered` event emitted

### Performance

- [ ] Processing in batches of 100 (configurable)
- [ ] Balance recalculated once per bulk operation, not per item
- [ ] 1000 transactions bulk create completes within 30 seconds
