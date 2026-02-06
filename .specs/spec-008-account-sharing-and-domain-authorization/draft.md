# Spec 008: Account Sharing & Domain Authorization

**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 007 (Account Management)
**Blocks:** 009 (Transaction Management)

---

## 1. Overview

This spec defines the AccountShare entity, the PermissionLevel value object, and the domain authorization model for the Core Finance context. Sharing allows account owners to grant other users access to their financial data at varying permission levels. Domain authorization is entirely separate from IAM system roles.

**Key Distinction:** IAM determines *which portals you can access* (system roles). Core Finance determines *what you can do with specific financial resources* (account shares). A SUPERADMIN has no special financial access — they must be explicitly shared on an account like any other user.

## 2. Scope

### In Scope

- `PermissionLevel` value object with hierarchy
- `AccountShare` entity with all attributes and invariants
- Share creation (granting access)
- Share update (changing permission level)
- Share revocation (removing access)
- Ownership transfer
- Resource access matrix (who can do what)
- Domain authorization checks

### Out of Scope

- System-level authorization / portal access (Spec 004)
- Transaction-level operations gated by permissions (Spec 009 — uses the authorization defined here)
- Notification delivery on share/revoke (Spec 019)

## 3. Value Objects

### 3.1 PermissionLevel

Hierarchical access level for account sharing. Determines what a user can do with a shared account.

**Enum with Hierarchy:**

| Value | Level | Description |
|-------|-------|-------------|
| VIEWER | 1 | Read-only access |
| EDITOR | 2 | View + modify (transactions, cards) |
| OWNER | 3 | Full control (delete, share, transfer) |

**Behavior:**

| Method | Description |
|--------|-------------|
| `has_at_least(required: PermissionLevel) -> bool` | Whether this level meets or exceeds required |
| `can_grant(level: PermissionLevel) -> bool` | Whether this level can grant the specified level (only OWNER can grant) |

**Comparison Logic:**

```
OWNER(3) > EDITOR(2) > VIEWER(1)

OWNER.has_at_least(VIEWER)   == True
OWNER.has_at_least(EDITOR)   == True
EDITOR.has_at_least(VIEWER)  == True
EDITOR.has_at_least(OWNER)   == False
VIEWER.has_at_least(EDITOR)  == False

Only OWNER.can_grant(*) returns True
EDITOR.can_grant(VIEWER) == False  (editors cannot share)
```

## 4. AccountShare Entity

### 4.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| share_id | UUID | No | Unique identifier |
| account_id | UUID | No | Account being shared |
| user_id | UUID | No | User with access |
| permission_level | PermissionLevel | Yes | Access level |
| granted_by | UUID | No | User who granted this share |
| granted_at | datetime | No | When granted |
| updated_at | datetime | Auto | Last permission change |
| deleted_at | datetime? | Yes | When revoked (soft delete) |

### 4.2 Invariants

| ID | Invariant | Description |
|----|-----------|-------------|
| ACC-005 | Exactly one OWNER share per account | An account must always have exactly one active OWNER share |
| ACC-006 | One active share per user per account | A user cannot have two active shares on the same account |
| ACC-007 | Cannot grant OWNER permission | OWNER is assigned only via creation or transfer |
| ACC-008 | Owner cannot revoke own ownership | Owner share can only change via transfer |

## 5. Resource Access Matrix

This matrix defines what each permission level allows across all account resources:

| Resource | OWNER | EDITOR | VIEWER | No Share |
|----------|-------|--------|--------|----------|
| **Account** | | | | |
| View account details | Yes | Yes | Yes | No |
| Edit account details | Yes | No | No | No |
| Delete account | Yes | No | No | No |
| Recover account | Yes | No | No | No |
| **Transactions** | | | | |
| View transactions | Yes | Yes | Yes | No |
| Create transaction | Yes | Yes | No | No |
| Edit transaction | Yes | Yes | No | No |
| Delete transaction | Yes | Yes | No | No |
| **Cards** | | | | |
| View cards | Yes | Yes | Yes | No |
| Manage cards (add/edit/remove) | Yes | Yes | No | No |
| **Shares** | | | | |
| View all shares | Yes | No | No | No |
| View own share | Yes | Yes | Yes | No |
| Grant shares | Yes | No | No | No |
| Revoke shares | Yes | No | No | No |
| Transfer ownership | Yes | No | No | No |
| **Trash** | | | | |
| View deleted items | Yes | Yes | No | No |
| Recover deleted items | Yes | No | No | No |
| Hard delete items | Yes | No | No | No |

## 6. Domain Methods (on Account Aggregate)

### 6.1 Share Management

```
Account:
  // Grant access
  + share_with(
      user_id: UUID,
      permission: PermissionLevel,
      granted_by: UUID
    ) -> AccountShare
      Validates:
        1. granted_by is the OWNER of this account
           Raises: InsufficientPermissionError
        2. permission is not OWNER
           Raises: CannotGrantOwnerError
        3. user_id != granted_by (cannot share with yourself)
           Raises: CannotShareWithSelfError
        4. No active share exists for user_id on this account
           Raises: AlreadySharedError
        5. Account is active (not deleted)
           Raises: AccountNotActiveError
      Creates: AccountShare entity
      Emits: AccountShared
      Returns: the created AccountShare

  // Update permission
  + update_share_permission(
      user_id: UUID,
      new_permission: PermissionLevel,
      updated_by: UUID
    ) -> None
      Validates:
        1. updated_by is the OWNER of this account
           Raises: InsufficientPermissionError
        2. Active share exists for user_id
           Raises: ShareNotFoundError
        3. new_permission is not OWNER
           Raises: CannotGrantOwnerError
        4. user_id is not the owner (cannot change owner's permission)
           Raises: CannotModifyOwnerShareError
      Updates: permission_level, updated_at
      Emits: AccountShareUpdated

  // Revoke access
  + revoke_share(user_id: UUID, revoked_by: UUID) -> None
      Validates:
        1. revoked_by is the OWNER of this account
           Raises: InsufficientPermissionError
        2. Active share exists for user_id
           Raises: ShareNotFoundError
        3. user_id is not the owner (cannot revoke owner)
           Raises: CannotRevokeOwnerError
      Effect: Soft deletes the AccountShare (sets deleted_at)
      Emits: AccountShareRevoked

  // Transfer ownership
  + transfer_ownership(new_owner_id: UUID, current_owner_id: UUID) -> None
      Validates:
        1. current_owner_id is the current OWNER
           Raises: InsufficientPermissionError
        2. Active share exists for new_owner_id (must already be shared)
           Raises: ShareNotFoundError
        3. new_owner_id != current_owner_id
           Raises: AlreadyOwnerError
      Effect:
        - Current owner's share: permission_level -> EDITOR
        - New owner's share: permission_level -> OWNER
      Emits: AccountOwnershipTransferred
```

### 6.2 Authorization Checks

```
Account:
  // Permission lookup
  + get_share_for_user(user_id: UUID) -> AccountShare?
      Returns active share for user, or None if no access

  + get_permission_level(user_id: UUID) -> PermissionLevel?
      Returns permission level for user, or None if no access

  + has_permission(user_id: UUID, required: PermissionLevel) -> bool
      Returns: share exists AND share.permission_level.has_at_least(required)

  // Convenience checks
  + is_owner(user_id: UUID) -> bool
      Returns: has_permission(user_id, OWNER)

  + can_edit(user_id: UUID) -> bool
      Returns: has_permission(user_id, EDITOR)

  + can_view(user_id: UUID) -> bool
      Returns: has_permission(user_id, VIEWER)

  // Share listing
  + get_active_shares() -> list[AccountShare]
      Returns all non-deleted shares

  + get_owner() -> AccountShare
      Returns the OWNER share (always exactly one)
```

## 7. Authorization Enforcement Pattern

Domain authorization is checked at the beginning of every operation on the Account aggregate:

```
Application Layer (Use Case):
  1. Load Account from repository
  2. Check permission: account.has_permission(requesting_user.user_id, required_level)
     Raises: InsufficientPermissionError if not authorized
  3. Proceed with domain operation

Example — Edit Transaction:
  account = repository.find_by_id(account_id)
  if not account.has_permission(user.user_id, PermissionLevel.EDITOR):
      raise InsufficientPermissionError("EDITOR access required")
  account.update_transaction(transaction_id, ...)
```

**Rules:**

- Authorization is always checked against the Account aggregate, even for child operations (transactions, cards)
- The permission check uses the domain's `AccountShare`, never IAM system roles
- `InsufficientPermissionError` is a domain exception (not HTTP 403 — the presentation layer maps it)

## 8. Share Lifecycle

### 8.1 Share States

```
┌──────────┐    revoke_share()    ┌──────────────┐
│  ACTIVE  │─────────────────────►│   REVOKED    │
│          │                      │ (soft deleted)│
└──────────┘                      └──────────────┘
     │
     │  update_share_permission()
     │  (stays ACTIVE, permission changes)
     ▼
┌──────────┐
│  ACTIVE  │ (updated permission)
└──────────┘
```

- Revoking a share is a soft delete (`deleted_at` set) — preserves history
- Revoked shares are excluded from permission checks
- Revoked shares are visible in audit/trash views

### 8.2 Ownership Transfer Flow

```
Before:
  Account "Savings"
    ├── Alice: OWNER
    └── Bob: EDITOR

transfer_ownership(new_owner=Bob, current_owner=Alice):

After:
  Account "Savings"
    ├── Alice: EDITOR  (demoted from OWNER)
    └── Bob: OWNER     (promoted to OWNER)
```

**Rules:**

- New owner must already have a share (at any level)
- Old owner is demoted to EDITOR (not removed)
- This is the ONLY way to change who the OWNER is
- Exactly one OWNER exists at all times (atomic swap)

## 9. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `AccountShared` | `share_with()` | account_id, user_id, permission_level, granted_by |
| `AccountShareUpdated` | `update_share_permission()` | account_id, user_id, old_permission, new_permission |
| `AccountShareRevoked` | `revoke_share()` | account_id, user_id, revoked_by |
| `AccountOwnershipTransferred` | `transfer_ownership()` | account_id, old_owner_id, new_owner_id |

## 10. Domain Errors

| Error | Trigger | Description |
|-------|---------|-------------|
| `InsufficientPermissionError` | Authorization check fails | User lacks required permission level |
| `CannotGrantOwnerError` | `share_with()` with OWNER level | OWNER can only be assigned via transfer |
| `CannotShareWithSelfError` | `share_with()` with own user_id | Owner already has access |
| `AlreadySharedError` | `share_with()` for user with active share | One share per user per account |
| `ShareNotFoundError` | Operation on non-existent share | User has no active share |
| `CannotRevokeOwnerError` | `revoke_share()` targeting owner | Owner share can only change via transfer |
| `CannotModifyOwnerShareError` | `update_share_permission()` targeting owner | Owner permission is not changeable |
| `AlreadyOwnerError` | `transfer_ownership()` to current owner | No-op transfer |
| `AccountNotActiveError` | Share operation on deleted account | Cannot share deleted accounts |

## 11. Repository Interface

```
AccountShareRepository (Protocol):
  + save(share: AccountShare) -> None
  + find_by_account_and_user(account_id: UUID, user_id: UUID) -> AccountShare?
      Returns active (non-deleted) share only
  + find_by_account(account_id: UUID, include_deleted: bool = False) -> list[AccountShare]
  + find_by_user(user_id: UUID, include_deleted: bool = False) -> list[AccountShare]
      Returns all shares for a user (across all accounts)
  + find_owner(account_id: UUID) -> AccountShare
      Returns the OWNER share (exactly one must exist)
```

## 12. Acceptance Criteria

### PermissionLevel

- [ ] `OWNER.has_at_least(VIEWER)` returns True
- [ ] `OWNER.has_at_least(EDITOR)` returns True
- [ ] `EDITOR.has_at_least(VIEWER)` returns True
- [ ] `EDITOR.has_at_least(OWNER)` returns False
- [ ] `VIEWER.has_at_least(EDITOR)` returns False
- [ ] Only `OWNER.can_grant()` returns True

### Share Creation

- [ ] Owner can share account with another user at VIEWER or EDITOR level
- [ ] Cannot grant OWNER permission — raises `CannotGrantOwnerError`
- [ ] Cannot share with self — raises `CannotShareWithSelfError`
- [ ] Cannot share if user already has active share — raises `AlreadySharedError`
- [ ] Cannot share a deleted account — raises `AccountNotActiveError`
- [ ] Non-owner cannot share — raises `InsufficientPermissionError`
- [ ] `AccountShared` event emitted on success

### Share Updates

- [ ] Owner can change a share's permission level (VIEWER <-> EDITOR)
- [ ] Cannot change to OWNER — raises `CannotGrantOwnerError`
- [ ] Cannot modify the owner share — raises `CannotModifyOwnerShareError`
- [ ] Non-owner cannot update shares — raises `InsufficientPermissionError`
- [ ] `AccountShareUpdated` event emitted on success

### Share Revocation

- [ ] Owner can revoke another user's share (soft delete)
- [ ] Cannot revoke owner share — raises `CannotRevokeOwnerError`
- [ ] Revoking a non-existent share raises `ShareNotFoundError`
- [ ] Revoked share is excluded from permission checks
- [ ] `AccountShareRevoked` event emitted on success

### Ownership Transfer

- [ ] Owner can transfer to a user who already has a share
- [ ] New owner becomes OWNER, old owner becomes EDITOR
- [ ] Transfer is atomic — exactly one OWNER at all times
- [ ] Target must have existing share — raises `ShareNotFoundError` otherwise
- [ ] Cannot transfer to self — raises `AlreadyOwnerError`
- [ ] `AccountOwnershipTransferred` event emitted on success

### Authorization Checks

- [ ] `has_permission()` returns True when user's share meets or exceeds required level
- [ ] `has_permission()` returns False when no share exists
- [ ] `has_permission()` returns False for revoked (soft deleted) shares
- [ ] Authorization is based on AccountShare, NOT on IAM system roles
- [ ] A SUPERADMIN with no share on an account is denied access

### Resource Access Matrix

- [ ] OWNER can perform all operations in the access matrix
- [ ] EDITOR can view + create/edit/delete transactions and manage cards
- [ ] EDITOR cannot delete account, manage shares, or recover/hard-delete
- [ ] VIEWER can only view (account, transactions, cards, own share)
- [ ] User with no share gets no access to any resource
