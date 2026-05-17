# Auth Infrastructure Adapters — Implementation Plan

**Spec:** `.specs/spec-023-auth-infrastructure-adapters/spec.md`
**Version:** 1.0
**Date:** 2026-02-21

---

## 1. Overview

Implement three IAM adapter classes that wrap third-party libraries behind domain protocols: `Argon2PasswordHasher` (argon2-cffi), `JwtTokenService` (PyJWT), and `OidcProviderAdapter` (httpx + PyJWT JWKS). All packages are already installed. Each adapter lives under `src/emerald/iam/adapters/outbound/auth/` and has a corresponding unit test file.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Component |
|---|---|---|
| REQ-001 (Argon2) | Infrastructure (Adapter) | `Argon2PasswordHasher` |
| REQ-002 (JWT) | Infrastructure (Adapter) | `JwtTokenService` |
| REQ-003 (OIDC) | Infrastructure (Adapter) | `OidcProviderAdapter` |

### 2.2 Ports → Adapters

| Port (Protocol) | Location | Adapter | Library |
|---|---|---|---|
| `PasswordHasherPort` | `iam/domain/ports/password_hasher_port.py` | `Argon2PasswordHasher` | `argon2-cffi` |
| `TokenPort` | `iam/application/ports/outbound/token_port.py` | `JwtTokenService` | `PyJWT`, `secrets`, `hashlib` |
| `OidcProviderPort` | `iam/application/ports/outbound/oidc_provider_port.py` | `OidcProviderAdapter` | `httpx`, `PyJWT` (PyJWKClient) |

### 2.3 Domain Types Used

- `AccessTokenClaims` — frozen dataclass: `sub(UUID)`, `email(str)`, `system_role(SystemRole)`, `iat(datetime)`, `exp(datetime)`, `jti(UUID)`, `username(str|None)`
- `OidcClaims` — frozen dataclass: `provider_type`, `external_id`, `email`, `email_verified`, `full_name`
- `ProviderType` — enum: `PASSWORD`, `GOOGLE`, `MICROSOFT`
- `SystemRole` — enum: `USER`, `ADMIN`, `SUPERADMIN`
- `JwtSettings` — pydantic: `secret_key`, `algorithm`, `access_token_ttl_minutes`, `refresh_token_ttl_days`, `issuer`
- `OidcSettings` — pydantic: google/microsoft `client_id`, `client_secret`, `redirect_uri` (all optional)

### 2.4 Exception Mapping

- `jwt.ExpiredSignatureError` → `TokenExpiredError(message)`
- `jwt.InvalidTokenError` (catch-all) → `InvalidTokenError(message)`
- All OIDC external failures → `OAuthCodeExchangeError(message)`

---

## 3. Technical Decisions

### 3.1 No Internal Provider Config Dataclass
The spec shows provider endpoints as constants. We'll use a simple dict/dataclass internal to `OidcProviderAdapter` to hold per-provider config (endpoints + credentials). No new domain types needed.

### 3.2 asyncio.to_thread for CPU-Bound Work
Only `Argon2PasswordHasher.hash()` and `verify()` need `asyncio.to_thread()`. JWT operations are fast enough to run synchronously within an async method.

### 3.3 PyJWKClient Lifecycle
One `PyJWKClient` per configured provider, created in `__init__`. PyJWKClient handles its own JWKS caching (300s default). Runs `get_signing_key_from_jwt()` in `asyncio.to_thread()` since it makes synchronous HTTP calls.

### 3.4 Microsoft Issuer Validation
Use `options={"verify_iss": False}` in `jwt.decode()` for Microsoft, then manually validate issuer prefix `https://login.microsoftonline.com/`.

---

## 4. Implementation Tasks

### Phase 1: Package & Directory Setup

#### TASK-001: Create adapter package structure
**Layer:** Infrastructure
**Depends On:** None

**Description:**
Create the `auth` package under `src/emerald/iam/adapters/outbound/auth/` and corresponding test directory.

**Files to Create:**
- `src/emerald/iam/adapters/outbound/auth/__init__.py` — re-exports all three adapter classes
- `tests/unit/iam/adapters/__init__.py`
- `tests/unit/iam/adapters/outbound/__init__.py`
- `tests/unit/iam/adapters/outbound/auth/__init__.py`

**Acceptance Criteria:**
- [ ] Package directories exist with `__init__.py` files
- [ ] `__init__.py` has `__all__` with the three adapter class names (populated after TASK-002–004)

---

### Phase 2: Adapter Implementations (inside-out)

#### TASK-002: Implement Argon2PasswordHasher
**Layer:** Infrastructure (Adapter)
**Depends On:** TASK-001

**Description:**
Create `argon2_hasher.py` implementing `PasswordHasherPort`. Uses `argon2.PasswordHasher` with library defaults. Both methods use `asyncio.to_thread()`.

**File:** `src/emerald/iam/adapters/outbound/auth/argon2_hasher.py`

**Implementation:**
- `__init__()`: create `argon2.PasswordHasher()` (library defaults: time_cost=3, memory_cost=65536, parallelism=4)
- `async hash(plaintext) -> str`: `await asyncio.to_thread(self._hasher.hash, plaintext)`
- `async verify(plaintext, hashed) -> bool`: wrap in `to_thread`, catch `VerifyMismatchError` → `False`, re-raise others

**Acceptance Criteria:**
- [ ] `hash()` returns Argon2id string (starts with `$argon2id$`)
- [ ] `verify()` returns True/False correctly
- [ ] Different hash calls produce different outputs (random salt)
- [ ] Uses `asyncio.to_thread()` for both methods
- [ ] Stateless — no constructor config needed

---

#### TASK-003: Implement JwtTokenService
**Layer:** Infrastructure (Adapter)
**Depends On:** TASK-001

**Description:**
Create `jwt_token_service.py` implementing `TokenPort`. Uses `PyJWT` for JWT operations and `secrets`/`hashlib` for refresh tokens.

**File:** `src/emerald/iam/adapters/outbound/auth/jwt_token_service.py`

**Implementation:**
- `__init__(settings: JwtSettings)`: store secret_key, algorithm, issuer
- `sign_access_token(claims)`: build payload dict from `AccessTokenClaims` fields, `jwt.encode()`
- `verify_access_token(token)`: `jwt.decode()` with algorithm, issuer verification. Catch `ExpiredSignatureError` → `TokenExpiredError`, `InvalidTokenError` → `InvalidTokenError`. Reconstruct `AccessTokenClaims` from payload; catch `KeyError`/`ValueError` → `InvalidTokenError`
- `generate_refresh_token()`: `secrets.token_urlsafe(32)` + SHA-256 hex
- `hash_token(raw)`: `hashlib.sha256(raw.encode()).hexdigest()`

**Key Details:**
- `sub` and `jti` serialized as `str(uuid)`, deserialized as `UUID(payload["sub"])`
- `system_role` serialized as `.value` string, deserialized as `SystemRole(payload["system_role"])`
- `iat`/`exp` are datetimes; PyJWT handles unix timestamp conversion
- `username` is `str | None` — use `payload.get("username")`

**Acceptance Criteria:**
- [ ] Round-trip sign→verify recovers identical `AccessTokenClaims`
- [ ] Expired token raises `TokenExpiredError`
- [ ] Invalid signature raises `InvalidTokenError`
- [ ] Wrong issuer raises `InvalidTokenError`
- [ ] Malformed/missing claims raises `InvalidTokenError`
- [ ] `generate_refresh_token()` returns unique `(raw, hash)` tuples
- [ ] `hash_token()` is deterministic SHA-256

---

#### TASK-004: Implement OidcProviderAdapter
**Layer:** Infrastructure (Adapter)
**Depends On:** TASK-001

**Description:**
Create `oidc_provider.py` implementing `OidcProviderPort`. Uses `httpx.AsyncClient` for token exchange and `PyJWKClient` for JWKS.

**File:** `src/emerald/iam/adapters/outbound/auth/oidc_provider.py`

**Implementation:**

Internal provider config structure (private dataclass or dict):
```
_ProviderConfig:
    client_id: str
    client_secret: str
    auth_endpoint: str
    token_endpoint: str
    jwks_uri: str
    issuer: str | None  (None for Microsoft — prefix-validated)
```

**Constructor:**
- Accept `OidcSettings` + `httpx.AsyncClient`
- Build `_configs: dict[ProviderType, _ProviderConfig]` for configured providers (where client_id is not None)
- Create `_jwk_clients: dict[ProviderType, PyJWKClient]` per configured provider

**`generate_authorization_url`:**
1. `_get_config(provider_type)` — raises `OAuthCodeExchangeError` if not configured or PASSWORD
2. Build URL with: `client_id`, `redirect_uri` (param), `response_type=code`, `scope=openid email profile`, `state` (param), `nonce` (uuid4), `access_type=offline` (Google only)
3. Return URL string (use `urllib.parse.urlencode`)

**`exchange_code_for_claims`:**
1. `_get_config(provider_type)`
2. POST to token endpoint with `grant_type=authorization_code`, `code`, `redirect_uri`, `client_id`, `client_secret`
3. Raise `OAuthCodeExchangeError` on HTTP error or non-200
4. Extract `id_token` from JSON response
5. Get signing key via `PyJWKClient.get_signing_key_from_jwt()` (in `asyncio.to_thread`)
6. `jwt.decode()` id_token with signing key, audience=client_id, algorithms=["RS256"]
   - Google: verify_iss=True, issuer="https://accounts.google.com"
   - Microsoft: verify_iss=False, then manually check issuer prefix
7. Extract `sub`, `email`, `name` from payload; wrap in `OidcClaims`
8. All exceptions caught → `OAuthCodeExchangeError`

**Provider Constants:**

| Provider | Auth Endpoint | Token Endpoint | JWKS URI | Issuer |
|---|---|---|---|---|
| Google | `https://accounts.google.com/o/oauth2/v2/auth` | `https://oauth2.googleapis.com/token` | `https://www.googleapis.com/oauth2/v3/certs` | `https://accounts.google.com` |
| Microsoft | `https://login.microsoftonline.com/common/oauth2/v2.0/authorize` | `https://login.microsoftonline.com/common/oauth2/v2.0/token` | `https://login.microsoftonline.com/common/discovery/v2.0/keys` | prefix: `https://login.microsoftonline.com/` |

**Acceptance Criteria:**
- [ ] `generate_authorization_url` builds correct URLs with all query params
- [ ] Unconfigured provider raises `OAuthCodeExchangeError`
- [ ] `ProviderType.PASSWORD` raises `OAuthCodeExchangeError`
- [ ] `exchange_code_for_claims` returns `OidcClaims` on success
- [ ] All external failures map to `OAuthCodeExchangeError`
- [ ] `httpx.AsyncClient` is injected, not created
- [ ] `PyJWKClient` instances created per configured provider

---

### Phase 3: Package Re-exports

#### TASK-005: Update `__init__.py` re-exports
**Layer:** Infrastructure
**Depends On:** TASK-002, TASK-003, TASK-004

**Description:**
Update `src/emerald/iam/adapters/outbound/auth/__init__.py` with explicit `__all__` re-exporting all three adapter classes.

**Acceptance Criteria:**
- [ ] `from emerald.iam.adapters.outbound.auth import Argon2PasswordHasher, JwtTokenService, OidcProviderAdapter` works

---

### Phase 4: Unit Tests

#### TASK-006: Unit tests for Argon2PasswordHasher
**Layer:** Testing
**Depends On:** TASK-002

**File:** `tests/unit/iam/adapters/outbound/auth/test_argon2_hasher.py`

**Tests (real argon2-cffi, no mocks):**
- `test_hash_produces_argon2id_format` — output starts with `$argon2id$`
- `test_verify_correct_password` — `verify(pw, hash(pw))` → True
- `test_verify_wrong_password` — `verify(wrong, hash(pw))` → False
- `test_hash_produces_unique_hashes` — two `hash(same)` calls differ
- `test_verify_corrupt_hash_raises` — `verify(pw, "garbage")` raises (not returns False)

**Acceptance Criteria:**
- [ ] 5 tests, all passing
- [ ] No mocks — uses real argon2-cffi library

---

#### TASK-007: Unit tests for JwtTokenService
**Layer:** Testing
**Depends On:** TASK-003

**File:** `tests/unit/iam/adapters/outbound/auth/test_jwt_token_service.py`

**Fixtures:**
- `jwt_settings` — `JwtSettings(secret_key="test-secret-key-minimum-length", algorithm="HS256", issuer="test-issuer", ...)`
- `service` — `JwtTokenService(jwt_settings)`
- `sample_claims` — valid `AccessTokenClaims` with known values

**Tests:**
- `test_sign_and_verify_round_trip` — sign → verify → same claims
- `test_payload_contains_all_claims` — decode raw (no verify), check all fields
- `test_verify_expired_token_raises_token_expired` — claims with past exp
- `test_verify_invalid_signature_raises_invalid_token` — token from different key
- `test_verify_wrong_issuer_raises_invalid_token` — different issuer in settings
- `test_verify_malformed_token_raises_invalid_token` — random string
- `test_verify_missing_claims_raises_invalid_token` — manually crafted JWT missing fields
- `test_generate_refresh_token_returns_tuple` — returns (str, str)
- `test_generate_refresh_token_unique` — two calls differ
- `test_hash_token_deterministic` — same input → same output
- `test_hash_token_matches_generate` — `hash_token(raw)` == hash from generate
- `test_username_none_handled` — None username round-trips correctly

**Acceptance Criteria:**
- [ ] 12 tests, all passing
- [ ] Uses real PyJWT library, no mocks
- [ ] Tests both happy paths and error cases

---

#### TASK-008: Unit tests for OidcProviderAdapter
**Layer:** Testing
**Depends On:** TASK-004

**File:** `tests/unit/iam/adapters/outbound/auth/test_oidc_provider.py`

**Approach:** Mock `httpx.AsyncClient` responses and patch `PyJWKClient`. Generate real RS256 JWT id_tokens for verification tests using a test RSA key pair.

**Fixtures:**
- `oidc_settings` — `OidcSettings(google_client_id="google-id", google_client_secret="google-secret", google_redirect_uri="http://localhost/callback", ...)`
- `rsa_private_key` / `rsa_public_key` — test RSA key pair for signing id_tokens
- `mock_http_client` — `AsyncMock` of `httpx.AsyncClient`
- `adapter` — `OidcProviderAdapter(settings, mock_http_client)` with patched `PyJWKClient`

**Tests:**
- `test_generate_auth_url_google` — URL contains Google endpoint, client_id, scope, state
- `test_generate_auth_url_microsoft` — URL contains Microsoft endpoint and parameters
- `test_generate_auth_url_unconfigured_provider_raises` — no config → `OAuthCodeExchangeError`
- `test_generate_auth_url_password_provider_raises` — PASSWORD → `OAuthCodeExchangeError`
- `test_exchange_code_success_google` — mock token response + valid id_token → `OidcClaims`
- `test_exchange_code_success_microsoft` — same for Microsoft with issuer prefix check
- `test_exchange_code_http_error_raises` — HTTP error → `OAuthCodeExchangeError`
- `test_exchange_code_no_id_token_raises` — missing id_token → `OAuthCodeExchangeError`
- `test_exchange_code_invalid_signature_raises` — bad key → `OAuthCodeExchangeError`
- `test_exchange_code_expired_id_token_raises` — expired → `OAuthCodeExchangeError`
- `test_exchange_code_missing_email_raises` — no email claim → `OAuthCodeExchangeError`
- `test_exchange_code_unverified_email_raises` — email_verified=false → error via `OidcClaims`

**Acceptance Criteria:**
- [ ] 12 tests, all passing
- [ ] Mock HTTP client (no real network calls)
- [ ] Real RSA key pair for id_token signing/verification in tests
- [ ] All error paths tested

---

### Phase 5: Quality Checks

#### TASK-009: Run linting, formatting, and type checks
**Layer:** Cross-cutting
**Depends On:** TASK-005, TASK-006, TASK-007, TASK-008

**Description:**
Run the full quality suite and fix any issues.

**Commands:**
```bash
uv run ruff format .
uv run ruff check --fix .
uv run ty check
uv run pytest tests/unit/iam/adapters/ -v
uv run pytest -v  # full suite to ensure no regressions
```

**Acceptance Criteria:**
- [ ] `ruff format` — no changes needed
- [ ] `ruff check` — no violations
- [ ] `ty check` — no errors
- [ ] All new tests pass
- [ ] Full test suite passes (no regressions)

---

## 5. Task Dependency Graph

```
TASK-001 (package structure)
    ├──► TASK-002 (Argon2) ──► TASK-006 (Argon2 tests)
    ├──► TASK-003 (JWT)    ──► TASK-007 (JWT tests)
    └──► TASK-004 (OIDC)   ──► TASK-008 (OIDC tests)
                                    │
TASK-002,003,004 ──► TASK-005 (re-exports)
                                    │
TASK-005,006,007,008 ──► TASK-009 (quality checks)
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| PyJWKClient sync calls block event loop | Medium | Medium | Run `get_signing_key_from_jwt()` in `asyncio.to_thread()` |
| Microsoft issuer validation too loose | Low | Medium | Validate prefix `https://login.microsoftonline.com/` + `v2.0` suffix |
| `ty` strict typing issues with third-party libs | Medium | Low | Use targeted `# type: ignore` with specific codes if needed |
| Argon2 hash format changes across versions | Low | Low | Pin `argon2-cffi` version; test format prefix |

---

## 7. Definition of Done

- [ ] All 9 tasks completed
- [ ] ~29 unit tests passing (5 + 12 + 12)
- [ ] Full test suite passes (no regressions from 2368 existing tests)
- [ ] `ruff format` clean
- [ ] `ruff check` clean
- [ ] `ty check` clean
- [ ] All three adapters importable from `emerald.iam.adapters.outbound.auth`
