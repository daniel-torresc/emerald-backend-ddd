# Spec 021: Configuration & Database Foundation — Implementation Plan

**Spec:** `.specs/spec-021-configuration-and-database-foundation/spec.md`
**Version:** 1.0
**Date:** 2026-02-18

---

## 1. Overview

This spec establishes the infrastructure skeleton for the Emerald backend: application settings (pydantic-settings), SQLAlchemy 2.0 async engine/session, Alembic migration scaffold, classical ORM mapping foundation, and the base `SqlAlchemyUnitOfWork`. It also migrates all existing abstract UoWs, application services, fake UoWs, and tests from sync to async.

**Approach:** Inside-out — infrastructure foundation first, then async migration of existing domain/application/test code.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|---|---|---|
| Settings (§4) | Infrastructure (cross-cutting) | `AppSettings`, `DatabaseSettings`, `JwtSettings`, `OidcSettings`, `CorsSettings` |
| Engine/Session (§5) | Adapters (outbound/persistence) | `create_async_engine_from_settings()`, `create_session_factory()`, `dispose_engine()` |
| ORM Registry (§7) | Adapters (outbound/persistence) | `metadata`, `mapper_registry`, column helpers, `configure_all_mappers()` |
| Base UoW (§9) | Adapters (outbound/persistence) | `SqlAlchemyUnitOfWork` |
| Alembic (§6) | Infrastructure (tooling) | `alembic/`, `alembic.ini` |
| Async migration (§8) | Application + Tests | Abstract UoWs, services, fakes, test call sites |

### 2.2 New File Structure

```
src/emerald/shared_kernel/
    infrastructure/
        __init__.py
        config/
            __init__.py
            settings.py              # AppSettings + all sub-settings
    adapters/
        __init__.py
        outbound/
            __init__.py
            persistence/
                __init__.py
                database.py          # Engine factory, session factory, dispose
                orm_registry.py      # MetaData, registry, column helpers
                base_unit_of_work.py # SqlAlchemyUnitOfWork
                mapper_setup.py      # configure_all_mappers() (initially no-op)
alembic/
    env.py
    script.py.mako
    versions/                        # empty
alembic.ini
.env.example
```

### 2.3 Async Migration Scope

**13 application services** (all using `with self._uow:` / `uow.commit()`):
- IAM (4): UserRegistrationService, AuthenticationService, RoleManagementService, SuperadminProvisioningService
- Core Finance (5): AccountManagementService, AccountSharingService, TransactionManagementService, BulkTransactionService, CardManagementService
- Classification (2): TaxonomyManagementService, TransactionCategorizationService
- Integrations (2): BankConnectionService, BankSyncService

**Note:** RetentionPolicyService does NOT use UoW — it uses `RetentionPolicyRepository` directly. Repository protocols remain sync per spec §8.3 ("repositories themselves are not async").

**5 abstract UoW classes:** 1 base + 4 context-specific
**4 fake UoW classes** in test fakes
**~34 test files** with `with uow:` / `uow.commit()` patterns

---

## 3. Technical Decisions

### 3.1 Settings Architecture
**Decision:** Single `settings.py` file with all sub-settings classes and `AppSettings` root.
**Rationale:** All settings are small, related, and benefit from being co-located. Separate files would create unnecessary fragmentation.

### 3.2 Column Helpers Return Type
**Decision:** Column helpers return `list[sa.Column]` that are spread into `Table(...)` constructors via `*uuid_pk()`.
**Rationale:** Matches the spec's description and allows composable table definitions in specs 022–025.

### 3.3 Async Migration Strategy
**Decision:** Big-bang migration — all services, UoWs, fakes, and tests converted in one pass.
**Rationale:** Partial migration is impossible because the abstract UoW base class must be either sync or async. All subclasses and consumers must match.

### 3.4 pytest-asyncio Mode
**Decision:** Use `asyncio_mode = "auto"` in pytest config so all `async def test_*` functions are automatically treated as async tests.
**Rationale:** Avoids adding `@pytest.mark.asyncio` to hundreds of test functions. Simpler migration.

---

## 4. Implementation Tasks

### Phase 1: Dependencies & Configuration

#### TASK-001: Add new dependencies to pyproject.toml
**Layer:** Project config
**Depends On:** None

**Description:**
Add all new runtime and dev dependencies specified in spec §10.

**Files to Modify:**
- `pyproject.toml` — add runtime deps: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `argon2-cffi`, `pyjwt[crypto]`, `httpx`, `fastapi`, `uvicorn[standard]`; add dev dep: `pytest-asyncio`

**Acceptance Criteria:**
- [ ] `uv sync` succeeds with all new packages installed
- [ ] `pytest-asyncio` available as dev dependency

---

#### TASK-002: Configure pytest-asyncio auto mode
**Layer:** Project config
**Depends On:** TASK-001

**Description:**
Add `asyncio_mode = "auto"` to pytest config so async test functions run automatically without decorators.

**Files to Modify:**
- `pyproject.toml` — add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]`

**Acceptance Criteria:**
- [ ] `async def test_*` functions automatically detected as async tests

---

#### TASK-003: Create AppSettings and sub-settings
**Layer:** Infrastructure (cross-cutting)
**Depends On:** TASK-001

**Description:**
Implement all settings classes per spec §4: `DatabaseSettings`, `JwtSettings`, `OidcSettings`, `CorsSettings`, and the root `AppSettings`. Each uses `pydantic_settings.BaseSettings` with `env_prefix`, frozen config, and validation rules. Settings are composed under `AppSettings`.

**Files to Create:**
- `src/emerald/shared_kernel/infrastructure/__init__.py`
- `src/emerald/shared_kernel/infrastructure/config/__init__.py`
- `src/emerald/shared_kernel/infrastructure/config/settings.py`

**Acceptance Criteria:**
- [ ] `AppSettings` loads from env vars and `.env` file
- [ ] `DatabaseSettings.url` required — `ValidationError` if missing
- [ ] `JwtSettings.secret_key` required — `ValidationError` if missing
- [ ] `JwtSettings.algorithm` validated against `[HS256, HS384, HS512, RS256]`
- [ ] `DatabaseSettings` validates `pool_size >= 1`, `max_overflow >= 0`
- [ ] OIDC fields all optional; model validator: if `client_id` set, `client_secret` + `redirect_uri` required
- [ ] CORS `allowed_origins` parsed from comma-separated string
- [ ] All settings frozen after creation

**Tests:**
- [ ] Unit tests for each sub-settings validation rule
- [ ] Unit tests for OIDC cross-field validation
- [ ] Tests for default values

---

#### TASK-004: Create .env.example
**Layer:** Project config
**Depends On:** TASK-003

**Description:**
Create `.env.example` documenting all environment variables per spec §12.

**Files to Create:**
- `.env.example`

**Acceptance Criteria:**
- [ ] All env vars from spec §12 documented with development defaults

---

### Phase 2: Database & ORM Foundation

#### TASK-005: Create shared MetaData, registry, and column helpers
**Layer:** Adapters (outbound/persistence)
**Depends On:** TASK-001

**Description:**
Create `orm_registry.py` with shared `MetaData` (with naming convention), shared `registry`, and column helper functions per spec §7.

**Files to Create:**
- `src/emerald/shared_kernel/adapters/__init__.py`
- `src/emerald/shared_kernel/adapters/outbound/__init__.py`
- `src/emerald/shared_kernel/adapters/outbound/persistence/__init__.py`
- `src/emerald/shared_kernel/adapters/outbound/persistence/orm_registry.py`

**Acceptance Criteria:**
- [ ] `metadata` with naming convention dict (§6.4)
- [ ] `mapper_registry = registry(metadata=metadata)`
- [ ] `uuid_pk()` returns UUID PK column
- [ ] `timestamp_columns()` returns timezone-aware created_at + updated_at
- [ ] `audit_columns()` extends timestamps with created_by + updated_by
- [ ] `soft_delete_columns()` returns 4 soft-delete columns
- [ ] `version_column()` returns integer version column (default 0)

**Tests:**
- [ ] Unit tests verifying each column helper returns correct columns with expected types/constraints

---

#### TASK-006: Create engine factory and session factory
**Layer:** Adapters (outbound/persistence)
**Depends On:** TASK-003, TASK-005

**Description:**
Implement `database.py` with `create_async_engine_from_settings()`, `create_session_factory()`, and `dispose_engine()` per spec §5.

**Files to Create:**
- `src/emerald/shared_kernel/adapters/outbound/persistence/database.py`

**Acceptance Criteria:**
- [ ] Engine factory creates async engine from `DatabaseSettings`
- [ ] Pool size and overflow configured from settings
- [ ] Echo modes configured from settings
- [ ] Session factory creates sessions with `expire_on_commit=False`, `autoflush=False`
- [ ] `dispose_engine()` cleans up engine and pool

**Tests:**
- [ ] Unit tests verifying engine creation with settings (mock engine or verify params)
- [ ] Unit tests for session factory configuration

---

#### TASK-007: Create base SqlAlchemyUnitOfWork
**Layer:** Adapters (outbound/persistence)
**Depends On:** TASK-006

**Description:**
Implement `SqlAlchemyUnitOfWork` async base class per spec §9.

**Files to Create:**
- `src/emerald/shared_kernel/adapters/outbound/persistence/base_unit_of_work.py`

**Acceptance Criteria:**
- [ ] `__aenter__` creates new session from factory
- [ ] `__aexit__` rolls back on exception, always closes session
- [ ] `commit()` persists changes via session
- [ ] `rollback()` discards uncommitted changes
- [ ] `session` property exposes the session for repository construction

**Tests:**
- [ ] Unit tests with mock session factory verifying lifecycle (enter/exit/commit/rollback)
- [ ] Test exception path triggers rollback + close
- [ ] Test normal path only closes (no rollback)

---

#### TASK-008: Create configure_all_mappers() stub
**Layer:** Adapters (outbound/persistence)
**Depends On:** TASK-005

**Description:**
Create `mapper_setup.py` with `configure_all_mappers()` — initially a no-op that will be populated by specs 022–025. This is needed by Alembic `env.py`.

**Files to Create:**
- `src/emerald/shared_kernel/adapters/outbound/persistence/mapper_setup.py`

**Acceptance Criteria:**
- [ ] `configure_all_mappers()` exists and is callable (no-op)
- [ ] Docstring documents that specs 022–025 will add context-specific mapper calls

---

### Phase 3: Alembic Scaffold

#### TASK-009: Initialize Alembic with async env.py
**Layer:** Infrastructure (tooling)
**Depends On:** TASK-005, TASK-008

**Description:**
Create the Alembic scaffold per spec §6: `alembic.ini`, async `env.py` with `run_async_migrations()` pattern, `script.py.mako`, and empty `versions/` directory. `env.py` imports `configure_all_mappers()` before autogenerate and references the shared `MetaData` as `target_metadata`.

**Files to Create:**
- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/.gitkeep`

**Acceptance Criteria:**
- [ ] `alembic.ini` at project root, pointing to `alembic/` directory
- [ ] `env.py` uses async `run_async_migrations()` pattern
- [ ] `env.py` reads `DATABASE_URL` from environment (via `sqlalchemy.url` in config or env override)
- [ ] `target_metadata` references shared `MetaData` instance
- [ ] `env.py` calls `configure_all_mappers()` before autogenerate
- [ ] Naming convention applied for consistent constraint names
- [ ] Empty `versions/` directory exists

---

### Phase 4: Async Migration — Abstract UoWs & Services

#### TASK-010: Migrate AbstractUnitOfWork to async
**Layer:** Application (shared kernel)
**Depends On:** TASK-002

**Description:**
Convert the base `AbstractUnitOfWork` from sync to async: `__enter__` → `__aenter__`, `__exit__` → `__aexit__`, `commit()` → `async commit()`, `rollback()` → `async rollback()`.

**Files to Modify:**
- `src/emerald/shared_kernel/application/ports/outbound/unit_of_work.py`

**Acceptance Criteria:**
- [ ] `__aenter__` / `__aexit__` async context manager
- [ ] `commit()` and `rollback()` are abstract async methods
- [ ] Docstring updated to show `async with` usage

---

#### TASK-011: Migrate all 4 context-specific abstract UoWs to async
**Layer:** Application (all contexts)
**Depends On:** TASK-010

**Description:**
Update all context-specific abstract UoW classes to use async `commit()` / `rollback()`.

**Files to Modify:**
- `src/emerald/iam/application/ports/outbound/unit_of_work.py`
- `src/emerald/core_finance/application/ports/outbound/unit_of_work.py`
- `src/emerald/classification/application/ports/outbound/unit_of_work.py`
- `src/emerald/integrations/application/ports/outbound/unit_of_work.py`

**Acceptance Criteria:**
- [ ] All 4 abstract UoWs have `async def commit()` and `async def rollback()`

---

#### TASK-012: Migrate all 13 application services to async
**Layer:** Application (all contexts)
**Depends On:** TASK-011

**Description:**
Convert all service methods that use `with self._uow:` → `async with self._uow:` and `self._uow.commit()` → `await self._uow.commit()`. All affected methods become `async def`.

**Files to Modify (13 files):**
- `src/emerald/iam/application/services/user_registration.py`
- `src/emerald/iam/application/services/authentication.py`
- `src/emerald/iam/application/services/role_management.py`
- `src/emerald/iam/application/services/superadmin_provisioning.py`
- `src/emerald/core_finance/application/services/account_management.py`
- `src/emerald/core_finance/application/services/account_sharing.py`
- `src/emerald/core_finance/application/services/transaction_management.py`
- `src/emerald/core_finance/application/services/bulk_transaction.py`
- `src/emerald/core_finance/application/services/card_management.py`
- `src/emerald/classification/application/services/taxonomy_management.py`
- `src/emerald/classification/application/services/transaction_categorization.py`
- `src/emerald/integrations/application/services/bank_connection.py`
- `src/emerald/integrations/application/services/bank_sync.py`

**Acceptance Criteria:**
- [ ] All methods using UoW are `async def`
- [ ] All `with self._uow:` → `async with self._uow:`
- [ ] All `self._uow.commit()` → `await self._uow.commit()`
- [ ] No sync UoW usage remains in any service

---

### Phase 5: Async Migration — Fakes & Tests

#### TASK-013: Migrate all 4 fake UoW implementations to async
**Layer:** Tests
**Depends On:** TASK-011

**Description:**
Update all fake UoW classes in test fakes to use async context manager and async commit/rollback.

**Files to Modify:**
- `tests/unit/iam/fakes.py`
- `tests/unit/core_finance/fakes.py`
- `tests/unit/classification/fakes.py`
- `tests/unit/integrations/fakes.py`

**Acceptance Criteria:**
- [ ] All 4 fakes use `async def commit()` and `async def rollback()`
- [ ] FakeUoWs satisfy their abstract parent class contracts

---

#### TASK-014: Migrate all test call sites to async
**Layer:** Tests
**Depends On:** TASK-012, TASK-013

**Description:**
Update all ~34 test files that use `with uow:` / `uow.commit()` to use `async with` / `await`. Convert test functions to `async def`. With `asyncio_mode = "auto"`, no `@pytest.mark.asyncio` decorators needed.

Also update `tests/unit/shared_kernel/application/test_unit_of_work.py` — the test that tests the base `AbstractUnitOfWork` with a `_ConcreteUnitOfWork` double.

**Files to Modify:**
- ~34 test files across `tests/unit/iam/`, `tests/unit/core_finance/`, `tests/unit/classification/`, `tests/unit/integrations/`, `tests/unit/shared_kernel/`

**Acceptance Criteria:**
- [ ] All `with uow:` → `async with uow:`
- [ ] All `uow.commit()` → `await uow.commit()`
- [ ] All test functions using UoW are `async def`
- [ ] All 2605+ existing tests pass

---

### Phase 6: Public API & Quality

#### TASK-015: Update context `__init__.py` re-exports
**Layer:** All contexts
**Depends On:** TASK-003, TASK-005, TASK-006, TASK-007, TASK-008

**Description:**
Update shared kernel `__init__.py` to re-export new infrastructure types. Add `__init__.py` files with `__all__` for new packages.

**Files to Modify/Create:**
- `src/emerald/shared_kernel/__init__.py` — add infrastructure re-exports
- New `__init__.py` files for infrastructure/adapters packages

**Acceptance Criteria:**
- [ ] All new public types accessible via package re-exports
- [ ] `__all__` lists maintained

---

#### TASK-016: Run full quality gate
**Layer:** Cross-cutting
**Depends On:** TASK-014, TASK-015

**Description:**
Verify all quality gates pass after complete migration.

**Acceptance Criteria:**
- [ ] `uv run ruff check .` — clean
- [ ] `uv run ruff format --check .` — clean
- [ ] `uv run ty check` — clean
- [ ] `uv run pytest` — all tests pass (2605+ tests)

---

## 5. Task Dependency Graph

```
TASK-001 (deps) ─┬─► TASK-002 (pytest-asyncio) ─► TASK-010 (base UoW async) ─► TASK-011 (ctx UoWs)
                 │                                                                  │
                 ├─► TASK-003 (settings) ─┬─► TASK-004 (.env.example)          ┌────┴────┐
                 │                        │                                    │         │
                 │                        └─► TASK-006 (engine/session)    TASK-012  TASK-013
                 │                                │                       (services) (fakes)
                 └─► TASK-005 (orm registry) ─┬─► TASK-006                    │         │
                                              │                               └────┬────┘
                                              ├─► TASK-007 (base UoW SA) ──┐       │
                                              │                            │   TASK-014
                                              └─► TASK-008 (mapper stub)   │   (tests)
                                                       │                   │       │
                                                       └─► TASK-009        │   TASK-015
                                                          (alembic)        │   (re-exports)
                                                                           │       │
                                                                           └───┬───┘
                                                                               │
                                                                           TASK-016
                                                                          (quality)
```

**Critical path:** TASK-001 → TASK-002 → TASK-010 → TASK-011 → TASK-012/013 → TASK-014 → TASK-016

**Parallelizable:**
- TASK-003, TASK-005 can start in parallel after TASK-001
- TASK-012 (services) and TASK-013 (fakes) can run in parallel after TASK-011
- TASK-004 (.env.example) is independent after TASK-003
- TASK-007 (base UoW SA), TASK-008 (mapper stub), TASK-009 (alembic) are independent of async migration path

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Async migration breaks many tests | Medium | High | `asyncio_mode = "auto"` minimizes decorator churn; systematic file-by-file conversion |
| `ty` strict checking rejects async patterns | Low | Medium | `ty` handles `async` well; test with small sample first |
| SQLAlchemy import in domain layer | Low | High | Column helpers only in adapters layer; no SA imports in domain/application |
| Alembic async env.py complexity | Low | Low | Well-documented pattern; no actual migrations yet |
| pydantic-settings env_nested_delimiter conflicts | Low | Low | Use `env_prefix` per sub-settings class instead of relying solely on nesting |

---

## 7. Definition of Done

- [ ] All 16 tasks completed
- [ ] Settings load correctly from environment variables
- [ ] ORM registry with column helpers ready for specs 022–025
- [ ] Engine/session factory functional
- [ ] SqlAlchemyUnitOfWork base class operational
- [ ] Alembic scaffold present and configured
- [ ] All abstract UoWs async
- [ ] All 13 application services async
- [ ] All 4 fake UoWs async
- [ ] All ~34 test files migrated to async
- [ ] All 2605+ existing tests pass
- [ ] `ruff check` clean
- [ ] `ruff format` clean
- [ ] `ty check` clean
- [ ] `.env.example` documents all environment variables
- [ ] New infrastructure tests cover settings, column helpers, base UoW
