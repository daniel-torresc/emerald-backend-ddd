# Spec 004: System Roles & Admin Permissions

**Version:** 1.0
**Status:** Implemented
**Bounded Context:** Identity & Access Management (IAM)
**Dependencies:** 002 (User Registration & Identity), 003 (Authentication & Sessions)
**Blocks:** None (enabling spec — consumed by presentation layer for portal access)

---

## 1. Overview

This spec defines the system-level role hierarchy, granular admin permissions, SUPERADMIN handling, and portal access rules. System roles determine **which parts of the platform** a user can access (portals), while admin permissions provide fine-grained control **within the admin portal**.

**Key Distinction:** System roles (IAM) determine portal access. Domain authorization (Core Finance, Spec 008) determines what a user can do with specific financial resources. These are fundamentally different concerns that must not be conflated.

---

## 2. Background & Context

### Problem Statement

The platform needs a multi-tier access control system that separates platform administration from regular user functionality. Admins need granular capabilities (managing master data, supporting users, compliance), while a SUPERADMIN serves as the root administrator provisioned only at installation time.

### Business Goals

- Provide secure, granular administrative access to platform operations
- Ensure SUPERADMIN is a protected, immutable root account for emergency and bootstrap operations
- Enable progressive delegation: SUPERADMIN grants admin roles, admins can grant their own permissions to others
- Enforce strict separation between platform-level roles and domain-level authorization

### Success Metrics

- All role transitions pass invariant checks (no inconsistent state)
- SUPERADMIN constraints are enforced at every boundary (no API creation, no deletion, no demotion, no suspension)
- Admin permission checks respect FULL_ADMIN inclusion semantics
- Portal access correctly restricted based on system role

---

## 3. Scope

### In Scope

- `AdminPermission` value object with FULL_ADMIN superset semantics
- `SystemRole` extensions: hierarchy comparison methods (`has_at_least`, `is_admin_or_above`, `can_access_admin_portal`)
- User aggregate extensions: role promotion/demotion, permission grant/revoke, permission checks
- SUPERADMIN provisioning application service
- SUPERADMIN constraints (cannot be created via API, deleted, demoted, or suspended)
- SUPERADMIN session TTL override (15-minute refresh token)
- Portal access rules (main app vs admin portal)
- Admin permission granting rules (cannot grant what you don't have)
- Domain events for all role/permission mutations
- New domain exceptions for role/permission violations

### Out of Scope

- Domain-level authorization for financial resources (Spec 008 — AccountShare / PermissionLevel)
- Admin portal UI/API endpoints (presentation layer)
- Master data management operations (future specs)
- Audit logging of SUPERADMIN actions (Spec 016)

---

## 4. Users & Personas

### Primary Users

- **SUPERADMIN**: Platform root administrator, provisioned at installation. Performs initial setup, promotes users to admins, handles emergency operations.
- **ADMIN**: Delegated administrator with specific permission scopes. Manages master data, supports users, or handles compliance depending on granted permissions.
- **USER**: Standard platform user. Unaffected by this spec except that admin portal access is denied.

### User Goals

- SUPERADMIN: Bootstrap the platform, manage admin team, maintain full control
- ADMIN: Perform delegated administrative tasks within their permission scope
- USER: Continue using the platform without disruption

---

## 5. Value Objects

### 5.1 AdminPermission

Granular capabilities within the admin portal. Implemented as a frozen dataclass wrapping an enum, following the project's value object pattern.

**Enum Values:**

| Value | Description |
|-------|-------------|
| `MASTER_DATA_ADMIN` | Manage financial institutions, account types, currencies |
| `USER_SUPPORT_ADMIN` | View user profiles (not financial data), unlock accounts, reset passwords |
| `COMPLIANCE_ADMIN` | View audit logs, manage retention policies, export compliance reports |
| `FULL_ADMIN` | Superset — includes all other administrative permissions |

**Behavior:**

| Method | Description |
|--------|-------------|
| `includes(other: AdminPermission) -> bool` | Whether this permission covers another. `FULL_ADMIN.includes(X)` is True for all X. Individual permissions only include themselves. |

**Inclusion Rules:**

```
FULL_ADMIN.includes(MASTER_DATA_ADMIN)     == True
FULL_ADMIN.includes(USER_SUPPORT_ADMIN)    == True
FULL_ADMIN.includes(COMPLIANCE_ADMIN)      == True
FULL_ADMIN.includes(FULL_ADMIN)            == True
MASTER_DATA_ADMIN.includes(FULL_ADMIN)     == False
MASTER_DATA_ADMIN.includes(USER_SUPPORT_ADMIN)  == False
COMPLIANCE_ADMIN.includes(MASTER_DATA_ADMIN)    == False
```

### 5.2 SystemRole Extensions

The `SystemRole` enum already exists (Spec 003: USER, ADMIN, SUPERADMIN). This spec adds hierarchy-aware methods.

**New Methods:**

| Method | Description |
|--------|-------------|
| `has_at_least(required: SystemRole) -> bool` | Whether this role meets or exceeds the required level. Uses integer level comparison. |
| `is_admin_or_above() -> bool` | Shorthand for `has_at_least(ADMIN)` |
| `can_access_admin_portal() -> bool` | Alias for `is_admin_or_above()` |

**Level Mapping:**

| Role | Level |
|------|-------|
| USER | 1 |
| ADMIN | 2 |
| SUPERADMIN | 3 |

**Hierarchy Examples:**

```
SUPERADMIN.has_at_least(USER)        == True
SUPERADMIN.has_at_least(ADMIN)       == True
SUPERADMIN.has_at_least(SUPERADMIN)  == True
ADMIN.has_at_least(USER)             == True
ADMIN.has_at_least(ADMIN)            == True
ADMIN.has_at_least(SUPERADMIN)       == False
USER.has_at_least(USER)              == True
USER.has_at_least(ADMIN)             == False
USER.has_at_least(SUPERADMIN)        == False
```

---

## 6. User Aggregate Extensions

This spec extends the User aggregate (Spec 002, extended by Spec 003) with role/permission mutation and query methods.

### 6.1 New Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `admin_permissions` | `frozenset[AdminPermission] \| None` | `None` | Granular admin capabilities. None for USER and SUPERADMIN roles. Non-empty frozenset for ADMIN role. |

**Note:** `system_role` already exists on User (Spec 003, default `SystemRole.USER`). This spec does not add it — it extends the User with methods that mutate it.

### 6.2 Domain Methods

#### Role Management

```
promote_to_admin(permissions: set[AdminPermission], promoted_by_role: SystemRole, promoted_by_id: UUID) -> None
```

Promotes a USER to ADMIN with the given permissions.

**Preconditions:**
- `self.system_role` must be `USER` → else `InvalidRoleTransitionError`
- `permissions` must be non-empty → else `EmptyAdminPermissionsError`
- `promoted_by_role` must be `SUPERADMIN` → else `InsufficientPermissionsError`

**Effects:**
- Sets `system_role = SystemRole.ADMIN`
- Sets `admin_permissions = frozenset(permissions)`
- Records `UserPromotedToAdmin` event
- Calls `_touch()` (updates `updated_at`)

**Design Decision:** The method accepts `promoted_by_role: SystemRole` and `promoted_by_id: UUID` instead of a full `User` object. This avoids loading a second aggregate into memory — the caller (application service) extracts role/id from the authenticated identity. This is consistent with patterns like `soft_delete(deleted_by: UUID, ...)`.

---

```
demote_to_user(demoted_by_role: SystemRole, demoted_by_id: UUID) -> None
```

Demotes an ADMIN to USER, clearing all permissions.

**Preconditions:**
- `self.system_role` must be `ADMIN` → else:
  - If `SUPERADMIN`: `CannotDemoteSuperadminError`
  - If `USER`: `InvalidRoleTransitionError`
- `demoted_by_role` must be `SUPERADMIN` → else `InsufficientPermissionsError`

**Effects:**
- Sets `system_role = SystemRole.USER`
- Sets `admin_permissions = None`
- Records `UserDemotedToUser` event
- Calls `_touch()`

---

#### Admin Permission Management

```
grant_admin_permission(
    permission: AdminPermission,
    granted_by_role: SystemRole,
    granted_by_id: UUID,
    granted_by_has_permission: bool,
) -> None
```

Adds a permission to an existing ADMIN.

**Preconditions:**
- `self.system_role` must be `ADMIN` → else `NotAdminError`
- `granted_by_role` must be `ADMIN` or `SUPERADMIN` → else `InsufficientPermissionsError`
- `granted_by_has_permission` must be `True` → else `CannotGrantUnownedPermissionError`
  - The caller checks this via `has_admin_permission()` on the granting user, which respects FULL_ADMIN inclusion

**Effects:**
- If permission already present: no-op (idempotent)
- Adds permission to `admin_permissions` (creates new frozenset)
- Records `AdminPermissionGranted` event
- Calls `_touch()`

**Note on `granted_by_has_permission`:** The application service calls `granting_user.has_admin_permission(permission)` and passes the result as a boolean. This avoids loading the granting User aggregate into the target User's domain method. The domain method trusts the caller's pre-check — this is the same pattern as passing `promoted_by_role` rather than a full User.

---

```
revoke_admin_permission(permission: AdminPermission, revoked_by_role: SystemRole, revoked_by_id: UUID) -> None
```

Removes a permission from an ADMIN.

**Preconditions:**
- `self.system_role` must be `ADMIN` → else `NotAdminError`
- `revoked_by_role` must be `SUPERADMIN` → else `InsufficientPermissionsError`
- Removing `permission` must not leave `admin_permissions` empty → else `LastAdminPermissionError`
- `permission` must exist in `admin_permissions` → else no-op (idempotent)

**Effects:**
- Removes permission from `admin_permissions` (creates new frozenset)
- Records `AdminPermissionRevoked` event
- Calls `_touch()`

---

#### Permission Checks

```
has_admin_permission(permission: AdminPermission) -> bool
```

Checks whether this user has a specific admin permission.

**Returns True if any of:**
1. `self.system_role` is `SUPERADMIN` (implicit full access, short-circuit)
2. `self.admin_permissions` is not None AND contains `permission`
3. `self.admin_permissions` is not None AND contains `FULL_ADMIN` (FULL_ADMIN includes everything)

**Returns False otherwise** (including when `admin_permissions` is None).

---

```
can_access_admin_portal() -> bool
```

**Returns:** `self.system_role.is_admin_or_above()`

---

### 6.3 SUPERADMIN Constraint Enforcement on Existing Methods

The following existing User methods (from Spec 002) must add SUPERADMIN guards:

| Existing Method | New Guard | Exception |
|----------------|-----------|-----------|
| `soft_delete()` | Reject if `system_role == SUPERADMIN` | `CannotDeleteSuperadminError` |
| `suspend()` | Reject if `system_role == SUPERADMIN` | `CannotSuspendSuperadminError` |

These guards are checked **before** the existing status checks (e.g., before `_require_status()`).

---

## 7. Invariants

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| ID-012 | `system_role` defaults to `USER` on registration | `User.register()` (Spec 002) — already implemented |
| ID-013 | `admin_permissions` must be `None` when `system_role` is `USER` | Checked on `demote_to_user()`. Constructor defaults to `None`. |
| ID-014 | ADMIN must have at least one admin permission | Checked on `promote_to_admin()` (non-empty) and `revoke_admin_permission()` (not last) |
| ID-007 | SUPERADMIN cannot be deleted or demoted | Checked on `soft_delete()` and `demote_to_user()` |
| ID-008 | SUPERADMIN provisioned at install only (no API creation) | `SuperadminProvisioningService` — no API route. Registration service rejects `SUPERADMIN` role. |
| ID-009 | Exactly one SUPERADMIN exists at all times | Provisioning checks no SUPERADMIN exists. SUPERADMIN cannot be demoted or deleted. |
| ID-010 | ADMIN cannot grant permissions they don't have | Checked on `grant_admin_permission()` via `granted_by_has_permission` |
| ID-015 | Non-ADMIN/SUPERADMIN cannot access admin portal | `can_access_admin_portal()` returns False for USER |
| ID-016 | `admin_permissions` must be `None` when `system_role` is `SUPERADMIN` | SUPERADMIN has implicit full access. No stored permissions needed. |

---

## 8. SUPERADMIN Handling

### 8.1 Provisioning

SUPERADMIN is created **only** during platform installation via `SuperadminProvisioningService`, never through any API.

```
SuperadminProvisioningService (Application Service):
  Dependencies: UserRepository, PasswordHasher

  + provision_superadmin(email: str, username: str, password: str) -> User
      1. Validate password strength (same rules as registration)
      2. Check no user with SUPERADMIN role exists via repository
         Raises: SuperadminAlreadyExistsError
      3. Check email/username uniqueness via repository
         Raises: EmailAlreadyExistsError, UsernameAlreadyExistsError
      4. Hash password via PasswordHasher
      5. Create User via User.register(email, username, hashed_password)
      6. Override: system_role = SUPERADMIN, status = ACTIVE, email_verified = True
         (Uses internal _force methods or object.__setattr__ for frozen-field bypass
          since this is a privileged bootstrap operation)
      7. Record SuperadminProvisioned event
      8. Persist user via repository
      9. Return user

  Note: This bypasses normal registration flow — no email verification needed.
        The service is called from a CLI command or installation script, never from an API.
```

**Repository Extension:**

The `UserRepository` protocol gains one new method:

```
exists_by_role(role: SystemRole) -> bool
```

Used by provisioning to check if a SUPERADMIN already exists.

### 8.2 SUPERADMIN Constraints Summary

| Constraint | Description | Enforcement |
|------------|-------------|-------------|
| Cannot be created via API | Only via `SuperadminProvisioningService` | No API route; service is CLI-only |
| Cannot be deleted | `soft_delete()` raises `CannotDeleteSuperadminError` | User aggregate guard |
| Cannot be demoted | `demote_to_user()` raises `CannotDemoteSuperadminError` | User aggregate guard |
| Cannot be suspended | `suspend()` raises `CannotSuspendSuperadminError` | User aggregate guard |
| Implicit full permissions | `has_admin_permission()` always returns True | Role-based short-circuit |
| `admin_permissions` is None | No stored permissions needed | Invariant ID-016 |
| Exactly one in system | Provisioning rejects if one exists | SuperadminProvisioningService check |
| 15-minute refresh token | Regardless of portal context | AuthenticationService override |

### 8.3 SUPERADMIN Session TTL Override

When a SUPERADMIN authenticates, the refresh token TTL is overridden to 15 minutes regardless of portal context.

**New Constant:**

```python
REFRESH_TOKEN_TTL_SUPERADMIN: timedelta = timedelta(minutes=15)
```

Added to `src/emerald/iam/domain/constants.py`.

**TTL Resolution Matrix:**

| User Role | Portal | Refresh Token TTL |
|-----------|--------|-------------------|
| USER | Regular | 7 days |
| ADMIN | Regular | 7 days |
| ADMIN | Admin | 4 hours |
| SUPERADMIN | Any | 15 minutes |

**Enforcement:** The `AuthenticationService.login()` and `AuthenticationService.refresh()` methods check the user's `system_role` and, if `SUPERADMIN`, use `REFRESH_TOKEN_TTL_SUPERADMIN` instead of the portal context's TTL.

---

## 9. Portal Access Rules

| Portal | URL | Allowed Roles | Unauthorized Response |
|--------|-----|---------------|----------------------|
| Main Application | emerald.com | All authenticated users | Standard login redirect |
| Admin Portal | admin.emerald.com | ADMIN, SUPERADMIN | 403 Forbidden |

**Enforcement:** Portal access is checked at the presentation layer using the `system_role` claim from the access token. This is NOT a domain rule — it's an infrastructure/presentation concern that reads domain state.

```
Presentation layer middleware:
  1. Extract system_role from access token claims
  2. If admin portal request AND system_role == USER:
     Return 403 Forbidden
```

This spec provides the domain building blocks (`can_access_admin_portal()`, `SystemRole.is_admin_or_above()`) that the presentation layer consumes. The middleware implementation is out of scope.

---

## 10. Role Transition Rules

### Valid Transitions

| From | To | Initiated By | Method |
|------|-----|-------------|--------|
| USER | ADMIN | SUPERADMIN | `promote_to_admin()` |
| ADMIN | USER | SUPERADMIN | `demote_to_user()` |

### Forbidden Transitions

| From | To | Reason | Exception |
|------|-----|--------|-----------|
| USER | SUPERADMIN | SUPERADMIN is install-only | `InvalidRoleTransitionError` |
| ADMIN | SUPERADMIN | SUPERADMIN is install-only | `InvalidRoleTransitionError` |
| SUPERADMIN | ADMIN | SUPERADMIN cannot be demoted | `CannotDemoteSuperadminError` |
| SUPERADMIN | USER | SUPERADMIN cannot be demoted | `CannotDemoteSuperadminError` |

### Self-Modification Rules

| Action | Allowed? | Reason |
|--------|----------|--------|
| ADMIN changes own permissions | No | Cannot self-escalate. Caller must check `promoted_by_id != self.id` |
| SUPERADMIN changes own role | No | SUPERADMIN is permanent |
| User changes own role | No | Only SUPERADMIN promotes/demotes |

**Note on self-modification enforcement:** The application service (not the aggregate) is responsible for checking that `actor_id != target_user_id` for role/permission mutations. This keeps the aggregate free from identity-checking logic that belongs at the application layer.

---

## 11. Domain Events

All events extend `DomainEvent` (frozen dataclass) with `aggregate_type = "User"`.

| Event | Trigger | Key Data |
|-------|---------|----------|
| `UserPromotedToAdmin` | `promote_to_admin()` | `user_id`, `permissions: frozenset[str]`, `promoted_by_id: UUID` |
| `UserDemotedToUser` | `demote_to_user()` | `user_id`, `demoted_by_id: UUID` |
| `AdminPermissionGranted` | `grant_admin_permission()` | `user_id`, `permission: str`, `granted_by_id: UUID` |
| `AdminPermissionRevoked` | `revoke_admin_permission()` | `user_id`, `permission: str`, `revoked_by_id: UUID` |
| `SuperadminProvisioned` | `provision_superadmin()` | `user_id` |

**Event data conventions:**
- Permissions are serialized as strings (enum `.value`) for event portability
- `user_id` is the `aggregate_id` from the base `DomainEvent`
- `*_by_id` fields identify the actor who performed the operation

---

## 12. Exceptions

All exceptions follow the shared kernel hierarchy with unique codes.

### New Exceptions

| Exception | Base Class | Code | Trigger |
|-----------|-----------|------|---------|
| `InvalidRoleTransitionError` | `InvariantViolationError` | `INVALID_ROLE_TRANSITION` | Promoting non-USER or forbidden transition |
| `CannotDemoteSuperadminError` | `InvariantViolationError` | `CANNOT_DEMOTE_SUPERADMIN` | Attempting to demote SUPERADMIN |
| `CannotDeleteSuperadminError` | `InvariantViolationError` | `CANNOT_DELETE_SUPERADMIN` | Attempting to soft-delete SUPERADMIN |
| `CannotSuspendSuperadminError` | `InvariantViolationError` | `CANNOT_SUSPEND_SUPERADMIN` | Attempting to suspend SUPERADMIN |
| `EmptyAdminPermissionsError` | `InvalidValueError` | `EMPTY_ADMIN_PERMISSIONS` | Promoting with empty permissions set |
| `InsufficientPermissionsError` | `DomainError` | `INSUFFICIENT_PERMISSIONS` | Non-SUPERADMIN trying to promote/demote, or non-admin trying to grant |
| `NotAdminError` | `InvariantViolationError` | `NOT_ADMIN` | Granting/revoking permission on non-ADMIN user |
| `CannotGrantUnownedPermissionError` | `DomainError` | `CANNOT_GRANT_UNOWNED_PERMISSION` | ADMIN trying to grant a permission they don't have |
| `LastAdminPermissionError` | `InvariantViolationError` | `LAST_ADMIN_PERMISSION` | Revoking would leave ADMIN with zero permissions |
| `SuperadminAlreadyExistsError` | `AlreadyExistsError` | `SUPERADMIN_ALREADY_EXISTS` | Provisioning when SUPERADMIN already exists |

---

## 13. Application Layer

### 13.1 Commands

New commands (frozen dataclasses extending `Command`):

```
PromoteToAdmin:
  user_id: str          # Target user ID
  permissions: list[str] # AdminPermission values (e.g., ["MASTER_DATA_ADMIN", "COMPLIANCE_ADMIN"])
  promoted_by_id: str    # Actor user ID (from authenticated identity)

DemoteToUser:
  user_id: str          # Target user ID
  demoted_by_id: str    # Actor user ID

GrantAdminPermission:
  user_id: str          # Target user ID
  permission: str       # AdminPermission value
  granted_by_id: str    # Actor user ID

RevokeAdminPermission:
  user_id: str          # Target user ID
  permission: str       # AdminPermission value
  revoked_by_id: str    # Actor user ID

ProvisionSuperadmin:
  email: str
  username: str
  password: str
```

### 13.2 RoleManagementService (Application Service)

Handles role promotion/demotion and permission grant/revoke operations.

```
RoleManagementService:
  Dependencies: AbstractIamUnitOfWork

  + promote_to_admin(cmd: PromoteToAdmin) -> None
      1. Parse UUIDs from command
      2. Load actor user from repository → check actor.system_role == SUPERADMIN
      3. Validate actor_id != target_user_id (self-promotion guard)
      4. Load target user from repository
      5. Parse permissions from command strings → set[AdminPermission]
      6. Call target_user.promote_to_admin(permissions, actor_role, actor_id)
      7. Save target user, commit

  + demote_to_user(cmd: DemoteToUser) -> None
      1. Parse UUIDs
      2. Load actor → check SUPERADMIN
      3. Validate actor_id != target_user_id
      4. Load target user
      5. Call target_user.demote_to_user(actor_role, actor_id)
      6. Save, commit

  + grant_admin_permission(cmd: GrantAdminPermission) -> None
      1. Parse UUIDs and permission
      2. Load actor user
      3. Check actor.system_role is ADMIN or SUPERADMIN
      4. Validate actor_id != target_user_id (self-grant guard)
      5. Check actor.has_admin_permission(permission) → passes result as bool
      6. Load target user
      7. Call target_user.grant_admin_permission(permission, actor_role, actor_id, has_perm)
      8. Save, commit

  + revoke_admin_permission(cmd: RevokeAdminPermission) -> None
      1. Parse UUIDs and permission
      2. Load actor → check SUPERADMIN
      3. Validate actor_id != target_user_id
      4. Load target user
      5. Call target_user.revoke_admin_permission(permission, actor_role, actor_id)
      6. Save, commit
```

### 13.3 SuperadminProvisioningService (Application Service)

See Section 8.1 for full specification.

### 13.4 AuthenticationService Modifications

The existing `AuthenticationService` (Spec 003) is modified to support SUPERADMIN session TTL override.

**Changes to `login()`:**
- After resolving `portal_context`, check if user's `system_role == SUPERADMIN`
- If yes, use `REFRESH_TOKEN_TTL_SUPERADMIN` (15 minutes) instead of `portal_context.refresh_ttl`

**Changes to `refresh()`:**
- When creating the replacement refresh token, check user's `system_role`
- If `SUPERADMIN`, use `REFRESH_TOKEN_TTL_SUPERADMIN` for the new token's `expires_at`

---

## 14. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Promote a user who is already ADMIN | `InvalidRoleTransitionError` (must be USER) |
| Promote with empty permissions set | `EmptyAdminPermissionsError` |
| Demote a SUPERADMIN | `CannotDemoteSuperadminError` |
| Demote a USER (already lowest) | `InvalidRoleTransitionError` |
| Grant permission to USER | `NotAdminError` |
| Grant permission to SUPERADMIN | `NotAdminError` (SUPERADMIN has implicit perms, no stored perms) |
| ADMIN grants permission they don't have | `CannotGrantUnownedPermissionError` |
| Revoke last permission from ADMIN | `LastAdminPermissionError` |
| Revoke permission ADMIN doesn't have | No-op (idempotent) |
| Grant permission ADMIN already has | No-op (idempotent) |
| Self-promote/demote/grant | Blocked at application service level (actor_id != target_id) |
| Provision SUPERADMIN when one exists | `SuperadminAlreadyExistsError` |
| Delete SUPERADMIN | `CannotDeleteSuperadminError` |
| Suspend SUPERADMIN | `CannotSuspendSuperadminError` |
| SUPERADMIN login on any portal | 15-minute refresh token TTL |
| ADMIN with FULL_ADMIN grants MASTER_DATA_ADMIN | Allowed — `has_admin_permission()` returns True for FULL_ADMIN holders |

---

## 15. Dependencies

### Internal Dependencies

- **Spec 001 (Shared Kernel):** Base types, DomainEvent, Entity, AggregateRoot, exception hierarchy
- **Spec 002 (User Registration & Identity):** User aggregate, UserRepository, registration flow
- **Spec 003 (Authentication & Sessions):** SystemRole enum, AuthenticationService, AccessTokenClaims, PortalContext, session TTL constants

### What This Spec Modifies in Prior Specs

| Artifact | Change |
|----------|--------|
| `SystemRole` (Spec 003) | Add `has_at_least()`, `is_admin_or_above()`, `can_access_admin_portal()` methods |
| `User` aggregate (Spec 002) | Add `admin_permissions` attribute; add role/permission methods; add SUPERADMIN guards on `soft_delete()` and `suspend()` |
| `UserRepository` (Spec 002) | Add `exists_by_role()` method |
| `AuthenticationService` (Spec 003) | Override refresh TTL for SUPERADMIN |
| `constants.py` (Spec 003) | Add `REFRESH_TOKEN_TTL_SUPERADMIN` |
| IAM `__init__.py` | Re-export all new public types |

---

## 16. Acceptance Criteria

### AC-01: SystemRole Hierarchy

- [ ] `USER.has_at_least(USER)` returns True
- [ ] `USER.has_at_least(ADMIN)` returns False
- [ ] `USER.has_at_least(SUPERADMIN)` returns False
- [ ] `ADMIN.has_at_least(USER)` returns True
- [ ] `ADMIN.has_at_least(ADMIN)` returns True
- [ ] `ADMIN.has_at_least(SUPERADMIN)` returns False
- [ ] `SUPERADMIN.has_at_least(USER)` returns True
- [ ] `SUPERADMIN.has_at_least(ADMIN)` returns True
- [ ] `SUPERADMIN.has_at_least(SUPERADMIN)` returns True
- [ ] `USER.is_admin_or_above()` returns False
- [ ] `ADMIN.is_admin_or_above()` returns True
- [ ] `SUPERADMIN.is_admin_or_above()` returns True
- [ ] `USER.can_access_admin_portal()` returns False
- [ ] `ADMIN.can_access_admin_portal()` returns True
- [ ] `SUPERADMIN.can_access_admin_portal()` returns True

### AC-02: AdminPermission

- [ ] `FULL_ADMIN.includes(MASTER_DATA_ADMIN)` returns True
- [ ] `FULL_ADMIN.includes(USER_SUPPORT_ADMIN)` returns True
- [ ] `FULL_ADMIN.includes(COMPLIANCE_ADMIN)` returns True
- [ ] `FULL_ADMIN.includes(FULL_ADMIN)` returns True
- [ ] `MASTER_DATA_ADMIN.includes(FULL_ADMIN)` returns False
- [ ] `MASTER_DATA_ADMIN.includes(USER_SUPPORT_ADMIN)` returns False
- [ ] `MASTER_DATA_ADMIN.includes(MASTER_DATA_ADMIN)` returns True

### AC-03: Role Promotion

- [ ] SUPERADMIN can promote USER to ADMIN with one or more permissions
- [ ] Promoted user's `system_role` becomes `ADMIN`
- [ ] Promoted user's `admin_permissions` contains exactly the given permissions
- [ ] Promoting with empty permissions raises `EmptyAdminPermissionsError`
- [ ] Promoting non-USER raises `InvalidRoleTransitionError`
- [ ] Non-SUPERADMIN promoting raises `InsufficientPermissionsError`
- [ ] `UserPromotedToAdmin` event is recorded with correct data

### AC-04: Role Demotion

- [ ] SUPERADMIN can demote ADMIN to USER
- [ ] Demoted user's `system_role` becomes `USER`
- [ ] Demoted user's `admin_permissions` becomes `None`
- [ ] Demoting SUPERADMIN raises `CannotDemoteSuperadminError`
- [ ] Demoting USER raises `InvalidRoleTransitionError`
- [ ] Non-SUPERADMIN demoting raises `InsufficientPermissionsError`
- [ ] `UserDemotedToUser` event is recorded with correct data

### AC-05: Permission Grant

- [ ] ADMIN with matching permission can grant to other ADMIN
- [ ] ADMIN with FULL_ADMIN can grant any individual permission
- [ ] SUPERADMIN can grant any permission
- [ ] Granting to non-ADMIN raises `NotAdminError`
- [ ] ADMIN without the permission raises `CannotGrantUnownedPermissionError`
- [ ] Non-ADMIN/SUPERADMIN granting raises `InsufficientPermissionsError`
- [ ] Granting already-held permission is idempotent (no error, no event)
- [ ] `AdminPermissionGranted` event is recorded with correct data

### AC-06: Permission Revoke

- [ ] SUPERADMIN can revoke permission from ADMIN
- [ ] Revoking last permission raises `LastAdminPermissionError`
- [ ] Non-SUPERADMIN revoking raises `InsufficientPermissionsError`
- [ ] Revoking from non-ADMIN raises `NotAdminError`
- [ ] Revoking non-held permission is idempotent (no error, no event)
- [ ] `AdminPermissionRevoked` event is recorded with correct data

### AC-07: Permission Checks

- [ ] `has_admin_permission()` returns True for SUPERADMIN regardless of permission
- [ ] `has_admin_permission()` returns True for ADMIN with matching permission
- [ ] `has_admin_permission()` returns True for ADMIN with FULL_ADMIN (any permission)
- [ ] `has_admin_permission()` returns False for ADMIN without the permission
- [ ] `has_admin_permission()` returns False for USER
- [ ] `can_access_admin_portal()` returns True for ADMIN and SUPERADMIN
- [ ] `can_access_admin_portal()` returns False for USER

### AC-08: SUPERADMIN Constraints

- [ ] SUPERADMIN cannot be created via `User.register()` (provisioning only)
- [ ] SUPERADMIN cannot be soft deleted — raises `CannotDeleteSuperadminError`
- [ ] SUPERADMIN cannot be suspended — raises `CannotSuspendSuperadminError`
- [ ] SUPERADMIN cannot be demoted — raises `CannotDemoteSuperadminError`
- [ ] SUPERADMIN `has_admin_permission()` returns True for any permission
- [ ] SUPERADMIN `admin_permissions` is None (implicit access, not stored)

### AC-09: SUPERADMIN Provisioning

- [ ] Provisioning creates user with SUPERADMIN role, ACTIVE status, email_verified=True
- [ ] Provisioning fails if SUPERADMIN already exists (`SuperadminAlreadyExistsError`)
- [ ] Provisioning validates email/username uniqueness
- [ ] Provisioning validates password strength
- [ ] `SuperadminProvisioned` event is recorded

### AC-10: SUPERADMIN Session TTL

- [ ] SUPERADMIN login produces refresh token with 15-minute TTL regardless of portal
- [ ] SUPERADMIN token refresh produces new refresh token with 15-minute TTL
- [ ] ADMIN login on admin portal produces 4-hour TTL (unchanged)
- [ ] USER login produces 7-day TTL (unchanged)

### AC-11: Invariant Consistency

- [ ] `admin_permissions` is always `None` when `system_role` is `USER`
- [ ] `admin_permissions` is always `None` when `system_role` is `SUPERADMIN`
- [ ] `admin_permissions` is always non-empty when `system_role` is `ADMIN`
- [ ] No role transition leaves the entity in an inconsistent state

### AC-12: Self-Modification Prevention (Application Layer)

- [ ] Actor cannot promote themselves
- [ ] Actor cannot demote themselves
- [ ] Actor cannot grant permissions to themselves
- [ ] Actor cannot revoke permissions from themselves

---

## 17. Glossary

- **SystemRole**: Platform-wide role determining access level (USER, ADMIN, SUPERADMIN)
- **AdminPermission**: Granular capability within the admin portal
- **SUPERADMIN**: Root administrator provisioned at installation; immutable role with implicit full access
- **Portal**: A web application entry point (main app or admin portal) with distinct access rules
- **Promotion**: Transitioning a user from USER to ADMIN role
- **Demotion**: Transitioning a user from ADMIN to USER role

---

## Implementation Notes

> This specification should be implemented following **Clean Architecture** patterns with ports-and-adapters structure, consistent with the existing IAM bounded context organization.
>
> Key implementation considerations:
> - `AdminPermission` is a new value object in `src/emerald/iam/domain/models/`
> - `SystemRole` is extended in-place (same file, new methods)
> - User aggregate gains new methods and the `admin_permissions` attribute
> - `SuperadminProvisioningService` is a new application service
> - `RoleManagementService` is a new application service
> - `AuthenticationService` modifications are minimal (TTL override)
> - All new exceptions go in `src/emerald/iam/domain/exceptions/`
> - All new events go in `src/emerald/iam/domain/events/`
> - New commands go in `src/emerald/iam/application/dto/`
> - Test fakes and factory helpers in `tests/unit/iam/fakes.py`
