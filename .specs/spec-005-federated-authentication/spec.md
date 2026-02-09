# Spec 005: Federated Authentication

**Version:** 1.0
**Status:** Draft
**Bounded Context:** Identity & Access Management (IAM)
**Dependencies:** 002 (User Registration & Identity), 003 (Authentication & Sessions)
**Date:** 2026-02-09

---

## 1. Overview

This spec defines federated authentication via OpenID Connect (OIDC), enabling users to sign in with external identity providers (Google, Microsoft). It covers the OAuth 2.0 Authorization Code Flow with PKCE, automatic account linking when emails match, social registration for new users, and provider management on existing accounts.

**Key Principle:** Social login is an alternative authentication method, not a separate identity. A user who registers with email/password and later signs in with Google (same email) gets the provider linked to their existing account — no duplicate user is created.

---

## 2. Background & Context

### Problem Statement

Users expect to sign in with their existing Google or Microsoft accounts rather than creating yet another email/password combination. Without federated auth, the platform loses users at registration and imposes unnecessary friction on sign-in.

### Business Goals

- Reduce registration friction by allowing one-click social sign-up
- Increase login convenience with provider-based authentication
- Maintain a single user identity regardless of authentication method
- Support the two most common enterprise/consumer identity providers

### Success Metrics

- Social registration creates a fully active user in a single flow
- Account linking is seamless and automatic (no user confirmation step)
- Users can manage their linked providers (link/unlink) from account settings

---

## 3. Scope

### In Scope

- OAuth 2.0 Authorization Code Flow with PKCE
- Google OIDC integration
- Microsoft OIDC integration
- Account linking (social provider matched to existing user by email)
- Social registration (new user via social provider)
- Provider linking/unlinking on existing accounts
- Username onboarding for social-only registrations
- PENDING_VERIFICATION → ACTIVE upgrade on social login (email verified by provider)
- OidcProvider protocol (port) for infrastructure abstraction
- OidcClaims value object for verified claims contract
- AccessTokenClaims extended with username
- User aggregate extended with optional username and social registration factory

### Out of Scope

- Additional providers beyond Google and Microsoft (extensible design via ProviderType enum, but only two specified)
- MFA (future enhancement)
- Device binding (future enhancement)
- Password registration flow (Spec 002)
- Token lifecycle mechanics (Spec 003 — this spec uses the token infrastructure)
- OIDC token verification implementation (JWKS, signature, iss/aud/exp checks are infrastructure)
- OAuth state management implementation (state, PKCE code_verifier/challenge are infrastructure)
- Provider configuration storage (client_id, client_secret, endpoints are infrastructure)

---

## 4. Users & Personas

### Primary Users

- **New users** who prefer social sign-in over creating a new email/password
- **Existing users** who want to add social login as a convenience alongside their password
- **Social-only users** who never set a password and rely entirely on provider authentication

### User Goals

- Sign in with Google or Microsoft in one click
- Link/unlink providers from account settings
- Have the same account regardless of sign-in method

---

## 5. Requirements

### 5.1 Functional Requirements

#### REQ-001: Social Login (Existing User — Provider Already Linked)

**Priority:** Must Have
**Description:** When a user signs in with a social provider that is already linked to their account, they are authenticated and receive platform tokens.

**Acceptance Criteria:**
- [ ] Social login with matching provider_type + external_id proceeds directly to token issuance
- [ ] User receives the same `LoginResult` as password-based login (access token + refresh token)
- [ ] `SocialLoginCompleted` event is emitted
- [ ] `record_login()` is called on the User aggregate

#### REQ-002: Social Login with Auto-Linking (Existing ACTIVE User — Provider Not Yet Linked)

**Priority:** Must Have
**Description:** When a social login matches an existing ACTIVE user's email but the provider is not yet linked, the provider is automatically linked to the account and the user is authenticated.

**Acceptance Criteria:**
- [ ] Provider email (after lowercase normalization) matches existing user's email
- [ ] Provider is automatically linked — no user confirmation required
- [ ] `AuthProviderLinked` event is emitted (existing event from Spec 002)
- [ ] `SocialLoginCompleted` event is emitted
- [ ] User receives platform tokens

#### REQ-003: Social Login with PENDING_VERIFICATION Upgrade

**Priority:** Must Have
**Description:** When a social login matches a PENDING_VERIFICATION user's email, the provider is linked, email is marked as verified (provider has proven ownership), and the user is upgraded to ACTIVE.

**Acceptance Criteria:**
- [ ] Provider is linked to the user
- [ ] `email_verified` is set to `True`
- [ ] User status transitions from PENDING_VERIFICATION to ACTIVE (via `verify_email()`)
- [ ] `AuthProviderLinked` event is emitted
- [ ] `EmailVerified` event is emitted
- [ ] `SocialLoginCompleted` event is emitted
- [ ] User receives platform tokens

#### REQ-004: Social Login — External ID Mismatch

**Priority:** Must Have
**Description:** When a social login matches a user's email and the provider type is already linked, but with a different external_id, the login is rejected.

**Acceptance Criteria:**
- [ ] Raises `ProviderExternalIdMismatchError`
- [ ] No tokens are issued
- [ ] No events are emitted

#### REQ-005: Social Login — Suspended User

**Priority:** Must Have
**Description:** Social login for a SUSPENDED user is rejected.

**Acceptance Criteria:**
- [ ] Raises `AccountSuspendedError` (existing exception from Spec 003)
- [ ] No tokens are issued

#### REQ-006: Social Login — Deleted User

**Priority:** Must Have
**Description:** Social login for a DELETED user is rejected with a generic error to avoid information leakage.

**Acceptance Criteria:**
- [ ] Raises `AuthenticationFailedError` (existing exception from Spec 003)
- [ ] No information about the user's existence or deletion is leaked

#### REQ-007: Social Login — Provider Email Not Verified

**Priority:** Must Have
**Description:** If the provider reports the email as unverified, the login is rejected.

**Acceptance Criteria:**
- [ ] Raises `ProviderEmailNotVerifiedError`
- [ ] No tokens are issued
- [ ] Validation happens before any user lookup

#### REQ-008: Social Registration (New User)

**Priority:** Must Have
**Description:** When no existing user matches the provider email, a new user is created via social registration.

**Acceptance Criteria:**
- [ ] New user created via `User.register_via_social(email, full_name, provider)` factory
- [ ] User status is ACTIVE (skip PENDING_VERIFICATION)
- [ ] `email_verified` is `True` (provider already verified)
- [ ] `password` is `None` (social-only account)
- [ ] `username` is `None` (requires onboarding)
- [ ] `auth_providers` contains the social provider
- [ ] `full_name` is populated from provider profile if available
- [ ] `system_role` defaults to USER
- [ ] `UserRegisteredViaSocialProvider` event is emitted
- [ ] Platform tokens are issued immediately

#### REQ-009: Username Onboarding

**Priority:** Must Have
**Description:** Social-registered users start without a username. The username must be set before certain operations are available.

**Acceptance Criteria:**
- [ ] Socially registered user has `username = None`
- [ ] Username can be set via `update_username()` with standard Spec 002 validation rules
- [ ] Username uniqueness is enforced (including 90-day deleted window)
- [ ] Clients detect onboarding state by checking `username == None` (no separate flag)

#### REQ-010: Link Additional Provider (Authenticated User)

**Priority:** Must Have
**Description:** An authenticated user can link an additional social provider from account settings.

**Acceptance Criteria:**
- [ ] Follows the same OAuth flow (PKCE)
- [ ] Provider email must match user's current email (raises `ProviderEmailMismatchError` if different)
- [ ] Cannot link a provider type that is already linked (raises `ProviderAlreadyLinkedError`, existing exception)
- [ ] `user.link_auth_provider(provider)` is called
- [ ] `AuthProviderLinked` event is emitted
- [ ] Linking does not change user's email or any other attributes

#### REQ-011: Unlink Provider

**Priority:** Must Have
**Description:** An authenticated user can remove a linked provider from account settings.

**Acceptance Criteria:**
- [ ] Cannot unlink if it would leave zero providers (raises `CannotUnlinkLastProviderError`, existing exception)
- [ ] `user.unlink_auth_provider(provider_type)` is called
- [ ] `AuthProviderUnlinked` event is emitted
- [ ] Unlinking PASSWORD is allowed if at least one social provider remains
- [ ] Unlinking a social provider is allowed if PASSWORD or another social provider remains

#### REQ-012: PKCE Security

**Priority:** Must Have
**Description:** All authorization flows use PKCE with S256 challenge method.

**Acceptance Criteria:**
- [ ] PKCE (S256) is used for all authorization flows — no plain code challenge
- [ ] OAuth state is single-use and short-lived (10 minutes)
- [ ] Code verifier is never exposed to the provider or client
- [ ] State parameter validated on callback (rejects mismatched/expired)

#### REQ-013: SUPERADMIN Refresh Token Override

**Priority:** Must Have
**Description:** Social login for SUPERADMIN users follows the same 15-minute refresh token TTL override from Spec 004.

**Acceptance Criteria:**
- [ ] SUPERADMIN social login uses `REFRESH_TOKEN_TTL_SUPERADMIN` (15 minutes)
- [ ] Consistent with password-based login behavior from Spec 004

### 5.2 Non-Functional Requirements

#### Security
- PKCE (S256) is mandatory for all OAuth flows
- OAuth state tokens are cryptographically random, single-use, 10-minute TTL
- Code verifier never leaves the server
- Provider secrets stored encrypted (infrastructure concern)
- ID tokens verified against provider JWKS before trusting claims (infrastructure concern)

#### Extensibility
- Adding new providers requires only extending the `ProviderType` enum and providing an `OidcProvider` implementation — no domain logic changes needed

---

## 6. Supported Providers

| Provider | Protocol | ID Token Claims Used |
|----------|----------|---------------------|
| Google | OAuth 2.0 + OIDC | `sub` (external ID), `email`, `email_verified`, `name` |
| Microsoft | OAuth 2.0 + OIDC | `sub` or `oid` (external ID), `email`, `email_verified`, `name` |

**Provider Configuration (infrastructure-only):**

| Setting | Description |
|---------|-------------|
| client_id | Application ID registered with provider |
| client_secret | Application secret (stored encrypted) |
| authorization_endpoint | Provider's OAuth authorization URL |
| token_endpoint | Provider's token exchange URL |
| userinfo_endpoint | Provider's user info URL (fallback) |
| jwks_uri | Provider's public keys for ID token verification |
| scopes | `openid email profile` |

---

## 7. Authentication Flows

### 7.1 Authorization Code Flow with PKCE

```
Client (browser)                    Platform                         Provider
     │                                 │                                │
     │  1. Click "Sign in with Google" │                                │
     │────────────────────────────────►│                                │
     │                                 │                                │
     │                                 │  2. Generate (infrastructure): │
     │                                 │     - state (CSRF protection)  │
     │                                 │     - code_verifier (PKCE)     │
     │                                 │     - code_challenge (S256)    │
     │                                 │     Store state + verifier     │
     │                                 │                                │
     │  3. Redirect to provider        │                                │
     │◄────────────────────────────────│                                │
     │                                                                  │
     │  4. User authenticates at provider                               │
     │─────────────────────────────────────────────────────────────────►│
     │                                                                  │
     │  5. Provider redirects back with authorization code + state      │
     │◄─────────────────────────────────────────────────────────────────│
     │                                                                  │
     │  6. Send code + state to platform                                │
     │────────────────────────────────►│                                │
     │                                 │                                │
     │                                 │  7. Validate state (infra)     │
     │                                 │  8. Exchange code via          │
     │                                 │     OidcProvider protocol      │
     │                                 │────────────────────────────────►
     │                                 │                                │
     │                                 │  9. Receive OidcClaims         │
     │                                 │◄────────────────────────────────
     │                                 │                                │
     │                                 │  10. Domain logic:             │
     │                                 │      - Validate claims         │
     │                                 │      - Link/register user      │
     │                                 │      - Issue platform tokens   │
     │                                 │                                │
     │  11. Return LoginResult         │                                │
     │◄────────────────────────────────│                                │
```

### 7.2 Post-Authentication Decision Tree

After receiving `OidcClaims` from the provider:

```
Receive OidcClaims from OidcProvider
     │
     ▼
claims.email_verified == True?
     │
     ├── No ──► Reject: ProviderEmailNotVerifiedError
     │
     ▼ Yes
     │
Find existing user by email (normalized lowercase)
     │
     ├── User exists ──► ACCOUNT LINKING (7.3)
     │
     └── No user ──► SOCIAL REGISTRATION (7.4)
```

### 7.3 Account Linking (Existing User)

```
Existing user found by email
     │
     ▼
Check user status
     │
     ├── DELETED ──► Reject: AuthenticationFailedError (no info leak)
     ├── SUSPENDED ──► Reject: AccountSuspendedError
     │
     ├── PENDING_VERIFICATION ──►
     │     1. Link provider: user.link_auth_provider(AuthProvider(...))
     │     2. Verify email: user.verify_email()  (→ ACTIVE, email_verified=True)
     │     3. Record login: user.record_login()
     │     4. Issue tokens
     │     5. Emit: AuthProviderLinked, EmailVerified, SocialLoginCompleted
     │
     └── ACTIVE ──►
           │
           ▼
     Check if provider already linked to this user
           │
           ├── Already linked (same provider_type + external_id)
           │   └── Record login, issue tokens
           │       Emit: SocialLoginCompleted
           │
           ├── Provider type linked but different external_id
           │   └── Reject: ProviderExternalIdMismatchError
           │
           └── Provider type not yet linked
               │
               ▼
           1. user.link_auth_provider(AuthProvider(provider_type, external_id, now))
           2. user.record_login()
           3. Issue tokens
           4. Emit: AuthProviderLinked, SocialLoginCompleted
```

### 7.4 Social Registration (New User)

```
No user with this email
     │
     ▼
Create new user via User.register_via_social():
  - email = provider email (verified by provider)
  - email_verified = True
  - password = None (social-only account)
  - auth_providers = {AuthProvider(provider_type, external_id, now)}
  - status = ACTIVE (skip PENDING_VERIFICATION)
  - full_name = provider profile name (if available)
  - username = None (requires onboarding)
  - system_role = USER (default)
     │
     ▼
Save user
     │
     ▼
Issue tokens
     │
     ▼
Emit: UserRegisteredViaSocialProvider
Return: LoginResult (is_new_registration = True)
```

### 7.5 Username Onboarding

```
Social registration complete, tokens issued
     │
     ▼
Client inspects access token claims:
  username == null → onboarding needed
     │
     ▼
Prompt user to choose username (client-side)
     │
     ▼
SetOnboardingUsername command:
  1. Validate Username value object rules (3-30 chars, alphanumeric + underscore/hyphen)
  2. Check uniqueness (including 90-day deleted window)
  3. user.update_username(username)
     │
     ▼
Onboarding complete — full functionality available
```

---

## 8. Domain Model Changes

### 8.1 New Value Object: OidcClaims

```
OidcClaims:
  + provider_type: ProviderType    # GOOGLE or MICROSOFT
  + external_id: str               # Provider's subject identifier (sub/oid)
  + email: str                     # Verified email from provider
  + email_verified: bool           # Whether provider verified the email
  + full_name: str | None          # Display name from provider profile

  Validation (__post_init__):
  - provider_type must not be PASSWORD
  - external_id must be non-empty
  - email must be non-empty
  - email_verified must be True (reject unverified at construction)
```

**Purpose:** Clean contract between the `OidcProvider` infrastructure port and domain logic. The domain never deals with raw JWTs or provider-specific claim formats.

### 8.2 Modified: User Aggregate

#### New Factory Method: `register_via_social()`

```
@classmethod
register_via_social(
    email: EmailAddress,
    full_name: str | None,
    auth_provider: AuthProvider,
    created_by: UUID
) -> User

Creates:
  - status = ACTIVE
  - email_verified = True
  - password = None
  - username = None
  - auth_providers = {auth_provider}
  - full_name = full_name
  - system_role = USER
  - Emits UserRegisteredViaSocialProvider
```

#### Modified Attribute: `username`

```
username: Username | None   # Was: Username (required)
                            # Now: None for social-only registrations until onboarding
```

**Impact:** `User.register()` (password-based) still requires `username: Username`. Only `register_via_social()` sets it to `None`.

### 8.3 Modified: AccessTokenClaims

```
AccessTokenClaims:
  + sub: UUID
  + email: str
  + username: str | None        # NEW — None if onboarding needed
  + system_role: SystemRole
  + iat: datetime
  + exp: datetime
  + jti: UUID
```

### 8.4 Modified: AuthenticationService

#### New Method: `login_with_provider()`

```
login_with_provider(
    claims: OidcClaims
) -> LoginResult

  1. Validate claims.email_verified == True
     Raises: ProviderEmailNotVerifiedError
  2. Normalize email via EmailAddress(claims.email)
  3. Look up user by email via UserRepository
  4. If user exists:
     a. Check status:
        - DELETED → raise AuthenticationFailedError
        - SUSPENDED → raise AccountSuspendedError
        - PENDING_VERIFICATION → link provider, verify_email(), proceed
        - ACTIVE → proceed
     b. Check/link provider (see 7.3 decision tree)
     c. user.record_login()
     d. Issue tokens (LoginResult) — uses existing token issuance logic
        - SUPERADMIN override: 15-min refresh TTL (Spec 004)
     e. Return LoginResult with is_new_registration = False
  5. If no user:
     a. Create via User.register_via_social()
     b. Save user
     c. Issue tokens (LoginResult)
     d. Return LoginResult with is_new_registration = True
```

**Note:** `LoginResult` may need an `is_new_registration: bool` field so the client knows to show the onboarding flow.

#### New Method: `link_provider()`

```
link_provider(
    user_id: UUID,
    claims: OidcClaims
) -> None

  1. Find user by ID (raises AuthenticationFailedError if not found)
  2. Verify user status is ACTIVE
  3. Verify claims.email matches user's email
     Raises: ProviderEmailMismatchError
  4. user.link_auth_provider(AuthProvider(claims.provider_type, claims.external_id, now))
     Raises: ProviderAlreadyLinkedError (existing)
  5. Save user
```

#### New Method: `unlink_provider()`

```
unlink_provider(
    user_id: UUID,
    provider_type: ProviderType
) -> None

  1. Find user by ID (raises AuthenticationFailedError if not found)
  2. user.unlink_auth_provider(provider_type)
     Raises: CannotUnlinkLastProviderError (existing), ProviderNotLinkedError (existing)
  3. Save user
```

---

## 9. New Domain Port: OidcProvider

```
OidcProvider (Protocol):

  + generate_authorization_url(
      provider_type: ProviderType,
      redirect_uri: str,
      state: str
    ) -> str
      Returns the full authorization URL with code_challenge, scopes, etc.

  + exchange_code_for_claims(
      provider_type: ProviderType,
      code: str,
      redirect_uri: str
    ) -> OidcClaims
      Exchanges authorization code for ID token, verifies signature/claims,
      extracts and returns OidcClaims.
      Raises: OAuthCodeExchangeError on failure.
```

**Infrastructure responsibilities** (behind this port):
- PKCE code_verifier generation and S256 code_challenge derivation
- OAuth state generation, storage, and single-use validation (10-minute TTL)
- JWKS key fetching, caching, and rotation
- ID token signature verification (iss, aud, exp, nonce)
- Provider-specific claim extraction (Google `sub` vs. Microsoft `sub`/`oid`)

---

## 10. Commands

| Command | Fields | Description |
|---------|--------|-------------|
| `InitiateOAuthLogin` | `provider_type: ProviderType`, `redirect_uri: str` | Generates authorization URL for the provider |
| `CompleteOAuthLogin` | `provider_type: ProviderType`, `code: str`, `state: str`, `redirect_uri: str` | Exchanges code for claims and authenticates |
| `LinkAuthProviderViaOAuth` | `user_id: UUID`, `provider_type: ProviderType`, `code: str`, `state: str`, `redirect_uri: str` | Authenticated user links a provider |
| `UnlinkAuthProvider` | `user_id: UUID`, `provider_type: ProviderType` | Remove a provider from account |
| `SetOnboardingUsername` | `user_id: UUID`, `username: str` | Set username after social registration |

---

## 11. Domain Events

### New Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `UserRegisteredViaSocialProvider` | Social registration (new user) | `user_id`, `email`, `provider_type`, `full_name` |
| `SocialLoginCompleted` | Successful social login (existing user) | `user_id`, `provider_type` |

### Reused Events (from Spec 002)

| Event | Trigger in This Spec |
|-------|---------------------|
| `AuthProviderLinked` | Provider auto-linked during social login, or linked from settings |
| `AuthProviderUnlinked` | Provider removed from settings |
| `EmailVerified` | PENDING_VERIFICATION user upgraded via social login |

---

## 12. Exceptions

### New Exceptions

| Exception | Code | Trigger | User-Facing Message |
|-----------|------|---------|-------------------|
| `ProviderEmailNotVerifiedError` | `PROVIDER_EMAIL_NOT_VERIFIED` | Provider reports email unverified | "Your email must be verified with {provider} first" |
| `ProviderEmailMismatchError` | `PROVIDER_EMAIL_MISMATCH` | Linking a provider whose email doesn't match account | "Provider email must match your account email" |
| `ProviderExternalIdMismatchError` | `PROVIDER_EXTERNAL_ID_MISMATCH` | Same provider type but different external user | "This provider is already linked to a different identity" |
| `OAuthStateInvalidError` | `OAUTH_STATE_INVALID` | State parameter mismatch or expired | "Authentication session expired, please try again" |
| `OAuthCodeExchangeError` | `OAUTH_CODE_EXCHANGE_FAILED` | Code exchange with provider failed | "Authentication failed, please try again" |

### Reused Exceptions (from Specs 002/003)

| Exception | Usage in This Spec |
|-----------|-------------------|
| `ProviderAlreadyLinkedError` | Linking a provider type that is already linked |
| `CannotUnlinkLastProviderError` | Unlinking would leave zero providers |
| `ProviderNotLinkedError` | Unlinking a provider that isn't linked |
| `AccountSuspendedError` | Social login for suspended user |
| `AuthenticationFailedError` | Social login for deleted user (no info leak) |

---

## 13. Account Linking Rules Summary

| Rule | Description |
|------|-------------|
| Email must match | Provider email must exactly match user's email after lowercase normalization |
| Auto-link | Linking is automatic on social login — no user confirmation required |
| Status check | User must be ACTIVE or PENDING_VERIFICATION (not SUSPENDED/DELETED) |
| PENDING upgrade | PENDING_VERIFICATION users are upgraded to ACTIVE (provider verified email) |
| Multiple providers | User can have PASSWORD + GOOGLE + MICROSOFT simultaneously |
| No external_id conflict | Cannot link if a different external_id exists for the same provider type |
| Provider email match for settings | Linking from settings requires provider email to match current account email |

---

## 14. Social Registration Rules Summary

| Rule | Description |
|------|-------------|
| Skip email verification | Provider has already verified the email |
| No password | `password` is `None`; user can add one later via `set_initial_password()` |
| No username | `username` is `None`; set during onboarding via `SetOnboardingUsername` |
| Immediate ACTIVE | Skip PENDING_VERIFICATION state entirely |
| Profile pre-fill | `full_name` populated from provider data if available |
| Default role | `system_role` defaults to USER |

---

## 15. Modified LoginResult

The existing `LoginResult` DTO from Spec 003 needs extension:

```
LoginResult:
  + access_token: str
  + refresh_token: str
  + is_new_registration: bool    # NEW — True for social registration, False otherwise
```

Clients use `is_new_registration` to determine whether to show the username onboarding flow.

---

## 16. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Provider email not verified | Reject with `ProviderEmailNotVerifiedError` before any user lookup |
| Email matches DELETED user | Reject with `AuthenticationFailedError` (generic, no info leak) |
| Email matches SUSPENDED user | Reject with `AccountSuspendedError` |
| Email matches PENDING_VERIFICATION user | Link provider, verify email, upgrade to ACTIVE, issue tokens |
| Same provider type, different external_id | Reject with `ProviderExternalIdMismatchError` |
| Provider email differs from account email (settings link) | Reject with `ProviderEmailMismatchError` |
| Unlinking last remaining provider | Reject with `CannotUnlinkLastProviderError` |
| OAuth state expired or mismatched | Reject with `OAuthStateInvalidError` (infrastructure raises) |
| Code exchange fails (network, invalid code) | Reject with `OAuthCodeExchangeError` (infrastructure raises) |
| Social login, user already linked (same external_id) | Proceed to login (no re-link, just authenticate) |
| Social registration, `full_name` not provided by provider | Create user with `full_name = None` |
| SUPERADMIN social login | 15-minute refresh token TTL override applied (Spec 004) |

---

## 17. Dependencies

### Internal Dependencies

- **Spec 002 (User Registration & Identity):** User aggregate, AuthProvider, ProviderType, email/username validation, `link_auth_provider()`, `unlink_auth_provider()`
- **Spec 003 (Authentication & Sessions):** AuthenticationService, LoginResult, token issuance, session management, AccessTokenClaims
- **Spec 004 (System Roles & Admin Permissions):** SUPERADMIN refresh token TTL override

### External Dependencies (Infrastructure)

- Google OIDC discovery and JWKS endpoints
- Microsoft Identity Platform OIDC discovery and JWKS endpoints

---

## 18. Constraints

- Only Google and Microsoft providers are supported in this spec
- OAuth state/PKCE management is an infrastructure concern — domain receives verified `OidcClaims`
- Email matching uses lowercase normalization only (no provider-specific dot-stripping or plus-addressing)
- Username is the only onboarding field for social-only users

---

## 19. Glossary

- **OIDC:** OpenID Connect — authentication layer on top of OAuth 2.0
- **PKCE:** Proof Key for Code Exchange — prevents authorization code interception
- **S256:** SHA-256 code challenge method for PKCE
- **ID Token:** JWT issued by the provider containing user identity claims
- **JWKS:** JSON Web Key Set — provider's public keys for verifying ID token signatures
- **External ID:** The provider's unique identifier for the user (Google `sub`, Microsoft `sub`/`oid`)
- **Account Linking:** Connecting a social provider to an existing platform user
- **Social Registration:** Creating a new platform user from a social provider login
- **Onboarding:** Post-registration flow to collect required user data (username)
