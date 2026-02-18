# Spec 027: API Middleware & Common HTTP Infrastructure

**Status:** Draft
**Bounded Context:** Infrastructure (Cross-Cutting)
**Dependencies:** 026 (Cross-Context Adapters & Composition Root)
**Blocks:** 028, 029, 030

---

## 1. Overview

This spec defines the HTTP middleware stack, domain-to-HTTP error mapping, JWT auth dependency, and shared API patterns that all endpoint specs (028-030) build upon.

**Key Principle:** Domain exceptions map cleanly to HTTP status codes. Authentication is handled via a reusable FastAPI dependency. All API responses follow consistent structure.

## 2. Scope

### In Scope

- JWT auth dependency (extracts Bearer token → `AuthenticatedIdentity`)
- Domain exception → HTTP response mapping
- CORS middleware configuration
- Request ID middleware (generates/propagates `X-Request-ID`)
- Shared Pydantic schemas (`PaginatedResponse`, `ErrorResponse`, UUID path params)
- Health endpoints (`GET /health`, `GET /ready`)

### Out of Scope

- Specific business endpoint routes (specs 028-030)
- Rate limiting (future enhancement)
- Request logging / structured logging (future enhancement)

## 3. JWT Auth Dependency

### 3.1 Purpose

FastAPI dependency that extracts and validates the JWT access token from the `Authorization` header, returning an `AuthenticatedIdentity` for use by endpoint handlers.

### 3.2 Implementation

```
async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    container: Container = Depends(get_container),
) -> AuthenticatedIdentity:
    """Extracts Bearer token, verifies, returns identity."""

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[len("Bearer "):]
    claims = container.token_service.verify_access_token(token)

    return AuthenticatedIdentity(
        user_id=claims.user_id,
        email=claims.email,
        username=claims.username,
        display_name=claims.username or claims.email,
        system_role=claims.system_role,
        admin_permissions=claims.admin_permissions,
    )
```

### 3.3 Optional Auth

For endpoints that work with or without authentication:

```
async def get_optional_user(
    authorization: str | None = Header(None, alias="Authorization"),
    container: Container = Depends(get_container),
) -> AuthenticatedIdentity | None:
    """Returns identity if token present and valid, None otherwise."""
```

### 3.4 Admin Guard

For admin-only endpoints:

```
async def require_admin(
    identity: AuthenticatedIdentity = Depends(get_current_user),
) -> AuthenticatedIdentity:
    """Verifies user has ADMIN or SUPERADMIN role."""
    if not identity.system_role.is_admin_or_above():
        raise HTTPException(status_code=403, detail="Admin access required")
    return identity
```

### 3.5 Error Responses

| Scenario | Status | Response |
|----------|--------|----------|
| Missing Authorization header | 401 | `{"error": {"code": "MISSING_TOKEN", "message": "..."}}` |
| Invalid Bearer format | 401 | `{"error": {"code": "INVALID_TOKEN", "message": "..."}}` |
| Expired token | 401 | `{"error": {"code": "TOKEN_EXPIRED", "message": "..."}}` |
| Invalid signature | 401 | `{"error": {"code": "INVALID_TOKEN", "message": "..."}}` |

## 4. Domain Exception → HTTP Mapping

### 4.1 Exception Handler Registry

Registers FastAPI exception handlers that convert domain exceptions to structured HTTP responses:

```
Exception Mapping:
    InvalidValueError       → 400 Bad Request
    AuthenticationFailedError → 401 Unauthorized
    AuthorizationError      → 403 Forbidden
    NotFoundError           → 404 Not Found
    InvariantViolationError → 409 Conflict
    DomainError (catch-all) → 400 Bad Request
```

### 4.2 Error Response Format

All error responses follow a consistent structure:

```json
{
    "error": {
        "code": "ACCOUNT_NAME_ALREADY_EXISTS",
        "message": "An account with this name already exists for this user."
    }
}
```

**Schema:**

```
class ErrorDetail(BaseModel):
    code: str           # Machine-readable error code (from domain exception)
    message: str        # Human-readable description

class ErrorResponse(BaseModel):
    error: ErrorDetail
```

### 4.3 Exception Handler Implementation

```
async def domain_exception_handler(request: Request, exc: DomainError) -> JSONResponse:
    status_code = _map_exception_to_status(exc)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code,
                "message": str(exc),
            }
        },
    )

def _map_exception_to_status(exc: DomainError) -> int:
    if isinstance(exc, InvalidValueError):
        return 400
    if isinstance(exc, AuthenticationFailedError):
        return 401
    if isinstance(exc, AuthorizationError):
        return 403
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, InvariantViolationError):
        return 409
    return 400  # DomainError catch-all
```

### 4.4 Validation Error Handler

FastAPI/Pydantic validation errors are also mapped to the same format:

```
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
            }
        },
    )
```

## 5. CORS Middleware

### 5.1 Configuration

Uses `CorsSettings` from spec 021:

```
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allowed_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allowed_methods,
    allow_headers=settings.cors.allowed_headers,
)
```

### 5.2 Default Development Config

- Origins: `http://localhost:3000`, `http://localhost:5173`
- Credentials: allowed
- Methods: all
- Headers: all

## 6. Request ID Middleware

### 6.1 Purpose

Generates or propagates a unique request ID for tracing:

```
class RequestIdMiddleware:
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### 6.2 Behavior

| Scenario | Behavior |
|----------|----------|
| Client sends `X-Request-ID` | Use client's value (propagate) |
| No `X-Request-ID` header | Generate new UUID |
| Response | Always includes `X-Request-ID` header |

## 7. Shared Pydantic Schemas

### 7.1 Pagination

```
class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
```

### 7.2 Common Types

```
class UUIDPath(BaseModel):
    """For UUID path parameters."""
    id: UUID

class TimestampResponse(BaseModel):
    """Standard timestamp fields included in responses."""
    created_at: datetime
    updated_at: datetime

class SoftDeleteResponse(BaseModel):
    """Soft-delete fields for entities that support it."""
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None
```

## 8. Health Endpoints

### 8.1 Liveness Check

```
GET /health

Response 200:
{
    "status": "ok",
    "service": "emerald-finance",
    "version": "1.0.0"
}
```

Always returns 200 if the process is running.

### 8.2 Readiness Check

```
GET /ready

Response 200:
{
    "status": "ready",
    "checks": {
        "database": "ok"
    }
}

Response 503:
{
    "status": "not_ready",
    "checks": {
        "database": "error: connection refused"
    }
}
```

Checks database connectivity. Returns 503 if any check fails.

## 9. File Structure

```
src/emerald/infrastructure/api/
    __init__.py
    dependencies/
        __init__.py
        auth.py             # get_current_user, get_optional_user, require_admin
        container.py        # get_container dependency
    middleware/
        __init__.py
        cors.py             # CORS setup
        request_id.py       # RequestIdMiddleware
    error_handlers.py       # Domain exception → HTTP mapping
    schemas/
        __init__.py
        common.py           # PaginatedResponse, ErrorResponse, etc.
    health.py               # Health endpoints router
```

## 10. Acceptance Criteria

### JWT Auth Dependency

- [ ] `get_current_user()` extracts Bearer token from Authorization header
- [ ] Returns `AuthenticatedIdentity` with all claims populated
- [ ] Returns 401 when Authorization header is missing
- [ ] Returns 401 when token format is invalid (not "Bearer <token>")
- [ ] Returns 401 when token is expired
- [ ] Returns 401 when token signature is invalid
- [ ] `get_optional_user()` returns None when no Authorization header
- [ ] `require_admin()` returns 403 for non-admin users

### Error Handling

- [ ] `InvalidValueError` → 400 with error code and message
- [ ] `AuthenticationFailedError` → 401
- [ ] `AuthorizationError` → 403
- [ ] `NotFoundError` → 404
- [ ] `InvariantViolationError` → 409
- [ ] `DomainError` (generic) → 400
- [ ] All error responses follow `{"error": {"code": "...", "message": "..."}}` format
- [ ] Pydantic validation errors → 422 with details
- [ ] Unhandled exceptions → 500 with generic message (no stack trace in production)

### CORS

- [ ] CORS middleware configured from settings
- [ ] Development defaults allow localhost origins
- [ ] Credentials (cookies) allowed
- [ ] Preflight OPTIONS requests handled

### Request ID

- [ ] Request ID generated if not provided
- [ ] Client-provided X-Request-ID propagated
- [ ] Response includes X-Request-ID header
- [ ] Request ID available via `request.state.request_id`

### Health Endpoints

- [ ] `GET /health` returns 200 always (liveness)
- [ ] `GET /ready` returns 200 when database is connectable
- [ ] `GET /ready` returns 503 when database is unreachable
- [ ] Health endpoints do not require authentication

### Shared Schemas

- [ ] `PaginatedResponse` includes items, total, page, page_size, total_pages
- [ ] `PaginationParams` validates page ≥ 1 and page_size between 1-100
- [ ] `ErrorResponse` matches documented format
