# Spec 008: Account Sharing & Domain Authorization

**Version:** 1.0
**Status:** Draft
**Bounded Context:** Core Finance
**Dependencies:** 007 (Account Management)
**Blocks:** 009 (Transaction Management)

---

## 1. Overview

This spec defines the AccountShare entity, the PermissionLevel value object, and the domain authorization model for the Core Finance context. Sharing allows account owners to grant other users access to their financial data at varying permission levels. Domain authorization is entirely separate from IAM system roles.

**Key Distinction:** IAM determines *which portals you can access* (system roles). Core Finance determines *what you can do with specific financial resources* (account shares). A SUPERADMIN has no special financial access -- they must be explicitly shared on an account like any other user.

---

## 2. Background & Context

### Problem Statement

The existing Account aggregate uses a simple `created_by` ownership model with no sharing capability. Users cannot grant family members or partners access to their financial accounts. All permission checks use `_verify_ownership()` which only compares against the account creator.

### Business Goals

- Enable family and household finance collaboration
- Allow account owners to share accounts with fine-grained permission control
- Establish a domain authorization model that is independent from system-level IAM roles
- Support ownership transfer for long-lived shared accounts

### Success Metrics

- Account owners can share accounts at VIEWER or EDITOR level
- Authorization checks use the share-based model for all account operations
- Ownership can be transferred atomically between shared users
- Maximum 20 shares per account to maintain bounded complexity

---

## 3. Scope

### In Scope

- `PermissionLevel` value object with hierarchy
- `AccountShare` entity with all attributes and invariants
- Shares as a child entity collection inside the Account aggregate
- Share creation (granting access), including initial OWNER share at account creation
- Share update (changing permission level)
- Share revocation (owner-initiated removal)
- Self-leave (non-owner voluntary removal)
- Ownership transfer
- Resource access matrix (who can do what)
- Domain authorization checks on Account aggregate
- Cascade: soft-deleting an account revokes all non-owner shares
- Migration of `AccountManagementService` from `_verify_ownership()` to share-based permissions
- New `AccountSharingService` application service
- Domain constant `MAX_SHARES_PER_ACCOUNT = 20`

### Out of Scope

- System-level authorization / portal access (Spec 004)
- Transaction-level operations gated by permissions (Spec 009 -- uses the authorization defined here)
- Notification delivery on share/revoke (Spec 019)
- Separate AccountShareRepository -- shares live inside the Account aggregate
- Cross-account share query port (deferred to infrastructure layer needs)

---

## 4. Users & Personas

### Primary Users

- **Account Owner**: The user who created the account (or received ownership via transfer). Has full control including sharing, deletion, and ownership transfer.
- **Shared User (Editor)**: A family member or partner with read/write access to transactions and cards but no administrative control.
- **Shared User (Viewer)**: A family member with read-only access for transparency and oversight.

### User Goals

- **Owner**: Share financial visibility and collaboration with household members while retaining administrative control.
- **Editor**: Record and manage transactions on shared accounts (e.g., joint spending, shared bills).
- **Viewer**: Monitor account activity without the ability to modify data (e.g., parent overseeing child's account).

---

## 5. Domain Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_SHARES_PER_ACCOUNT` | 20 | Maximum number of active shares (including owner) per account |

---

## 6. Value Objects

### 6.1 PermissionLevel

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
| `level` property | Integer level for comparison (VIEWER=1, EDITOR=2, OWNER=3) |

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

---

## 7. AccountShare Entity

### 7.1 Entity Characteristics

- **Base class:** `Entity` (not AggregateRoot)
- **Lifecycle:** Managed as a child entity inside the Account aggregate
- **No mixins:** Uses explicit domain-specific fields rather than SoftDeletableMixin or AuditableMixin
- **Revocation model:** Simple `revoked_at` / `revoked_by` fields (not full soft-delete lifecycle)

### 7.2 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| id | UUID | No | Unique share identifier (from Entity base) |
| account_id | UUID | No | Account being shared |
| user_id | UUID | No | User with access |
| permission_level | PermissionLevel | Yes | Access level (VIEWER, EDITOR, OWNER) |
| granted_by | UUID | No | User who granted this share |
| granted_at | datetime | No | When share was created (UTC) |
| updated_at | datetime | Auto | Last permission change (UTC) |
| revoked_at | datetime? | Yes | When revoked (UTC), None if active |
| revoked_by | UUID? | Yes | Who revoked, None if active |

### 7.3 Entity Methods

```
AccountShare:
  + is_active() -> bool
      Returns: revoked_at is None

  + is_revoked() -> bool
      Returns: revoked_at is not None

  + revoke(revoked_by: UUID) -> None
      Validates: share is currently active
      Raises: ShareAlreadyRevokedError if already revoked
      Effect: Sets revoked_at to now, revoked_by to actor

  + update_permission(new_level: PermissionLevel) -> None
      Effect: Sets permission_level, updates updated_at
```

### 7.4 Invariants

| ID | Invariant | Description |
|----|-----------|-------------|
| ACC-005 | Exactly one OWNER share per account | An account must always have exactly one active OWNER share |
| ACC-006 | One active share per user per account | A user cannot have two active shares on the same account |
| ACC-007 | Cannot grant OWNER permission | OWNER is assigned only via creation or ownership transfer |
| ACC-008 | Owner cannot revoke own share | Owner share can only change via transfer |
| ACC-009 | Max shares per account | At most MAX_SHARES_PER_ACCOUNT (20) active shares per account |

---

## 8. Account Aggregate Extensions

### 8.1 New Internal State

The Account aggregate gains an internal `_shares: list[AccountShare]` collection that holds all shares (active and revoked) for the account.

### 8.2 Factory Method Change

```
Account.create() is modified to:
  1. Create the Account instance (existing behavior)
  2. Create an initial OWNER AccountShare for the creator
  3. Add the share to _shares collection
  4. Register AccountCreated event (existing behavior)

  This ensures invariant ACC-005 (exactly one OWNER) holds from birth.
```

### 8.3 Share Management Methods

```
Account:
  // Grant access
  + share_with(
      user_id: UUID,
      permission: PermissionLevel,
      granted_by: UUID
    ) -> AccountShare
      Validates:
        1. Account is active (not deleted)
           Raises: AccountNotActiveError
        2. granted_by is the OWNER of this account
           Raises: InsufficientPermissionError
        3. permission is not OWNER
           Raises: CannotGrantOwnerError
        4. user_id != granted_by (cannot share with yourself)
           Raises: CannotShareWithSelfError
        5. No active share exists for user_id on this account
           Raises: AlreadySharedError
        6. Active share count < MAX_SHARES_PER_ACCOUNT
           Raises: MaxSharesReachedError
      Creates: AccountShare entity, adds to _shares
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
      Updates: share.permission_level, share.updated_at
      Emits: AccountShareUpdated

  // Revoke access (owner-initiated)
  + revoke_share(user_id: UUID, revoked_by: UUID) -> None
      Validates:
        1. revoked_by is the OWNER of this account
           Raises: InsufficientPermissionError
        2. Active share exists for user_id
           Raises: ShareNotFoundError
        3. user_id is not the owner (cannot revoke own ownership)
           Raises: CannotRevokeOwnerError
      Effect: Marks the AccountShare as revoked (sets revoked_at, revoked_by)
      Emits: AccountShareRevoked

  // Leave account (non-owner self-removal)
  + leave_share(user_id: UUID) -> None
      Validates:
        1. Active share exists for user_id
           Raises: ShareNotFoundError
        2. user_id is NOT the owner (owner cannot leave)
           Raises: CannotLeaveAsOwnerError
      Effect: Marks the AccountShare as revoked (sets revoked_at, revoked_by=user_id)
      Emits: AccountShareLeft

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
        - Both shares get updated_at refreshed
      Emits: AccountOwnershipTransferred
```

### 8.4 Authorization Check Methods

```
Account:
  // Permission lookup
  + get_share_for_user(user_id: UUID) -> AccountShare | None
      Returns active share for user, or None if no access

  + get_permission_level(user_id: UUID) -> PermissionLevel | None
      Returns permission level for user, or None if no access

  + has_permission(user_id: UUID, required: PermissionLevel) -> bool
      Returns: active share exists AND share.permission_level.has_at_least(required)

  // Convenience checks
  + is_owner(user_id: UUID) -> bool
      Returns: has_permission(user_id, OWNER)

  + can_edit(user_id: UUID) -> bool
      Returns: has_permission(user_id, EDITOR)

  + can_view(user_id: UUID) -> bool
      Returns: has_permission(user_id, VIEWER)

  // Share listing
  + get_active_shares() -> list[AccountShare]
      Returns all non-revoked shares

  + get_owner() -> AccountShare
      Returns the OWNER share (always exactly one active)

  + active_share_count -> int (property)
      Returns count of active (non-revoked) shares
```

### 8.5 Soft-Delete Cascade

```
Account.soft_delete() is extended to:
  1. Perform existing soft-delete behavior (SoftDeletableMixin)
  2. Revoke ALL non-owner shares (cascade)
     - Each non-owner active share is marked as revoked
     - revoked_by = the user performing the account delete
  3. The OWNER share remains active (owner retains relationship to deleted account)
  4. Register AccountSoftDeleted event (existing behavior)

Account.recover() behavior:
  1. Perform existing recovery (SoftDeletableMixin)
  2. Shares remain revoked -- they are NOT automatically restored
  3. Owner must explicitly re-share after recovery
  4. Register AccountRecovered event (existing behavior)
```

---

## 9. Resource Access Matrix

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
| Leave (self-revoke) | N/A | Yes | Yes | No |
| **Trash** | | | | |
| View deleted items | Yes | Yes | No | No |
| Recover deleted items | Yes | No | No | No |
| Hard delete items | Yes | No | No | No |

---

## 10. Authorization Enforcement Pattern

Domain authorization is checked at the beginning of every operation on the Account aggregate:

```
Application Layer (Use Case):
  1. Load Account from repository (shares loaded as part of aggregate)
  2. Check permission: account.has_permission(requesting_user_id, required_level)
     Raises: InsufficientPermissionError if not authorized
  3. Proceed with domain operation

Example -- Edit Account Name:
  account = uow.accounts.find_by_id(account_id)
  if not account.has_permission(user_id, PermissionLevel.OWNER):
      raise InsufficientPermissionError("OWNER access required")
  account.update_name(new_name, updated_by=user_id)

Example -- View Account (future query):
  account = uow.accounts.find_by_id(account_id)
  if not account.has_permission(user_id, PermissionLevel.VIEWER):
      raise InsufficientPermissionError("VIEWER access required")
```

**Rules:**

- Authorization is always checked against the Account aggregate, even for child operations (transactions, cards)
- The permission check uses the domain's `AccountShare`, never IAM system roles
- `InsufficientPermissionError` is a domain exception (not HTTP 403 -- the presentation layer maps it)
- `AccountManagementService` is updated to use `account.has_permission()` / `account.is_owner()` instead of `_verify_ownership()`

---

## 11. Share Lifecycle

### 11.1 Share States

```
                              revoke_share() / leave_share()
  ┌──────────┐                ┌──────────────┐
  │  ACTIVE  │───────────────>│   REVOKED    │
  │          │                │              │
  └──────────┘                └──────────────┘
       │
       │  update_share_permission()
       │  (stays ACTIVE, permission changes)
       ▼
  ┌──────────┐
  │  ACTIVE  │ (updated permission)
  └──────────┘
```

- Revoking a share sets `revoked_at` and `revoked_by` -- preserves history
- Revoked shares are excluded from all permission checks
- A revoked share for user X does NOT block a new share for user X (re-sharing allowed)
- Revoked shares are retained in the aggregate for audit purposes

### 11.2 Ownership Transfer Flow

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

- New owner must already have an active share (at any level)
- Old owner is demoted to EDITOR (not removed)
- This is the ONLY way to change who the OWNER is
- Exactly one OWNER exists at all times (atomic swap)

### 11.3 Account Deletion Cascade

```
Before account.soft_delete():
  Account "Savings" (active)
    ├── Alice: OWNER
    ├── Bob: EDITOR
    └── Carol: VIEWER

After account.soft_delete(deleted_by=Alice):
  Account "Savings" (soft-deleted)
    ├── Alice: OWNER (retained)
    ├── Bob: EDITOR -> REVOKED (cascade)
    └── Carol: VIEWER -> REVOKED (cascade)

After account.recover():
  Account "Savings" (active)
    ├── Alice: OWNER (active)
    ├── Bob: REVOKED (stays revoked, must be re-shared)
    └── Carol: REVOKED (stays revoked, must be re-shared)
```

---

## 12. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `AccountShared` | `share_with()` | account_id, user_id, permission_level, granted_by |
| `AccountShareUpdated` | `update_share_permission()` | account_id, user_id, old_permission, new_permission, updated_by |
| `AccountShareRevoked` | `revoke_share()` | account_id, user_id, revoked_by |
| `AccountShareLeft` | `leave_share()` | account_id, user_id |
| `AccountOwnershipTransferred` | `transfer_ownership()` | account_id, old_owner_id, new_owner_id |

All events include `aggregate_id` (account_id) and `aggregate_type = "account"` from DomainEvent base.

---

## 13. Domain Errors

| Error | Parent | Code | Trigger |
|-------|--------|------|---------|
| `InsufficientPermissionError` | `AuthorizationError` | `INSUFFICIENT_PERMISSION` | User lacks required permission level for operation |
| `CannotGrantOwnerError` | `InvariantViolationError` | `CANNOT_GRANT_OWNER` | Attempted to grant OWNER via share_with() or update |
| `CannotShareWithSelfError` | `InvariantViolationError` | `CANNOT_SHARE_WITH_SELF` | Owner attempted to share with themselves |
| `AlreadySharedError` | `ConflictError` | `ALREADY_SHARED` | User already has an active share on this account |
| `ShareNotFoundError` | `NotFoundError` | `SHARE_NOT_FOUND` | No active share exists for the specified user |
| `CannotRevokeOwnerError` | `InvariantViolationError` | `CANNOT_REVOKE_OWNER` | Attempted to revoke the owner's share |
| `CannotModifyOwnerShareError` | `InvariantViolationError` | `CANNOT_MODIFY_OWNER_SHARE` | Attempted to change the owner's permission level |
| `AlreadyOwnerError` | `InvariantViolationError` | `ALREADY_OWNER` | Attempted to transfer ownership to the current owner |
| `AccountNotActiveError` | `InvariantViolationError` | `ACCOUNT_NOT_ACTIVE` | Share operation attempted on a soft-deleted account |
| `MaxSharesReachedError` | `InvariantViolationError` | `MAX_SHARES_REACHED` | Account has reached MAX_SHARES_PER_ACCOUNT (20) active shares |
| `CannotLeaveAsOwnerError` | `InvariantViolationError` | `CANNOT_LEAVE_AS_OWNER` | Owner attempted to leave; must transfer ownership first |
| `ShareAlreadyRevokedError` | `ConflictError` | `SHARE_ALREADY_REVOKED` | Attempted to revoke an already-revoked share |

**Deprecation:** `NotAccountOwnerError` from spec-007 is replaced by `InsufficientPermissionError`. The old exception is removed.

---

## 14. Application Layer

### 14.1 Commands

| Command | Fields | Description |
|---------|--------|-------------|
| `ShareAccountWith` | account_id, requesting_user_id, target_user_id, permission_level (str) | Grant share access |
| `UpdateSharePermission` | account_id, requesting_user_id, target_user_id, new_permission_level (str) | Change a share's permission |
| `RevokeAccountShare` | account_id, requesting_user_id, target_user_id | Owner revokes a share |
| `LeaveAccountShare` | account_id, requesting_user_id | Non-owner removes own share |
| `TransferAccountOwnership` | account_id, requesting_user_id, new_owner_id | Transfer OWNER to another user |

All commands are `@dataclass(frozen=True)` extending `Command`.

### 14.2 AccountSharingService

New application service that orchestrates share operations.

```
AccountSharingService:
  Dependencies:
    - uow: AbstractCoreFinanceUnitOfWork

  Methods:
    + share_account(cmd: ShareAccountWith) -> AccountShare
        1. Load account (active only)
        2. Convert permission_level string to PermissionLevel
        3. Call account.share_with(...)
        4. Commit
        5. Return created share

    + update_share_permission(cmd: UpdateSharePermission) -> None
        1. Load account
        2. Convert new_permission_level to PermissionLevel
        3. Call account.update_share_permission(...)
        4. Commit

    + revoke_share(cmd: RevokeAccountShare) -> None
        1. Load account
        2. Call account.revoke_share(...)
        3. Commit

    + leave_share(cmd: LeaveAccountShare) -> None
        1. Load account
        2. Call account.leave_share(...)
        3. Commit

    + transfer_ownership(cmd: TransferAccountOwnership) -> None
        1. Load account
        2. Call account.transfer_ownership(...)
        3. Commit
```

### 14.3 AccountManagementService Updates

The existing `AccountManagementService` is modified:

1. **Remove** `_verify_ownership()` helper and `NotAccountOwnerError` usage
2. **Replace** all ownership checks with share-based permission checks:
   - `create_account`: After Account.create() (which now creates the OWNER share), no permission check needed (creator is owner)
   - `rename_account`: Check `account.is_owner(requesting_user_id)` -> raise `InsufficientPermissionError`
   - `update_account_type`: Check `account.is_owner(requesting_user_id)`
   - `update_financial_institution`: Check `account.is_owner(requesting_user_id)`
   - `update_account_notes`: Check `account.is_owner(requesting_user_id)`
   - `soft_delete_account`: Check `account.is_owner(requesting_user_id)`
   - `recover_account`: Check `account.is_owner(requesting_user_id)`
3. **Account name uniqueness**: `exists_by_name_for_user` continues to check against the requesting user (who must be the owner for rename operations)

### 14.4 Repository Extensions

`AccountRepository` protocol is extended with:

```
AccountRepository (Protocol):
  # Existing methods unchanged
  + save(account: Account) -> None
  + find_by_id(account_id: UUID, include_deleted: bool = False) -> Account | None
  + find_by_owner(user_id: UUID, include_deleted: bool = False) -> list[Account]
  + exists_by_name_for_user(account_name: AccountName, user_id: UUID) -> bool

  # New method
  + find_accessible_by_user(
      user_id: UUID,
      include_deleted: bool = False
    ) -> list[Account]
      Returns all accounts where user has any active share.
      When include_deleted=False, excludes soft-deleted accounts.
      Accounts are loaded with their full shares collection.
```

**Note:** Since AccountShare entities live inside the Account aggregate, they are persisted and loaded as part of the Account. No separate AccountShareRepository is needed. The `find_accessible_by_user` method enables cross-account queries like "show me all accounts I can access."

---

## 15. Acceptance Criteria

### REQ-001: PermissionLevel Value Object
**Priority:** Must Have

- [ ] `OWNER.has_at_least(VIEWER)` returns True
- [ ] `OWNER.has_at_least(EDITOR)` returns True
- [ ] `EDITOR.has_at_least(VIEWER)` returns True
- [ ] `EDITOR.has_at_least(OWNER)` returns False
- [ ] `VIEWER.has_at_least(EDITOR)` returns False
- [ ] Only `OWNER.can_grant()` returns True for any level
- [ ] `EDITOR.can_grant(VIEWER)` returns False
- [ ] `VIEWER.can_grant(VIEWER)` returns False

### REQ-002: AccountShare Entity
**Priority:** Must Have

- [ ] AccountShare has all required attributes (id, account_id, user_id, permission_level, granted_by, granted_at, updated_at, revoked_at, revoked_by)
- [ ] `is_active()` returns True when revoked_at is None
- [ ] `is_revoked()` returns True when revoked_at is set
- [ ] `revoke()` sets revoked_at and revoked_by
- [ ] `revoke()` raises ShareAlreadyRevokedError on double-revoke
- [ ] `update_permission()` changes level and updates updated_at
- [ ] Identity-based equality (from Entity base)

### REQ-003: Initial OWNER Share at Account Creation
**Priority:** Must Have

- [ ] `Account.create()` produces an Account with exactly one OWNER share
- [ ] The OWNER share's user_id matches the creator's user_id
- [ ] The OWNER share's granted_by is the creator
- [ ] `account.is_owner(creator_id)` returns True immediately after creation
- [ ] `account.active_share_count` is 1 after creation

### REQ-004: Share Creation
**Priority:** Must Have

- [ ] Owner can share account with another user at VIEWER level
- [ ] Owner can share account with another user at EDITOR level
- [ ] Cannot grant OWNER permission -- raises `CannotGrantOwnerError`
- [ ] Cannot share with self -- raises `CannotShareWithSelfError`
- [ ] Cannot share if user already has active share -- raises `AlreadySharedError`
- [ ] Cannot share a deleted account -- raises `AccountNotActiveError`
- [ ] Non-owner cannot share -- raises `InsufficientPermissionError`
- [ ] Cannot exceed MAX_SHARES_PER_ACCOUNT -- raises `MaxSharesReachedError`
- [ ] `AccountShared` event emitted on success
- [ ] Created share has correct granted_by, granted_at, permission_level

### REQ-005: Share Permission Updates
**Priority:** Must Have

- [ ] Owner can change a share's permission level (VIEWER -> EDITOR)
- [ ] Owner can change a share's permission level (EDITOR -> VIEWER)
- [ ] Cannot change to OWNER -- raises `CannotGrantOwnerError`
- [ ] Cannot modify the owner's share -- raises `CannotModifyOwnerShareError`
- [ ] Non-owner cannot update shares -- raises `InsufficientPermissionError`
- [ ] Updating non-existent share raises `ShareNotFoundError`
- [ ] `AccountShareUpdated` event emitted with old and new permission levels
- [ ] Share's updated_at is refreshed

### REQ-006: Share Revocation (Owner-Initiated)
**Priority:** Must Have

- [ ] Owner can revoke another user's share
- [ ] Cannot revoke owner's own share -- raises `CannotRevokeOwnerError`
- [ ] Revoking a non-existent or already-revoked share raises `ShareNotFoundError`
- [ ] Revoked share is excluded from permission checks
- [ ] Re-sharing with a previously revoked user is allowed (new share created)
- [ ] `AccountShareRevoked` event emitted on success

### REQ-007: Self-Leave
**Priority:** Must Have

- [ ] Non-owner user (EDITOR or VIEWER) can leave a shared account
- [ ] Owner cannot leave -- raises `CannotLeaveAsOwnerError`
- [ ] Leaving user with no active share raises `ShareNotFoundError`
- [ ] After leaving, user has no access to the account
- [ ] `AccountShareLeft` event emitted on success

### REQ-008: Ownership Transfer
**Priority:** Must Have

- [ ] Owner can transfer ownership to a user who already has an active share
- [ ] New owner becomes OWNER, old owner becomes EDITOR
- [ ] Transfer is atomic -- exactly one OWNER at all times
- [ ] Target must have an existing active share -- raises `ShareNotFoundError` otherwise
- [ ] Cannot transfer to self -- raises `AlreadyOwnerError`
- [ ] Non-owner cannot initiate transfer -- raises `InsufficientPermissionError`
- [ ] `AccountOwnershipTransferred` event emitted on success
- [ ] Both shares have updated_at refreshed

### REQ-009: Authorization Checks
**Priority:** Must Have

- [ ] `has_permission()` returns True when user's share meets or exceeds required level
- [ ] `has_permission()` returns False when no active share exists
- [ ] `has_permission()` returns False for revoked shares
- [ ] Authorization is based on AccountShare, NOT on IAM system roles
- [ ] A SUPERADMIN with no share on an account is denied access
- [ ] `is_owner()`, `can_edit()`, `can_view()` convenience methods work correctly
- [ ] `get_owner()` always returns exactly one share
- [ ] `get_active_shares()` excludes revoked shares

### REQ-010: Resource Access Matrix
**Priority:** Must Have

- [ ] OWNER can perform all operations in the access matrix
- [ ] EDITOR can view + create/edit/delete transactions and manage cards
- [ ] EDITOR cannot delete account, manage shares, or recover/hard-delete
- [ ] EDITOR can leave the account
- [ ] VIEWER can only view (account, transactions, cards, own share)
- [ ] VIEWER can leave the account
- [ ] User with no share gets no access to any resource

### REQ-011: Account Deletion Cascade
**Priority:** Must Have

- [ ] Soft-deleting an account revokes all non-owner active shares
- [ ] The OWNER share is retained (not revoked) during account soft-delete
- [ ] Recovering an account does NOT restore revoked shares
- [ ] After recovery, only the owner has access; shares must be re-granted
- [ ] Cascade revocation sets revoked_by to the user who deleted the account

### REQ-012: AccountManagementService Migration
**Priority:** Must Have

- [ ] `_verify_ownership()` is removed
- [ ] `NotAccountOwnerError` is removed (replaced by `InsufficientPermissionError`)
- [ ] All account operations check permissions via `account.is_owner()` or `account.has_permission()`
- [ ] Account creation still works (creator gets automatic OWNER share)
- [ ] All existing AccountManagementService tests pass (adapted to new permission model)

### REQ-013: AccountSharingService
**Priority:** Must Have

- [ ] `share_account()` orchestrates share creation
- [ ] `update_share_permission()` orchestrates permission updates
- [ ] `revoke_share()` orchestrates owner-initiated revocation
- [ ] `leave_share()` orchestrates self-leave
- [ ] `transfer_ownership()` orchestrates ownership transfer
- [ ] All operations commit via UnitOfWork

### REQ-014: AccountRepository Extension
**Priority:** Must Have

- [ ] `find_accessible_by_user(user_id)` returns accounts with active shares for user
- [ ] Accounts are loaded with their full shares collection
- [ ] `include_deleted=False` excludes soft-deleted accounts

---

## 16. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Share with user who was previously revoked | Allowed -- new share created (old revoked share remains in history) |
| Transfer ownership then transfer back | Allowed -- ownership ping-pong is valid |
| Delete account with 19 shared users | All 19 non-owner shares cascade-revoked, owner share retained |
| Recover account after cascade revoke | Only owner has access, must re-share individually |
| Owner tries to leave | Raises `CannotLeaveAsOwnerError` -- must transfer first |
| Share with 20th user (limit reached) | Raises `MaxSharesReachedError` |
| Revoke share then share again to same user | Allowed -- creates new AccountShare entity |
| Update permission to same level | No-op or allowed (implementation may skip event if no change) |
| Transfer to VIEWER-level user | Allowed -- VIEWER is promoted to OWNER, old owner becomes EDITOR |

---

## 17. Dependencies

### Internal Dependencies

- **Spec 001 (Shared Kernel):** Entity base, DomainEvent, Command, exception hierarchy
- **Spec 007 (Account Management):** Account aggregate, AccountRepository, AccountManagementService

### Blocked By This Spec

- **Spec 009 (Transaction Management):** Uses `account.has_permission(user_id, EDITOR)` for write operations, `VIEWER` for reads
- **Spec 011 (Card Management):** Uses share-based permissions for card operations

---

## 18. Glossary

- **PermissionLevel:** Hierarchical access level (VIEWER < EDITOR < OWNER) determining what a user can do with a shared account
- **AccountShare:** A child entity within the Account aggregate representing a user's access grant to an account
- **Domain Authorization:** Permission checks based on AccountShare, independent from IAM system roles
- **Cascade Revocation:** Automatic revocation of non-owner shares when an account is soft-deleted
- **Self-Leave:** A non-owner user voluntarily removing their own share from an account
- **Ownership Transfer:** Atomic reassignment of OWNER permission from one user to another
