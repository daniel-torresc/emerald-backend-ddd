# Spec 016: Audit Logging

**Status:** Draft
**Bounded Context:** Cross-Cutting
**Dependencies:** 001 (Shared Kernel)
**Blocks:** None

---

## 1. Overview

This spec defines the audit logging infrastructure — an immutable, write-once record of every meaningful state change in the platform. Audit logs capture who did what, when, to which entity, and the before/after state. They serve as the foundation for compliance (SOX, GDPR), security monitoring, and operational debugging.

**Key Principle:** Audit logs are immutable and never deleted. They are write-once records that capture before and after states for every change. The audit system is asynchronous — it must not block or slow down domain operations, but delivery must be guaranteed.

## 2. Scope

### In Scope

- AuditEntry entity (immutable record)
- Audit actions catalog (all auditable actions across contexts)
- Audit context capture (actor, IP, user agent, request correlation)
- Before/after state snapshots
- SUPERADMIN enhanced logging
- Audit retention and archival
- Audit query capabilities (for admin portal and compliance)

### Out of Scope

- Audit log storage implementation (infrastructure — could be DB, event store, log aggregator)
- Real-time alerting on audit events (future enhancement)
- Audit log export to SIEM systems (future enhancement)
- Admin portal UI for audit browsing (presentation layer)

## 3. AuditEntry Entity

### 3.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| audit_id | UUID | No | Unique identifier |
| timestamp | datetime | No | When action occurred (UTC) |
| actor_type | ActorType | No | User or System |
| actor_id | UUID? | No | Who performed action (None for system) |
| action | AuditAction | No | What was done |
| entity_type | str | No | What type of entity was affected |
| entity_id | UUID | No | Which specific entity |
| old_state | dict? | No | State before change (JSON, None for creates) |
| new_state | dict? | No | State after change (JSON, None for deletes) |
| metadata | dict | No | Additional context |
| ip_address | str? | No | Client IP address |
| user_agent | str? | No | Client info |
| request_id | UUID? | No | Correlation ID for request tracing |
| result | AuditResult | No | Success, Failure, or Partial |

**Immutability:** All fields are set at creation and never modified. AuditEntry has no update methods.

### 3.2 ActorType

| Value | Description |
|-------|-------------|
| USER | Action performed by an authenticated user |
| SYSTEM | Action performed by platform automation (scheduled jobs, event handlers) |

### 3.3 AuditResult

| Value | Description |
|-------|-------------|
| SUCCESS | Action completed successfully |
| FAILURE | Action failed (business rule violation, validation error) |
| PARTIAL | Action partially completed (bulk operations with some failures) |

## 4. Audit Actions Catalog

### 4.1 Authentication Actions

| Action | Entity Type | Trigger | Captures |
|--------|-------------|---------|----------|
| `USER_LOGIN` | User | Successful login | user_id, login_method (password/social), portal |
| `USER_LOGIN_FAILED` | User | Failed login attempt | email (not user_id), failure_reason |
| `USER_LOGOUT` | User | Logout | user_id, session_type (single/all) |
| `TOKEN_REFRESHED` | RefreshToken | Token rotation | user_id, family_id |
| `TOKEN_REVOKED` | RefreshToken | Token revocation | user_id, revocation_reason |
| `TOKEN_FAMILY_COMPROMISED` | RefreshToken | Theft detection | user_id, family_id |
| `PASSWORD_CHANGED` | User | Password change | user_id (no password data) |
| `PASSWORD_RESET_REQUESTED` | User | Reset request | user_id |
| `PASSWORD_RESET_COMPLETED` | User | Reset executed | user_id |

### 4.2 User Lifecycle Actions

| Action | Entity Type | Trigger | Captures |
|--------|-------------|---------|----------|
| `USER_REGISTERED` | User | Registration | user_id, email, registration_method |
| `USER_EMAIL_VERIFIED` | User | Email verification | user_id |
| `USER_PROFILE_UPDATED` | User | Profile change | user_id, changed_fields (old → new) |
| `USER_SUSPENDED` | User | Admin suspends user | user_id, suspended_by, reason |
| `USER_UNSUSPENDED` | User | Admin unsuspends | user_id, unsuspended_by |
| `USER_SOFT_DELETED` | User | Soft delete | user_id, deleted_by, reason |
| `USER_RECOVERED` | User | Recovery from trash | user_id, recovered_by |
| `USER_HARD_DELETED` | User | Permanent deletion | user_id (final record before removal) |
| `USER_PROMOTED_TO_ADMIN` | User | Role promotion | user_id, promoted_by, permissions |
| `USER_DEMOTED_TO_USER` | User | Role demotion | user_id, demoted_by |
| `ADMIN_PERMISSION_GRANTED` | User | Permission added | user_id, permission, granted_by |
| `ADMIN_PERMISSION_REVOKED` | User | Permission removed | user_id, permission, revoked_by |
| `AUTH_PROVIDER_LINKED` | User | Social provider linked | user_id, provider_type |
| `AUTH_PROVIDER_UNLINKED` | User | Social provider removed | user_id, provider_type |

### 4.3 Account Operations Actions

| Action | Entity Type | Trigger | Captures |
|--------|-------------|---------|----------|
| `ACCOUNT_CREATED` | Account | Account creation | account_id, owner_id, currency |
| `ACCOUNT_UPDATED` | Account | Account edit | account_id, changed_fields (old → new) |
| `ACCOUNT_SOFT_DELETED` | Account | Soft delete | account_id, deleted_by, reason |
| `ACCOUNT_RECOVERED` | Account | Recovery | account_id, recovered_by |
| `ACCOUNT_HARD_DELETED` | Account | Permanent deletion | account_id (final record) |
| `ACCOUNT_SHARED` | AccountShare | Share granted | account_id, user_id, permission, granted_by |
| `ACCOUNT_SHARE_UPDATED` | AccountShare | Permission changed | account_id, user_id, old/new permission |
| `ACCOUNT_SHARE_REVOKED` | AccountShare | Share removed | account_id, user_id, revoked_by |
| `ACCOUNT_OWNERSHIP_TRANSFERRED` | Account | Ownership transfer | account_id, old_owner, new_owner |

### 4.4 Transaction Actions

| Action | Entity Type | Trigger | Captures |
|--------|-------------|---------|----------|
| `TRANSACTION_CREATED` | Transaction | Manual creation | transaction_id, account_id, amount |
| `TRANSACTION_UPDATED` | Transaction | Edit | transaction_id, changed_fields (old → new) |
| `TRANSACTION_SOFT_DELETED` | Transaction | Soft delete | transaction_id, deleted_by |
| `TRANSACTION_RECOVERED` | Transaction | Recovery | transaction_id, recovered_by |
| `TRANSACTION_HARD_DELETED` | Transaction | Permanent deletion | transaction_id (final record) |
| `TRANSACTION_SPLIT` | Transaction | Split operation | parent_id, child_ids, split_amounts |
| `TRANSACTION_SPLITS_JOINED` | Transaction | Join operation | parent_id, removed_child_count |
| `TRANSACTIONS_BULK_CREATED` | Account | Bulk create | account_id, success/failure counts |
| `TRANSACTIONS_IMPORTED` | Account | Bank import | account_id, connection_id, import_counts |

### 4.5 Bank Connection Actions

| Action | Entity Type | Trigger | Captures |
|--------|-------------|---------|----------|
| `BANK_CONNECTION_ESTABLISHED` | BankConnection | Connection activated | connection_id, provider, account_id |
| `BANK_SYNC_COMPLETED` | BankConnection | Sync success | connection_id, sync_counts |
| `BANK_SYNC_FAILED` | BankConnection | Sync failure | connection_id, error |
| `BANK_CONNECTION_DISCONNECTED` | BankConnection | User disconnects | connection_id, disconnected_by |
| `BANK_CONNECTION_NEEDS_REAUTH` | BankConnection | Credentials expired | connection_id |

### 4.6 Classification Actions

| Action | Entity Type | Trigger | Captures |
|--------|-------------|---------|----------|
| `TAXONOMY_CREATED` | Taxonomy | Creation | taxonomy_id, owner_id, name |
| `TAXONOMY_UPDATED` | Taxonomy | Edit | taxonomy_id, changed_fields |
| `TAXONOMY_SOFT_DELETED` | Taxonomy | Soft delete | taxonomy_id, deleted_by |
| `TERM_ADDED` | TaxonomyTerm | Term creation | term_id, taxonomy_id, name |
| `TERM_MOVED` | TaxonomyTerm | Hierarchy change | term_id, old_parent, new_parent |
| `TRANSACTION_CATEGORIZED` | TransactionTermAssignment | Term assigned | transaction_id, term_id |
| `TRANSACTION_UNCATEGORIZED` | TransactionTermAssignment | Term removed | transaction_id, taxonomy_id |

### 4.7 Admin Actions

| Action | Entity Type | Trigger | Captures |
|--------|-------------|---------|----------|
| `MASTER_DATA_CREATED` | Various | Admin creates master data | entity_type, entity_id, created_by |
| `MASTER_DATA_UPDATED` | Various | Admin edits master data | entity_type, changed_fields |
| `RETENTION_POLICY_CHANGED` | RetentionPolicy | Policy updated | entity_type, old/new period |
| `SUPERADMIN_PROVISIONED` | User | Initial setup | user_id |

## 5. State Capture

### 5.1 Before/After States

For update operations, the audit entry captures the state before and after the change:

```
old_state: {
    "account_name": "Savings",
    "notes": null
}
new_state: {
    "account_name": "Emergency Fund",
    "notes": "For unexpected expenses"
}
```

**Rules:**

| Operation | old_state | new_state |
|-----------|-----------|-----------|
| Create | None | Full entity state |
| Update | Changed fields only (before) | Changed fields only (after) |
| Delete (soft) | Relevant fields | Deletion fields set |
| Delete (hard) | Full entity state (final snapshot) | None |
| Recovery | Deletion fields | Cleared fields |

### 5.2 Sensitive Data Handling

Certain fields must NEVER appear in audit state snapshots:

| Field | Treatment |
|-------|-----------|
| password / password_hash | Never captured — log "password changed" only |
| access_token (bank) | Never captured — log "credentials updated" only |
| full card numbers | Never stored (only last four exist in system) |
| password reset tokens | Never captured |

### 5.3 SUPERADMIN Enhanced Logging

All SUPERADMIN actions are logged with additional detail:

```
metadata (for SUPERADMIN actions):
  {
    "enhanced_audit": true,
    "actor_role": "SUPERADMIN",
    "session_id": "...",
    "action_justification": "..."  (optional, for sensitive operations)
  }
```

## 6. Audit Context

### 6.1 AuditContext (Value Object)

Captures the request context for every auditable operation:

| Attribute | Type | Description |
|-----------|------|-------------|
| actor_type | ActorType | USER or SYSTEM |
| actor_id | UUID? | Authenticated user ID |
| ip_address | str? | Client IP |
| user_agent | str? | Client info |
| request_id | UUID | Correlation ID (generated per request) |

**Population:**

- Populated at the presentation layer (middleware/interceptor)
- Threaded through the application layer to the audit writer
- System actions (scheduled jobs) use `actor_type=SYSTEM` with no actor_id

### 6.2 Request Correlation

Every API request gets a unique `request_id` (UUID). All audit entries generated within that request share the same `request_id`, enabling tracing of multi-step operations.

```
Single API request may generate multiple audit entries:
  request_id: abc-123
    ├── ACCOUNT_SOFT_DELETED (account)
    ├── TRANSACTION_SOFT_DELETED (transaction 1, cascade)
    ├── TRANSACTION_SOFT_DELETED (transaction 2, cascade)
    └── CARD_SOFT_DELETED (card 1, cascade)
```

## 7. Audit Writing

### 7.1 Domain Event → Audit Entry

Audit entries are created by consuming domain events. This decouples the domain from audit infrastructure:

```
Domain Layer                 Application Layer             Audit Infrastructure
     │                             │                              │
     │  emit(AccountCreated)       │                              │
     │────────────────────────────►│                              │
     │                             │  publish event               │
     │                             │─────────────────────────────►│
     │                             │                              │
     │                             │              AuditEventHandler:
     │                             │              1. Map event → AuditAction
     │                             │              2. Capture old/new state
     │                             │              3. Add audit context
     │                             │              4. Write AuditEntry
     │                             │                              │
```

### 7.2 Guaranteed Delivery

Audit logging must be reliable — no audit entries should be lost:

| Guarantee | Implementation |
|-----------|---------------|
| At-least-once delivery | Domain events persisted before dispatch |
| Async processing | Audit writes don't block domain operations |
| Retry on failure | Failed audit writes retried with backoff |
| Dead letter queue | Permanently failed entries stored for manual review |
| No data loss | Even if audit infra is temporarily down, events are queued |

### 7.3 Audit Writer Interface

```
AuditWriter (Protocol):
  + write(entry: AuditEntry) -> None
      Persists audit entry to storage
      Must be idempotent (same audit_id → same result)

  + write_many(entries: list[AuditEntry]) -> None
      Batch write for cascade operations
```

## 8. Audit Retention and Archival

### 8.1 Retention Rules

| Rule | Description |
|------|-------------|
| Never deleted | Audit logs are never deleted (only archived) |
| Minimum retention | 7 years (regulatory compliance — SOX) |
| Active storage | Recent entries (e.g., last 1 year) in primary storage |
| Archive | Older entries moved to cold storage (same data, cheaper) |
| Immutable | No updates or modifications to existing entries |

### 8.2 Archival Schedule

```
Audit entries lifecycle:
  0-12 months: Primary storage (fast queries)
  12+ months: Archived to cold storage (slow queries, compliance access)
  Never: Deletion
```

## 9. Query Capabilities

### 9.1 Audit Query Service

```
AuditQueryService:
  + find_by_entity(
      entity_type: str,
      entity_id: UUID,
      date_range: DateRange? = None
    ) -> list[AuditEntry]
      "Show me everything that happened to this account"

  + find_by_actor(
      actor_id: UUID,
      date_range: DateRange? = None,
      action: AuditAction? = None
    ) -> list[AuditEntry]
      "Show me everything this user did"

  + find_by_action(
      action: AuditAction,
      date_range: DateRange? = None,
      entity_type: str? = None
    ) -> list[AuditEntry]
      "Show me all login failures"

  + find_by_request(request_id: UUID) -> list[AuditEntry]
      "Show me everything that happened in this request"

  + find_by_criteria(
      actor_id: UUID? = None,
      entity_type: str? = None,
      action: AuditAction? = None,
      result: AuditResult? = None,
      date_range: DateRange? = None,
      page: int = 1,
      page_size: int = 50
    ) -> PaginatedResult[AuditEntry]
      General-purpose query with pagination
```

### 9.2 Access Control for Audit Queries

| Actor | Access Level |
|-------|-------------|
| Regular User | Own actions only (actor_id = self) |
| ADMIN (compliance_admin) | All audit entries (via admin portal) |
| SUPERADMIN | All audit entries + enhanced detail |

## 10. Repository Interface

```
AuditEntryRepository (Protocol):
  + save(entry: AuditEntry) -> None
      Idempotent write (audit_id is unique key)
  + save_many(entries: list[AuditEntry]) -> None
  + find_by_entity(entity_type: str, entity_id: UUID, ...) -> list[AuditEntry]
  + find_by_actor(actor_id: UUID, ...) -> list[AuditEntry]
  + find_by_action(action: AuditAction, ...) -> list[AuditEntry]
  + find_by_request_id(request_id: UUID) -> list[AuditEntry]
  + find_by_criteria(...) -> PaginatedResult[AuditEntry]
  + count_by_criteria(...) -> int
```

## 11. Acceptance Criteria

### AuditEntry Immutability

- [ ] AuditEntry has no update or delete methods
- [ ] All fields are set at creation and never modified
- [ ] Duplicate audit_id writes are idempotent (no error, no duplicate)

### State Capture

- [ ] Create operations capture full entity state as `new_state`
- [ ] Update operations capture only changed fields in `old_state` and `new_state`
- [ ] Hard delete captures full entity state as `old_state` (final snapshot)
- [ ] Passwords, tokens, and secrets are NEVER captured in state snapshots
- [ ] SUPERADMIN actions include `enhanced_audit: true` in metadata

### Action Coverage

- [ ] All authentication events (login, logout, failed, token refresh/revoke) are audited
- [ ] All user lifecycle events (register, verify, suspend, delete, recover) are audited
- [ ] All account operations (create, update, delete, share, transfer) are audited
- [ ] All transaction operations (create, update, delete, split, join, bulk, import) are audited
- [ ] All bank connection events (connect, sync, disconnect, reauth) are audited
- [ ] All classification events (taxonomy CRUD, term operations, categorization) are audited
- [ ] All admin actions (master data, policy changes, user management) are audited

### Audit Context

- [ ] Every audit entry has a `request_id` for correlation
- [ ] Multiple entries from one request share the same `request_id`
- [ ] `ip_address` and `user_agent` captured for user actions
- [ ] System actions have `actor_type = SYSTEM` and no `actor_id`

### Reliability

- [ ] Audit writes are asynchronous (don't block domain operations)
- [ ] Failed audit writes are retried
- [ ] No audit entries are lost even under infrastructure failures
- [ ] Audit writing is idempotent

### Retention

- [ ] Audit entries are never deleted
- [ ] Minimum 7-year retention (SOX compliance)
- [ ] Entries older than 12 months eligible for archival to cold storage

### Query Access Control

- [ ] Regular users can only query their own audit entries
- [ ] compliance_admin can query all audit entries
- [ ] SUPERADMIN can query all entries including enhanced detail
- [ ] Queries support filtering by entity, actor, action, date range, result
- [ ] Queries support pagination
