# Federated Authentication Implementation Plan

**Spec:** `.specs/spec-005-federated-authentication/spec.md`
**Version:** 1.0
**Date:** 2026-02-09

---

## 1. Overview

Implement federated authentication via OIDC (Google, Microsoft) within the IAM bounded context. This covers social login (existing + new users), automatic account linking, social registration, username onboarding, and provider link/unlink from settings. All OIDC infrastructure (PKCE, JWKS, state management) is behind a `OidcProvider` protocol port — domain logic receives verified `OidcClaims` only.

**Approach:** Inside-out — domain layer first (value objects, aggregate changes, events, exceptions), then application layer (commands, service methods, port protocol). Token issuance logic is extracted into a shared private helper within `AuthenticationService` to avoid duplication between password and social login flows.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| REQ-001..007 (Social Login) | Application | `AuthenticationService.login_with_provider()` |
| REQ-008 (Social Registration) | Domain + Application | `User.register_via_social()`, `AuthenticationService.login_with_provider()` |
| REQ-009 (Username Onboarding) | Application | `AuthenticationService.set_onboarding_username()` |
| REQ-010 (Link Provider) | Application | `AuthenticationService.link_provider()` |
| REQ-011 (Unlink Provider) | Application | `AuthenticationService.unlink_provider()` |
| REQ-012 (PKCE Security) | Infrastructure (behind port) | `OidcProvider` protocol |
| REQ-013 (SUPERADMIN TTL) | Application | Existing logic reused via `_issue_tokens()` helper |

### 2.2 Component Diagram

```
                    ┌─────────────────────────────┐
                    │   AuthenticationService     │
                    │  ┌──────────────────────┐   │
                    │  │ login_with_provider()│   │
                    │  │ link_provider()      │   │
                    │  │ unlink_provider()    │   │
                    │  │ set_onboarding_username()│
                    │  │ _issue_tokens()      │   │  ← NEW shared helper
                    │  └──────────┬───────────┘   │
                    └─────────────┼───────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
     ┌────────────┐     ┌──────────────┐     ┌──────────────┐
     │ OidcProvider│    │ User         │     │ UoW          │
     │ (Protocol)  │    │ (Aggregate)  │     │ (repos)      │
     └─────┬──────┘     │  + register  │     └──────────────┘
           │            │    _via_social│
      Infrastructure    │  + username   │
      (out of scope)    │    now Optional│
                        └──────────────┘
```

### 2.3 Ports and Adapters

| Port (Protocol) | Purpose | Location |
|------------------|---------|----------|
| `OidcProvider` | Exchange auth codes for verified claims, generate auth URLs | `domain/ports/oidc_provider.py` |

**Note:** `OidcProvider` is a domain port because it defines a contract the domain/application depends on. The infrastructure adapter (Google/Microsoft OIDC clients, PKCE, JWKS) is out of scope for this spec's implementation.

---

## 3. Technical Decisions

### 3.1 `User.username` Becomes Optional
**Decision:** Change `username: Username` to `username: Username | None` in the User aggregate constructor. The `register()` factory keeps `username: Username` as required. Only `register_via_social()` sets it to `None`.
**Rationale:** Minimal disruption — password registration path unchanged. Social registration explicitly opts into `None`.
**Impact:** `update_username()` needs to handle `old_username` being `None` (emit `str(self.username)` vs `""` or `None`). `verify_access_token()` in AuthenticationService references `user.username.value` — needs a null guard.

### 3.2 PENDING_VERIFICATION Provider Linking
**Decision:** Modify `link_auth_provider()` to accept both `ACTIVE` and `PENDING_VERIFICATION` status.
**Rationale:** The spec flow (section 7.3) requires linking the provider first, then calling `verify_email()`. The current `_require_status(ACTIVE)` guard would block this. Relaxing the guard is cleaner than reordering the flow (which would lose the semantic meaning of "provider caused the verification").
**Alternative Considered:** Calling `verify_email()` first, then `link_auth_provider()`. Rejected because the spec explicitly orders link before verify, and conceptually the provider link is what triggers the verification.

### 3.3 Token Issuance Extraction
**Decision:** Extract steps 5-11 of `AuthenticationService.login()` into a private `_issue_tokens(user, portal_context)` method.
**Rationale:** Social login uses identical token issuance logic (session limit enforcement, refresh token creation, SUPERADMIN TTL override, AccessTokenClaims building). Extracting avoids duplicating ~30 lines of code.
**Change:** `login()` and `login_with_provider()` both call `_issue_tokens()`. Social login always uses `PortalContext.REGULAR`.

### 3.4 `OidcProvider` Port Location
**Decision:** Place in `domain/ports/oidc_provider.py` alongside `password_hasher.py` and `token_service.py`.
**Rationale:** Follows existing port organization pattern. The port defines a domain-level contract.

### 3.5 External ID Mismatch Detection
**Decision:** The `login_with_provider()` method checks for external_id mismatch at the application layer before calling `user.link_auth_provider()`.
**Rationale:** `AuthProvider.__eq__` only compares `provider_type`, so the aggregate's `link_auth_provider()` can't distinguish "same type, same external_id" from "same type, different external_id". The application service inspects the existing provider's `external_id` before calling aggregate methods.

### 3.6 `LoginResult` Extension
**Decision:** Add `is_new_registration: bool = False` to `LoginResult`.
**Rationale:** Default `False` maintains backward compatibility with existing `login()` and `refresh()` callers.

### 3.7 New Events File
**Decision:** Add new social events to a new `domain/events/social_events.py` file.
**Rationale:** Follows the pattern of thematic grouping (`user_events.py`, `auth_events.py`, `role_events.py`).

---

## 4. Implementation Tasks

### Phase 1: Domain Layer — Value Objects & Exceptions

#### TASK-001: Add OidcClaims Value Object
**Layer:** Domain
**Depends On:** None

**Description:**
Create the `OidcClaims` frozen dataclass value object that represents verified claims from an OIDC provider. This is the clean contract between infrastructure (OIDC token verification) and domain logic.

**Files to Create:**
- `src/emerald/iam/domain/models/oidc_claims.py`

**Implementation Details:**
```python
@dataclass(frozen=True)
class OidcClaims:
    provider_type: ProviderType
    external_id: str
    email: str
    email_verified: bool
    full_name: str | None = None
```

**Validation (`__post_init__`):**
- `provider_type` must not be `PASSWORD` → raise `InvalidValueError`
- `external_id` must be non-empty (stripped) → raise `InvalidValueError`
- `email` must be non-empty (stripped) → raise `InvalidValueError`
- `email_verified` must be `True` → raise `InvalidValueError` (domain rejects unverified at construction)

**Files to Modify:**
- `src/emerald/iam/domain/models/__init__.py` — re-export `OidcClaims`

**Tests:**
- `tests/unit/iam/domain/value_objects/test_oidc_claims.py`
- Valid construction, PASSWORD rejection, empty external_id, empty email, email_verified=False rejection, full_name optional

---

#### TASK-002: Add New Exceptions
**Layer:** Domain
**Depends On:** None

**Description:**
Add 5 new exception classes for federated authentication error cases.

**Files to Modify:**
- `src/emerald/iam/domain/exceptions/iam_exceptions.py`

**Exceptions to Add:**
| Exception | Parent | Code |
|-----------|--------|------|
| `ProviderEmailNotVerifiedError` | `DomainError` | `PROVIDER_EMAIL_NOT_VERIFIED` |
| `ProviderEmailMismatchError` | `DomainError` | `PROVIDER_EMAIL_MISMATCH` |
| `ProviderExternalIdMismatchError` | `ConflictError` | `PROVIDER_EXTERNAL_ID_MISMATCH` |
| `OAuthStateInvalidError` | `DomainError` | `OAUTH_STATE_INVALID` |
| `OAuthCodeExchangeError` | `DomainError` | `OAUTH_CODE_EXCHANGE_FAILED` |

**Files to Modify:**
- `src/emerald/iam/domain/exceptions/__init__.py` — re-export new exceptions

**Tests:**
- `tests/unit/iam/domain/exceptions/test_social_auth_exceptions.py`
- Verify code and message for each, inheritance hierarchy

---

#### TASK-003: Add New Domain Events
**Layer:** Domain
**Depends On:** None

**Description:**
Create 2 new domain events for social authentication flows.

**Files to Create:**
- `src/emerald/iam/domain/events/social_events.py`

**Events:**

| Event | Fields |
|-------|--------|
| `UserRegisteredViaSocialProvider` | `aggregate_id`, `email: str`, `provider_type: str`, `full_name: str \| None` |
| `SocialLoginCompleted` | `aggregate_id`, `user_id: UUID`, `provider_type: str` |

Both have `aggregate_type: ClassVar[str] = "User"`.

**Files to Modify:**
- `src/emerald/iam/domain/events/__init__.py` — re-export new events

**Tests:**
- `tests/unit/iam/domain/events/test_social_events.py`
- Verify construction, field values, aggregate_type

---

### Phase 2: Domain Layer — Aggregate & Port Changes

#### TASK-004: Make User.username Optional + Add register_via_social()
**Layer:** Domain
**Depends On:** TASK-001, TASK-003

**Description:**
Modify the User aggregate to support optional username and add the social registration factory method.

**Changes to `src/emerald/iam/domain/models/user.py`:**

1. **Constructor:** Change `username: Username` to `username: Username | None = None`
2. **`register()` factory:** Keep `username: Username` required (no change)
3. **New factory `register_via_social()`:**
   ```python
   @classmethod
   def register_via_social(
       cls,
       email: EmailAddress,
       full_name: str | None,
       auth_provider: AuthProvider,
   ) -> User:
   ```
   - `status = ACTIVE`, `email_verified = True`, `password = None`, `username = None`
   - `created_by = user_id` (self-created)
   - Emits `UserRegisteredViaSocialProvider`
4. **`link_auth_provider()`:** Change guard from `_require_status(ACTIVE)` to accepting both `ACTIVE` and `PENDING_VERIFICATION`:
   ```python
   if self.status not in (UserStatus.ACTIVE, UserStatus.PENDING_VERIFICATION):
       raise InvalidStateTransitionError(...)
   ```
5. **`update_username()`:** Handle `self.username` being `None` for `old_username`:
   ```python
   old_username = str(self.username) if self.username is not None else ""
   ```

**Tests:**
- `tests/unit/iam/domain/aggregates/test_user.py` — new test class `TestSocialRegistration`:
  - `register_via_social()` creates correct state (ACTIVE, email_verified, no password, no username, provider linked)
  - Emits `UserRegisteredViaSocialProvider` event
  - `full_name` is set when provided, `None` when not
  - `system_role` defaults to USER
- `TestLinkAuthProvider` — add test for linking from PENDING_VERIFICATION status
- `TestUpdateUsername` — test updating from `None` username (onboarding)

---

#### TASK-005: Add OidcProvider Domain Port
**Layer:** Domain
**Depends On:** TASK-001

**Description:**
Define the `OidcProvider` protocol port that infrastructure will implement.

**Files to Create:**
- `src/emerald/iam/domain/ports/oidc_provider.py`

**Protocol Definition:**
```python
class OidcProvider(Protocol):
    def generate_authorization_url(
        self,
        provider_type: ProviderType,
        redirect_uri: str,
        state: str,
    ) -> str: ...

    def exchange_code_for_claims(
        self,
        provider_type: ProviderType,
        code: str,
        redirect_uri: str,
    ) -> OidcClaims: ...
```

**Files to Modify:**
- `src/emerald/iam/domain/ports/__init__.py` — re-export `OidcProvider`

**Tests:**
- No dedicated tests (protocol is structural) — tested via fake in service tests

---

#### TASK-006: Extend AccessTokenClaims with username
**Layer:** Domain
**Depends On:** None

**Description:**
Add `username: str | None` field to `AccessTokenClaims`. This allows clients to detect onboarding state.

**Files to Modify:**
- `src/emerald/iam/domain/models/access_token_claims.py`

**Change:**
```python
@dataclass(frozen=True)
class AccessTokenClaims:
    sub: uuid.UUID
    email: str
    username: str | None          # NEW — None if onboarding needed
    system_role: SystemRole
    iat: datetime
    exp: datetime
    jti: uuid.UUID
```

**Impact:** All places that construct `AccessTokenClaims` (in `AuthenticationService.login()` and `refresh()`) must now pass `username`. This is addressed in TASK-009.

**Tests:**
- `tests/unit/iam/domain/value_objects/test_access_token_claims.py` — update existing tests to pass `username`, add tests for `username=None`

---

### Phase 3: Application Layer — Commands & DTOs

#### TASK-007: Add New Commands
**Layer:** Application
**Depends On:** None

**Description:**
Create 5 new command dataclasses for social auth operations.

**Files to Create:**
- `src/emerald/iam/application/dtos/commands/social_auth.py`

**Commands:**
```python
@dataclass(frozen=True)
class InitiateOAuthLogin(Command):
    provider_type: str        # "GOOGLE" or "MICROSOFT"
    redirect_uri: str

@dataclass(frozen=True)
class CompleteOAuthLogin(Command):
    provider_type: str
    code: str
    state: str
    redirect_uri: str

@dataclass(frozen=True)
class LinkAuthProviderViaOAuth(Command):
    user_id: str              # UUID as string
    provider_type: str
    code: str
    state: str
    redirect_uri: str

@dataclass(frozen=True)
class UnlinkAuthProvider(Command):
    user_id: str
    provider_type: str

@dataclass(frozen=True)
class SetOnboardingUsername(Command):
    user_id: str
    username: str
```

**Files to Modify:**
- `src/emerald/iam/application/dtos/commands/__init__.py` — re-export new commands

**Tests:**
- Construction tests in `tests/unit/iam/application/commands/test_social_auth_commands.py`

---

#### TASK-008: Extend LoginResult DTO
**Layer:** Application
**Depends On:** None

**Description:**
Add `is_new_registration: bool = False` to `LoginResult`.

**Files to Modify:**
- `src/emerald/iam/application/dtos/responses/authentication.py`

**Change:**
```python
@dataclass(frozen=True)
class LoginResult:
    access_token: str
    refresh_token: str
    expires_in: int
    is_new_registration: bool = False
```

**Impact:** Existing callers (`login()`, `refresh()`) don't pass this field, so they get `False` by default. No breaking changes.

**Tests:**
- Verify default `False`, verify `True` when explicitly set

---

### Phase 4: Application Layer — Service Implementation

#### TASK-009: Extract _issue_tokens() Helper + Add username to Claims
**Layer:** Application
**Depends On:** TASK-006, TASK-008

**Description:**
Refactor `AuthenticationService` to extract token issuance logic into a reusable private method. Update all `AccessTokenClaims` construction to include `username`.

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**Changes:**
1. Add `_issue_tokens()` private method:
   ```python
   def _issue_tokens(
       self,
       user: User,
       portal_context: PortalContext,
       is_new_registration: bool = False,
   ) -> LoginResult:
       # Session limit enforcement
       # Refresh token generation with SUPERADMIN override
       # AccessTokenClaims building (now with username)
       # Return LoginResult
   ```
2. Refactor `login()` to call `_issue_tokens(user, portal_context)`
3. Refactor `refresh()` to include `username` in `AccessTokenClaims`
4. Update `verify_access_token()` — null guard on `user.username`:
   ```python
   display_name = user.full_name if user.full_name else (
       user.username.value if user.username else str(user.email)
   )
   ```

**Tests:**
- Existing login tests must still pass (verify `username` appears in claims)
- Existing refresh tests must still pass
- `verify_access_token` test for user with `username=None`

---

#### TASK-010: Add FakeOidcProvider to Test Fakes
**Layer:** Test Infrastructure
**Depends On:** TASK-005

**Description:**
Create a fake `OidcProvider` implementation for unit testing social auth flows.

**Files to Modify:**
- `tests/unit/iam/fakes.py`

**Implementation:**
```python
class FakeOidcProvider:
    def __init__(self) -> None:
        self._claims: dict[str, OidcClaims] = {}   # keyed by code
        self._auth_urls: dict[str, str] = {}        # keyed by state
        self.generate_call_count: int = 0
        self.exchange_call_count: int = 0

    def set_claims_for_code(self, code: str, claims: OidcClaims) -> None:
        self._claims[code] = claims

    def set_auth_url(self, state: str, url: str) -> None:
        self._auth_urls[state] = url

    def generate_authorization_url(
        self, provider_type: ProviderType, redirect_uri: str, state: str
    ) -> str:
        self.generate_call_count += 1
        return self._auth_urls.get(state, f"https://provider.example.com/auth?state={state}")

    def exchange_code_for_claims(
        self, provider_type: ProviderType, code: str, redirect_uri: str
    ) -> OidcClaims:
        self.exchange_call_count += 1
        if code not in self._claims:
            raise OAuthCodeExchangeError()
        return self._claims[code]
```

---

#### TASK-011: Implement login_with_provider()
**Layer:** Application
**Depends On:** TASK-004, TASK-005, TASK-009, TASK-010

**Description:**
Add the `login_with_provider()` method to `AuthenticationService`. This is the core social login flow handling all cases: existing user (already linked, auto-link, PENDING_VERIFICATION upgrade), new user (social registration), and error cases.

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**Constructor Change:** Add `oidc_provider: OidcProvider` parameter.

**Method Signature:**
```python
def login_with_provider(self, claims: OidcClaims) -> LoginResult:
```

**Flow (matches spec section 7.2-7.4):**
1. Validate `claims.email_verified == True` → raise `ProviderEmailNotVerifiedError`
2. Normalize email via `EmailAddress(claims.email)`
3. Find user by email
4. **User exists:**
   a. DELETED → raise `AuthenticationFailedError`
   b. SUSPENDED → raise `AccountSuspendedError`
   c. Check if provider type already linked:
      - Same type + same external_id → proceed (login)
      - Same type + different external_id → raise `ProviderExternalIdMismatchError`
      - Not linked → link provider
   d. If PENDING_VERIFICATION: link provider (if not yet linked), call `verify_email()`
   e. `record_login()`
   f. `_issue_tokens(user, REGULAR, is_new_registration=False)`
5. **No user:**
   a. Create via `User.register_via_social(email, claims.full_name, auth_provider)`
   b. Save user
   c. `_issue_tokens(user, REGULAR, is_new_registration=True)`

**Service-level event:** Emit `SocialLoginCompleted` for existing user login.

**Tests (`tests/unit/iam/application/services/test_social_login.py`):**
- Existing user, provider already linked → login succeeds, `SocialLoginCompleted` emitted
- Existing ACTIVE user, provider not linked → auto-link, `AuthProviderLinked` + `SocialLoginCompleted`
- PENDING_VERIFICATION user → link, verify, `AuthProviderLinked` + `EmailVerified` + `SocialLoginCompleted`
- DELETED user → `AuthenticationFailedError`
- SUSPENDED user → `AccountSuspendedError`
- External ID mismatch → `ProviderExternalIdMismatchError`
- Provider email not verified → `ProviderEmailNotVerifiedError`
- New user → social registration, `UserRegisteredViaSocialProvider`, `is_new_registration=True`
- New user with `full_name=None` → still registers
- SUPERADMIN social login → 15-min refresh TTL
- `record_login()` called on existing user
- Session limit enforced

---

#### TASK-012: Implement link_provider() and unlink_provider()
**Layer:** Application
**Depends On:** TASK-009, TASK-010

**Description:**
Add `link_provider()` and `unlink_provider()` methods to `AuthenticationService` for authenticated provider management from account settings.

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**link_provider():**
```python
def link_provider(self, user_id: uuid.UUID, claims: OidcClaims) -> None:
    1. Find user by ID → raise AuthenticationFailedError if not found
    2. Require ACTIVE status
    3. Verify claims.email matches user.email → raise ProviderEmailMismatchError
    4. user.link_auth_provider(AuthProvider(claims.provider_type, claims.external_id, now))
       (raises ProviderAlreadyLinkedError if already linked)
    5. Commit
```

**unlink_provider():**
```python
def unlink_provider(self, cmd: UnlinkAuthProvider) -> None:
    1. Find user by ID → raise AuthenticationFailedError if not found
    2. user.unlink_auth_provider(ProviderType(cmd.provider_type))
       (raises CannotUnlinkLastProviderError or ProviderNotLinkedError)
    3. Commit
```

**Tests (`tests/unit/iam/application/services/test_provider_management.py`):**
- Link provider — success, `AuthProviderLinked` emitted
- Link provider — email mismatch → `ProviderEmailMismatchError`
- Link provider — already linked → `ProviderAlreadyLinkedError`
- Link provider — user not found → `AuthenticationFailedError`
- Unlink provider — success, `AuthProviderUnlinked` emitted
- Unlink provider — last provider → `CannotUnlinkLastProviderError`
- Unlink provider — not linked → `ProviderNotLinkedError`
- Unlink PASSWORD when social provider remains → success

---

#### TASK-013: Implement set_onboarding_username()
**Layer:** Application
**Depends On:** TASK-004

**Description:**
Add `set_onboarding_username()` method to `AuthenticationService` (or create a separate small service — prefer keeping in AuthenticationService for cohesion since it's part of the social login lifecycle).

**Files to Modify:**
- `src/emerald/iam/application/services/authentication.py`

**Method:**
```python
def set_onboarding_username(self, cmd: SetOnboardingUsername) -> None:
    1. Find user by ID → raise AuthenticationFailedError if not found
    2. Require ACTIVE status
    3. Validate Username value object (raises InvalidUsernameError)
    4. Check uniqueness via uow.users.exists_by_username(username, include_recently_deleted=True)
       → raise UsernameAlreadyExistsError
    5. user.update_username(username)
    6. Commit
```

**Tests (`tests/unit/iam/application/services/test_onboarding_username.py`):**
- Set username — success, `UserUsernameChanged` emitted
- Username already taken → `UsernameAlreadyExistsError`
- Invalid username format → `InvalidUsernameError`
- User not found → `AuthenticationFailedError`
- User with existing username (not social-only) → still works (update_username allows overwrite)

---

### Phase 5: Re-exports & Integration

#### TASK-014: Update All Re-exports and Public API
**Layer:** Cross-cutting
**Depends On:** TASK-001 through TASK-013

**Description:**
Update all intermediate `__init__.py` files to re-export new types, and update the top-level `src/emerald/iam/__init__.py` `__all__` list.

**New symbols to export:**
- **Value Objects:** `OidcClaims`
- **Events:** `UserRegisteredViaSocialProvider`, `SocialLoginCompleted`
- **Exceptions:** `ProviderEmailNotVerifiedError`, `ProviderEmailMismatchError`, `ProviderExternalIdMismatchError`, `OAuthStateInvalidError`, `OAuthCodeExchangeError`
- **Commands:** `InitiateOAuthLogin`, `CompleteOAuthLogin`, `LinkAuthProviderViaOAuth`, `UnlinkAuthProvider`, `SetOnboardingUsername`
- **Ports:** `OidcProvider`

**Files to Modify:**
- `src/emerald/iam/domain/models/__init__.py`
- `src/emerald/iam/domain/events/__init__.py`
- `src/emerald/iam/domain/exceptions/__init__.py`
- `src/emerald/iam/domain/ports/__init__.py`
- `src/emerald/iam/application/dtos/commands/__init__.py`
- `src/emerald/iam/application/ports/__init__.py` (if OidcProvider is also re-exported at app level)
- `src/emerald/iam/__init__.py`

---

### Phase 6: Quality Assurance

#### TASK-015: Run Full Test Suite + Quality Checks
**Layer:** Cross-cutting
**Depends On:** TASK-014

**Description:**
Run the complete test suite and all quality checks to verify nothing is broken and all new code passes.

**Commands:**
```bash
uv run pytest -v
uv run ruff check --fix .
uv run ruff format .
uv run ty check
```

**Acceptance Criteria:**
- [ ] All existing 823 tests still pass
- [ ] All new tests pass
- [ ] `ruff check` clean (no lint warnings)
- [ ] `ruff format` clean (no formatting changes)
- [ ] `ty check` clean (no type errors)

---

## 5. Task Dependency Graph

```
TASK-001 (OidcClaims) ──┬──► TASK-004 (User aggregate) ──┬──► TASK-011 (login_with_provider)
                         │                                 │
                         ├──► TASK-005 (OidcProvider port) ─┤
                         │                                 │
TASK-002 (Exceptions)    │                                 ├──► TASK-012 (link/unlink provider)
                         │                                 │
TASK-003 (Events) ───────┘                                 ├──► TASK-013 (set_onboarding_username)
                                                           │
TASK-006 (AccessTokenClaims) ──► TASK-009 (_issue_tokens) ─┘
                                                           │
TASK-007 (Commands)                                        │
                                                           │
TASK-008 (LoginResult) ─────► TASK-009 (_issue_tokens) ────┘
                                                           │
TASK-010 (FakeOidcProvider) ──► TASK-011, TASK-012         │
                                                           │
                              TASK-014 (Re-exports) ◄──────┘
                                         │
                              TASK-015 (Quality) ◄─────────┘
```

**Parallelizable groups:**
- TASK-001, TASK-002, TASK-003, TASK-006, TASK-007, TASK-008 (all independent domain/DTO tasks)
- TASK-004, TASK-005 (after TASK-001/003)
- TASK-009, TASK-010 (after TASK-006/008 and TASK-005)
- TASK-011, TASK-012, TASK-013 (after TASK-009/010/004)
- TASK-014 (after all implementation tasks)
- TASK-015 (final)

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `username` optionality breaks existing tests | High | Medium | Update all test factories to pass `username` where needed. Grep for `user.username.value` to find all access points |
| `AccessTokenClaims` change breaks existing test assertions | High | Low | Update all existing claims constructions to include `username` param |
| `link_auth_provider()` guard relaxation introduces unexpected states | Low | Medium | Only allow `PENDING_VERIFICATION` + `ACTIVE`, not `SUSPENDED`/`DELETED`. Add explicit tests for rejected states |
| `AuthenticationService` constructor change breaks existing test setup | Medium | Low | Add `oidc_provider` with a default `None` or make it an optional dependency; or update all test fixtures |

---

## 7. File Summary

### New Files (7)
| File | Purpose |
|------|---------|
| `src/emerald/iam/domain/models/oidc_claims.py` | OidcClaims value object |
| `src/emerald/iam/domain/events/social_events.py` | Social auth domain events |
| `src/emerald/iam/domain/ports/oidc_provider.py` | OidcProvider protocol port |
| `src/emerald/iam/application/dtos/commands/social_auth.py` | Social auth commands |
| `tests/unit/iam/domain/value_objects/test_oidc_claims.py` | OidcClaims tests |
| `tests/unit/iam/domain/events/test_social_events.py` | Social events tests |
| `tests/unit/iam/application/services/test_social_login.py` | Social login service tests |
| `tests/unit/iam/application/services/test_provider_management.py` | Provider link/unlink tests |
| `tests/unit/iam/application/services/test_onboarding_username.py` | Username onboarding tests |

### Modified Files (12)
| File | Changes |
|------|---------|
| `src/emerald/iam/domain/models/user.py` | Optional username, `register_via_social()`, relaxed `link_auth_provider()` guard |
| `src/emerald/iam/domain/models/access_token_claims.py` | Add `username: str \| None` field |
| `src/emerald/iam/domain/exceptions/iam_exceptions.py` | 5 new exception classes |
| `src/emerald/iam/application/dtos/responses/authentication.py` | Add `is_new_registration` to `LoginResult` |
| `src/emerald/iam/application/services/authentication.py` | `_issue_tokens()` helper, `login_with_provider()`, `link_provider()`, `unlink_provider()`, `set_onboarding_username()`, `oidc_provider` dependency |
| `tests/unit/iam/fakes.py` | `FakeOidcProvider` |
| `src/emerald/iam/domain/models/__init__.py` | Re-export `OidcClaims` |
| `src/emerald/iam/domain/events/__init__.py` | Re-export new events |
| `src/emerald/iam/domain/exceptions/__init__.py` | Re-export new exceptions |
| `src/emerald/iam/domain/ports/__init__.py` | Re-export `OidcProvider` |
| `src/emerald/iam/application/dtos/commands/__init__.py` | Re-export new commands |
| `src/emerald/iam/__init__.py` | Update `__all__` with all new symbols |

---

## 8. Definition of Done

- [ ] All 15 tasks completed
- [ ] All acceptance criteria from spec requirements (REQ-001 through REQ-013) covered by tests
- [ ] All existing 823 tests still passing
- [ ] New tests cover all social login paths (happy + error cases)
- [ ] `uv run ruff check` clean
- [ ] `uv run ruff format` clean
- [ ] `uv run ty check` clean
- [ ] IAM `__init__.py` exports all new public symbols
- [ ] No duplicate user creation — account linking works seamlessly
