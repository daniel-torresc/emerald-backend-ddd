# Spec 023: Auth Infrastructure Adapters

**Status:** Draft
**Bounded Context:** IAM (Infrastructure)
**Dependencies:** 021 (Configuration & Database Foundation), 003 (Authentication & Sessions), 005 (Federated Authentication)
**Blocks:** 026

---

## 1. Overview

This spec implements the non-database auth ports — password hashing, JWT token signing/verification, and OIDC provider communication. These adapters translate between domain protocols and third-party libraries (`argon2-cffi`, `PyJWT`, `httpx`).

**Key Principle:** Each adapter wraps a single third-party library and implements a domain Protocol. The domain layer has zero knowledge of Argon2, JWT, or HTTP. Adapters are stateless where possible.

## 2. Scope

### In Scope

- `Argon2PasswordHasher` — wraps `argon2-cffi`, implements `PasswordHasher` protocol
- `JwtTokenService` — wraps `PyJWT`, implements `TokenService` protocol
- `OidcProviderAdapter` — uses `httpx.AsyncClient` for Google/Microsoft OIDC, implements `OidcProvider` protocol

### Out of Scope

- Database persistence (spec 022)
- Token storage (RefreshTokenRepository handles that — spec 022)
- FastAPI auth dependency (spec 027)
- Additional OIDC providers beyond Google and Microsoft

## 3. Argon2 Password Hasher

### 3.1 Purpose

Implements the `PasswordHasher` protocol (spec 002) using the Argon2id algorithm via `argon2-cffi`.

### 3.2 Protocol Implemented

```
PasswordHasher (Protocol):
    def hash(self, password: str) -> str
    def verify(self, password: str, hashed: str) -> bool
```

### 3.3 Implementation Details

```
Argon2PasswordHasher:
    __init__():
        Creates argon2.PasswordHasher with default parameters

    hash(password: str) -> str:
        Returns Argon2id hash string
        Uses library defaults (time_cost=3, memory_cost=65536, parallelism=4)

    verify(password: str, hashed: str) -> bool:
        Returns True if password matches hash
        Returns False on VerifyMismatchError
        Raises on other argon2 errors (corrupt hash)
```

**Rules:**
- Uses Argon2id variant (recommended for password hashing)
- Library default parameters are suitable for production
- `verify()` catches `VerifyMismatchError` and returns `False`, re-raises other exceptions
- Stateless — no configuration needed

## 4. JWT Token Service

### 4.1 Purpose

Implements the `TokenService` protocol (spec 003) using PyJWT for signing and verifying access tokens, and generating/hashing refresh tokens.

### 4.2 Protocol Implemented

```
TokenService (Protocol):
    def create_access_token(self, claims: AccessTokenClaims) -> str
    def verify_access_token(self, token: str) -> AccessTokenClaims
    def generate_refresh_token(self) -> str
    def hash_refresh_token(self, token: str) -> str
```

### 4.3 Implementation Details

```
JwtTokenService:
    __init__(settings: JwtSettings):
        Stores secret_key, algorithm, issuer, TTLs

    create_access_token(claims: AccessTokenClaims) -> str:
        Payload:
            sub: str(claims.user_id)
            email: claims.email
            username: claims.username
            system_role: claims.system_role
            portal_context: claims.portal_context
            admin_permissions: list(claims.admin_permissions)
            iss: settings.issuer
            iat: now (UTC)
            exp: now + access_token_ttl
            jti: uuid4() (unique token ID)
        Signs with HMAC-SHA256 (or configured algorithm)
        Returns encoded JWT string

    verify_access_token(token: str) -> AccessTokenClaims:
        Decodes and validates JWT:
            - Verifies signature
            - Checks expiration (exp)
            - Checks issuer (iss)
        Reconstructs AccessTokenClaims from payload
        Raises: InvalidTokenError (domain exception) on any failure

    generate_refresh_token() -> str:
        Returns cryptographically random URL-safe string (32 bytes, base64-encoded)
        Uses secrets.token_urlsafe(32)

    hash_refresh_token(token: str) -> str:
        Returns SHA-256 hex digest of token
        Uses hashlib.sha256
```

**Rules:**
- Access tokens are short-lived (configured TTL, default 15 min)
- Refresh tokens are opaque random strings (not JWTs)
- Refresh token hash uses SHA-256 (fast, no salt needed — token is already high-entropy)
- `verify_access_token` maps all PyJWT exceptions to domain `InvalidTokenError`
- Token `jti` provides uniqueness for each issued token

### 4.4 Error Mapping

| PyJWT Exception | Domain Exception |
|----------------|------------------|
| `ExpiredSignatureError` | `TokenExpiredError` (or domain equivalent) |
| `InvalidTokenError` | `InvalidTokenError` |
| `DecodeError` | `InvalidTokenError` |
| `InvalidIssuerError` | `InvalidTokenError` |

## 5. OIDC Provider Adapter

### 5.1 Purpose

Implements the `OidcProvider` protocol (spec 005) for communicating with Google and Microsoft OAuth 2.0 / OIDC endpoints.

### 5.2 Protocol Implemented

```
OidcProvider (Protocol):
    async def get_authorization_url(
        self, provider_type: AuthProviderType, state: str, nonce: str
    ) -> str

    async def exchange_code(
        self, provider_type: AuthProviderType, code: str, code_verifier: str | None = None
    ) -> OidcClaims
```

### 5.3 Implementation Details

```
OidcProviderAdapter:
    __init__(settings: OidcSettings, http_client: httpx.AsyncClient):
        Stores provider configurations
        Uses shared httpx client for connection pooling

    get_authorization_url(
        provider_type: AuthProviderType, state: str, nonce: str
    ) -> str:
        Builds OAuth authorization URL with:
            - client_id
            - redirect_uri
            - response_type=code
            - scope=openid email profile
            - state (CSRF protection)
            - nonce (replay protection)
            - code_challenge + code_challenge_method=S256 (PKCE)
        Returns full authorization URL

    exchange_code(
        provider_type: AuthProviderType, code: str, code_verifier: str | None = None
    ) -> OidcClaims:
        1. POST to token endpoint:
            - grant_type=authorization_code
            - code
            - redirect_uri
            - client_id + client_secret
            - code_verifier (PKCE)
        2. Parse token response → id_token
        3. Decode and validate id_token (verify signature against provider's JWKS)
        4. Extract claims → OidcClaims value object
        Raises: OidcAuthenticationError on any failure
```

### 5.4 Provider Configurations

**Google:**

| Setting | Value |
|---------|-------|
| Authorization endpoint | `https://accounts.google.com/o/oauth2/v2/auth` |
| Token endpoint | `https://oauth2.googleapis.com/token` |
| JWKS URI | `https://www.googleapis.com/oauth2/v3/certs` |
| Scopes | `openid email profile` |

**Microsoft:**

| Setting | Value |
|---------|-------|
| Authorization endpoint | `https://login.microsoftonline.com/common/oauth2/v2.0/authorize` |
| Token endpoint | `https://login.microsoftonline.com/common/oauth2/v2.0/token` |
| JWKS URI | `https://login.microsoftonline.com/common/discovery/v2.0/keys` |
| Scopes | `openid email profile` |

### 5.5 JWKS Caching

- Provider JWKS (JSON Web Key Sets) are fetched and cached in memory
- Cache TTL: 1 hour (keys rotate infrequently)
- Cache is refreshed on key-not-found (handles key rotation gracefully)

### 5.6 Error Handling

| Scenario | Behavior |
|----------|----------|
| Provider unreachable | Raises `OidcAuthenticationError` with descriptive message |
| Invalid authorization code | Raises `OidcAuthenticationError` |
| ID token signature invalid | Raises `OidcAuthenticationError` |
| ID token expired | Raises `OidcAuthenticationError` |
| Missing required claims (email) | Raises `OidcAuthenticationError` |
| Unsupported provider type | Raises `OidcProviderNotConfiguredError` |

## 6. File Structure

```
src/emerald/infrastructure/
    auth/
        __init__.py
        argon2_hasher.py       # Argon2PasswordHasher
        jwt_token_service.py   # JwtTokenService
        oidc_provider.py       # OidcProviderAdapter
```

## 7. Acceptance Criteria

### Argon2 Password Hasher

- [ ] `hash()` produces valid Argon2id hash string
- [ ] `verify()` returns `True` for correct password
- [ ] `verify()` returns `False` for incorrect password
- [ ] Different `hash()` calls produce different hashes (random salt)
- [ ] Hash format is recognizable as Argon2id (`$argon2id$...`)

### JWT Token Service

- [ ] `create_access_token()` returns valid JWT string
- [ ] JWT contains all required claims (sub, email, system_role, exp, iat, iss, jti)
- [ ] `verify_access_token()` reconstructs `AccessTokenClaims` from valid token
- [ ] `verify_access_token()` raises on expired token
- [ ] `verify_access_token()` raises on invalid signature
- [ ] `verify_access_token()` raises on wrong issuer
- [ ] `generate_refresh_token()` returns URL-safe string
- [ ] `generate_refresh_token()` returns unique values on each call
- [ ] `hash_refresh_token()` returns deterministic SHA-256 hash
- [ ] `hash_refresh_token()` returns same hash for same input

### OIDC Provider Adapter

- [ ] `get_authorization_url()` returns valid URL with all required parameters
- [ ] Authorization URL includes PKCE code_challenge
- [ ] `exchange_code()` sends correct POST to token endpoint
- [ ] `exchange_code()` validates id_token signature against provider JWKS
- [ ] `exchange_code()` returns `OidcClaims` with email, external_id, display_name
- [ ] Raises `OidcAuthenticationError` on HTTP failure
- [ ] Raises `OidcAuthenticationError` on invalid id_token
- [ ] Raises error for unconfigured provider (missing client_id)
- [ ] JWKS keys are cached in memory (not re-fetched per request)
- [ ] JWKS cache refreshes on key-not-found
