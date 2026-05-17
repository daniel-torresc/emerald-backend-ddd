# Spec 023: Auth Infrastructure Adapters

**Version:** 1.0
**Status:** Draft
**Date:** 2026-02-21
**Bounded Context:** IAM (Adapters Layer)
**Dependencies:** 021 (Configuration & Database Foundation), 003 (Authentication & Sessions), 005 (Federated Authentication)
**Blocks:** 026 (Cross-Context Adapters & Composition Root)

---

## 1. Overview

This spec implements the three non-database IAM adapter ports: password hashing, JWT token signing/verification, and OIDC provider communication. Each adapter wraps a single third-party library and implements a domain Protocol. The domain layer has zero knowledge of Argon2, JWT, or HTTP.

---

## 2. Background & Context

### Problem Statement

The IAM domain layer defines three outbound ports (`PasswordHasherPort`, `TokenPort`, `OidcProviderPort`) that require infrastructure implementations to function. Without these adapters, the authentication and identity system cannot hash passwords, issue tokens, or communicate with external OIDC providers.

### Business Goals

- Enable secure password storage using industry-standard Argon2id
- Support JWT-based stateless access tokens for API authentication
- Allow social login via Google and Microsoft OIDC providers

---

## 3. Scope

### In Scope

- `Argon2PasswordHasher` — wraps `argon2-cffi`, implements `PasswordHasherPort`
- `JwtTokenService` — wraps `PyJWT`, implements `TokenPort`
- `OidcProviderAdapter` — wraps `httpx` + `PyJWT` (for JWKS), implements `OidcProviderPort`
- Unit tests for all three adapters

### Out of Scope

- Database persistence (spec 022)
- Token storage (RefreshTokenRepository — spec 022)
- FastAPI auth dependency (spec 027)
- Additional OIDC providers beyond Google and Microsoft
- Integration tests against real OIDC endpoints

---

## 4. Protocols Implemented

All protocols are **async** and use structural subtyping (`typing.Protocol`).

### 4.1 PasswordHasherPort

**Location:** `src/emerald/iam/domain/ports/password_hasher_port.py`

```python
class PasswordHasherPort(Protocol):
    async def hash(self, plaintext: str) -> str: ...
    async def verify(self, plaintext: str, hashed: str) -> bool: ...
```

### 4.2 TokenPort

**Location:** `src/emerald/iam/application/ports/outbound/token_port.py`

```python
class TokenPort(Protocol):
    async def sign_access_token(self, claims: AccessTokenClaims) -> str: ...
    async def verify_access_token(self, token: str) -> AccessTokenClaims: ...
    async def generate_refresh_token(self) -> tuple[str, str]: ...
    async def hash_token(self, raw_token: str) -> str: ...
```

### 4.3 OidcProviderPort

**Location:** `src/emerald/iam/application/ports/outbound/oidc_provider_port.py`

```python
class OidcProviderPort(Protocol):
    async def generate_authorization_url(
        self, provider_type: ProviderType, redirect_uri: str, state: str,
    ) -> str: ...

    async def exchange_code_for_claims(
        self, provider_type: ProviderType, code: str, redirect_uri: str,
    ) -> OidcClaims: ...
```

---

## 5. Requirements

### 5.1 Argon2 Password Hasher

#### REQ-001: Argon2PasswordHasher implements PasswordHasherPort
**Priority:** Must Have

**Description:** Wraps `argon2-cffi` to hash and verify passwords using the Argon2id variant.

**Implementation Details:**

```
Argon2PasswordHasher:
    __init__():
        Creates argon2.PasswordHasher with library defaults
        (time_cost=3, memory_cost=65536, parallelism=4)

    async hash(plaintext: str) -> str:
        Returns Argon2id hash string via argon2.PasswordHasher.hash()
        (CPU-bound; runs in thread executor)

    async verify(plaintext: str, hashed: str) -> bool:
        Returns True if password matches hash
        Catches argon2.exceptions.VerifyMismatchError → returns False
        Re-raises other argon2 exceptions (corrupt hash, etc.)
        (CPU-bound; runs in thread executor)
```

**Rules:**
- Uses Argon2id variant (library default, recommended for password hashing)
- Library default parameters are suitable for production
- `hash()` and `verify()` are CPU-bound — use `asyncio.to_thread()` to avoid blocking the event loop
- Stateless — no configuration required beyond library defaults
- Different `hash()` calls for the same password produce different results (random salt)

**Acceptance Criteria:**
- [ ] `hash()` produces valid Argon2id hash string (starts with `$argon2id$`)
- [ ] `verify()` returns `True` for correct password
- [ ] `verify()` returns `False` for incorrect password
- [ ] Different `hash()` calls produce different hashes (random salt)
- [ ] Methods are async and use `asyncio.to_thread()`

---

### 5.2 JWT Token Service

#### REQ-002: JwtTokenService implements TokenPort
**Priority:** Must Have

**Description:** Wraps `PyJWT` for JWT signing/verification and `secrets`/`hashlib` for refresh token generation and hashing.

**Constructor:**

```
JwtTokenService:
    __init__(settings: JwtSettings):
        Stores secret_key, algorithm, issuer, access_token_ttl_minutes
```

**`JwtSettings` reference** (from spec-021, `src/emerald/shared_kernel/infrastructure/config/settings.py`):

| Field | Type | Default | Env Var |
|-------|------|---------|---------|
| `secret_key` | `str` | (required) | `JWT_SECRET_KEY` |
| `algorithm` | `Literal["HS256","HS384","HS512","RS256"]` | `"HS256"` | `JWT_ALGORITHM` |
| `access_token_ttl_minutes` | `int` | `15` | `JWT_ACCESS_TOKEN_TTL_MINUTES` |
| `refresh_token_ttl_days` | `int` | `30` | `JWT_REFRESH_TOKEN_TTL_DAYS` |
| `issuer` | `str` | `"emerald-finance"` | `JWT_ISSUER` |

#### REQ-002a: sign_access_token

```
async sign_access_token(claims: AccessTokenClaims) -> str:
    Payload mapping from AccessTokenClaims fields:
        sub: str(claims.sub)         # UUID → string
        email: claims.email
        username: claims.username    # str | None
        system_role: claims.system_role.value  # enum → string
        iss: settings.issuer
        iat: claims.iat              # datetime (UTC)
        exp: claims.exp              # datetime (UTC)
        jti: str(claims.jti)         # UUID → string
    Signs with configured algorithm (default HS256)
    Returns encoded JWT string
```

**Rules:**
- Payload uses the claims' own `iat`/`exp` timestamps (the application service sets these)
- `sub` and `jti` are serialized as strings
- `system_role` is serialized as its enum value string

#### REQ-002b: verify_access_token

```
async verify_access_token(token: str) -> AccessTokenClaims:
    Decodes JWT with:
        - Signature verification (secret_key + algorithm)
        - Expiration check (exp)
        - Issuer check (iss must match settings.issuer)
    Reconstructs AccessTokenClaims:
        sub: UUID(payload["sub"])
        email: payload["email"]
        username: payload.get("username")
        system_role: SystemRole(payload["system_role"])
        iat: datetime.fromtimestamp(payload["iat"], tz=UTC)
        exp: datetime.fromtimestamp(payload["exp"], tz=UTC)
        jti: UUID(payload["jti"])
    Raises domain exceptions on failure (see error mapping)
```

**Error Mapping:**

| PyJWT Exception | Domain Exception |
|---|---|
| `jwt.ExpiredSignatureError` | `TokenExpiredError(message)` |
| `jwt.InvalidTokenError` (and all other subclasses) | `InvalidTokenError(message)` |

**Rules:**
- All PyJWT exceptions map to either `TokenExpiredError` or `InvalidTokenError`
- `ExpiredSignatureError` is caught first (it's a subclass of `InvalidTokenError`)
- Invalid/missing claims during reconstruction also raise `InvalidTokenError`

#### REQ-002c: generate_refresh_token

```
async generate_refresh_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    Returns (raw_token, token_hash)
```

**Rules:**
- Returns `(raw_token, token_hash)` tuple — matches `TokenPort` signature
- Uses `secrets.token_urlsafe(32)` for 256-bit entropy
- SHA-256 is appropriate since the input is already high-entropy (no salt needed)

#### REQ-002d: hash_token

```
async hash_token(raw_token: str) -> str:
    Returns hashlib.sha256(raw_token.encode()).hexdigest()
```

**Rules:**
- Deterministic: same input always produces same hash
- Used for hashing refresh tokens and password reset tokens for lookup

**Acceptance Criteria:**
- [ ] `sign_access_token()` returns valid JWT string
- [ ] JWT payload contains all required claims (`sub`, `email`, `system_role`, `exp`, `iat`, `iss`, `jti`)
- [ ] `verify_access_token()` reconstructs `AccessTokenClaims` from valid token
- [ ] `verify_access_token()` raises `TokenExpiredError` on expired token
- [ ] `verify_access_token()` raises `InvalidTokenError` on invalid signature
- [ ] `verify_access_token()` raises `InvalidTokenError` on wrong issuer
- [ ] `verify_access_token()` raises `InvalidTokenError` on malformed/missing claims
- [ ] `generate_refresh_token()` returns `(raw_token, hash)` tuple
- [ ] `generate_refresh_token()` produces unique values on each call
- [ ] `hash_token()` returns deterministic SHA-256 hex digest
- [ ] `hash_token()` returns same hash for same input
- [ ] Round-trip: sign → verify recovers identical `AccessTokenClaims`

---

### 5.3 OIDC Provider Adapter

#### REQ-003: OidcProviderAdapter implements OidcProviderPort
**Priority:** Must Have

**Description:** Uses `httpx.AsyncClient` for OAuth 2.0 token exchange and `PyJWT`'s `PyJWKClient` for JWKS-based id_token verification with Google and Microsoft.

**Constructor:**

```
OidcProviderAdapter:
    __init__(settings: OidcSettings, http_client: httpx.AsyncClient):
        Stores provider configurations derived from settings
        Creates PyJWKClient instances per provider (for JWKS caching)
        Uses injected httpx client for token exchange
```

**`OidcSettings` reference** (from spec-021):

| Field | Type | Env Var |
|-------|------|---------|
| `google_client_id` | `str \| None` | `OIDC_GOOGLE_CLIENT_ID` |
| `google_client_secret` | `str \| None` | `OIDC_GOOGLE_CLIENT_SECRET` |
| `google_redirect_uri` | `str \| None` | `OIDC_GOOGLE_REDIRECT_URI` |
| `microsoft_client_id` | `str \| None` | `OIDC_MICROSOFT_CLIENT_ID` |
| `microsoft_client_secret` | `str \| None` | `OIDC_MICROSOFT_CLIENT_SECRET` |
| `microsoft_redirect_uri` | `str \| None` | `OIDC_MICROSOFT_REDIRECT_URI` |

All fields are optional. The model validator ensures that if `client_id` is set for a provider, `client_secret` and `redirect_uri` must also be set.

#### REQ-003a: generate_authorization_url

```
async generate_authorization_url(
    provider_type: ProviderType, redirect_uri: str, state: str,
) -> str:
    1. Look up provider config (client_id, endpoints)
    2. Raise OAuthCodeExchangeError if provider not configured
    3. Build authorization URL with query parameters:
        - client_id
        - redirect_uri (from parameter, NOT from settings)
        - response_type=code
        - scope=openid email profile
        - state (CSRF protection)
        - nonce (generated internally, UUID4)
        - access_type=offline (Google-specific, for refresh tokens)
    4. Return full URL string
```

**Provider Endpoints:**

| Provider | Authorization Endpoint |
|---|---|
| Google | `https://accounts.google.com/o/oauth2/v2/auth` |
| Microsoft | `https://login.microsoftonline.com/common/oauth2/v2.0/authorize` |

**Rules:**
- `redirect_uri` parameter comes from the caller (API layer), not from settings
- `state` comes from the caller (API layer generates and validates CSRF state)
- `nonce` is generated internally by the adapter (UUID4 string)
- Raises `OAuthCodeExchangeError` if provider type has no configuration (client_id is None)
- `ProviderType.PASSWORD` is never valid — raise `OAuthCodeExchangeError`

#### REQ-003b: exchange_code_for_claims

```
async exchange_code_for_claims(
    provider_type: ProviderType, code: str, redirect_uri: str,
) -> OidcClaims:
    1. Look up provider config
    2. POST to token endpoint:
        - grant_type=authorization_code
        - code
        - redirect_uri (from parameter)
        - client_id
        - client_secret
    3. Parse response → extract id_token
    4. Fetch signing key from JWKS via PyJWKClient
    5. Decode and verify id_token:
        - Signature verification (RS256)
        - Audience check (must match client_id)
        - Issuer check
        - Expiration check
    6. Extract claims → build OidcClaims:
        - provider_type: from parameter
        - external_id: payload["sub"]
        - email: payload["email"]
        - email_verified: payload.get("email_verified", False)
        - full_name: payload.get("name")
    7. Return OidcClaims (its __post_init__ validates email_verified=True)
```

**Provider Token Endpoints:**

| Provider | Token Endpoint | JWKS URI | Issuer |
|---|---|---|---|
| Google | `https://oauth2.googleapis.com/token` | `https://www.googleapis.com/oauth2/v3/certs` | `https://accounts.google.com` |
| Microsoft | `https://login.microsoftonline.com/common/oauth2/v2.0/token` | `https://login.microsoftonline.com/common/discovery/v2.0/keys` | `https://login.microsoftonline.com/{tenant}/v2.0` |

**Microsoft Issuer Note:** Microsoft's issuer contains the tenant ID. Use `options={"verify_iss": False}` and manually validate the issuer starts with `https://login.microsoftonline.com/`.

**JWKS Caching:**
- `PyJWKClient` handles caching internally (default lifespan: 300 seconds)
- On key-not-found, `PyJWKClient` automatically refetches
- One `PyJWKClient` instance per provider, created in `__init__`

**Error Handling:**

| Scenario | Behavior |
|---|---|
| Provider not configured (client_id is None) | `OAuthCodeExchangeError("Provider {type} is not configured")` |
| `ProviderType.PASSWORD` | `OAuthCodeExchangeError("PASSWORD is not a social provider")` |
| HTTP error on token exchange | `OAuthCodeExchangeError(message)` |
| Non-200 response from token endpoint | `OAuthCodeExchangeError(message)` |
| Missing id_token in response | `OAuthCodeExchangeError("No id_token in provider response")` |
| JWKS fetch failure | `OAuthCodeExchangeError(message)` |
| id_token signature invalid | `OAuthCodeExchangeError(message)` |
| id_token expired | `OAuthCodeExchangeError(message)` |
| Missing required claims (email, sub) | `OAuthCodeExchangeError(message)` |
| email_verified=False | Handled by `OidcClaims.__post_init__` → `InvalidValueError` |

**Rules:**
- All external failures (network, validation) map to `OAuthCodeExchangeError`
- The adapter never exposes raw HTTP errors or PyJWT errors to the domain
- `httpx.AsyncClient` is injected (not created) — caller manages lifecycle
- `PyJWKClient` instances are created internally (one per configured provider)

---

## 6. File Structure

```
src/emerald/iam/
    adapters/
        outbound/
            auth/
                __init__.py              # Re-exports all three adapters
                argon2_hasher.py         # Argon2PasswordHasher
                jwt_token_service.py     # JwtTokenService
                oidc_provider.py         # OidcProviderAdapter
            persistence/                 # (existing from spec-022)
                ...

tests/unit/iam/
    adapters/
        outbound/
            auth/
                __init__.py
                test_argon2_hasher.py
                test_jwt_token_service.py
                test_oidc_provider.py
```

---

## 7. Dependencies (Python Packages)

| Package | Purpose | Add Command |
|---|---|---|
| `argon2-cffi` | Argon2id password hashing | `uv add argon2-cffi` |
| `PyJWT[crypto]` | JWT signing/verification + JWKS client | `uv add "PyJWT[crypto]"` |
| `httpx` | Async HTTP client for OIDC token exchange | `uv add httpx` |

**Note:** `PyJWT[crypto]` installs `cryptography` for RS256 support needed for OIDC id_token verification.

---

## 8. Testing Strategy

### 8.1 Argon2 Password Hasher Tests

**Approach:** Real `argon2-cffi` — lightweight, no network, deterministic.

| Test | Description |
|---|---|
| `test_hash_produces_argon2id_format` | Hash output starts with `$argon2id$` |
| `test_verify_correct_password` | `verify(password, hash(password))` returns `True` |
| `test_verify_wrong_password` | `verify(wrong, hash(password))` returns `False` |
| `test_hash_produces_unique_hashes` | Two `hash()` calls with same input produce different outputs |
| `test_verify_corrupt_hash_raises` | `verify(password, "garbage")` raises (not returns False) |

### 8.2 JWT Token Service Tests

**Approach:** Real `PyJWT` — lightweight, no network. Use known `JwtSettings` fixture.

| Test | Description |
|---|---|
| `test_sign_and_verify_round_trip` | Sign claims → verify → identical `AccessTokenClaims` |
| `test_payload_contains_all_claims` | Decode without verification, check all fields present |
| `test_verify_expired_token_raises_token_expired` | Token with past `exp` raises `TokenExpiredError` |
| `test_verify_invalid_signature_raises_invalid_token` | Token signed with wrong key raises `InvalidTokenError` |
| `test_verify_wrong_issuer_raises_invalid_token` | Token with different issuer raises `InvalidTokenError` |
| `test_verify_malformed_token_raises_invalid_token` | Random string raises `InvalidTokenError` |
| `test_verify_missing_claims_raises_invalid_token` | Token missing required claims raises `InvalidTokenError` |
| `test_generate_refresh_token_returns_tuple` | Returns `(raw_token, hash)` tuple |
| `test_generate_refresh_token_unique` | Two calls produce different raw tokens |
| `test_hash_token_deterministic` | Same input → same SHA-256 hex digest |
| `test_hash_token_matches_generate` | `hash_token(raw)` matches hash from `generate_refresh_token()` |
| `test_username_none_handled` | Claims with `username=None` round-trip correctly |

### 8.3 OIDC Provider Adapter Tests

**Approach:** Mock `httpx.AsyncClient` responses. Mock `PyJWKClient` for JWKS. No real network calls.

| Test | Description |
|---|---|
| `test_generate_auth_url_google` | URL contains correct Google endpoint, client_id, scopes, state |
| `test_generate_auth_url_microsoft` | URL contains correct Microsoft endpoint and parameters |
| `test_generate_auth_url_unconfigured_provider_raises` | Provider with no client_id raises `OAuthCodeExchangeError` |
| `test_generate_auth_url_password_provider_raises` | `ProviderType.PASSWORD` raises `OAuthCodeExchangeError` |
| `test_exchange_code_success_google` | Mock token response + valid id_token → returns `OidcClaims` |
| `test_exchange_code_success_microsoft` | Mock token response + valid id_token → returns `OidcClaims` |
| `test_exchange_code_http_error_raises` | HTTP error → `OAuthCodeExchangeError` |
| `test_exchange_code_no_id_token_raises` | Response missing id_token → `OAuthCodeExchangeError` |
| `test_exchange_code_invalid_signature_raises` | Bad JWKS → `OAuthCodeExchangeError` |
| `test_exchange_code_expired_id_token_raises` | Expired id_token → `OAuthCodeExchangeError` |
| `test_exchange_code_missing_email_raises` | id_token without email → `OAuthCodeExchangeError` |
| `test_exchange_code_unverified_email_raises` | email_verified=false → error (via `OidcClaims` validation) |

---

## 9. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|---|---|
| Argon2: corrupt/truncated hash in `verify()` | Re-raises argon2 exception (not caught as mismatch) |
| JWT: token with future `iat` | PyJWT allows by default; no special handling needed |
| JWT: claims with extra unknown fields | Ignored during verify (only mapped fields extracted) |
| JWT: `None` username in payload | Reconstructed as `username=None` in `AccessTokenClaims` |
| OIDC: provider configured but endpoints unreachable | `OAuthCodeExchangeError` with descriptive message |
| OIDC: valid token response but JWKS fetch fails | `OAuthCodeExchangeError` with descriptive message |
| OIDC: Microsoft multi-tenant issuer | Skip strict issuer validation; check prefix instead |
| OIDC: Google returns `email_verified=false` | `OidcClaims.__post_init__` raises `InvalidValueError` |

---

## 10. Constraints

- **Async-only:** All adapter methods are `async` to match the domain protocols
- **CPU-bound work:** Argon2 hashing uses `asyncio.to_thread()` to avoid blocking
- **No global state:** Adapters are instantiated with their dependencies (settings, http_client)
- **Single responsibility:** Each adapter wraps exactly one third-party library concern
- **Domain purity:** Adapters never import from other adapters; only from domain/application layer

---

## 11. Open Questions

None — all questions resolved during clarification.

---

## 12. Glossary

- **Argon2id:** Memory-hard password hashing algorithm, recommended by OWASP
- **JWKS:** JSON Web Key Set — a set of public keys used to verify JWT signatures
- **PKCE:** Proof Key for Code Exchange — OAuth 2.0 extension for public clients
- **PyJWKClient:** PyJWT's built-in utility for fetching and caching JWKS endpoints
- **TokenPort:** Application-layer port (not domain) because token operations are an application concern
