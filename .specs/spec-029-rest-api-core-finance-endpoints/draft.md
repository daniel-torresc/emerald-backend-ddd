# Spec 029: REST API — Core Finance Endpoints

**Status:** Draft
**Bounded Context:** Core Finance (Presentation)
**Dependencies:** 027 (API Middleware & Common HTTP), 007-012 (Core Finance domain specs)
**Blocks:** 031

---

## 1. Overview

This spec defines all Core Finance HTTP routes — accounts, sharing, transactions (including splits and bulk), and cards. These endpoints are the most data-intensive in the platform.

**Key Principle:** Permission checks are embedded in every endpoint. Account access requires an active share. Write operations require EDITOR or OWNER. Destructive operations require OWNER.

## 2. Scope

### In Scope

- Account CRUD routes
- Account sharing management routes
- Transaction CRUD, review, split, and join routes
- Bulk transaction operations routes
- Card CRUD routes

### Out of Scope

- Bank import triggers (spec 030 — integrations)
- Transaction categorization (spec 030 — classification)
- Multi-currency conversion (future spec 017)

## 3. Account Routes

### 3.1 Create Account

```
POST /api/v1/accounts

Request Body:
{
    "account_name": "Savings Account",
    "currency": "EUR",
    "opening_balance": "1000.00",
    "account_type_id": "uuid",
    "financial_institution_id": "uuid",
    "iban": "DE89370400440532013000",   // optional
    "notes": "Main savings"              // optional
}

Response 201:
{
    "account_id": "uuid",
    "account_name": "Savings Account",
    "currency": "EUR",
    "opening_balance": { "amount": "1000.00", "currency": "EUR" },
    "iban": "****3000",
    "notes": "Main savings",
    "created_at": "...",
    "shares": [
        { "user_id": "uuid", "permission_level": "OWNER", "granted_at": "..." }
    ]
}

Errors:
    400 — Invalid input (name, currency, IBAN)
    409 — Account name already exists for user
```

**Auth:** Bearer token required
**Service:** `AccountManagementService.create_account()`

### 3.2 List Accounts

```
GET /api/v1/accounts

Query Params:
    include_deleted: bool = false

Response 200:
{
    "items": [
        {
            "account_id": "uuid",
            "account_name": "Savings Account",
            "currency": "EUR",
            "current_balance": { "amount": "1500.00", "currency": "EUR" },
            "permission_level": "OWNER",
            ...
        }
    ]
}
```

**Auth:** Bearer token required
**Service:** `AccountRepository.find_accessible_by_user()`

### 3.3 Get Account

```
GET /api/v1/accounts/{account_id}

Response 200:
{
    "account_id": "uuid",
    "account_name": "Savings Account",
    "currency": "EUR",
    "opening_balance": { "amount": "1000.00", "currency": "EUR" },
    "current_balance": { "amount": "1500.00", "currency": "EUR" },
    "transaction_count": 15,
    "iban": "****3000",
    ...
}

Errors:
    403 — No share on this account
    404 — Account not found
```

**Auth:** Bearer token required (VIEWER+)

### 3.4 Update Account

```
PATCH /api/v1/accounts/{account_id}

Request Body (all fields optional):
{
    "account_name": "Updated Name",
    "account_type_id": "uuid",
    "financial_institution_id": "uuid",
    "notes": "Updated notes"
}

Response 200: { ... updated account ... }

Errors:
    403 — Not OWNER
    404 — Account not found
    409 — Account name already exists
```

**Auth:** Bearer token required (OWNER only for rename, EDITOR+ for other fields)

### 3.5 Soft Delete Account

```
DELETE /api/v1/accounts/{account_id}

Response 204: (no content)

Errors:
    403 — Not OWNER
    404 — Account not found
    409 — Already deleted
```

**Auth:** Bearer token required (OWNER only)
**Service:** `AccountManagementService.soft_delete_account()`

### 3.6 Recover Account

```
POST /api/v1/accounts/{account_id}/recover

Response 200: { ... recovered account ... }

Errors:
    403 — Not OWNER
    404 — Account not found
    409 — Not deleted
```

**Auth:** Bearer token required (OWNER only)
**Service:** `AccountManagementService.recover_account()`

## 4. Sharing Routes

### 4.1 Share Account

```
POST /api/v1/accounts/{account_id}/shares

Request Body:
{
    "user_id": "uuid",
    "permission_level": "EDITOR"
}

Response 201:
{
    "share_id": "uuid",
    "user_id": "uuid",
    "permission_level": "EDITOR",
    "granted_at": "...",
    "granted_by": "uuid"
}

Errors:
    403 — Not OWNER
    404 — Account not found
    409 — User already has active share
    409 — Max shares exceeded
```

**Auth:** Bearer token required (OWNER only)
**Service:** `AccountSharingService.share_account()`

### 4.2 List Shares

```
GET /api/v1/accounts/{account_id}/shares

Response 200:
{
    "items": [
        {
            "share_id": "uuid",
            "user_id": "uuid",
            "permission_level": "OWNER",
            "granted_at": "...",
            "is_active": true
        }
    ]
}
```

**Auth:** Bearer token required (VIEWER+)

### 4.3 Update Share Permission

```
PATCH /api/v1/accounts/{account_id}/shares/{share_id}

Request Body:
{
    "permission_level": "VIEWER"
}

Response 200: { ... updated share ... }

Errors:
    403 — Not OWNER
    409 — Cannot change owner's permission
```

**Auth:** Bearer token required (OWNER only)
**Service:** `AccountSharingService.update_share_permission()`

### 4.4 Revoke Share

```
DELETE /api/v1/accounts/{account_id}/shares/{share_id}

Response 204: (no content)

Errors:
    403 — Not OWNER
    409 — Cannot revoke owner share
```

**Auth:** Bearer token required (OWNER only)
**Service:** `AccountSharingService.revoke_share()`

### 4.5 Leave Account

```
POST /api/v1/accounts/{account_id}/leave

Response 204: (no content)

Errors:
    409 — Owner cannot leave (must transfer first)
```

**Auth:** Bearer token required
**Service:** `AccountSharingService.leave_account()`

### 4.6 Transfer Ownership

```
POST /api/v1/accounts/{account_id}/transfer-ownership

Request Body:
{
    "new_owner_id": "uuid"
}

Response 200: { ... updated shares ... }

Errors:
    403 — Not OWNER
    404 — New owner has no share
```

**Auth:** Bearer token required (OWNER only)
**Service:** `AccountSharingService.transfer_ownership()`

## 5. Transaction Routes

### 5.1 Create Transaction

```
POST /api/v1/accounts/{account_id}/transactions

Request Body:
{
    "amount": "-45.99",
    "currency": "EUR",
    "description": "Grocery shopping",
    "merchant": "Whole Foods",
    "transaction_date": "2024-01-15",
    "value_date": "2024-01-16",            // optional
    "external_id": "ext-123",              // optional
    "card_id": "uuid",                     // optional
    "comments": "Weekly groceries"         // optional
}

Response 201: { ... transaction ... }

Errors:
    400 — Invalid input
    403 — Not EDITOR+
    404 — Account not found
    409 — Currency mismatch
```

**Auth:** Bearer token required (EDITOR+)
**Service:** `TransactionManagementService.create_transaction()`

### 5.2 List Transactions

```
GET /api/v1/accounts/{account_id}/transactions

Query Params:
    page: int = 1
    page_size: int = 20
    include_deleted: bool = false

Response 200:
{
    "items": [ ... transactions ... ],
    "total": 150,
    "page": 1,
    "page_size": 20,
    "total_pages": 8,
    "balance": { "amount": "1500.00", "currency": "EUR" }
}
```

**Auth:** Bearer token required (VIEWER+)

### 5.3 Get Transaction

```
GET /api/v1/accounts/{account_id}/transactions/{transaction_id}

Response 200: { ... transaction with split children if applicable ... }

Errors:
    403 — No share on account
    404 — Transaction not found
```

**Auth:** Bearer token required (VIEWER+)

### 5.4 Update Transaction

```
PATCH /api/v1/accounts/{account_id}/transactions/{transaction_id}

Request Body (all fields optional):
{
    "description": "Updated description",
    "merchant": "New Merchant",
    "amount": "-50.00",
    "transaction_date": "2024-01-16",
    "comments": "Updated"
}

Response 200: { ... updated transaction ... }

Errors:
    403 — Not EDITOR+
    404 — Transaction not found
    409 — Cannot update split parent amount
```

**Auth:** Bearer token required (EDITOR+)

### 5.5 Delete Transaction

```
DELETE /api/v1/accounts/{account_id}/transactions/{transaction_id}

Response 204: (no content)

Errors:
    403 — Not EDITOR+
    404 — Transaction not found
    409 — Already deleted
```

**Auth:** Bearer token required (EDITOR+)

### 5.6 Recover Transaction

```
POST /api/v1/accounts/{account_id}/transactions/{transaction_id}/recover

Response 200: { ... recovered transaction ... }

Errors:
    403 — Not EDITOR+
    404 — Transaction not found
    409 — Not deleted
```

**Auth:** Bearer token required (EDITOR+)

### 5.7 Review / Unreview Transaction

```
POST /api/v1/accounts/{account_id}/transactions/{transaction_id}/review

Response 200: { ... transaction with review_status=REVIEWED ... }

POST /api/v1/accounts/{account_id}/transactions/{transaction_id}/unreview

Response 200: { ... transaction with review_status=TO_REVIEW ... }
```

**Auth:** Bearer token required (EDITOR+)

### 5.8 Split Transaction

```
POST /api/v1/accounts/{account_id}/transactions/{transaction_id}/split

Request Body:
{
    "splits": [
        { "amount": "-25.00", "description": "Groceries", "merchant": "Whole Foods" },
        { "amount": "-20.99", "description": "Cleaning supplies" }
    ]
}

Response 200:
{
    "parent": { ... parent transaction with is_split_parent=true ... },
    "children": [ ... split children ... ]
}

Errors:
    400 — Split amounts don't sum to parent
    403 — Not EDITOR+
    409 — Already split
```

**Auth:** Bearer token required (EDITOR+)
**Service:** `TransactionManagementService.split_transaction()`

### 5.9 Join Splits

```
POST /api/v1/accounts/{account_id}/transactions/{transaction_id}/join

Response 200: { ... parent transaction with is_split_parent=false ... }

Errors:
    403 — Not EDITOR+
    409 — Not a split parent
```

**Auth:** Bearer token required (EDITOR+)
**Service:** `TransactionManagementService.join_transaction_splits()`

### 5.10 Get Account Balance

```
GET /api/v1/accounts/{account_id}/balance

Response 200:
{
    "opening_balance": { "amount": "1000.00", "currency": "EUR" },
    "current_balance": { "amount": "1500.00", "currency": "EUR" },
    "transaction_count": 15
}
```

**Auth:** Bearer token required (VIEWER+)

## 6. Bulk Transaction Routes

### 6.1 Bulk Create

```
POST /api/v1/accounts/{account_id}/transactions/bulk

Request Body:
{
    "transactions": [
        { "amount": "-10.00", "currency": "EUR", "description": "Item 1", "transaction_date": "2024-01-15" },
        { "amount": "-20.00", "currency": "EUR", "description": "Item 2", "transaction_date": "2024-01-15" }
    ]
}

Response 200:
{
    "total": 2,
    "succeeded": 2,
    "failed": 0,
    "results": [
        { "index": 0, "status": "success", "transaction_id": "uuid" },
        { "index": 1, "status": "success", "transaction_id": "uuid" }
    ]
}

Errors:
    400 — Empty request or exceeds bulk limit
    403 — Not EDITOR+
```

**Auth:** Bearer token required (EDITOR+)
**Service:** `BulkTransactionService.bulk_create()`

### 6.2 Bulk Update

```
PATCH /api/v1/accounts/{account_id}/transactions/bulk

Request Body:
{
    "transaction_ids": ["uuid1", "uuid2"],
    "updates": {
        "merchant": "Updated Merchant"
    }
}

Response 200: { ... bulk result ... }
```

**Auth:** Bearer token required (EDITOR+)

### 6.3 Bulk Delete

```
POST /api/v1/accounts/{account_id}/transactions/bulk/delete

Request Body:
{
    "transaction_ids": ["uuid1", "uuid2"]
}

Response 200: { ... bulk result ... }
```

**Auth:** Bearer token required (EDITOR+)

### 6.4 Bulk Recover

```
POST /api/v1/accounts/{account_id}/transactions/bulk/recover

Request Body:
{
    "transaction_ids": ["uuid1", "uuid2"]
}

Response 200: { ... bulk result ... }
```

**Auth:** Bearer token required (EDITOR+)

## 7. Card Routes

### 7.1 Create Card

```
POST /api/v1/accounts/{account_id}/cards

Request Body:
{
    "card_name": "Main Visa",
    "last_four_digits": "1234",
    "card_type": "DEBIT",
    "card_network": "VISA",
    "expiration_date": "2026-12"     // optional
}

Response 201: { ... card ... }

Errors:
    403 — Not EDITOR+
    409 — Card name already exists for account
```

**Auth:** Bearer token required (EDITOR+)

### 7.2 List Cards

```
GET /api/v1/accounts/{account_id}/cards

Response 200:
{
    "items": [ ... cards ... ]
}
```

**Auth:** Bearer token required (VIEWER+)

### 7.3 Update Card

```
PATCH /api/v1/accounts/{account_id}/cards/{card_id}

Request Body (all fields optional):
{
    "card_name": "Updated Name",
    "is_active": false
}

Response 200: { ... updated card ... }
```

**Auth:** Bearer token required (EDITOR+)

### 7.4 Delete Card

```
DELETE /api/v1/accounts/{account_id}/cards/{card_id}

Response 204: (no content)
```

**Auth:** Bearer token required (OWNER only)

## 8. File Structure

```
src/emerald/infrastructure/api/
    routers/
        accounts.py          # Account CRUD
        account_shares.py    # Sharing routes
        transactions.py      # Transaction CRUD + split/join/review
        bulk_transactions.py # Bulk operations
        cards.py             # Card CRUD
    schemas/
        core_finance.py      # Core Finance request/response schemas
```

## 9. Acceptance Criteria

### Account Routes

- [ ] CRUD operations work for authenticated users
- [ ] Account name uniqueness enforced per user
- [ ] Currency immutable after creation
- [ ] IBAN validated and masked in responses
- [ ] Soft delete requires OWNER
- [ ] Recover requires OWNER

### Sharing Routes

- [ ] Only OWNER can share, update permissions, revoke
- [ ] Any user with share can list shares
- [ ] Leave works for non-owners
- [ ] Transfer ownership updates both shares atomically
- [ ] Max shares limit enforced

### Transaction Routes

- [ ] Create requires EDITOR+
- [ ] List requires VIEWER+
- [ ] Split validates amounts sum to parent
- [ ] Join removes children and restores parent
- [ ] Review/unreview are idempotent
- [ ] Balance calculation excludes deleted and split parents

### Bulk Routes

- [ ] Bulk limit enforced (400 if exceeded)
- [ ] Per-item success/failure reporting
- [ ] Empty request returns 400
- [ ] Partial success returns 200 with mixed results

### Card Routes

- [ ] CRUD operations with proper permission checks
- [ ] Delete requires OWNER
- [ ] Card name uniqueness per account

### Permission Checks

- [ ] 403 returned when user has no share on account
- [ ] 403 returned when user has insufficient permission level
- [ ] Permission checks applied consistently across all endpoints
