# Spec 021: Configuration & Database Foundation

**Version:** 1.0
**Status:** Draft
**Bounded Context:** Shared Kernel (Infrastructure)
**Dependencies:** None (first infrastructure spec)
**Blocks:** 022, 023, 024, 025, 026

---

## 1. Overview

This spec establishes the infrastructure skeleton — application settings, database engine, session management, migration scaffold, classical ORM mapping foundation, and base SQLAlchemy Unit of Work. It provides the shared foundation upon which all context-specific persistence and API layers are built.

**Key Principles:**
- Infrastructure concerns are isolated from domain logic
- Settings are loaded from environment variables with sensible defaults
- The database layer uses SQLAlchemy 2.0 async with asyncpg
- Migrations are managed by Alembic
- Domain objects remain pure Python — ORM uses **classical/imperative mapping** (no declarative base inheritance)
- Existing domain abstract UoWs are migrated from sync to async

---

## 2. Background & Context

### Problem Statement

The project has 15 implemented domain specs (001–015) with complete domain and application layers, but zero infrastructure. All tests use in-memory fakes. To deploy the application, we need: configuration management, database connectivity, ORM mapping strategy, migration tooling, and a base Unit of Work that integrates with SQLAlchemy.

### Business Goals

- Enable persistence of all domain aggregates and entities to PostgreSQL
- Establish patterns that specs 022–025 (context-specific persistence) will follow
- Keep domain code pure — no SQLAlchemy imports in domain or application layers
- Provide a clean async foundation for the FastAPI-based API layer (specs 026+)

### Success Metrics

- All existing 2605+ unit tests continue to pass (domain purity preserved)
- New infrastructure unit tests cover settings validation, session lifecycle, and base UoW behavior
- `ruff check`, `ruff format`, and `ty check` all pass clean
- Alembic scaffold operational (`alembic upgrade head` on empty DB succeeds)

---

## 3. Scope

### In Scope

- `AppSettings` (pydantic-settings, composes sub-settings, loads `.env`)
- `DatabaseSettings`, `JwtSettings`, `OidcSettings`, `CorsSettings`
- SQLAlchemy 2.0 async engine factory + `async_sessionmaker`
- Alembic init with async `env.py`
- Shared `MetaData` + `registry` for classical/imperative ORM mapping
- Reusable column helpers for common patterns (UUID PK, timestamps, soft-delete, audit, version)
- `SqlAlchemyUnitOfWork` async base class
- **Migration of existing abstract UoWs from sync to async** (shared kernel + all 4 contexts)
- **Migration of existing test fakes from sync to async** (all context fake UoWs)
- `.env.example` with all variables documented
- New dependencies added to `pyproject.toml`

### Out of Scope

- Concrete repository implementations (specs 022–025)
- Concrete ORM table definitions and mappers for specific entities (specs 022–025)
- Auth adapter implementations (spec 023)
- FastAPI application factory (spec 026)
- Docker / containerization (spec 031)

---

## 4. Application Settings

### 4.1 AppSettings (Root)

Composes all sub-settings under a single entry point using `pydantic-settings`. Lives in `src/emerald/shared_kernel/infrastructure/config/settings.py`.

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| app_name | str | "Emerald Finance" | `APP_NAME` | Application display name |
| environment | str | "development" | `ENVIRONMENT` | dev / staging / production |
| debug | bool | False | `DEBUG` | Debug mode |
| database | DatabaseSettings | — | `DATABASE_*` | DB config |
| jwt | JwtSettings | — | `JWT_*` | Token config |
| oidc | OidcSettings | — | `OIDC_*` | Social login config |
| cors | CorsSettings | — | `CORS_*` | CORS config |

**Rules:**
- Uses `pydantic_settings.BaseSettings` with `model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__")`
- Settings are frozen after creation (`model_config` frozen=True)
- Sub-settings use `env_prefix` to namespace their variables

### 4.2 DatabaseSettings

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| url | str | — (required) | `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| pool_size | int | 10 | `DATABASE_POOL_SIZE` | Connection pool size |
| max_overflow | int | 20 | `DATABASE_MAX_OVERFLOW` | Pool overflow limit |
| echo | bool | False | `DATABASE_ECHO` | Log SQL statements |
| echo_pool | bool | False | `DATABASE_ECHO_POOL` | Log pool events |

**Validation Rules:**
- `url` is required — raises `ValidationError` if missing
- `pool_size` must be ≥ 1
- `max_overflow` must be ≥ 0

### 4.3 JwtSettings

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| secret_key | str | — (required) | `JWT_SECRET_KEY` | HMAC signing key |
| algorithm | str | "HS256" | `JWT_ALGORITHM` | JWT algorithm |
| access_token_ttl_minutes | int | 15 | `JWT_ACCESS_TOKEN_TTL_MINUTES` | Access token lifetime |
| refresh_token_ttl_days | int | 30 | `JWT_REFRESH_TOKEN_TTL_DAYS` | Refresh token lifetime |
| issuer | str | "emerald-finance" | `JWT_ISSUER` | Token issuer claim |

**Validation Rules:**
- `secret_key` is required — raises `ValidationError` if missing
- `algorithm` must be one of: `HS256`, `HS384`, `HS512`, `RS256`

### 4.4 OidcSettings

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| google_client_id | str \| None | None | `OIDC_GOOGLE_CLIENT_ID` | Google OAuth client ID |
| google_client_secret | str \| None | None | `OIDC_GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| google_redirect_uri | str \| None | None | `OIDC_GOOGLE_REDIRECT_URI` | Google callback URL |
| microsoft_client_id | str \| None | None | `OIDC_MICROSOFT_CLIENT_ID` | Microsoft OAuth client ID |
| microsoft_client_secret | str \| None | None | `OIDC_MICROSOFT_CLIENT_SECRET` | Microsoft OAuth client secret |
| microsoft_redirect_uri | str \| None | None | `OIDC_MICROSOFT_REDIRECT_URI` | Microsoft callback URL |

**Validation Rules:**
- All OIDC fields are optional (social login is opt-in)
- If `client_id` is set for a provider, `client_secret` and `redirect_uri` must also be set (model validator)

### 4.5 CorsSettings

| Attribute | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| allowed_origins | list[str] | ["http://localhost:3000"] | `CORS_ALLOWED_ORIGINS` | Allowed origins (comma-separated in env) |
| allow_credentials | bool | True | `CORS_ALLOW_CREDENTIALS` | Allow cookies |
| allowed_methods | list[str] | ["*"] | `CORS_ALLOWED_METHODS` | Allowed HTTP methods |
| allowed_headers | list[str] | ["*"] | `CORS_ALLOWED_HEADERS` | Allowed HTTP headers |

---

## 5. Database Engine & Session

### 5.1 Engine Factory

```
create_async_engine_from_settings(settings: DatabaseSettings) -> AsyncEngine
```

Creates a SQLAlchemy async engine with:
- asyncpg driver (derived from `url`)
- Connection pool configured from `pool_size` and `max_overflow`
- SQL echo from `echo` setting
- Pool echo from `echo_pool` setting

### 5.2 Session Factory

```
create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]
```

Creates async session maker with:
- `expire_on_commit=False` (required for async — prevents lazy loads after commit)
- `autoflush=False` (explicit flush control)

### 5.3 Engine Disposal

```
async dispose_engine(engine: AsyncEngine) -> None
```

Cleanly disposes the engine and its connection pool. Called during application shutdown.

**Session Rules:**
- Sessions are request-scoped (one per API request / UoW instance)
- Sessions must be explicitly committed or rolled back
- Sessions are closed after use (via UoW `__aexit__`)

---

## 6. Alembic Migration Scaffold

### 6.1 Configuration

- `alembic.ini` at project root, pointing to migrations directory
- Async `env.py` using `run_async_migrations()` pattern with `connectable.run_sync()`
- `sqlalchemy.url` sourced from `DATABASE_URL` environment variable
- `target_metadata` references the shared `MetaData` instance
- `env.py` imports and calls `configure_all_mappers()` before autogenerate (so Alembic sees all mapped tables)

### 6.2 Directory Structure

```
alembic/
    env.py              # Async migration runner
    script.py.mako      # Migration template
    versions/           # Migration files (empty — populated by specs 022-025)
alembic.ini             # Alembic configuration
```

### 6.3 Table Naming Convention

All tables use bounded context prefixes:

| Prefix | Context | Example Tables |
|--------|---------|----------------|
| `iam_` | IAM | `iam_users`, `iam_refresh_tokens`, `iam_password_reset_tokens` |
| `cf_` | Core Finance | `cf_accounts`, `cf_account_shares`, `cf_transactions`, `cf_cards` |
| `cls_` | Classification | `cls_taxonomies`, `cls_taxonomy_terms`, `cls_transaction_term_assignments` |
| `int_` | Integrations | `int_bank_connections`, `int_sync_history`, `int_pending_transactions` |
| `sk_` | Shared Kernel | `sk_user_retention_preferences` |

### 6.4 Naming Convention for Constraints

SQLAlchemy metadata uses a naming convention dict for consistent constraint names:

```python
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

---

## 7. Classical ORM Mapping Foundation

### 7.1 Design Approach

Following the architecture-patterns guidance for Ports & Adapters:

> *"Domain objects remain plain Python classes with no awareness of how they're stored. Persistence Ignorance is achieved through classical ORM mapping."*

**No declarative base class.** Instead:
- A shared `MetaData` instance holds all table definitions
- A shared `registry` provides `map_imperatively()` for binding domain classes to tables
- Table definitions live in each context's adapters module (specs 022–025)
- Each context exposes a `configure_mappers()` function in its adapters module
- The **composition root** (spec 026) calls all context mapper functions once during app bootstrap

### 7.2 Shared MetaData & Registry

```python
# src/emerald/shared_kernel/adapters/outbound/persistence/orm_registry.py

from sqlalchemy import MetaData
from sqlalchemy.orm import registry

metadata = MetaData(naming_convention={...})
mapper_registry = registry(metadata=metadata)
```

This is imported by:
- Alembic `env.py` (for `target_metadata`)
- Each context's ORM mapping module (for table definitions and `map_imperatively()`)

**No `start_mappers()` lives here.** The composition root (spec 026) is responsible for calling each context's `configure_mappers()` at app startup. SQLAlchemy's `registry` inherently prevents double-mapping — attempting to map an already-mapped class raises an error, so no idempotency flag is needed.

### 7.3 Column Helper Functions

Reusable functions that return lists of `Column` objects for common patterns. These are used when defining `Table` objects in context-specific specs (022–025).

**`uuid_pk()`** — UUID primary key:

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | Primary key, not null |

**`timestamp_columns()`** — Created/updated timestamps:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| created_at | DateTime(timezone=True) | server_default=`now()` | Creation timestamp (UTC) |
| updated_at | DateTime(timezone=True) | server_default=`now()`, onupdate=`now()` | Last update (UTC) |

**`audit_columns()`** — Extends timestamps with actor tracking:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| created_at | DateTime(timezone=True) | server_default=`now()` | Creation timestamp |
| updated_at | DateTime(timezone=True) | server_default=`now()`, onupdate=`now()` | Last update |
| created_by | UUID | not null | Creator user ID |
| updated_by | UUID | nullable | Last updater user ID |

**`soft_delete_columns()`** — All 4 soft-delete fields matching `SoftDeletableMixin`:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| deleted_at | DateTime(timezone=True) | nullable | Soft delete timestamp |
| deleted_by | UUID | nullable | Who deleted |
| deletion_reason | String | nullable | Reason for deletion |
| hard_delete_scheduled_at | DateTime(timezone=True) | nullable | Scheduled hard delete |

**`version_column()`** — Optimistic concurrency:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| version | Integer | 0 | Optimistic locking token |

### 7.4 Mapper Configuration Pattern

When context-specific specs (022–025) define their mappers, they use `version_id_col` for aggregates that extend `AggregateRoot`:

```python
# Example pattern (actual implementation in spec-022+)
mapper_registry.map_imperatively(
    User,
    iam_users_table,
    version_id_col=iam_users_table.c.version,
    properties={
        "_id": iam_users_table.c.id,
        "_created_at": iam_users_table.c.created_at,
        "_created_by": iam_users_table.c.created_by,
        "_version": iam_users_table.c.version,
        # ... public attrs map directly
    },
)
```

**Key mapping rules for private attributes:**
- `_id` → `id` column (Entity base)
- `_created_at` → `created_at` column (TimestampedMixin)
- `_created_by` → `created_by` column (AuditableMixin)
- `_version` → `version` column (AggregateRoot)
- Public attributes (`updated_at`, `updated_by`, `deleted_at`, etc.) map directly by name

SQLAlchemy's `version_id_col` automatically:
- Adds `WHERE version = X` to UPDATE statements
- Raises `StaleDataError` on optimistic concurrency conflicts
- Increments version on each flush

### 7.5 Context Mapper Registration Pattern

Each context (specs 022–025) exposes a `configure_mappers()` function in its adapters module:

```python
# Example: src/emerald/iam/adapters/outbound/persistence/orm.py (spec 022)

def configure_iam_mappers() -> None:
    """Register IAM domain class → table mappings."""
    mapper_registry.map_imperatively(User, iam_users_table, ...)
    mapper_registry.map_imperatively(RefreshToken, iam_refresh_tokens_table, ...)
```

The **composition root** (spec 026) calls all context mapper functions once at app startup:

```python
# Example: src/emerald/shared_kernel/adapters/outbound/persistence/mapper_setup.py (spec 026)

def configure_all_mappers() -> None:
    from emerald.iam.adapters.outbound.persistence.orm import configure_iam_mappers
    from emerald.core_finance.adapters.outbound.persistence.orm import configure_core_finance_mappers
    # ...
    configure_iam_mappers()
    configure_core_finance_mappers()
    # ...
```

**No global boolean flags.** SQLAlchemy's `registry` inherently prevents double-mapping — attempting to map an already-mapped class raises an error. The composition root is the single place responsible for calling mapper configuration, called once during app bootstrap.

Alembic's `env.py` also calls `configure_all_mappers()` before autogenerate so it can see all mapped tables.

---

## 8. Abstract UoW Migration (Sync → Async)

### 8.1 Rationale

The existing abstract UoWs use synchronous `__enter__`/`__exit__` and sync `commit()`/`rollback()`. Since the infrastructure uses SQLAlchemy async (asyncpg), and FastAPI is async, all UoW contracts must become async.

### 8.2 Changes to AbstractUnitOfWork (Shared Kernel)

**Before (current):**
```python
class AbstractUnitOfWork(ABC):
    def __enter__(self) -> "AbstractUnitOfWork": ...
    def __exit__(self, *args) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

**After:**
```python
class AbstractUnitOfWork(ABC):
    async def __aenter__(self) -> "AbstractUnitOfWork": ...
    async def __aexit__(self, *args) -> None: ...
    @abstractmethod
    async def commit(self) -> None: ...
    @abstractmethod
    async def rollback(self) -> None: ...
```

### 8.3 Changes to Context-Specific Abstract UoWs

All 4 context-specific UoWs are updated identically — only the method signatures change to async:

- `AbstractIamUnitOfWork` — `async commit()`, `async rollback()`
- `AbstractCoreFinanceUnitOfWork` — `async commit()`, `async rollback()`
- `AbstractClassificationUnitOfWork` — `async commit()`, `async rollback()`
- `AbstractIntegrationsUnitOfWork` — `async commit()`, `async rollback()`

Repository attributes remain the same (repositories themselves are not async — they operate within the session provided by the UoW).

### 8.4 Changes to Test Fakes

All fake UoW implementations in `tests/unit/{context}/fakes.py` are updated:

- `__enter__` → `async def __aenter__`
- `__exit__` → `async def __aexit__`
- `def commit()` → `async def commit()`
- `def rollback()` → `async def rollback()`

### 8.5 Changes to Test Call Sites

All tests that use `with uow:` become `async with uow:`, and all `uow.commit()` become `await uow.commit()`. Test functions using UoWs become `async def` with `@pytest.mark.asyncio` (or `pytest-asyncio` auto mode).

**New dev dependency:** `pytest-asyncio` (added to `pyproject.toml`)

### 8.6 Changes to Application Services

All application service methods that call `uow.commit()` or use `with uow:` are updated to `async` with `await` and `async with`. This affects all services across all contexts:

- **IAM:** RegistrationService, AuthenticationService, RoleManagementService, SuperadminProvisioningService
- **Core Finance:** AccountManagementService, AccountSharingService, TransactionManagementService, BulkTransactionService
- **Classification:** TaxonomyManagementService, TransactionCategorizationService
- **Integrations:** BankConnectionService, BankSyncService, DeduplicationService
- **Shared Kernel:** RetentionPolicyService

---

## 9. Base SqlAlchemyUnitOfWork

### 9.1 Implementation

```python
class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    @property
    def session(self) -> AsyncSession:
        return self._session
```

**Rules:**
- Always creates a new session on `__aenter__`
- Rolls back on `__aexit__` only if an exception occurred
- Always closes session on `__aexit__` regardless of success/failure
- Context-specific UoWs (specs 022–025) extend this and add repository attributes
- Repositories created per UoW instance share the same session via `self.session`

---

## 10. New Dependencies

| Package | Purpose | Dep Type |
|---------|---------|----------|
| `sqlalchemy[asyncio]` | ORM + async support | Runtime |
| `asyncpg` | PostgreSQL async driver | Runtime |
| `alembic` | Database migrations | Runtime |
| `pydantic-settings` | Settings management | Runtime |
| `argon2-cffi` | Password hashing (used in spec 023) | Runtime |
| `pyjwt[crypto]` | JWT tokens (used in spec 023) | Runtime |
| `httpx` | HTTP client for OIDC (used in spec 023) | Runtime |
| `fastapi` | Web framework (used in spec 026+) | Runtime |
| `uvicorn[standard]` | ASGI server (used in spec 031) | Runtime |
| `pytest-asyncio` | Async test support | Dev |

---

## 11. File Structure

```
src/emerald/shared_kernel/
    infrastructure/                          # Cross-cutting concerns
        __init__.py
        config/
            __init__.py
            settings.py                      # AppSettings + all sub-settings
    adapters/                                # Infrastructure adapters
        __init__.py
        outbound/
            __init__.py
            persistence/
                __init__.py
                database.py                  # Engine factory, session factory, dispose
                orm_registry.py              # MetaData, registry, column helpers
                base_unit_of_work.py         # SqlAlchemyUnitOfWork base class
alembic/
    env.py                                   # Async migration runner
    script.py.mako                           # Migration template
    versions/                                # (empty initially)
alembic.ini                                  # Alembic config
.env.example                                 # Environment variable documentation
```

**Directory rationale (per architecture-patterns Ports & Adapters):**
- `infrastructure/config/` — Cross-cutting concerns (settings, feature flags)
- `adapters/outbound/persistence/` — Driven adapters (database engine, ORM registry, base UoW)

**Note:** Context-specific adapters (ORM tables, mappers, repositories) will live in `src/emerald/{context}/adapters/outbound/persistence/` as defined by specs 022–025.

---

## 12. Environment File

### 12.1 .env.example

```env
# Application
APP_NAME=Emerald Finance
ENVIRONMENT=development
DEBUG=true

# Database
DATABASE_URL=postgresql+asyncpg://emerald:emerald@localhost:5432/emerald_dev
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_ECHO=false
DATABASE_ECHO_POOL=false

# JWT
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_TTL_MINUTES=15
JWT_REFRESH_TOKEN_TTL_DAYS=30
JWT_ISSUER=emerald-finance

# OIDC (optional — social login)
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

---

## 13. Acceptance Criteria

### Settings

- [ ] `AppSettings` loads from environment variables and `.env` file
- [ ] `DatabaseSettings.url` is required — raises `ValidationError` if missing
- [ ] `JwtSettings.secret_key` is required — raises `ValidationError` if missing
- [ ] OIDC settings are optional — app starts without social login config
- [ ] OIDC model validator: if `client_id` is set, `client_secret` and `redirect_uri` must be set too
- [ ] CORS origins parsed from comma-separated string
- [ ] All settings have sensible development defaults where appropriate
- [ ] Settings are immutable after creation (frozen)
- [ ] `DatabaseSettings` validates `pool_size >= 1` and `max_overflow >= 0`
- [ ] `JwtSettings` validates `algorithm` against allowed list

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

- [ ] `alembic.ini` scaffold present
- [ ] Async `env.py` with `run_async_migrations()` pattern
- [ ] Migrations directory exists (empty — migrations created by specs 022–025)
- [ ] Alembic reads database URL from environment
- [ ] `target_metadata` references the shared `MetaData` instance
- [ ] Naming convention dict applied to MetaData for consistent constraint names
- [ ] `env.py` calls `configure_all_mappers()` before autogenerate

### ORM Foundation

- [ ] Shared `MetaData` instance with naming convention
- [ ] Shared `registry` for imperative mapping
- [ ] `uuid_pk()` column helper returns UUID PK column
- [ ] `timestamp_columns()` returns created_at + updated_at columns (timezone-aware)
- [ ] `audit_columns()` extends timestamps with created_by + updated_by
- [ ] `soft_delete_columns()` returns all 4 soft-delete columns (deleted_at, deleted_by, deletion_reason, hard_delete_scheduled_at)
- [ ] `version_column()` returns integer version column for optimistic locking
- [ ] No `start_mappers()` global — composition root pattern documented for spec 026
- [ ] `configure_all_mappers()` pattern established (initially no-op, populated by specs 022–025)
- [ ] All timestamps are timezone-aware UTC

### Base Unit of Work

- [ ] `SqlAlchemyUnitOfWork` implements async context manager protocol
- [ ] `commit()` persists changes
- [ ] `rollback()` discards uncommitted changes
- [ ] Exception in context manager triggers automatic rollback
- [ ] Session is closed after `__aexit__` regardless of success/failure
- [ ] Exposes `session` property for repository construction

### Abstract UoW Migration

- [ ] `AbstractUnitOfWork` uses `__aenter__`/`__aexit__` and async commit/rollback
- [ ] All 4 context-specific abstract UoWs updated to async
- [ ] All fake UoWs in test suites updated to async
- [ ] All application services updated to async (methods using UoW)
- [ ] All test call sites updated (`async with`, `await`, `@pytest.mark.asyncio`)
- [ ] All 2605+ existing tests pass after migration
- [ ] `pytest-asyncio` added as dev dependency

### Environment File

- [ ] `.env.example` documents all environment variables
- [ ] Development defaults allow local startup without modification (except secrets)

### Quality Gates

- [ ] `ruff check` passes clean
- [ ] `ruff format` passes clean
- [ ] `ty check` passes clean
- [ ] All tests pass

---

## 14. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Missing `DATABASE_URL` env var | `ValidationError` raised at settings construction |
| Missing `JWT_SECRET_KEY` env var | `ValidationError` raised at settings construction |
| Invalid JWT algorithm | `ValidationError` with message listing valid options |
| OIDC client_id set without client_secret | `ValidationError` from model validator |
| `pool_size = 0` | `ValidationError` — must be ≥ 1 |
| `max_overflow = -1` | `ValidationError` — must be ≥ 0 |
| `configure_*_mappers()` called twice | SQLAlchemy raises error on double-mapping — composition root ensures single call |
| Exception inside `async with uow:` | Automatic rollback, then session close |
| `commit()` called after `__aexit__` | Session already closed — raises SQLAlchemy error |
| Optimistic concurrency conflict | `StaleDataError` from SQLAlchemy (via `version_id_col`) |

---

## 15. Dependencies

### Internal Dependencies

- **Shared Kernel domain layer** — abstract UoWs being migrated to async
- **All context application layers** — services migrated to async
- **All test fakes** — migrated to async

### External Dependencies

- PostgreSQL 15+ (target database)
- Python 3.13+ (already required by project)

---

## 16. Constraints

- **No declarative ORM models** — domain classes stay pure Python. Classical mapping only.
- **No synchronous database code** — everything async (asyncpg + async engine)
- **Alembic autogenerate** requires `configure_all_mappers()` to run first
- **`env_nested_delimiter`** for pydantic-settings: double underscore (`__`) for nested settings in env vars
- **Line length** ≤ 100 chars (ruff config)

---

## 17. Glossary

- **Classical/Imperative Mapping** — SQLAlchemy pattern where `Table` objects are defined separately from domain classes, and `registry.map_imperatively()` binds them. Domain classes have zero ORM awareness.
- **version_id_col** — SQLAlchemy mapper option that enables automatic optimistic locking via a version counter column.
- **configure_all_mappers()** — Composition root function (spec 026) that calls each context's `configure_*_mappers()` once during app bootstrap and before Alembic autogenerate. No global state — relies on SQLAlchemy's built-in double-mapping prevention.
- **Column helpers** — Reusable functions returning `list[Column]` for common patterns (UUID PK, timestamps, etc.), used when defining `Table` objects.
