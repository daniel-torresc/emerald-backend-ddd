# Spec 004: System Roles & Admin Permissions

**Status:** Draft
**Bounded Context:** Identity & Access Management (IAM)
**Dependencies:** 002 (User Registration & Identity), 003 (Authentication & Sessions)
**Blocks:** None (enabling spec — consumed by presentation layer for portal access)

---

## 1. Overview

This spec defines the system-level role hierarchy, granular admin permissions, SUPERADMIN handling, and portal access rules. System roles determine **which parts of the platform** a user can access (portals), while admin permissions provide fine-grained control **within the admin portal**.

**Key Distinction:** System roles (IAM) determine portal access. Domain authorization (Core Finance, Spec 008) determines what a user can do with specific financial resources. These are fundamentally different concerns that must not be conflated.

## 2. Scope

### In Scope

- `SystemRole` value object with hierarchy (USER < ADMIN < SUPERADMIN)
- `AdminPermission` enum and rules
- Role assignment and promotion/demotion
- SUPERADMIN provisioning and constraints
- Portal access rules (emerald.com vs admin.emerald.com)
- Admin permission granting rules

### Out of Scope

- Domain-level authorization for financial resources (Spec 008 — AccountShare / PermissionLevel)
- Admin portal UI/API endpoints (presentation layer)
- Master data management operations (future specs)

## 3. Value Objects

### 3.1 SystemRole

Hierarchical role determining platform access level.

**Enum with Hierarchy:**

| Value | Level | Default | Description |
|-------|-------|---------|-------------|
| USER | 1 | Yes | Full financial tracking, collaboration |
| ADMIN | 2 | No | All USER + admin portal access |
| SUPERADMIN | 3 | No | All ADMIN + bootstrap, emergency access |

**Behavior:**

| Method | Description |
|--------|-------------|
| `has_at_least(required: SystemRole) -> bool` | Whether this role meets or exceeds the required level |
| `is_admin_or_above() -> bool` | Shorthand for `has_at_least(ADMIN)` |
| `can_access_admin_portal() -> bool` | Whether this role grants admin portal access |

**Hierarchy Rule:**

```
SUPERADMIN > ADMIN > USER

SUPERADMIN.has_at_least(USER)      == True
SUPERADMIN.has_at_least(ADMIN)     == True
ADMIN.has_at_least(USER)           == True
ADMIN.has_at_least(SUPERADMIN)     == False
USER.has_at_least(ADMIN)           == False
```

### 3.2 AdminPermission

Granular capabilities within the admin portal.

**Enum:**

| Value | Description |
|-------|-------------|
| MASTER_DATA_ADMIN | Manage financial institutions, account types, currencies |
| USER_SUPPORT_ADMIN | View user profiles (not financial data), unlock accounts, reset passwords |
| COMPLIANCE_ADMIN | View audit logs, manage retention policies, export compliance reports |
| FULL_ADMIN | All administrative permissions (convenience superset) |

**Behavior:**

| Method | Description |
|--------|-------------|
| `includes(other: AdminPermission) -> bool` | Whether this permission covers another |

**Inclusion Rule:**

```
FULL_ADMIN.includes(MASTER_DATA_ADMIN)  == True
FULL_ADMIN.includes(USER_SUPPORT_ADMIN) == True
FULL_ADMIN.includes(COMPLIANCE_ADMIN)   == True
MASTER_DATA_ADMIN.includes(FULL_ADMIN)  == False
```

## 4. User Entity Extensions

This spec extends the User entity (defined in Spec 002) with role and permission behavior.

### 4.1 Role-Related Attributes (from Spec 002)

| Attribute | Type | Description |
|-----------|------|-------------|
| system_role | SystemRole | USER (default), ADMIN, or SUPERADMIN |
| admin_permissions | set[AdminPermission]? | Granular admin capabilities (None for USER) |

### 4.2 Domain Methods

```
User:
  // Role management
  + promote_to_admin(permissions: set[AdminPermission], promoted_by: User) -> None
      Validates:
        - Current role is USER
        - permissions is non-empty
        - promoted_by has SUPERADMIN role
      Sets: system_role = ADMIN, admin_permissions = permissions
      Raises: InvalidRoleTransitionError, InsufficientPermissionsError,
              EmptyAdminPermissionsError

  + demote_to_user(demoted_by: User) -> None
      Validates:
        - Current role is ADMIN (not SUPERADMIN)
        - demoted_by has SUPERADMIN role
      Sets: system_role = USER, admin_permissions = None
      Raises: InvalidRoleTransitionError, CannotDemoteSuperadminError

  // Admin permission management
  + grant_admin_permission(permission: AdminPermission, granted_by: User) -> None
      Validates:
        - Current role is ADMIN
        - granted_by is ADMIN or SUPERADMIN
        - granted_by has the permission being granted (or is SUPERADMIN)
      Adds: permission to admin_permissions
      Raises: NotAdminError, InsufficientPermissionsError,
              CannotGrantUnownedPermissionError

  + revoke_admin_permission(permission: AdminPermission, revoked_by: User) -> None
      Validates:
        - Current role is ADMIN
        - revoked_by has SUPERADMIN role (only SUPERADMIN can revoke)
        - Revoking won't leave admin_permissions empty
      Removes: permission from admin_permissions
      Raises: NotAdminError, InsufficientPermissionsError,
              LastAdminPermissionError

  // Permission checks
  + has_admin_permission(permission: AdminPermission) -> bool
      Returns True if:
        - system_role is SUPERADMIN (implicitly has all), OR
        - admin_permissions contains permission, OR
        - admin_permissions contains FULL_ADMIN

  + can_access_admin_portal() -> bool
      Returns: system_role.is_admin_or_above()
```

## 5. Invariants

These rules must **always** hold true on the User entity regarding roles and permissions:

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| ID-012 | `system_role` defaults to USER on registration | `User.register()` (Spec 002) |
| ID-013 | `admin_permissions` must be None when `system_role` is USER | Checked on every role change |
| ID-014 | ADMIN must have at least one admin permission | Checked on role promotion and permission revocation |
| ID-007 | SUPERADMIN cannot be deleted or demoted | Checked on `demote_to_user()` and `soft_delete()` |
| ID-008 | SUPERADMIN provisioned at install only (no API creation) | Domain service rejects role=SUPERADMIN in registration |
| ID-009 | At least one SUPERADMIN must exist at all times | Domain service (checked before any SUPERADMIN demotion — N/A since SUPERADMIN can't be demoted) |
| ID-010 | ADMIN cannot grant permissions they don't have | Checked on `grant_admin_permission()` |
| ID-015 | Non-ADMIN/SUPERADMIN cannot access admin portal | `can_access_admin_portal()` returns False for USER |

## 6. SUPERADMIN Handling

### 6.1 Provisioning

SUPERADMIN is created **only** during platform installation, never through any API.

```
SuperadminProvisioningService:
  + provision_superadmin(email: str, username: str, password: str) -> User
      1. Check no SUPERADMIN exists (first-time setup only)
         Raises: SuperadminAlreadyExistsError
      2. Create User via register()
      3. Override: system_role = SUPERADMIN, status = ACTIVE, email_verified = True
      4. Return user
      Note: This bypasses normal registration (no email verification needed)
```

### 6.2 SUPERADMIN Constraints

| Constraint | Description |
|------------|-------------|
| Cannot be created via API | Only provisioned at installation |
| Cannot be deleted | `soft_delete()` raises `CannotDeleteSuperadminError` |
| Cannot be demoted | `demote_to_user()` raises `CannotDemoteSuperadminError` |
| Cannot be suspended | `suspend()` raises `CannotSuspendSuperadminError` |
| Implicit full permissions | `has_admin_permission()` always returns True |
| Enhanced audit logging | All SUPERADMIN actions logged with extra detail |
| Session timeout | 15 minutes (non-configurable) — enforced via shorter refresh token |

### 6.3 SUPERADMIN Session Override

When a SUPERADMIN authenticates, the refresh token TTL is overridden regardless of portal context:

| User Role | Portal | Refresh Token TTL |
|-----------|--------|-------------------|
| USER | Regular | 7 days |
| ADMIN | Regular | 7 days |
| ADMIN | Admin | 4 hours |
| SUPERADMIN | Any | 15 minutes |

## 7. Portal Access Rules

| Portal | URL | Allowed Roles | Unauthorized Response |
|--------|-----|---------------|----------------------|
| Main Application | emerald.com | All authenticated users | Standard login redirect |
| Admin Portal | admin.emerald.com | ADMIN, SUPERADMIN | 403 Forbidden |

**Enforcement:**

Portal access is checked at the presentation layer using the `system_role` claim from the access token. This is NOT a domain rule — it's an infrastructure/presentation concern that reads domain state.

```
Presentation layer middleware:
  1. Extract system_role from access token
  2. If admin portal request and system_role == USER:
     Return 403 Forbidden
```

## 8. Role Transition Rules

### Valid Transitions

| From | To | Initiated By | Method |
|------|-----|-------------|--------|
| USER | ADMIN | SUPERADMIN | `promote_to_admin()` |
| ADMIN | USER | SUPERADMIN | `demote_to_user()` |

### Forbidden Transitions

| From | To | Reason |
|------|-----|--------|
| USER | SUPERADMIN | SUPERADMIN is install-only |
| ADMIN | SUPERADMIN | SUPERADMIN is install-only |
| SUPERADMIN | ADMIN | SUPERADMIN cannot be demoted |
| SUPERADMIN | USER | SUPERADMIN cannot be demoted |

### Self-Modification Rules

| Action | Allowed? | Reason |
|--------|----------|--------|
| ADMIN changes own permissions | No | Cannot self-escalate |
| SUPERADMIN changes own role | No | SUPERADMIN is permanent |
| User changes own role | No | Only SUPERADMIN promotes/demotes |

## 9. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `UserPromotedToAdmin` | `promote_to_admin()` | user_id, permissions, promoted_by |
| `UserDemotedToUser` | `demote_to_user()` | user_id, demoted_by |
| `AdminPermissionGranted` | `grant_admin_permission()` | user_id, permission, granted_by |
| `AdminPermissionRevoked` | `revoke_admin_permission()` | user_id, permission, revoked_by |
| `SuperadminProvisioned` | `provision_superadmin()` | user_id |

## 10. Acceptance Criteria

### SystemRole

- [ ] `USER.has_at_least(USER)` returns True
- [ ] `USER.has_at_least(ADMIN)` returns False
- [ ] `ADMIN.has_at_least(USER)` returns True
- [ ] `ADMIN.has_at_least(SUPERADMIN)` returns False
- [ ] `SUPERADMIN.has_at_least(*)` returns True for all roles
- [ ] Only ADMIN and SUPERADMIN can access admin portal

### AdminPermission

- [ ] `FULL_ADMIN.includes()` returns True for all other permissions
- [ ] Individual permissions do not include each other

### Role Promotion / Demotion

- [ ] SUPERADMIN can promote USER to ADMIN with permissions
- [ ] Promoting to ADMIN requires at least one permission
- [ ] Promoting to ADMIN with empty permissions raises `EmptyAdminPermissionsError`
- [ ] SUPERADMIN can demote ADMIN to USER (clears admin_permissions to None)
- [ ] Non-SUPERADMIN cannot promote or demote
- [ ] Nobody can be promoted to SUPERADMIN
- [ ] SUPERADMIN cannot be demoted

### Admin Permission Management

- [ ] ADMIN/SUPERADMIN can grant permissions to other ADMINs
- [ ] ADMIN cannot grant a permission they don't have themselves
- [ ] SUPERADMIN can grant any permission (implicit full access)
- [ ] Only SUPERADMIN can revoke permissions
- [ ] Cannot revoke last admin permission (would violate ID-014)

### SUPERADMIN Constraints

- [ ] SUPERADMIN cannot be created via normal registration flow
- [ ] SUPERADMIN cannot be soft deleted — raises `CannotDeleteSuperadminError`
- [ ] SUPERADMIN cannot be suspended — raises `CannotSuspendSuperadminError`
- [ ] SUPERADMIN `has_admin_permission()` returns True for any permission
- [ ] SUPERADMIN refresh token TTL is 15 minutes regardless of portal

### Invariants

- [ ] `admin_permissions` is always None when `system_role` is USER
- [ ] `admin_permissions` is always non-empty when `system_role` is ADMIN
- [ ] State is never inconsistent — every role transition enforces both invariants atomically

### Domain Events

- [ ] Promotion emits `UserPromotedToAdmin` with correct data
- [ ] Demotion emits `UserDemotedToUser` with correct data
- [ ] Permission grant/revoke emits corresponding events
- [ ] SUPERADMIN provisioning emits `SuperadminProvisioned`
