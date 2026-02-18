# Spec 021: Configuration & Database Foundation

**Status:** Draft
**Bounded Context:** Infrastructure (Cross-Cutting)
**Dependencies:** None (first infrastructure spec)
**Blocks:** 022, 023, 024, 025, 026

---

## 1. Overview

This spec establishes the infrastructure skeleton — application settings, database engine, session management, migration scaffold, and base SQLAlchemy Unit of Work. It provides the foundation upon which all persistence and API layers are built.

**Key Principle:** Infrastructure concerns are isolated from domain logic. Settings are loaded from environment variables with sensible defaults. The database layer uses SQLAlchemy 2.0 async with asyncpg. Migrations are managed by Alembic.

## 2. Scope

### In Scope

- `AppSettings` (pydantic-settings, composes sub-settings, loads `.env`)
- `DatabaseSettings` (PostgreSQL URL, pool size, echo)
- `JwtSettings` (secret key, algorithm, access/refresh TTLs)
- `OidcSettings` (Google/Microsoft client IDs/secrets, discovery endpoints)
- `CorsSettings` (allowed origins, methods, headers)
- SQLAlchemy 2.0 async engine factory + `async_sessionmaker`
- Alembic init with async `env.py`
- Declarative ORM base class with common column patterns (UUID PK, timestamps, soft-delete)
- `SqlAlchemyUnitOfWork` base class implementing session lifecycle (commit/rollback)
- `.env.example` with all variables documented

### Out of Scope

- Concrete repository implementations (specs 022-025)
- Auth adapter implementations (spec 023)
- FastAPI application factory (spec 026)
- Docker / containerization (spec 031)

## 3. Application Settings

### 3.1 AppSettings (Root)

Composes all sub-settings under a single entry point using `pydantic-settings`:

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| app_name | str | "Emerald Finance" | `APP_NAME` | Application display name |
| environment | str | "development" | `ENVIRONMENT` | dev / staging / production |
| debug | bool | False | `DEBUG` | Debug mode |
| database | DatabaseSettings | — | `DATABASE_*` | DB config |
| jwt | JwtSettings | — | `JWT_*` | Token config |
| oidc | OidcSettings | — | `OIDC_*` | Social login config |
| cors | CorsSettings | — | `CORS_*` | CORS config |

### 3.2 DatabaseSettings

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| url | str | — | `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| pool_size | int | 10 | `DATABASE_POOL_SIZE` | Connection pool size |
| max_overflow | int | 20 | `DATABASE_MAX_OVERFLOW` | Pool overflow limit |
| echo | bool | False | `DATABASE_ECHO` | Log SQL statements |
| echo_pool | bool | False | `DATABASE_ECHO_POOL` | Log pool events |

**Rules:**
- `url` is required, no default
- Pool size must be ≥ 1
- Max overflow must be ≥ 0

### 3.3 JwtSettings

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| secret_key | str | — | `JWT_SECRET_KEY` | HMAC signing key |
| algorithm | str | "HS256" | `JWT_ALGORITHM` | JWT algorithm |
| access_token_ttl_minutes | int | 15 | `JWT_ACCESS_TOKEN_TTL_MINUTES` | Access token lifetime |
| refresh_token_ttl_days | int | 30 | `JWT_REFRESH_TOKEN_TTL_DAYS` | Refresh token lifetime |
| issuer | str | "emerald-finance" | `JWT_ISSUER` | Token issuer claim |

**Rules:**
- `secret_key` is required, no default
- Algorithm must be one of: HS256, HS384, HS512, RS256

### 3.4 OidcSettings

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| google_client_id | str? | None | `OIDC_GOOGLE_CLIENT_ID` | Google OAuth client ID |
| google_client_secret | str? | None | `OIDC_GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| google_redirect_uri | str? | None | `OIDC_GOOGLE_REDIRECT_URI` | Google callback URL |
| microsoft_client_id | str? | None | `OIDC_MICROSOFT_CLIENT_ID` | Microsoft OAuth client ID |
| microsoft_client_secret | str? | None | `OIDC_MICROSOFT_CLIENT_SECRET` | Microsoft OAuth client secret |
| microsoft_redirect_uri | str? | None | `OIDC_MICROSOFT_REDIRECT_URI` | Microsoft callback URL |

**Rules:**
- All OIDC fields are optional (social login is opt-in)
- If client_id is set, client_secret and redirect_uri must also be set for that provider

### 3.5 CorsSettings

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| allowed_origins | list[str] | ["http://localhost:3000"] | `CORS_ALLOWED_ORIGINS` | Allowed origins (comma-separated) |
| allow_credentials | bool | True | `CORS_ALLOW_CREDENTIALS` | Allow cookies |
| allowed_methods | list[str] | ["*"] | `CORS_ALLOWED_METHODS` | Allowed HTTP methods |
| allowed_headers | list[str] | ["*"] | `CORS_ALLOWED_HEADERS` | Allowed HTTP headers |

## 4. Database Engine & Session

### 4.1 Engine Factory

```
create_async_engine_from_settings(settings: DatabaseSettings) -> AsyncEngine:
    Creates SQLAlchemy async engine with:
      - asyncpg driver
      - Connection pool from settings
      - Echo from settings
```

### 4.2 Session Factory

```
create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    Creates session maker with:
      - expire_on_commit=False (important for async)
      - autoflush=False
```

**Rules:**
- Sessions are request-scoped (one per API request)
- Sessions must be explicitly committed or rolled back
- Expired sessions must not be reused

## 5. Alembic Migration Scaffold

### 5.1 Configuration

- `alembic.ini` at project root, pointing to migrations directory
- Async `env.py` using `run_async_migrations()` pattern
- `sqlalchemy.url` sourced from `DATABASE_URL` environment variable
- `target_metadata` from the declarative base

### 5.2 Directory Structure

```
alembic/
    env.py              # Async migration runner
    script.py.mako      # Migration template
    versions/           # Migration files (auto-generated)
alembic.ini             # Alembic configuration
```

### 5.3 Table Naming Convention

All tables use bounded context prefixes:

| Prefix | Context | Example |
|--------|---------|---------|
| `iam_` | IAM | `iam_users`, `iam_refresh_tokens` |
| `cf_` | Core Finance | `cf_accounts`, `cf_transactions` |
| `cls_` | Classification | `cls_taxonomies`, `cls_taxonomy_terms` |
| `int_` | Integrations | `int_bank_connections`, `int_sync_history` |
| `sk_` | Shared Kernel | `sk_user_retention_preferences` |

## 6. ORM Base Model

### 6.1 Declarative Base

A single declarative base class for all ORM models:

```
Base = declarative_base()
```

### 6.2 Common Mixins

**TimestampMixin:**

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| created_at | datetime (UTC) | `now()` | Creation timestamp |
| updated_at | datetime (UTC) | `now()`, `onupdate=now()` | Last update timestamp |

**SoftDeleteMixin:**

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| deleted_at | datetime? (UTC) | None | Soft delete timestamp |
| deleted_by | UUID? | None | Who deleted |

**AuditMixin (extends TimestampMixin):**

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| created_at | datetime (UTC) | `now()` | Creation timestamp |
| created_by | UUID | — | Who created |
| updated_at | datetime (UTC) | `now()`, `onupdate=now()` | Last update timestamp |
| updated_by | UUID? | None | Who last updated |

### 6.3 UUID Primary Key Convention

All entity tables use UUID primary keys:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | UUID | `uuid4()` | Primary key |

## 7. Base Unit of Work

### 7.1 SqlAlchemyUnitOfWork

Base class that all context-specific UoWs extend:

```
SqlAlchemyUnitOfWork:
    __init__(session_factory: async_sessionmaker[AsyncSession])

    // Context manager protocol
    async __aenter__() -> Self
        Creates session

    async __aexit__(exc_type, exc_val, exc_tb) -> None
        Rolls back on exception, closes session

    // Explicit lifecycle
    async commit() -> None
        Commits transaction

    async rollback() -> None
        Rolls back transaction
```

**Rules:**
- Always creates a new session on `__aenter__`
- Rolls back uncommitted changes on `__aexit__` if exception occurred
- Closes session on `__aexit__` regardless of success/failure
- Repositories created per UoW instance share the same session

## 8. Environment File

### 8.1 .env.example

Documents all environment variables with sensible development defaults:

```
# Application
APP_NAME=Emerald Finance
ENVIRONMENT=development
DEBUG=true

# Database
DATABASE_URL=postgresql+asyncpg://emerald:emerald@localhost:5432/emerald_dev
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_ECHO=false

# JWT
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_TTL_MINUTES=15
JWT_REFRESH_TOKEN_TTL_DAYS=30
JWT_ISSUER=emerald-finance

# OIDC (optional - social login)
# OIDC_GOOGLE_CLIENT_ID=
# OIDC_GOOGLE_CLIENT_SECRET=
# OIDC_GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback
# OIDC_MICROSOFT_CLIENT_ID=
# OIDC_MICROSOFT_CLIENT_SECRET=
# OIDC_MICROSOFT_REDIRECT_URI=http://localhost:3000/auth/microsoft/callback

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
CORS_ALLOW_CREDENTIALS=true
```

## 9. New Dependencies

| Package | Purpose |
|---------|---------|
| `sqlalchemy[asyncio]` | ORM + async support |
| `asyncpg` | PostgreSQL async driver |
| `alembic` | Database migrations |
| `pydantic-settings` | Settings management |
| `argon2-cffi` | Password hashing (used in spec 023) |
| `pyjwt[crypto]` | JWT tokens (used in spec 023) |
| `httpx` | HTTP client for OIDC (used in spec 023) |
| `fastapi` | Web framework (used in spec 026+) |
| `uvicorn[standard]` | ASGI server (used in spec 031) |

## 10. File Structure

```
src/emerald/infrastructure/
    __init__.py
    config/
        __init__.py
        settings.py           # AppSettings and all sub-settings
    persistence/
        __init__.py
        database.py           # Engine factory, session factory
        base_model.py         # Declarative base, column mixins
        base_unit_of_work.py  # SqlAlchemyUnitOfWork base
alembic/
    env.py                    # Async migration runner
    script.py.mako            # Migration template
    versions/                 # (empty initially)
alembic.ini                   # Alembic config
.env.example                  # Environment variable documentation
```

## 11. Acceptance Criteria

### Settings

- [ ] `AppSettings` loads from environment variables and `.env` file
- [ ] `DatabaseSettings.url` is required — raises validation error if missing
- [ ] `JwtSettings.secret_key` is required — raises validation error if missing
- [ ] OIDC settings are optional — app starts without social login config
- [ ] CORS origins parsed from comma-separated string
- [ ] All settings have sensible development defaults where appropriate
- [ ] Settings are immutable after creation (frozen)

### Database Engine

- [ ] Engine factory creates async engine with asyncpg driver
- [ ] Connection pool size and overflow configurable
- [ ] SQL echo mode toggleable via settings
- [ ] Engine can be properly disposed (shutdown cleanup)

### Session Management

- [ ] Session factory creates async sessions with `expire_on_commit=False`
- [ ] Sessions are independent (one per UoW instance)
- [ ] Sessions are properly closed after use

### Alembic

- [ ] `alembic init` scaffold present with async `env.py`
- [ ] Migrations directory exists (empty — migrations created by specs 022-025)
- [ ] Alembic reads database URL from environment
- [ ] `target_metadata` references the declarative base
- [ ] `alembic upgrade head` and `alembic downgrade` work

### Base Unit of Work

- [ ] `SqlAlchemyUnitOfWork` implements async context manager protocol
- [ ] Commit persists changes to database
- [ ] Rollback discards uncommitted changes
- [ ] Exception in context manager triggers automatic rollback
- [ ] Session is closed after `__aexit__` regardless of success/failure
- [ ] Multiple repositories within one UoW share the same session

### ORM Base

- [ ] UUID primary key convention applied
- [ ] TimestampMixin auto-sets `created_at` and `updated_at`
- [ ] SoftDeleteMixin provides `deleted_at` and `deleted_by` columns
- [ ] AuditMixin extends TimestampMixin with `created_by` and `updated_by`
- [ ] All timestamps are timezone-aware UTC

### Environment File

- [ ] `.env.example` documents all environment variables
- [ ] Development defaults allow local startup without modification (except secrets)
