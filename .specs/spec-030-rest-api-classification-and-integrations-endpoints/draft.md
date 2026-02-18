# Spec 030: REST API — Classification & Integrations Endpoints

**Status:** Draft
**Bounded Context:** Classification + Integrations (Presentation)
**Dependencies:** 027 (API Middleware & Common HTTP), 013 (Classification & Taxonomies), 014 (Transaction Categorization), 015 (Bank Connections & Sync), 006 (Data Lifecycle Management)
**Blocks:** 031

---

## 1. Overview

This spec defines HTTP routes for taxonomies, transaction categorization, bank connections, sync management, pending transaction review, and the trash/lifecycle management endpoints.

**Key Principle:** Taxonomies are user-owned (ownership verified by owner_id match). Bank connections are user-owned. Categorization requires EDITOR+ on the transaction's account. Trash endpoints aggregate soft-deleted items across contexts.

## 2. Scope

### In Scope

- Taxonomy CRUD and term management routes
- Transaction categorization routes
- Bank connection management routes
- Sync trigger and history routes
- Pending transaction review routes
- Trash listing and cascade summary routes

### Out of Scope

- System taxonomy management (admin feature — future)
- Automated categorization rules (future enhancement)
- Webhook-based sync (future enhancement)

## 3. Taxonomy Routes

### 3.1 Create Taxonomy

```
POST /api/v1/taxonomies

Request Body:
{
    "name": "Expense Categories",
    "description": "Personal expense tracking"    // optional
}

Response 201:
{
    "taxonomy_id": "uuid",
    "name": "Expense Categories",
    "description": "Personal expense tracking",
    "owner_id": "uuid",
    "is_system": false,
    "terms": [],
    "created_at": "..."
}

Errors:
    400 — Invalid name
    409 — Taxonomy name already exists for user
```

**Auth:** Bearer token required
**Service:** `TaxonomyManagementService.create_taxonomy()`

### 3.2 List Taxonomies

```
GET /api/v1/taxonomies

Query Params:
    include_deleted: bool = false

Response 200:
{
    "items": [
        {
            "taxonomy_id": "uuid",
            "name": "Expense Categories",
            "term_count": 15,
            "is_system": false,
            ...
        }
    ]
}
```

**Auth:** Bearer token required (returns user's taxonomies + system taxonomies)

### 3.3 Get Taxonomy

```
GET /api/v1/taxonomies/{taxonomy_id}

Response 200:
{
    "taxonomy_id": "uuid",
    "name": "Expense Categories",
    "terms": [
        {
            "term_id": "uuid",
            "name": "Food",
            "parent_id": null,
            "sort_order": 0,
            "children": [
                { "term_id": "uuid", "name": "Groceries", "parent_id": "uuid", "sort_order": 0 },
                { "term_id": "uuid", "name": "Restaurants", "parent_id": "uuid", "sort_order": 1 }
            ]
        }
    ],
    ...
}
```

**Auth:** Bearer token required (owner or system taxonomy)
**Note:** Terms returned as nested tree structure.

### 3.4 Update Taxonomy

```
PATCH /api/v1/taxonomies/{taxonomy_id}

Request Body:
{
    "name": "Updated Name",
    "description": "Updated description"
}

Response 200: { ... updated taxonomy ... }

Errors:
    403 — Not owner
    409 — Name already exists
```

**Auth:** Bearer token required (owner only)

### 3.5 Delete Taxonomy

```
DELETE /api/v1/taxonomies/{taxonomy_id}

Response 204: (no content)

Errors:
    403 — Not owner
    409 — Already deleted
```

**Auth:** Bearer token required (owner only)

### 3.6 Recover Taxonomy

```
POST /api/v1/taxonomies/{taxonomy_id}/recover

Response 200: { ... recovered taxonomy ... }
```

**Auth:** Bearer token required (owner only)

## 4. Term Management Routes

### 4.1 Add Term

```
POST /api/v1/taxonomies/{taxonomy_id}/terms

Request Body:
{
    "name": "Groceries",
    "description": "Grocery shopping",    // optional
    "parent_id": "uuid"                   // optional (null = root)
}

Response 201: { ... term ... }

Errors:
    400 — Invalid name
    404 — Parent term not found
    409 — Term name already exists in taxonomy
```

**Auth:** Bearer token required (taxonomy owner)

### 4.2 Rename Term

```
PATCH /api/v1/taxonomies/{taxonomy_id}/terms/{term_id}

Request Body:
{
    "name": "Updated Name",
    "description": "Updated description"
}

Response 200: { ... updated term ... }
```

**Auth:** Bearer token required (taxonomy owner)

### 4.3 Move Term

```
POST /api/v1/taxonomies/{taxonomy_id}/terms/{term_id}/move

Request Body:
{
    "new_parent_id": "uuid"    // null = move to root
}

Response 200: { ... moved term ... }

Errors:
    409 — Would create cycle
```

**Auth:** Bearer token required (taxonomy owner)

### 4.4 Reorder Terms

```
POST /api/v1/taxonomies/{taxonomy_id}/terms/reorder

Request Body:
{
    "term_orders": [
        { "term_id": "uuid", "sort_order": 0 },
        { "term_id": "uuid", "sort_order": 1 }
    ]
}

Response 200: { "message": "Terms reordered successfully." }
```

**Auth:** Bearer token required (taxonomy owner)

### 4.5 Delete Term

```
DELETE /api/v1/taxonomies/{taxonomy_id}/terms/{term_id}

Response 204: (no content)

Errors:
    409 — Already deleted
```

**Auth:** Bearer token required (taxonomy owner)
**Note:** Cascades to descendant terms.

### 4.6 Recover Term

```
POST /api/v1/taxonomies/{taxonomy_id}/terms/{term_id}/recover

Response 200: { ... recovered term ... }
```

**Auth:** Bearer token required (taxonomy owner)

## 5. Categorization Routes

### 5.1 Assign Category

```
POST /api/v1/transactions/{transaction_id}/categories

Request Body:
{
    "term_id": "uuid"
}

Response 201:
{
    "assignment_id": "uuid",
    "transaction_id": "uuid",
    "term_id": "uuid",
    "taxonomy_id": "uuid",
    "taxonomy_name": "Expense Categories",
    "term_name": "Groceries",
    "assigned_at": "..."
}

Errors:
    403 — Not EDITOR+ on transaction's account
    404 — Transaction or term not found
    409 — Already assigned in this taxonomy (will reassign)
```

**Auth:** Bearer token required (EDITOR+ on account)
**Service:** `TransactionCategorizationService.assign_term()`
**Note:** If transaction already has assignment in the same taxonomy, it's replaced (reassignment).

### 5.2 Remove Category

```
DELETE /api/v1/transactions/{transaction_id}/categories/{assignment_id}

Response 204: (no content)

Errors:
    403 — Not EDITOR+ on account
    404 — Assignment not found
```

**Auth:** Bearer token required (EDITOR+ on account)

### 5.3 List Transaction Categories

```
GET /api/v1/transactions/{transaction_id}/categories

Response 200:
{
    "items": [
        {
            "assignment_id": "uuid",
            "taxonomy_id": "uuid",
            "taxonomy_name": "Expense Categories",
            "term_id": "uuid",
            "term_name": "Groceries",
            "term_path": "Food > Groceries",
            "assigned_at": "..."
        }
    ]
}
```

**Auth:** Bearer token required (VIEWER+ on account)

## 6. Bank Connection Routes

### 6.1 Initiate Connection

```
POST /api/v1/bank-connections

Request Body:
{
    "account_id": "uuid",
    "provider": "PLAID",
    "institution_id": "uuid",
    "external_account_id": "ext-acc-123"
}

Response 201:
{
    "connection_id": "uuid",
    "status": "PENDING",
    "provider": "PLAID",
    "account_id": "uuid",
    ...
}

Errors:
    403 — Not OWNER of account
    409 — Connection already exists for account+provider
```

**Auth:** Bearer token required (OWNER of target account)
**Service:** `BankConnectionService.initiate_connection()`

### 6.2 Activate Connection

```
POST /api/v1/bank-connections/{connection_id}/activate

Request Body:
{
    "access_token": "provider-access-token"
}

Response 200:
{
    "connection_id": "uuid",
    "status": "ACTIVE",
    ...
}

Errors:
    409 — Invalid state (not PENDING or NEEDS_REAUTH)
```

**Auth:** Bearer token required (connection owner)

### 6.3 List Connections

```
GET /api/v1/bank-connections

Query Params:
    account_id: uuid = None    // filter by account
    include_deleted: bool = false

Response 200:
{
    "items": [
        {
            "connection_id": "uuid",
            "account_id": "uuid",
            "provider": "PLAID",
            "status": "ACTIVE",
            "last_sync_at": "...",
            "next_sync_scheduled_at": "...",
            ...
        }
    ]
}
```

**Auth:** Bearer token required (returns user's connections only)

### 6.4 Get Connection

```
GET /api/v1/bank-connections/{connection_id}

Response 200: { ... connection details ... }

Errors:
    403 — Not connection owner
    404 — Not found
```

**Auth:** Bearer token required (connection owner)

### 6.5 Disconnect

```
POST /api/v1/bank-connections/{connection_id}/disconnect

Response 200:
{
    "connection_id": "uuid",
    "status": "DISCONNECTED"
}

Errors:
    403 — Not connection owner
```

**Auth:** Bearer token required (connection owner)

### 6.6 Reconnect

```
POST /api/v1/bank-connections/{connection_id}/reconnect

Request Body:
{
    "access_token": "new-provider-token"
}

Response 200:
{
    "connection_id": "uuid",
    "status": "ACTIVE"
}

Errors:
    409 — Invalid state (not NEEDS_REAUTH or ERROR)
```

**Auth:** Bearer token required (connection owner)

### 6.7 Update Sync Frequency

```
PATCH /api/v1/bank-connections/{connection_id}

Request Body:
{
    "sync_frequency_hours": 12
}

Response 200: { ... updated connection ... }

Errors:
    400 — Frequency outside 1-24 hour range
```

**Auth:** Bearer token required (connection owner)

### 6.8 Delete Connection

```
DELETE /api/v1/bank-connections/{connection_id}

Response 204: (no content)
```

**Auth:** Bearer token required (connection owner)

## 7. Sync Routes

### 7.1 Trigger Sync

```
POST /api/v1/bank-connections/{connection_id}/sync

Response 202:
{
    "sync_id": "uuid",
    "status": "IN_PROGRESS",
    "started_at": "..."
}

Errors:
    409 — Connection not ACTIVE
    409 — Sync already in progress
```

**Auth:** Bearer token required (connection owner)
**Service:** `BankSyncService.trigger_sync()`

### 7.2 Get Sync History

```
GET /api/v1/bank-connections/{connection_id}/sync-history

Query Params:
    limit: int = 10

Response 200:
{
    "items": [
        {
            "sync_id": "uuid",
            "status": "SUCCESS",
            "started_at": "...",
            "completed_at": "...",
            "transactions_found": 25,
            "transactions_imported": 20,
            "transactions_duplicate": 5,
            ...
        }
    ]
}
```

**Auth:** Bearer token required (connection owner)

## 8. Pending Transaction Routes

### 8.1 List Pending Transactions

```
GET /api/v1/bank-connections/{connection_id}/pending

Query Params:
    status: "NEEDS_REVIEW" | "NEW" | "all" = "NEEDS_REVIEW"

Response 200:
{
    "items": [
        {
            "pending_id": "uuid",
            "external_id": "ext-tx-123",
            "match_status": "NEEDS_REVIEW",
            "normalized_data": {
                "transaction_date": "2024-01-15",
                "amount": "-45.99",
                "currency": "EUR",
                "description": "GROCERY STORE",
                "merchant": "Whole Foods"
            },
            "matched_transaction_id": "uuid",
            "created_at": "..."
        }
    ]
}
```

**Auth:** Bearer token required (connection owner)

### 8.2 Approve Pending Transaction

```
POST /api/v1/bank-connections/{connection_id}/pending/{pending_id}/approve

Response 200:
{
    "pending_id": "uuid",
    "match_status": "USER_APPROVED",
    "created_transaction_id": "uuid"
}
```

**Auth:** Bearer token required (connection owner)

### 8.3 Reject Pending Transaction

```
POST /api/v1/bank-connections/{connection_id}/pending/{pending_id}/reject

Response 200:
{
    "pending_id": "uuid",
    "match_status": "USER_REJECTED"
}
```

**Auth:** Bearer token required (connection owner)

## 9. Trash Routes

### 9.1 List Trash Items

```
GET /api/v1/trash

Query Params:
    entity_type: str = None    // filter by type (ACCOUNT, TRANSACTION, etc.)
    page: int = 1
    page_size: int = 20

Response 200:
{
    "items": [
        {
            "entity_type": "ACCOUNT",
            "entity_id": "uuid",
            "name": "Old Savings Account",
            "deleted_at": "...",
            "deleted_by": "uuid",
            "scheduled_hard_delete_at": "...",
            "days_until_permanent_deletion": 25
        }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
}
```

**Auth:** Bearer token required (returns user's trash items only)
**Service:** `TrashQueryPort.find_trash_items()`

### 9.2 Get Cascade Summary

```
GET /api/v1/trash/{entity_type}/{entity_id}/cascade

Response 200:
{
    "entity_type": "ACCOUNT",
    "entity_id": "uuid",
    "children": {
        "transactions": 45,
        "cards": 3,
        "shares": 2,
        "bank_connections": 1
    },
    "total_affected": 51
}
```

**Auth:** Bearer token required
**Service:** `TrashQueryPort.get_cascade_summary()`

## 10. File Structure

```
src/emerald/infrastructure/api/
    routers/
        taxonomies.py           # Taxonomy CRUD + term management
        categorization.py       # Transaction categorization
        bank_connections.py     # Bank connection management
        sync.py                 # Sync trigger + history
        pending_transactions.py # Pending review
        trash.py                # Trash listing + cascade
    schemas/
        classification.py       # Classification schemas
        integrations.py         # Integrations schemas
        lifecycle.py            # Trash/lifecycle schemas
```

## 11. Acceptance Criteria

### Taxonomy Routes

- [ ] CRUD operations for taxonomies with ownership verification
- [ ] Term add/rename/move/delete/recover/reorder work correctly
- [ ] Terms returned as nested tree structure in GET
- [ ] Cycle detection prevents invalid moves (409)
- [ ] Term name uniqueness enforced within taxonomy
- [ ] Cascading soft-delete for taxonomy → terms and term → descendants

### Categorization Routes

- [ ] Assign requires EDITOR+ on transaction's account
- [ ] One assignment per taxonomy — reassignment replaces existing
- [ ] Remove requires EDITOR+ on account
- [ ] List includes taxonomy name and term path for display

### Bank Connection Routes

- [ ] Initiate requires OWNER of target account
- [ ] One connection per account per provider
- [ ] Activate transitions PENDING → ACTIVE
- [ ] Disconnect transitions to DISCONNECTED, soft-deletes pending
- [ ] Reconnect works from NEEDS_REAUTH or ERROR
- [ ] Delete soft-deletes connection

### Sync Routes

- [ ] Trigger sync returns 202 Accepted
- [ ] Only ACTIVE connections can sync
- [ ] Sync history ordered by most recent
- [ ] History includes import counts

### Pending Transaction Routes

- [ ] List shows NEEDS_REVIEW items by default
- [ ] Approve creates real transaction, returns transaction ID
- [ ] Reject marks as USER_REJECTED, no transaction created
- [ ] Only connection owner can review pending transactions

### Trash Routes

- [ ] Lists soft-deleted items across all contexts for current user
- [ ] Filterable by entity type
- [ ] Paginated results
- [ ] Cascade summary shows affected children count
- [ ] Days until permanent deletion calculated correctly
