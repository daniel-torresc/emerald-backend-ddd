# Spec 022: IAM Persistence Layer

**Version:** 1.0
**Status:** Draft
**Date:** 2026-02-21
**Bounded Context:** IAM (Infrastructure)
**Dependencies:** 021 (Configuration & Database Foundation), 002-006 (IAM domain specs)
**Blocks:** 024, 026

---

## 1. Overview

This spec implements the IAM context's persistence layer: ORM models for all IAM entities, repository implementations for all IAM ports, the IAM Unit of Work, and the initial Alembic migration. The shared kernel's `RetentionPolicyRepository` is also implemented here since its backing table (`sk_user_retention_preferences`) has a FK to `iam_users`.

**Key Principle:** ORM models are separate lightweight classes from domain entities. Mapping is explicit via `to_domain()` / `from_domain()` converters. The domain layer remains free of SQLAlchemy imports.

---

## 2. Background & Context

### Problem Statement
The IAM bounded context has a complete domain and application layer (specs 002-006) with 5 Protocol ports that need infrastructure implementations. Without persistence, the system can only run with in-memory test fakes.

### Business Goals
- Enable real database-backed persistence for users, tokens, and retention preferences
- Establish the pattern for all subsequent persistence layers (specs 024-025)

---

## 3. Scope

### In Scope
- ORM model classes: `UserModel`, `UserAuthProviderModel`, `RefreshTokenModel`, `PasswordResetTokenModel`, `UserRetentionPreferenceModel`
- `to_domain()` / `from_domain()` mapping between ORM ↔ domain entities
- Repository implementations for all 4 IAM + shared kernel ports
- `SqlAlchemyIamUnitOfWork`
- Alembic migration for all IAM + shared kernel tables
- Integration tests with real PostgreSQL (via testcontainers or similar)

### Out of Scope
- Auth adapters (password hasher, JWT, OIDC) — spec 023
- Core Finance persistence — spec 024
- FastAPI integration — spec 026
- The `mapper_registry.map_imperatively()` approach from spec-021 — we use separate ORM models instead (see Section 4.1)

---

## 4. ORM Mapping Strategy

### 4.1 Approach: Separate ORM Models with Converters

Each domain entity gets a corresponding ORM model class (SQLAlchemy declarative or mapped Table). The ORM model is a thin data carrier with two conversion methods:

```
@staticmethod
def from_domain(entity: DomainEntity) -> OrmModel:
    """Decompose domain entity into ORM-friendly flat columns."""

def to_domain(self) -> DomainEntity:
    """Reconstruct domain entity from ORM columns."""
```

**Why not imperative mapping?** The domain entities use frozen dataclass VOs (`HashedPassword`, `AdminPermission` frozenset), private attributes with property accessors (`_id`, `_version`), and complex collections (`set[AuthProvider]`, `password_history: list[str]`). SQLAlchemy imperative mapping requires direct attribute mutation, which conflicts with these patterns.

**Impact on spec-021:** The `mapper_registry` and `map_imperatively()` scaffolding from spec-021 will not be used for entity mapping. The `metadata` object is still used for table definitions. The `mapper_setup.py` file can be repurposed or removed.

### 4.2 ORM Base Class

All ORM models inherit from a declarative base tied to the existing shared `metadata`:

```python
from emerald.shared_kernel.adapters.outbound.persistence.orm_registry import metadata

class Base(DeclarativeBase):
    metadata = metadata
```

This ensures all ORM tables use the same `MetaData` instance and naming conventions from spec-021.

---

## 5. ORM Models

### 5.1 UserModel

**Table:** `iam_users`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `User.id` (via `_id`) |
| email | VARCHAR(255) | No | UNIQUE | `User.email.address` |
| username | VARCHAR(50) | Yes | UNIQUE (partial) | `User.username.value` if set, else NULL |
| hashed_password | VARCHAR(255) | Yes | — | `User.password.hashed_value` if set, else NULL |
| password_history | JSON | No | DEFAULT '[]' | `User.password_history` (list[str]) |
| full_name | VARCHAR(200) | Yes | — | `User.full_name` (str \| None) |
| status | VARCHAR(30) | No | — | `User.status.value` (enum name) |
| system_role | VARCHAR(20) | No | DEFAULT 'USER' | `User.system_role.value` |
| admin_permissions | JSON | No | DEFAULT '[]' | `User.admin_permissions` (frozenset → JSON list) |
| email_verified | BOOLEAN | No | DEFAULT false | `User.email_verified` |
| preferences_timezone | VARCHAR(50) | No | DEFAULT 'UTC' | `User.preferences.timezone` |
| preferences_locale | VARCHAR(20) | No | DEFAULT 'en-US' | `User.preferences.locale` |
| preferences_display_currency | VARCHAR(3) | No | DEFAULT 'USD' | `User.preferences.display_currency.code` |
| last_login_at | TIMESTAMP(tz) | Yes | — | `User.last_login_at` |
| suspension_reason | TEXT | Yes | — | `User.suspension_reason` |
| version | INTEGER | No | DEFAULT 0 | `User.version` (via `_version`) |
| created_at | TIMESTAMP(tz) | No | server_default=now | `User.created_at` (via `_created_at`) |
| updated_at | TIMESTAMP(tz) | No | server_default=now | `User.updated_at` |
| created_by | UUID | No | — | `User.created_by` (via `_created_by`) |
| updated_by | UUID | Yes | — | `User.updated_by` |
| deleted_at | TIMESTAMP(tz) | Yes | — | `User.deleted_at` |
| deleted_by | UUID | Yes | — | `User.deleted_by` |
| deletion_reason | TEXT | Yes | — | `User.deletion_reason` |
| hard_delete_scheduled_at | TIMESTAMP(tz) | Yes | — | `User.hard_delete_scheduled_at` |

**Indexes:**
- `ix_iam_users_email` — unique on `email`
- `ix_iam_users_username` — unique on `username`, partial: `WHERE username IS NOT NULL`
- `ix_iam_users_status` — on `status`
- `ix_iam_users_system_role` — on `system_role`

**Mapping notes:**
- `UserPreferences` VO is flattened into 3 columns (timezone, locale, display_currency) rather than a JSON blob, enabling direct SQL queries on preferences
- `admin_permissions` frozenset serialized as JSON array of string values: `[p.value for p in user.admin_permissions]`
- `password_history` serialized as JSON array of hash strings
- `from_domain()`: extracts `user.password.hashed_value` for `hashed_password` column
- `to_domain()`: reconstructs `HashedPassword(hashed_value=row.hashed_password)` if not NULL

### 5.2 UserAuthProviderModel

**Table:** `iam_user_auth_providers`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | synthetic (not in domain VO) |
| user_id | UUID | No | FK → iam_users.id | parent User.id |
| provider_type | VARCHAR(20) | No | — | `AuthProvider.provider_type.value` |
| external_id | VARCHAR(255) | Yes | — | `AuthProvider.external_id` (None for PASSWORD) |
| linked_at | TIMESTAMP(tz) | No | — | `AuthProvider.linked_at` |

**Constraints:**
- UNIQUE(`user_id`, `provider_type`) — one link per provider per user
- UNIQUE(`provider_type`, `external_id`) — one user per external ID per provider (partial: WHERE external_id IS NOT NULL)
- FK `user_id` → `iam_users.id` ON DELETE CASCADE

**Mapping notes:**
- `AuthProvider` is a frozen value object with equality by `provider_type` only
- The `id` column is synthetic — the domain VO has no identity
- `from_domain()` generates a UUID for the `id` column
- Sync strategy on user save: delete-and-reinsert (or merge by provider_type). Since AuthProvider equality is by provider_type, we can match existing rows by (user_id, provider_type)

### 5.3 RefreshTokenModel

**Table:** `iam_refresh_tokens`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `RefreshToken.id` |
| user_id | UUID | No | FK → iam_users.id | `RefreshToken.user_id` |
| token_hash | VARCHAR(255) | No | UNIQUE | `RefreshToken.token_hash` |
| family_id | UUID | No | — | `RefreshToken.family_id` |
| portal_context | VARCHAR(20) | No | — | `RefreshToken.portal_context.value` |
| expires_at | TIMESTAMP(tz) | No | — | `RefreshToken.expires_at` |
| created_at | TIMESTAMP(tz) | No | server_default=now | `RefreshToken.created_at` |
| revoked_at | TIMESTAMP(tz) | Yes | — | `RefreshToken.revoked_at` |

**Indexes:**
- `ix_iam_refresh_tokens_user_id` — on `user_id`
- `ix_iam_refresh_tokens_token_hash` — unique on `token_hash`
- `ix_iam_refresh_tokens_family_id` — on `family_id`

**Mapping notes:**
- No `is_revoked` column — derived from `revoked_at IS NOT NULL` in domain entity
- `portal_context` stored as enum string value

### 5.4 PasswordResetTokenModel

**Table:** `iam_password_reset_tokens`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `PasswordResetToken.id` |
| user_id | UUID | No | FK → iam_users.id | `PasswordResetToken.user_id` |
| token_hash | VARCHAR(255) | No | UNIQUE | `PasswordResetToken.token_hash` |
| expires_at | TIMESTAMP(tz) | No | — | `PasswordResetToken.expires_at` |
| created_at | TIMESTAMP(tz) | No | server_default=now | `PasswordResetToken.created_at` |
| used_at | TIMESTAMP(tz) | Yes | — | `PasswordResetToken.used_at` |

**Indexes:**
- `ix_iam_password_reset_tokens_user_id` — on `user_id`
- `ix_iam_password_reset_tokens_token_hash` — unique on `token_hash`

**Mapping notes:**
- No `is_used` column — derived from `used_at IS NOT NULL` in domain entity

### 5.5 UserRetentionPreferenceModel

**Table:** `sk_user_retention_preferences`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `UserRetentionPreference.id` |
| user_id | UUID | No | FK → iam_users.id | `UserRetentionPreference.user_id` |
| entity_type | VARCHAR(50) | No | — | `UserRetentionPreference.entity_type.value` |
| retention_duration | INTEGER | No | — | `UserRetentionPreference.retention_period.duration` |
| retention_unit | VARCHAR(10) | No | — | `UserRetentionPreference.retention_period.unit.value` |
| created_at | TIMESTAMP(tz) | No | server_default=now | — |
| updated_at | TIMESTAMP(tz) | No | server_default=now | — |

**Constraints:**
- UNIQUE(`user_id`, `entity_type`) — one preference per entity type per user
- FK `user_id` → `iam_users.id` ON DELETE CASCADE

**Mapping notes:**
- `RetentionPeriod` VO decomposed into two columns (`retention_duration` + `retention_unit`) rather than a single `retention_days` integer, preserving the full VO semantics (days vs months vs years)

---

## 6. Repository Implementations

All repositories receive an `AsyncSession` via constructor injection. The session is provided by the Unit of Work.

### 6.1 SqlAlchemyUserRepository

Implements `UserRepository` protocol from `src/emerald/iam/application/ports/outbound/user_repository.py`.

```
SqlAlchemyUserRepository:
    __init__(session: AsyncSession)

    async add(user: User) -> None
        - Converts User to UserModel via from_domain()
        - Converts each AuthProvider to UserAuthProviderModel
        - Uses session.merge() for upsert semantics (add + update support)
        - Syncs auth provider rows: match by (user_id, provider_type),
          add new, update existing, remove missing

    async find_by_id(user_id: UUID) -> User | None
        - Query UserModel by PK
        - Eager-load auth provider rows (selectinload or joinedload)
        - Convert to domain via to_domain()

    async find_by_email(email: EmailAddress) -> User | None
        - Query by email string (case-insensitive via func.lower())
        - Eager-load auth providers

    async find_by_username(username: Username) -> User | None
        - Query by username string (case-insensitive via func.lower())
        - Eager-load auth providers

    async exists_by_email(email: EmailAddress) -> bool
        - SELECT EXISTS query, no entity loading
        - Case-insensitive comparison

    async exists_by_username(username: Username, include_recently_deleted: bool = True) -> bool
        - SELECT EXISTS query
        - Case-insensitive comparison
        - When include_recently_deleted=True: includes rows where deleted_at IS NOT NULL
        - When include_recently_deleted=False: only rows where deleted_at IS NULL

    async exists_by_role(role: SystemRole) -> bool
        - SELECT EXISTS query filtered by system_role column
```

**Design decisions:**
- `add()` uses `session.merge()` to support both insert and update. The protocol name is `add` but application services call it for both new and existing users (after mutations).
- Case-insensitive queries use `func.lower()` on both the column and the input value.
- `find_by_external_id()` is NOT implemented — it does not exist in the protocol. The `AuthenticationService` already handles this lookup through the user's `auth_providers` collection after finding the user.

### 6.2 SqlAlchemyRefreshTokenRepository

Implements `RefreshTokenRepository` protocol from `src/emerald/iam/application/ports/outbound/refresh_token_repository.py`.

```
SqlAlchemyRefreshTokenRepository:
    __init__(session: AsyncSession)

    async add(token: RefreshToken) -> None
        - Convert to RefreshTokenModel, session.add()

    async find_by_hash(token_hash: str) -> RefreshToken | None
        - Query by token_hash column
        - Convert to domain via to_domain()

    async find_active_families_by_user(user_id: UUID) -> list[UUID]
        - SELECT DISTINCT family_id WHERE user_id = ? AND revoked_at IS NULL AND expires_at > now()
        - Returns list of family UUIDs (not full token entities)

    async revoke_family(family_id: UUID) -> None
        - UPDATE SET revoked_at = now() WHERE family_id = ? AND revoked_at IS NULL
        - Bulk update, no entity loading

    async revoke_all_for_user(user_id: UUID) -> None
        - UPDATE SET revoked_at = now() WHERE user_id = ? AND revoked_at IS NULL
        - Bulk update, no entity loading

    async count_active_families(user_id: UUID) -> int
        - SELECT COUNT(DISTINCT family_id) WHERE user_id = ? AND revoked_at IS NULL AND expires_at > now()
```

### 6.3 SqlAlchemyPasswordResetTokenRepository

Implements `PasswordResetTokenRepository` protocol from `src/emerald/iam/application/ports/outbound/password_reset_token_repository.py`.

```
SqlAlchemyPasswordResetTokenRepository:
    __init__(session: AsyncSession)

    async add(token: PasswordResetToken) -> None
        - Convert to PasswordResetTokenModel, session.add()

    async find_by_hash(token_hash: str) -> PasswordResetToken | None
        - Query by token_hash column
        - Convert to domain via to_domain()

    async invalidate_existing_for_user(user_id: UUID) -> None
        - UPDATE SET used_at = now() WHERE user_id = ? AND used_at IS NULL
        - Bulk update, no entity loading
```

### 6.4 SqlAlchemyRetentionPolicyRepository

Implements `RetentionPolicyRepository` protocol from `src/emerald/shared_kernel/application/ports/outbound/retention_policy_repository.py`.

```
SqlAlchemyRetentionPolicyRepository:
    __init__(session: AsyncSession)

    async find_user_preference(
        entity_type: DeletableEntityType, user_id: UUID
    ) -> UserRetentionPreference | None
        - Query by (user_id, entity_type)
        - Convert to domain via to_domain()

    async save_user_preference(preference: UserRetentionPreference) -> None
        - Convert to UserRetentionPreferenceModel via from_domain()
        - Use session.merge() for upsert

    async delete_user_preference(
        entity_type: DeletableEntityType, user_id: UUID
    ) -> None
        - DELETE WHERE user_id = ? AND entity_type = ?
```

---

## 7. IAM Unit of Work

### 7.1 SqlAlchemyIamUnitOfWork

Extends `SqlAlchemyUnitOfWork` from spec-021. Implements `AbstractIamUnitOfWork` protocol.

```
SqlAlchemyIamUnitOfWork(SqlAlchemyUnitOfWork):
    __init__(session_factory: async_sessionmaker[AsyncSession])

    @property
    users -> SqlAlchemyUserRepository
        Lazily created on first access, using self.session

    @property
    refresh_tokens -> SqlAlchemyRefreshTokenRepository
        Lazily created on first access, using self.session

    @property
    password_reset_tokens -> SqlAlchemyPasswordResetTokenRepository
        Lazily created on first access, using self.session
```

**Rules:**
- Repository instances are cached per UoW usage (created once per `async with` block)
- All repositories share the same `AsyncSession` — ensuring atomicity
- Reset cached repositories on `__aenter__` (new session = new repos)
- Inherits `commit()`, `rollback()`, `__aenter__`, `__aexit__` from `SqlAlchemyUnitOfWork`

---

## 8. Alembic Migration

### 8.1 Migration File

```
alembic/versions/001_iam_and_shared_kernel_tables.py
```

### 8.2 Tables Created (in order)

1. `iam_users` — User aggregate (root table, no FKs)
2. `iam_user_auth_providers` — Auth provider links (FK → iam_users)
3. `iam_refresh_tokens` — Refresh tokens (FK → iam_users)
4. `iam_password_reset_tokens` — Password reset tokens (FK → iam_users)
5. `sk_user_retention_preferences` — Retention preferences (FK → iam_users)

### 8.3 Requirements
- Migration must be reversible (`downgrade` drops all 5 tables in reverse FK order)
- All foreign keys use `ON DELETE CASCADE`
- All indexes and unique constraints created in the `upgrade` function
- Timestamps use `sa.DateTime(timezone=True)` with `server_default=sa.func.now()` where applicable

---

## 9. File Structure

```
src/emerald/iam/
    adapters/
        outbound/
            persistence/
                __init__.py
                orm_models.py              # UserModel, UserAuthProviderModel,
                                           # RefreshTokenModel, PasswordResetTokenModel
                user_repository.py         # SqlAlchemyUserRepository
                refresh_token_repository.py
                password_reset_token_repository.py
                unit_of_work.py            # SqlAlchemyIamUnitOfWork
    __init__.py                            # re-export public types

src/emerald/shared_kernel/
    adapters/
        outbound/
            persistence/
                retention_policy_repository.py  # SqlAlchemyRetentionPolicyRepository
                orm_models.py                   # UserRetentionPreferenceModel

alembic/
    versions/
        001_iam_and_shared_kernel_tables.py
```

Each context's adapters live under `{context}/adapters/outbound/persistence/`, colocated with their bounded context.

---

## 10. Domain ↔ ORM Mapping Details

### 10.1 User Reconstruction (to_domain)

The `UserModel.to_domain()` must reconstruct the full `User` aggregate:

```
User(
    id=row.id,
    email=EmailAddress(row.email),
    username=Username(row.username) if row.username else None,
    password=HashedPassword(row.hashed_password) if row.hashed_password else None,
    password_history=row.password_history or [],
    auth_providers={provider_model.to_domain() for provider_model in row.auth_providers},
    status=UserStatus(row.status),
    email_verified=row.email_verified,
    preferences=UserPreferences(
        timezone=row.preferences_timezone,
        locale=row.preferences_locale,
        display_currency=Currency(row.preferences_display_currency),
    ),
    full_name=row.full_name,
    last_login_at=row.last_login_at,
    suspension_reason=row.suspension_reason,
    system_role=SystemRole(row.system_role),
    admin_permissions=frozenset(
        AdminPermission(p) for p in (row.admin_permissions or [])
    ),
    version=row.version,
    created_at=row.created_at,
    created_by=row.created_by,
)
```

After construction, mutable mixin fields are set directly:
- `user.updated_at = row.updated_at`
- `user.updated_by = row.updated_by`
- `user.deleted_at = row.deleted_at`
- `user.deleted_by = row.deleted_by`
- `user.deletion_reason = row.deletion_reason`
- `user.hard_delete_scheduled_at = row.hard_delete_scheduled_at`

### 10.2 AuthProvider Sync Strategy

On `UserRepository.add()`, auth provider rows are synced:

1. Query existing `UserAuthProviderModel` rows for the user
2. Build a map of `provider_type → existing_row`
3. For each domain `AuthProvider`:
   - If matching row exists: update `external_id` and `linked_at` if changed
   - If no matching row: insert new row
4. Delete rows whose `provider_type` is not in the domain set

This avoids delete-and-reinsert, which would churn synthetic IDs unnecessarily.

---

## 11. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| `add()` called for user with no auth_providers | User saved with empty providers list; no provider rows created |
| `add()` called for user with NULL password | `hashed_password` column set to NULL |
| `find_by_username()` with NULL username | Returns None (no match possible) |
| `exists_by_username()` with `include_recently_deleted=True` | Includes soft-deleted users in existence check |
| `revoke_all_for_user()` with no active tokens | No-op (UPDATE affects 0 rows, no error) |
| `invalidate_existing_for_user()` with no active tokens | No-op (UPDATE affects 0 rows, no error) |
| `delete_user_preference()` for non-existent preference | No-op (DELETE affects 0 rows, no error) |
| Concurrent `add()` for same user email | Database UNIQUE constraint raises; repository lets IntegrityError propagate |
| `admin_permissions` with empty frozenset | Stored as `[]` in JSON column |
| `password_history` with empty list | Stored as `[]` in JSON column |

---

## 12. Testing Strategy

### 12.1 Integration Tests (with real PostgreSQL)

Tests use a real PostgreSQL database (via testcontainers, Docker fixture, or test database).

**Test categories:**
- **ORM model round-trip**: `from_domain() → persist → reload → to_domain()` for each entity, verifying all fields survive the round-trip
- **Repository method tests**: One test per protocol method, covering happy path and edge cases
- **UoW atomicity**: Verify commit persists all repo changes; rollback discards all
- **Constraint enforcement**: Unique email, unique username (partial), unique (user_id, entity_type)
- **Auth provider sync**: Add, update, remove providers across multiple saves
- **Case-insensitive queries**: Email and username lookups are case-insensitive

### 12.2 Test File Structure

```
tests/integration/iam/
    conftest.py                    # DB engine, session factory, fixtures
    test_user_repository.py
    test_refresh_token_repository.py
    test_password_reset_token_repository.py
    test_iam_unit_of_work.py
tests/integration/shared_kernel/
    test_retention_policy_repository.py
```

---

## 13. Dependencies

### Internal Dependencies
- spec-021: `SqlAlchemyUnitOfWork`, `metadata`, column helpers, `DatabaseSettings`, Alembic scaffold
- specs 002-006: All domain entities, value objects, enums, and repository protocols

### External Dependencies
- `sqlalchemy[asyncio]` + `asyncpg` — async PostgreSQL driver (already in spec-021)
- `alembic` — migrations (already in spec-021)

---

## 14. Constraints

- All timestamps stored as UTC timezone-aware (`DateTime(timezone=True)`)
- No SQLAlchemy imports in domain or application layers
- ORM models must not leak into domain — conversion happens at the repository boundary
- Repository methods must match the Protocol signatures exactly (method names, parameter names, return types)
- Version column starts at 0 (matching `orm_registry.version_column()` from spec-021)

---

## 15. Acceptance Criteria

### ORM Models
- [ ] All 5 ORM model classes created with correct column types and constraints
- [ ] `UserModel.to_domain()` reconstructs full User aggregate including auth_providers, password, preferences
- [ ] `UserModel.from_domain()` handles optional fields (username=None → NULL, password=None → NULL)
- [ ] `admin_permissions` round-trips through JSON correctly (frozenset ↔ JSON array)
- [ ] `password_history` round-trips through JSON correctly (list[str] ↔ JSON array)
- [ ] `UserPreferences` decomposes into 3 columns and reconstructs correctly
- [ ] `RetentionPeriod` decomposes into duration + unit columns and reconstructs correctly
- [ ] Auth provider rows synced on user save (add/update/remove)
- [ ] All timestamps are timezone-aware UTC

### UserRepository
- [ ] `add()` inserts new user with auth providers
- [ ] `add()` updates existing user (upsert via merge)
- [ ] `find_by_id()` returns full User with providers eager-loaded
- [ ] `find_by_email()` performs case-insensitive lookup
- [ ] `find_by_username()` performs case-insensitive lookup
- [ ] `exists_by_email()` returns bool without loading entity
- [ ] `exists_by_username(include_recently_deleted=True)` includes soft-deleted users
- [ ] `exists_by_username(include_recently_deleted=False)` excludes soft-deleted users
- [ ] `exists_by_role()` returns bool without loading entity
- [ ] All find methods return `None` when not found (not exception)

### RefreshTokenRepository
- [ ] `add()` persists token
- [ ] `find_by_hash()` returns token or None
- [ ] `find_active_families_by_user()` returns distinct family UUIDs for active tokens only
- [ ] `revoke_family()` sets revoked_at on all tokens in family
- [ ] `revoke_all_for_user()` sets revoked_at on all user tokens
- [ ] `count_active_families()` returns count of distinct active families

### PasswordResetTokenRepository
- [ ] `add()` persists token
- [ ] `find_by_hash()` returns token or None
- [ ] `invalidate_existing_for_user()` sets used_at on all unused tokens for user

### RetentionPolicyRepository
- [ ] `find_user_preference()` returns preference by (entity_type, user_id) or None
- [ ] `save_user_preference()` creates or updates preference
- [ ] `delete_user_preference()` removes preference by (entity_type, user_id)
- [ ] UNIQUE constraint on (user_id, entity_type) enforced at DB level

### Unit of Work
- [ ] `SqlAlchemyIamUnitOfWork` exposes `users`, `refresh_tokens`, `password_reset_tokens` properties
- [ ] All repos share the same session within one UoW
- [ ] Commit persists changes from all repos atomically
- [ ] Rollback discards all changes
- [ ] Satisfies `AbstractIamUnitOfWork` protocol (structural subtyping)

### Migration
- [ ] Alembic migration creates all 5 tables with correct schema
- [ ] Foreign keys reference `iam_users.id` with ON DELETE CASCADE
- [ ] All indexes created (email, username partial, status, system_role, token_hash, family_id, user_id)
- [ ] Unique constraints enforced at database level
- [ ] Migration is reversible (downgrade drops tables in reverse FK order)

---

## 16. Glossary

- **ORM Model**: SQLAlchemy class mapped to a database table, separate from domain entities
- **Imperative Mapping**: SQLAlchemy pattern where domain classes are mapped directly to tables (not used here)
- **Declarative Base**: SQLAlchemy pattern where ORM classes inherit from a base with metadata
- **Upsert**: Insert or update — `session.merge()` provides this behavior
- **Partial Index**: Index with a WHERE clause, e.g., unique username only where not NULL
