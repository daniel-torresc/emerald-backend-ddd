# Spec 005: Federated Authentication

**Status:** Draft
**Bounded Context:** Identity & Access Management (IAM)
**Dependencies:** 002 (User Registration & Identity), 003 (Authentication & Sessions)
**Blocks:** None

---

## 1. Overview

This spec defines federated authentication via OpenID Connect (OIDC), enabling users to sign in with external identity providers (Google, Microsoft). It covers the OAuth 2.0 Authorization Code Flow with PKCE, automatic account linking when emails match, social registration for new users, and provider management on existing accounts.

**Key Principle:** Social login is an alternative authentication method, not a separate identity. A user who registers with email/password and later signs in with Google (same email) gets the provider linked to their existing account — no duplicate user is created.

## 2. Scope

### In Scope

- OAuth 2.0 Authorization Code Flow with PKCE
- Google OIDC integration
- Microsoft OIDC integration
- Account linking (social provider matched to existing user by email)
- Social registration (new user via social provider)
- Provider linking/unlinking on existing accounts
- Username onboarding for social-only registrations

### Out of Scope

- Additional providers beyond Google and Microsoft (extensible design, but only two specified)
- MFA (future enhancement)
- Device binding (future enhancement)
- Password registration flow (Spec 002)
- Token lifecycle mechanics (Spec 003 — this spec uses the token infrastructure)

## 3. Supported Providers

| Provider | Protocol | ID Token Claims Used |
|----------|----------|---------------------|
| Google | OAuth 2.0 + OIDC | `sub` (external ID), `email`, `email_verified`, `name` |
| Microsoft | OAuth 2.0 + OIDC | `sub` or `oid` (external ID), `email`, `email_verified`, `name` |

**Provider Configuration (infrastructure):**

| Setting | Description |
|---------|-------------|
| client_id | Application ID registered with provider |
| client_secret | Application secret (stored encrypted) |
| authorization_endpoint | Provider's OAuth authorization URL |
| token_endpoint | Provider's token exchange URL |
| userinfo_endpoint | Provider's user info URL (fallback) |
| jwks_uri | Provider's public keys for ID token verification |
| scopes | `openid email profile` |

## 4. Authentication Flows

### 4.1 Authorization Code Flow with PKCE

```
Client (browser)                    Platform                         Provider
     │                                 │                                │
     │  1. Click "Sign in with Google" │                                │
     │────────────────────────────────►│                                │
     │                                 │                                │
     │                                 │  2. Generate:                  │
     │                                 │     - state (CSRF protection)  │
     │                                 │     - code_verifier (PKCE)     │
     │                                 │     - code_challenge           │
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
     │                                 │  7. Validate state             │
     │                                 │  8. Exchange code for tokens   │
     │                                 │────────────────────────────────►
     │                                 │                                │
     │                                 │  9. Receive ID token           │
     │                                 │◄────────────────────────────────
     │                                 │                                │
     │                                 │  10. Verify ID token signature │
     │                                 │  11. Extract claims            │
     │                                 │  12. Process (see 4.2)         │
     │                                 │                                │
     │  13. Return platform tokens     │                                │
     │◄────────────────────────────────│                                │
```

### 4.2 Post-Authentication Decision

After extracting claims from the verified ID token:

```
Extract: email, external_id (sub), name, email_verified
     │
     ▼
Provider email verified?
     │
     ├── No ──► Reject: ProviderEmailNotVerifiedError
     │
     ▼ Yes
     │
Find existing user by email
     │
     ├── User exists ──► ACCOUNT LINKING (4.3)
     │
     └── No user ──► SOCIAL REGISTRATION (4.4)
```

### 4.3 Account Linking (Existing User)

When a social login matches an existing user's email:

```
Existing user found by email
     │
     ▼
Check if provider already linked to this user
     │
     ├── Already linked (same provider type + external_id)
     │   └── Proceed to login (issue tokens)
     │
     ├── Provider type linked but different external_id
     │   └── Reject: ProviderExternalIdMismatchError
     │
     └── Provider not yet linked
         │
         ▼
     Link provider to user:
       1. user.link_auth_provider(AuthProvider(provider, external_id, now))
       2. Emit AuthProviderLinked event
       3. Proceed to login (issue tokens)
```

**Account Linking Rules:**

| Rule | Description |
|------|-------------|
| Email must match | Provider email must exactly match user's email (after normalization) |
| Auto-link | Linking is automatic — no user confirmation required |
| Status check | User must be ACTIVE (not suspended/deleted/pending) |
| Multiple providers | User can have PASSWORD + GOOGLE + MICROSOFT simultaneously |
| No external_id conflict | Cannot link if a different external_id exists for the same provider type |

### 4.4 Social Registration (New User)

When no existing user matches the provider email:

```
No user with this email
     │
     ▼
Create new user:
  1. email = provider email (verified by provider)
  2. email_verified = True (provider already verified)
  3. password = None (social-only account)
  4. auth_providers = {AuthProvider(provider, external_id, now)}
  5. status = ACTIVE (skip PENDING_VERIFICATION)
  6. full_name = provider profile name (if available)
  7. username = NEEDS ONBOARDING (see 4.5)
     │
     ▼
Emit UserRegistered event (with social_provider info)
     │
     ▼
Issue tokens (user is immediately active)
```

**Social Registration Rules:**

| Rule | Description |
|------|-------------|
| Skip email verification | Provider has already verified the email |
| No password | `password` is None; user can add one later via `set_initial_password()` |
| Immediate ACTIVE | Skip PENDING_VERIFICATION state entirely |
| Profile pre-fill | `full_name` populated from provider data if available |

### 4.5 Username Onboarding

Social registration creates a user without a username (since providers don't supply one in a suitable format). The username must be collected during first login.

```
Social registration complete, tokens issued
     │
     ▼
Client detects: user has no username (from token claims or user profile)
     │
     ▼
Prompt user to choose username (client-side onboarding screen)
     │
     ▼
User submits username:
  1. Validate Username value object rules
  2. Check uniqueness via domain service
  3. user.update_username(username)
     │
     ▼
Onboarding complete — full functionality available
```

**Onboarding Rules:**

| Rule | Description |
|------|-------------|
| Required for full functionality | Certain operations may require a username to be set |
| Not blocking authentication | User receives valid tokens immediately; username is set after |
| Same validation rules | Username rules from Spec 002 apply (3-30 chars, alphanumeric, etc.) |
| Uniqueness enforced | Same 90-day deleted window uniqueness check |

## 5. Provider Management

### 5.1 Linking Additional Providers

A user already authenticated can link additional providers from their account settings.

```
Authenticated user initiates "Link Google Account"
     │
     ▼
Same OAuth flow (4.1) but post-authentication:
  1. Verify provider email matches user's current email
     Raises: ProviderEmailMismatchError if different
  2. user.link_auth_provider(provider)
  3. Emit AuthProviderLinked event
```

**Rules:**

- Provider email must match user's current email at link time
- Cannot link a provider type that is already linked
- Linking does not change user's email or any other attributes

### 5.2 Unlinking Providers

A user can remove a linked provider from their account settings.

```
Authenticated user requests "Unlink Google"
     │
     ▼
  1. Validate at least one other provider will remain
     Raises: CannotUnlinkLastProviderError
  2. If unlinking PASSWORD and no password set: this is inherently safe
     (PASSWORD can only exist if password is set — invariant from Spec 002)
  3. user.unlink_auth_provider(provider_type)
  4. Emit AuthProviderUnlinked event
```

**Rules:**

| Rule | Description |
|------|-------------|
| Cannot unlink last provider | User must always have at least one auth method |
| Unlinking PASSWORD | Allowed only if at least one social provider remains |
| Unlinking social | Allowed only if PASSWORD or another social provider remains |

## 6. OIDC Token Validation

The platform must verify ID tokens from providers before trusting the claims.

**Verification Steps:**

| Step | Description |
|------|-------------|
| 1. Signature | Verify JWT signature using provider's public keys (JWKS) |
| 2. Issuer | `iss` claim matches expected provider issuer URL |
| 3. Audience | `aud` claim matches our `client_id` |
| 4. Expiration | `exp` claim is in the future |
| 5. Nonce | If sent in auth request, `nonce` claim must match |
| 6. Email verified | `email_verified` claim is `true` |

**Infrastructure Concern:** JWKS key caching and rotation is an infrastructure detail. The domain receives already-verified claims.

## 7. Domain Service: Federated Authentication Service

```
FederatedAuthenticationService:

  + authenticate_with_provider(
      provider_type: ProviderType,
      email: str,
      external_id: str,
      full_name: str?
    ) -> tuple[User, bool]
      Returns: (user, is_new_registration)

      1. Normalize email
      2. Look up existing user by email
      3. If user exists:
         a. Check user status is ACTIVE
            Raises: AccountSuspendedError, AuthenticationFailedError (for deleted)
         b. Check/link provider (see 4.3)
         c. Record login
         d. Return (user, False)
      4. If no user:
         a. Create social registration (see 4.4)
         b. Return (user, True)
```

## 8. OAuth State Management

**State Entity (short-lived):**

| Attribute | Type | Description |
|-----------|------|-------------|
| state_id | str | Random state parameter (CSRF token) |
| code_verifier | str | PKCE code verifier |
| provider_type | ProviderType | Which provider initiated |
| redirect_uri | str | Where to redirect after auth |
| created_at | datetime | When created |
| expires_at | datetime | Short TTL (10 minutes) |

**Rules:**

- State is single-use (consumed on callback)
- Expires after 10 minutes
- `code_verifier` never sent to provider (only `code_challenge` derived from it)

## 9. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `UserRegisteredViaSocialProvider` | Social registration | user_id, provider_type, email |
| `AuthProviderLinked` | Provider linked to existing account | user_id, provider_type |
| `AuthProviderUnlinked` | Provider removed from account | user_id, provider_type |
| `SocialLoginCompleted` | Successful social login (existing user) | user_id, provider_type |

**Note:** `AuthProviderLinked` and `AuthProviderUnlinked` are the same events defined in Spec 002. They are listed here for completeness as they are the primary triggers in federated auth flows.

## 10. Error Handling

| Error | Trigger | User-Facing Message |
|-------|---------|-------------------|
| `ProviderEmailNotVerifiedError` | Provider reports email unverified | "Your email must be verified with {provider} first" |
| `ProviderEmailMismatchError` | Linking a provider whose email doesn't match | "Provider email must match your account email" |
| `ProviderExternalIdMismatchError` | Same provider type but different external user | "This provider is already linked to a different identity" |
| `ProviderAlreadyLinkedError` | Provider type already linked | "This provider is already linked to your account" |
| `CannotUnlinkLastProviderError` | Unlinking would leave zero providers | "You must have at least one sign-in method" |
| `AccountSuspendedError` | Social login for suspended user | "Your account has been suspended" |
| `OAuthStateInvalidError` | State parameter mismatch or expired | "Authentication session expired, please try again" |
| `OAuthCodeExchangeError` | Code exchange with provider failed | "Authentication failed, please try again" |

## 11. Acceptance Criteria

### OAuth Flow

- [ ] Authorization URL is generated with correct state, code_challenge (S256), and scopes
- [ ] State parameter is validated on callback (rejects mismatched/expired)
- [ ] Authorization code is exchanged for ID token using code_verifier (PKCE)
- [ ] ID token signature is verified against provider's JWKS
- [ ] ID token claims (iss, aud, exp) are validated
- [ ] Unverified provider email is rejected

### Account Linking

- [ ] Social login with email matching existing ACTIVE user links the provider automatically
- [ ] Linked user receives platform tokens (same as password login)
- [ ] Already-linked provider (same type + external_id) proceeds directly to login
- [ ] Different external_id for same provider type raises `ProviderExternalIdMismatchError`
- [ ] Social login for SUSPENDED user raises `AccountSuspendedError`
- [ ] Social login for DELETED user raises `AuthenticationFailedError` (no info leak)
- [ ] Social login for PENDING_VERIFICATION user links provider and upgrades to ACTIVE (email now verified by provider)

### Social Registration

- [ ] New email creates a new user with ACTIVE status (skip PENDING_VERIFICATION)
- [ ] New user has `email_verified = True`
- [ ] New user has `password = None`
- [ ] New user has the social provider in `auth_providers`
- [ ] `full_name` is populated from provider profile if available
- [ ] `UserRegisteredViaSocialProvider` event is emitted
- [ ] Platform tokens are issued immediately

### Username Onboarding

- [ ] Socially registered user has no username initially
- [ ] Username can be set via `update_username()` with standard validation
- [ ] Username uniqueness is enforced (including 90-day deleted window)

### Provider Management

- [ ] User can link additional provider from settings (email must match)
- [ ] User can unlink a provider if at least one other remains
- [ ] Cannot unlink last provider — raises `CannotUnlinkLastProviderError`

### Security

- [ ] PKCE (S256) is used for all authorization flows (no plain code challenge)
- [ ] OAuth state is single-use and short-lived (10 minutes)
- [ ] Code verifier is never exposed to the provider or client
- [ ] Provider secrets are stored encrypted
