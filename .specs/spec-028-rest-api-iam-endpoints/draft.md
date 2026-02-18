# Spec 028: REST API — IAM Endpoints

**Status:** Draft
**Bounded Context:** IAM (Presentation)
**Dependencies:** 027 (API Middleware & Common HTTP), 002-005 (IAM domain specs)
**Blocks:** 031

---

## 1. Overview

This spec defines all IAM HTTP routes — authentication, registration, social login, user profile management, and admin role management. All endpoints use the middleware and auth dependencies from spec 027.

**Key Principle:** Thin controllers — endpoint handlers validate input, delegate to domain services, and map domain results to HTTP responses. No business logic in the presentation layer.

## 2. Scope

### In Scope

- Auth routes: register, login, refresh, logout, password reset
- Social login routes: authorize URL, callback, link, unlink, set username
- User profile routes: get, update
- Admin routes: promote, demote, grant/revoke permissions, provision superadmin

### Out of Scope

- User listing/search (admin portal — future spec)
- Account/session management UI (presentation concern)
- Email sending (infrastructure concern — for password reset)

## 3. Auth Routes

### 3.1 Register

```
POST /api/v1/auth/register

Request Body:
{
    "email": "user@example.com",
    "username": "johndoe",
    "password": "SecureP@ss123",
    "full_name": "John Doe"
}

Response 201:
{
    "user_id": "uuid",
    "email": "user@example.com",
    "username": "johndoe",
    "status": "PENDING_VERIFICATION"
}

Errors:
    400 — Invalid email/password/username format
    409 — Email or username already taken
```

**Auth:** None (public)
**Service:** `RegistrationService.register()`

### 3.2 Login

```
POST /api/v1/auth/login

Request Body:
{
    "email": "user@example.com",
    "password": "SecureP@ss123",
    "portal_context": "USER"      // optional, default USER
}

Response 200:
{
    "access_token": "eyJ...",
    "refresh_token": "random-string",
    "token_type": "Bearer",
    "expires_in": 900,
    "user": {
        "user_id": "uuid",
        "email": "user@example.com",
        "username": "johndoe",
        "system_role": "USER"
    }
}

Errors:
    401 — Invalid credentials
    403 — Account suspended or inactive
```

**Auth:** None (public)
**Service:** `AuthenticationService.login()`

### 3.3 Refresh Token

```
POST /api/v1/auth/refresh

Request Body:
{
    "refresh_token": "random-string"
}

Response 200:
{
    "access_token": "eyJ...",
    "refresh_token": "new-random-string",
    "token_type": "Bearer",
    "expires_in": 900
}

Errors:
    401 — Invalid, expired, or revoked refresh token
```

**Auth:** None (uses refresh token instead)
**Service:** `AuthenticationService.refresh()`

### 3.4 Logout

```
POST /api/v1/auth/logout

Request Body:
{
    "refresh_token": "random-string"
}

Response 204: (no content)

Errors:
    401 — Invalid token
```

**Auth:** Bearer token required
**Service:** `AuthenticationService.logout()`

### 3.5 Logout All Sessions

```
POST /api/v1/auth/logout-all

Response 204: (no content)
```

**Auth:** Bearer token required
**Service:** `AuthenticationService.logout_all()`

### 3.6 Request Password Reset

```
POST /api/v1/auth/password-reset/request

Request Body:
{
    "email": "user@example.com"
}

Response 202: (accepted — always returns 202 regardless of email existence)
{
    "message": "If the email exists, a reset link will be sent."
}
```

**Auth:** None (public)
**Service:** `AuthenticationService.request_password_reset()`
**Note:** Always returns 202 to prevent email enumeration.

### 3.7 Submit Password Reset

```
POST /api/v1/auth/password-reset/submit

Request Body:
{
    "token": "reset-token-string",
    "new_password": "NewSecureP@ss456"
}

Response 200:
{
    "message": "Password reset successfully."
}

Errors:
    400 — Invalid or expired token
    400 — Password doesn't meet requirements
```

**Auth:** None (uses reset token)
**Service:** `AuthenticationService.submit_password_reset()`

## 4. Social Login Routes

### 4.1 Get Authorization URL

```
GET /api/v1/auth/social/{provider}/authorize

Path Params:
    provider: "google" | "microsoft"

Query Params:
    state: string (CSRF token)
    nonce: string (replay protection)

Response 200:
{
    "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}

Errors:
    400 — Unsupported provider
    400 — Provider not configured
```

**Auth:** None (public)
**Service:** `OidcProvider.get_authorization_url()`

### 4.2 Social Login Callback

```
POST /api/v1/auth/social/{provider}/callback

Request Body:
{
    "code": "authorization-code",
    "state": "csrf-token",
    "code_verifier": "pkce-verifier"   // optional
}

Response 200:
{
    "access_token": "eyJ...",
    "refresh_token": "random-string",
    "token_type": "Bearer",
    "expires_in": 900,
    "is_new_registration": false,
    "user": { ... }
}

Errors:
    401 — Invalid authorization code
    409 — External ID already linked to different user
```

**Auth:** None (uses OAuth code)
**Service:** `AuthenticationService.login_with_provider()`

### 4.3 Link Provider

```
POST /api/v1/auth/social/link

Request Body:
{
    "provider": "google",
    "code": "authorization-code",
    "code_verifier": "pkce-verifier"
}

Response 200:
{
    "message": "Provider linked successfully.",
    "provider": "google"
}

Errors:
    401 — Unauthorized
    409 — Provider already linked or external ID taken
```

**Auth:** Bearer token required
**Service:** `AuthenticationService.link_provider()`

### 4.4 Unlink Provider

```
POST /api/v1/auth/social/unlink

Request Body:
{
    "provider": "google"
}

Response 200:
{
    "message": "Provider unlinked successfully."
}

Errors:
    401 — Unauthorized
    409 — Cannot unlink last auth method (no password set)
```

**Auth:** Bearer token required
**Service:** `AuthenticationService.unlink_provider()`

### 4.5 Set Onboarding Username

```
POST /api/v1/auth/social/set-username

Request Body:
{
    "username": "johndoe"
}

Response 200:
{
    "message": "Username set successfully.",
    "username": "johndoe"
}

Errors:
    400 — Invalid username format
    409 — Username already taken
    409 — Username already set
```

**Auth:** Bearer token required
**Service:** `AuthenticationService.set_onboarding_username()`

## 5. User Profile Routes

### 5.1 Get Current User

```
GET /api/v1/users/me

Response 200:
{
    "user_id": "uuid",
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "status": "ACTIVE",
    "system_role": "USER",
    "auth_providers": ["google"],
    "email_verified_at": "2024-01-15T10:30:00Z",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
}
```

**Auth:** Bearer token required
**Service:** Reads from `UserRepository.find_by_id()`

### 5.2 Update Profile

```
PATCH /api/v1/users/me

Request Body (all fields optional):
{
    "full_name": "John A. Doe",
    "username": "johndoe_updated"
}

Response 200:
{
    "user_id": "uuid",
    "email": "user@example.com",
    "username": "johndoe_updated",
    "full_name": "John A. Doe",
    ...
}

Errors:
    400 — Invalid format
    409 — Username already taken
```

**Auth:** Bearer token required
**Service:** Domain service (update user fields)

## 6. Admin Routes

### 6.1 Promote User to Admin

```
POST /api/v1/admin/users/{user_id}/promote

Request Body:
{
    "permissions": ["USER_MANAGEMENT", "COMPLIANCE_ADMIN"]
}

Response 200:
{
    "user_id": "uuid",
    "system_role": "ADMIN",
    "admin_permissions": ["USER_MANAGEMENT", "COMPLIANCE_ADMIN"]
}

Errors:
    403 — Not SUPERADMIN
    404 — User not found
    409 — User already admin or above
```

**Auth:** Bearer token required (SUPERADMIN only)
**Service:** `RoleManagementService.promote()`

### 6.2 Demote Admin to User

```
POST /api/v1/admin/users/{user_id}/demote

Response 200:
{
    "user_id": "uuid",
    "system_role": "USER",
    "admin_permissions": []
}

Errors:
    403 — Not SUPERADMIN
    404 — User not found
    409 — User is not an admin
    409 — Cannot demote yourself
```

**Auth:** Bearer token required (SUPERADMIN only)
**Service:** `RoleManagementService.demote()`

### 6.3 Grant Permission

```
POST /api/v1/admin/users/{user_id}/permissions/grant

Request Body:
{
    "permission": "COMPLIANCE_ADMIN"
}

Response 200:
{
    "user_id": "uuid",
    "admin_permissions": ["USER_MANAGEMENT", "COMPLIANCE_ADMIN"]
}

Errors:
    403 — Not SUPERADMIN
    404 — User not found
    409 — User is not an admin
    409 — Permission already granted
```

**Auth:** Bearer token required (SUPERADMIN only)
**Service:** `RoleManagementService.grant_permission()`

### 6.4 Revoke Permission

```
POST /api/v1/admin/users/{user_id}/permissions/revoke

Request Body:
{
    "permission": "COMPLIANCE_ADMIN"
}

Response 200:
{
    "user_id": "uuid",
    "admin_permissions": ["USER_MANAGEMENT"]
}

Errors:
    403 — Not SUPERADMIN
    404 — User not found
    409 — Permission not granted
```

**Auth:** Bearer token required (SUPERADMIN only)
**Service:** `RoleManagementService.revoke_permission()`

### 6.5 Provision Superadmin

```
POST /api/v1/admin/provision-superadmin

Request Body:
{
    "email": "admin@example.com",
    "password": "SuperSecureP@ss",
    "full_name": "System Admin"
}

Response 201:
{
    "user_id": "uuid",
    "email": "admin@example.com",
    "system_role": "SUPERADMIN"
}

Errors:
    409 — Superadmin already exists
```

**Auth:** None (only works when no SUPERADMIN exists)
**Service:** `SuperadminProvisioningService.provision()`

## 7. Request/Response Schemas

### 7.1 Pydantic Models

Each endpoint has explicit Pydantic request/response models:

- Request models: validation constraints (min length, regex, etc.)
- Response models: camelCase JSON aliases where appropriate
- All UUID fields use Python's `uuid.UUID` type
- All datetime fields are ISO 8601 UTC

### 7.2 Token Response Schema

```
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds
```

### 7.3 User Response Schema

```
class UserResponse(BaseModel):
    user_id: UUID
    email: str
    username: str | None
    full_name: str
    status: str
    system_role: str
    auth_providers: list[str]
    email_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

## 8. File Structure

```
src/emerald/infrastructure/api/
    routers/
        __init__.py
        auth.py             # Auth routes (register, login, refresh, logout, reset)
        social_auth.py      # Social login routes
        users.py            # User profile routes
        admin.py            # Admin routes
    schemas/
        iam.py              # IAM-specific request/response schemas
```

## 9. Acceptance Criteria

### Registration

- [ ] `POST /api/v1/auth/register` creates user and returns 201
- [ ] Returns 400 for invalid email/password/username
- [ ] Returns 409 for duplicate email or username

### Login

- [ ] `POST /api/v1/auth/login` returns tokens on valid credentials
- [ ] Returns 401 for invalid credentials
- [ ] Returns 403 for suspended/inactive accounts

### Token Refresh

- [ ] `POST /api/v1/auth/refresh` returns new token pair
- [ ] Returns 401 for invalid/expired/revoked refresh token
- [ ] Old refresh token is invalidated after rotation

### Logout

- [ ] `POST /api/v1/auth/logout` revokes refresh token, returns 204
- [ ] `POST /api/v1/auth/logout-all` revokes all user tokens, returns 204

### Password Reset

- [ ] `POST /api/v1/auth/password-reset/request` always returns 202
- [ ] `POST /api/v1/auth/password-reset/submit` resets password with valid token

### Social Login

- [ ] `GET /api/v1/auth/social/{provider}/authorize` returns authorization URL
- [ ] `POST /api/v1/auth/social/{provider}/callback` exchanges code for tokens
- [ ] `POST /api/v1/auth/social/link` links provider to authenticated user
- [ ] `POST /api/v1/auth/social/unlink` unlinks provider
- [ ] `POST /api/v1/auth/social/set-username` sets username for social-only users

### User Profile

- [ ] `GET /api/v1/users/me` returns current user profile
- [ ] `PATCH /api/v1/users/me` updates mutable profile fields

### Admin Routes

- [ ] All admin routes require SUPERADMIN (403 otherwise)
- [ ] Promote/demote/grant/revoke modify user roles and permissions
- [ ] Provision superadmin only works when none exists
- [ ] Self-modification prevention (cannot demote yourself)

### General

- [ ] All endpoints return consistent error format
- [ ] All authenticated endpoints return 401 without token
- [ ] Request/response schemas have proper validation
