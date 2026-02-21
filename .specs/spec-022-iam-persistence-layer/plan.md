# Spec 022: IAM Persistence Layer — Implementation Plan

**Spec:** `.specs/spec-022-iam-persistence-layer/spec.md`
**Version:** 1.0
**Date:** 2026-02-21

---

## 1. Overview

Implement the IAM bounded context's persistence layer: ORM models for all IAM entities, repository implementations for all IAM ports, the IAM Unit of Work, and the initial Alembic migration. Also implement the shared kernel's `RetentionPolicyRepository` since its table has a FK to `iam_users`.

**Approach:** Separate ORM model classes with `to_domain()` / `from_domain()` converters. Domain layer remains free of SQLAlchemy imports. All repositories receive `AsyncSession` via constructor injection from the Unit of Work.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| ORM model classes | Infrastructure (Adapters) | `UserModel`, `UserAuthProviderModel`, `RefreshTokenModel`, `PasswordResetTokenModel`, `UserRetentionPreferenceModel` |
| Repository implementations | Infrastructure (Adapters) | `SqlAlchemyUserRepository`, `SqlAlchemyRefreshTokenRepository`, `SqlAlchemyPasswordResetTokenRepository`, `SqlAlchemyRetentionPolicyRepository` |
| Unit of Work | Infrastructure (Adapters) | `SqlAlchemyIamUnitOfWork` |
| Database schema | Infrastructure (Migration) | Alembic migration `001_iam_and_shared_kernel_tables.py` |

### 2.2 Component Diagram

```
SqlAlchemyIamUnitOfWork (extends SqlAlchemyUnitOfWork)
├── .users            → SqlAlchemyUserRepository(session)
│                         └── UserModel ←→ User aggregate
│                         └── UserAuthProviderModel ←→ AuthProvider VO
├── .refresh_tokens   → SqlAlchemyRefreshTokenRepository(session)
│                         └── RefreshTokenModel ←→ RefreshToken entity
└── .password_reset_tokens → SqlAlchemyPasswordResetTokenRepository(session)
                              └── PasswordResetTokenModel ←→ PasswordResetToken entity

SqlAlchemyRetentionPolicyRepository(session)  [standalone, shared kernel]
    └── UserRetentionPreferenceModel ←→ UserRetentionPreference entity
```

### 2.3 Ports and Adapters

| Port (Protocol) | Location | Adapter (Implementation) |
|------------------|----------|--------------------------|
| `UserRepository` | `iam/application/ports/outbound/user_repository.py` | `SqlAlchemyUserRepository` |
| `RefreshTokenRepository` | `iam/application/ports/outbound/refresh_token_repository.py` | `SqlAlchemyRefreshTokenRepository` |
| `PasswordResetTokenRepository` | `iam/application/ports/outbound/password_reset_token_repository.py` | `SqlAlchemyPasswordResetTokenRepository` |
| `RetentionPolicyRepository` | `shared_kernel/application/ports/outbound/retention_policy_repository.py` | `SqlAlchemyRetentionPolicyRepository` |
| `AbstractIamUnitOfWork` | `iam/application/ports/outbound/unit_of_work.py` | `SqlAlchemyIamUnitOfWork` |

---

## 3. Technical Decisions

### 3.1 ORM Mapping Strategy
**Decision:** Separate ORM model classes with `to_domain()` / `from_domain()` converters (not imperative mapping).
**Rationale:** Domain entities use frozen dataclass VOs, private `_id`/`_version` attributes with property accessors, and complex collections (`set[AuthProvider]`, `frozenset[AdminPermission]`). These conflict with SQLAlchemy's attribute mutation requirements for imperative mapping.

### 3.2 Declarative Base
**Decision:** ORM models inherit from a `Base(DeclarativeBase)` that references the shared `metadata` from `orm_registry.py`.
**Rationale:** Ensures all ORM tables share the same `MetaData` instance and naming conventions established in spec-021.

### 3.3 Auth Provider Sync
**Decision:** Merge-by-provider-type strategy (not delete-and-reinsert).
**Rationale:** Preserves synthetic row IDs, avoids unnecessary churn. Match existing rows by `(user_id, provider_type)`.

### 3.4 Upsert via session.merge()
**Decision:** `UserRepository.add()` uses `session.merge()` for upsert semantics.
**Rationale:** The protocol name is `add` but application services call it for both new users and existing users after mutations.

### 3.5 User Reconstruction Post-Init Fields
**Decision:** After `User.__init__()`, mutable mixin fields (`updated_at`, `updated_by`, `deleted_at`, `deleted_by`, `deletion_reason`, `hard_delete_scheduled_at`) are set directly via attribute assignment.
**Rationale:** These fields come from `SoftDeletableMixin` and `AuditableMixin` and are not part of `__init__` kwargs — they must be hydrated after construction.

### 3.6 Test Infrastructure
**Decision:** Integration tests use `testcontainers` with a real PostgreSQL instance.
**Rationale:** Tests must validate actual SQL behavior (case-insensitive queries, partial indexes, JSON columns, ON DELETE CASCADE).

---

## 4. Implementation Tasks

### Phase 1: ORM Base & Models

#### TASK-001: Create ORM declarative base
**Layer:** Infrastructure
**Depends On:** None

**Description:**
Create a shared ORM `Base` class that uses the existing `metadata` from `orm_registry.py`. This base is shared across all bounded contexts' ORM models.

**Files:**
- `src/emerald/shared_kernel/adapters/outbound/persistence/orm_base.py` — `Base(DeclarativeBase)` tied to shared `metadata`

**Acceptance Criteria:**
- [ ] `Base` inherits from `DeclarativeBase`
- [ ] `Base.metadata` is the same `MetaData` instance from `orm_registry.py`

**Tests:**
- No unit tests needed (validated by subsequent ORM model tests)

---

#### TASK-002: Create IAM ORM models
**Layer:** Infrastructure
**Depends On:** TASK-001

**Description:**
Implement all 4 IAM ORM model classes: `UserModel`, `UserAuthProviderModel`, `RefreshTokenModel`, `PasswordResetTokenModel`. Each model includes `to_domain()` and `from_domain()` converters.

**Files:**
- `src/emerald/iam/adapters/__init__.py` (empty)
- `src/emerald/iam/adapters/outbound/__init__.py` (empty)
- `src/emerald/iam/adapters/outbound/persistence/__init__.py` (empty)
- `src/emerald/iam/adapters/outbound/persistence/orm_models.py`

**Key Implementation Details:**

`UserModel`:
- Table `iam_users`, columns per spec section 5.1
- `UserPreferences` VO flattened to 3 columns (timezone, locale, display_currency)
- `admin_permissions` frozenset → JSON array of string values
- `password_history` → JSON array of hash strings
- `from_domain()`: extract `user.password.hashed_value` if password is not None
- `to_domain()`: reconstruct full User aggregate including auth_providers from relationship
- Post-construction: set `updated_at`, `updated_by`, `deleted_at`, `deleted_by`, `deletion_reason`, `hard_delete_scheduled_at`
- Relationship to `UserAuthProviderModel` via `cascade="all, delete-orphan"`

`UserAuthProviderModel`:
- Table `iam_user_auth_providers`, synthetic `id` PK
- `from_domain()` generates UUID for `id`
- `to_domain()` returns `AuthProvider` VO

`RefreshTokenModel`:
- Table `iam_refresh_tokens`, columns per spec section 5.3
- Straightforward `to_domain()`/`from_domain()`
- `portal_context` stored as enum string value

`PasswordResetTokenModel`:
- Table `iam_password_reset_tokens`, columns per spec section 5.4
- Straightforward `to_domain()`/`from_domain()`

**Acceptance Criteria:**
- [ ] All 4 ORM model classes with correct column types and constraints
- [ ] `to_domain()` reconstructs full domain entity for each model
- [ ] `from_domain()` decomposes domain entity into ORM-friendly columns
- [ ] Indexes defined per spec (email unique, username partial unique, status, system_role, token_hash unique, family_id, user_id)
- [ ] FK relationships defined (all → `iam_users.id` with CASCADE)

**Tests:**
- Tested via integration round-trip tests in TASK-007

---

#### TASK-003: Create shared kernel ORM model for UserRetentionPreference
**Layer:** Infrastructure
**Depends On:** TASK-001

**Description:**
Implement `UserRetentionPreferenceModel` in the shared kernel's persistence adapters.

**Files:**
- `src/emerald/shared_kernel/adapters/outbound/persistence/orm_models.py`

**Key Implementation Details:**
- Table `sk_user_retention_preferences`
- `RetentionPeriod` VO decomposed into `retention_duration` + `retention_unit`
- UNIQUE(`user_id`, `entity_type`)
- FK → `iam_users.id` ON DELETE CASCADE
- `to_domain()` must pass validation in `UserRetentionPreference.__init__` (which checks against `DEFAULT_RETENTION`)
- `from_domain()` extracts `preference.retention_period.duration` and `preference.retention_period.unit.value`

**Acceptance Criteria:**
- [ ] ORM model with correct columns and constraints
- [ ] `to_domain()` and `from_domain()` handle `RetentionPeriod` decomposition/reconstruction
- [ ] UNIQUE constraint on (user_id, entity_type)

**Tests:**
- Tested via integration tests in TASK-009

---

### Phase 2: Repository Implementations

#### TASK-004: Implement SqlAlchemyUserRepository
**Layer:** Infrastructure
**Depends On:** TASK-002

**Description:**
Implement the `UserRepository` protocol using SQLAlchemy async session.

**Files:**
- `src/emerald/iam/adapters/outbound/persistence/user_repository.py`

**Key Implementation Details:**
- `add()`: Uses `session.merge()` for upsert. Auth provider sync via merge-by-provider-type:
  1. Query existing `UserAuthProviderModel` rows for user
  2. Build map of `provider_type → existing_row`
  3. For each domain `AuthProvider`: update existing or insert new
  4. Delete rows whose `provider_type` not in domain set
- `find_by_id()`: Query by PK with `selectinload` for auth providers
- `find_by_email()`: Case-insensitive via `func.lower()`, eager-load providers
- `find_by_username()`: Case-insensitive via `func.lower()`, eager-load providers
- `exists_by_email()`: `SELECT EXISTS` with `func.lower()`
- `exists_by_username()`: `SELECT EXISTS`, conditional `deleted_at IS NULL` filter
- `exists_by_role()`: `SELECT EXISTS` filtered by `system_role`

**Acceptance Criteria:**
- [ ] All 7 protocol methods implemented with correct signatures
- [ ] Case-insensitive lookups for email and username
- [ ] Auth provider sync (add/update/remove) on `add()`
- [ ] `exists_by_username` handles `include_recently_deleted` flag
- [ ] No domain types imported at runtime (use `TYPE_CHECKING` where possible, but runtime imports needed for conversion)

**Tests:**
- Integration tests in TASK-007

---

#### TASK-005: Implement SqlAlchemyRefreshTokenRepository and SqlAlchemyPasswordResetTokenRepository
**Layer:** Infrastructure
**Depends On:** TASK-002

**Description:**
Implement both token repository protocols.

**Files:**
- `src/emerald/iam/adapters/outbound/persistence/refresh_token_repository.py`
- `src/emerald/iam/adapters/outbound/persistence/password_reset_token_repository.py`

**Key Implementation Details:**

`SqlAlchemyRefreshTokenRepository`:
- `add()`: Convert to model, `session.add()`
- `find_by_hash()`: Query by `token_hash`
- `find_active_families_by_user()`: `SELECT DISTINCT family_id WHERE user_id=? AND revoked_at IS NULL AND expires_at > now()`
- `revoke_family()`: Bulk `UPDATE SET revoked_at=now() WHERE family_id=? AND revoked_at IS NULL`
- `revoke_all_for_user()`: Bulk `UPDATE SET revoked_at=now() WHERE user_id=? AND revoked_at IS NULL`
- `count_active_families()`: `SELECT COUNT(DISTINCT family_id) WHERE ...`

`SqlAlchemyPasswordResetTokenRepository`:
- `add()`: Convert to model, `session.add()`
- `find_by_hash()`: Query by `token_hash`
- `invalidate_existing_for_user()`: Bulk `UPDATE SET used_at=now() WHERE user_id=? AND used_at IS NULL`

**Acceptance Criteria:**
- [ ] All protocol methods match signatures exactly
- [ ] Bulk operations (revoke, invalidate) use UPDATE without loading entities
- [ ] No-op when bulk operations affect 0 rows (no error)

**Tests:**
- Integration tests in TASK-008

---

#### TASK-006: Implement SqlAlchemyRetentionPolicyRepository and SqlAlchemyIamUnitOfWork
**Layer:** Infrastructure
**Depends On:** TASK-003, TASK-004, TASK-005

**Description:**
Implement the shared kernel retention repository and the IAM Unit of Work.

**Files:**
- `src/emerald/shared_kernel/adapters/outbound/persistence/retention_policy_repository.py`
- `src/emerald/iam/adapters/outbound/persistence/unit_of_work.py`

**Key Implementation Details:**

`SqlAlchemyRetentionPolicyRepository`:
- `find_user_preference()`: Query by `(user_id, entity_type)`, convert to domain
- `save_user_preference()`: `session.merge()` for upsert
- `delete_user_preference()`: `DELETE WHERE user_id=? AND entity_type=?`

`SqlAlchemyIamUnitOfWork`:
- Extends `SqlAlchemyUnitOfWork` from shared kernel
- Lazily creates repositories on first property access using `self.session`
- Caches repo instances per `async with` block
- Resets cached repos on `__aenter__` (new session = new repos)
- Satisfies `AbstractIamUnitOfWork` protocol via structural subtyping

**Acceptance Criteria:**
- [ ] `SqlAlchemyIamUnitOfWork` exposes `users`, `refresh_tokens`, `password_reset_tokens` properties
- [ ] All repos share the same session within one UoW
- [ ] Repos lazily created and cached
- [ ] Reset on re-entry (`__aenter__`)
- [ ] Inherits `commit()`, `rollback()`, `__aenter__`, `__aexit__` from base

**Tests:**
- Integration tests in TASK-009, TASK-010

---

### Phase 3: Alembic Migration

#### TASK-007: Create Alembic migration for IAM and shared kernel tables
**Layer:** Infrastructure
**Depends On:** TASK-002, TASK-003

**Description:**
Write the initial Alembic migration that creates all 5 tables.

**Files:**
- `alembic/versions/001_iam_and_shared_kernel_tables.py`

**Tables (in order):**
1. `iam_users` — root table, no FKs
2. `iam_user_auth_providers` — FK → `iam_users.id`
3. `iam_refresh_tokens` — FK → `iam_users.id`
4. `iam_password_reset_tokens` — FK → `iam_users.id`
5. `sk_user_retention_preferences` — FK → `iam_users.id`

**Key Implementation Details:**
- All FKs use `ON DELETE CASCADE`
- Partial unique index on `username` (`WHERE username IS NOT NULL`)
- Partial unique index on `(provider_type, external_id)` (`WHERE external_id IS NOT NULL`)
- All timestamps use `sa.DateTime(timezone=True)` with `server_default=sa.func.now()` where applicable
- JSON columns for `admin_permissions` and `password_history` with `server_default='[]'`
- `downgrade` drops tables in reverse FK order

**Acceptance Criteria:**
- [ ] All 5 tables created with correct column types
- [ ] All indexes and unique constraints created
- [ ] All FKs reference `iam_users.id` with CASCADE
- [ ] Migration is reversible
- [ ] Timestamps timezone-aware

**Tests:**
- Validated by running migration in integration tests

---

### Phase 4: Integration Tests

#### TASK-008: Set up integration test infrastructure
**Layer:** Testing
**Depends On:** TASK-006, TASK-007

**Description:**
Create the integration test fixtures: PostgreSQL testcontainer, engine, session factory, Alembic migration runner, and shared helpers.

**Files:**
- `tests/integration/__init__.py`
- `tests/integration/conftest.py` — shared engine/session fixtures, migration setup
- `tests/integration/iam/__init__.py`
- `tests/integration/iam/conftest.py` — IAM-specific fixtures (user factories, UoW factory)
- `tests/integration/shared_kernel/__init__.py`

**Key Implementation Details:**
- Use `testcontainers` PostgreSQL container (or `pytest-docker` fixture)
- Create async engine per test session, run Alembic migrations on startup
- Per-test: create session via session factory, wrap in transaction, rollback after test
- Factory helpers for creating domain entities (User, RefreshToken, etc.) with sensible defaults
- Add `testcontainers` to dev dependencies

**Acceptance Criteria:**
- [ ] PostgreSQL container starts/stops per test session
- [ ] Alembic migrations run successfully on fresh database
- [ ] Each test gets a clean transaction (rollback isolation)
- [ ] Factory helpers create valid domain entities

**Tests:**
- Smoke test: basic connection and table existence verification

---

#### TASK-009: Integration tests for UserRepository
**Layer:** Testing
**Depends On:** TASK-008

**Description:**
Test all `SqlAlchemyUserRepository` methods and the ORM round-trip.

**Files:**
- `tests/integration/iam/test_user_repository.py`

**Test Cases:**
- ORM round-trip: `User → from_domain → persist → reload → to_domain → verify all fields`
- `add()` inserts new user with auth providers
- `add()` updates existing user (upsert)
- Auth provider sync: add new, update existing, remove missing
- `find_by_id()` returns User with providers or None
- `find_by_email()` case-insensitive
- `find_by_username()` case-insensitive
- `find_by_username()` returns None for username=None case
- `exists_by_email()` returns bool
- `exists_by_username(include_recently_deleted=True)` includes soft-deleted
- `exists_by_username(include_recently_deleted=False)` excludes soft-deleted
- `exists_by_role()` returns bool
- `admin_permissions` frozenset round-trip through JSON
- `password_history` list round-trip through JSON
- `UserPreferences` decomposition/reconstruction (3 columns)
- Optional fields: username=None, password=None
- DB unique constraint on email
- DB partial unique constraint on username

**Acceptance Criteria:**
- [ ] All repository methods tested (happy path + edge cases)
- [ ] Full domain entity round-trip verified (all fields survive persist → reload)
- [ ] Case-insensitive queries proven
- [ ] Auth provider sync verified across multiple saves

---

#### TASK-010: Integration tests for token repositories
**Layer:** Testing
**Depends On:** TASK-008

**Description:**
Test `SqlAlchemyRefreshTokenRepository` and `SqlAlchemyPasswordResetTokenRepository`.

**Files:**
- `tests/integration/iam/test_refresh_token_repository.py`
- `tests/integration/iam/test_password_reset_token_repository.py`

**Test Cases (RefreshToken):**
- `add()` persists token, `find_by_hash()` retrieves it
- `find_by_hash()` returns None for unknown hash
- `find_active_families_by_user()` returns only active, non-expired families
- `revoke_family()` sets `revoked_at` on all family tokens
- `revoke_all_for_user()` revokes all user tokens
- `count_active_families()` counts distinct active families
- No-op for revoke operations with 0 matching rows

**Test Cases (PasswordResetToken):**
- `add()` persists token, `find_by_hash()` retrieves it
- `find_by_hash()` returns None for unknown hash
- `invalidate_existing_for_user()` sets `used_at` on unused tokens
- No-op for invalidation with 0 matching rows

**Acceptance Criteria:**
- [ ] All protocol methods tested
- [ ] Bulk operations verified (revoke, invalidate)
- [ ] Edge cases (no matching rows) verified

---

#### TASK-011: Integration tests for RetentionPolicyRepository and IamUnitOfWork
**Layer:** Testing
**Depends On:** TASK-008

**Description:**
Test the shared kernel retention repository and UoW atomicity.

**Files:**
- `tests/integration/shared_kernel/test_retention_policy_repository.py`
- `tests/integration/iam/test_iam_unit_of_work.py`

**Test Cases (RetentionPolicy):**
- `find_user_preference()` returns preference or None
- `save_user_preference()` creates new preference
- `save_user_preference()` updates existing (upsert)
- `delete_user_preference()` removes preference
- `delete_user_preference()` no-op for non-existent
- UNIQUE constraint on (user_id, entity_type)

**Test Cases (UoW):**
- All repos accessible and share same session
- Commit persists changes from all repos atomically
- Rollback discards all changes
- Repository instances reset on re-entry

**Acceptance Criteria:**
- [ ] RetentionPolicyRepository fully tested
- [ ] UoW atomicity verified (commit/rollback)
- [ ] Cross-repo transaction isolation confirmed

---

### Phase 5: Finalize

#### TASK-012: Update __init__.py exports and run quality checks
**Layer:** Cross-cutting
**Depends On:** TASK-004, TASK-005, TASK-006

**Description:**
Update public API exports and ensure all quality checks pass.

**Files:**
- `src/emerald/iam/__init__.py` — add adapter exports if appropriate (infrastructure types may not be public API)
- `src/emerald/iam/adapters/outbound/persistence/__init__.py` — export all persistence types

**Acceptance Criteria:**
- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format .` passes
- [ ] `uv run ty check` passes
- [ ] `uv run pytest` passes (all existing + new tests)
- [ ] No SQLAlchemy imports in domain or application layers

---

## 5. Task Dependency Graph

```
TASK-001 (ORM Base)
├──► TASK-002 (IAM ORM Models) ──┬──► TASK-004 (UserRepository)     ──┐
│                                ├──► TASK-005 (Token Repositories)  ──┤
│                                └──► TASK-007 (Migration)           ──┤
└──► TASK-003 (SK ORM Model)  ───┬──► TASK-007 (Migration)           ──┤
                                 └──► TASK-006 (RetentionRepo + UoW) ──┤
                                                                       │
TASK-004 + TASK-005 ──► TASK-006 (UoW depends on all repos)           │
                                                                       ▼
                                                              TASK-008 (Test Infra)
                                                              ├──► TASK-009 (User tests)
                                                              ├──► TASK-010 (Token tests)
                                                              └──► TASK-011 (Retention + UoW tests)

                                                              TASK-012 (Quality checks) — after all
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| User `to_domain()` reconstruction misses mixin fields | Medium | High | Thorough round-trip integration tests |
| Auth provider sync edge cases (concurrent modifications) | Low | Medium | DB unique constraint `(user_id, provider_type)` as safety net |
| `session.merge()` behavior with relationships | Medium | Medium | Test upsert with providers carefully; consider explicit sync logic |
| `testcontainers` setup complexity | Low | Low | Fallback to manual Docker fixture if needed |
| `UserRetentionPreference.to_domain()` triggers validation | Medium | Medium | Ensure test data respects `DEFAULT_RETENTION` minimums |

---

## 7. Definition of Done

- [ ] All 12 tasks completed
- [ ] All acceptance criteria from spec section 15 met
- [ ] All integration tests passing with real PostgreSQL
- [ ] All existing unit tests still passing (no regressions)
- [ ] `uv run ruff check .` clean
- [ ] `uv run ruff format .` clean
- [ ] `uv run ty check` clean
- [ ] No SQLAlchemy imports in domain or application layers
- [ ] Migration is reversible (upgrade + downgrade verified)
