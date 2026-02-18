# Spec 022: IAM Persistence Layer

**Status:** Draft
**Bounded Context:** IAM (Infrastructure)
**Dependencies:** 021 (Configuration & Database Foundation), 002 (User Registration & Identity), 003 (Authentication & Sessions), 004 (System Roles & Admin Permissions), 005 (Federated Authentication), 006 (Data Lifecycle Management)
**Blocks:** 024, 026

---

## 1. Overview

This spec implements the first real repository and Unit of Work — the IAM context's persistence layer. It maps domain entities (User, RefreshToken, PasswordResetToken) to SQLAlchemy ORM models, creates the Alembic migration, and provides the shared kernel's `RetentionPolicyRepository` implementation.

**Key Principle:** ORM models are separate from domain entities. Mapping is explicit via `to_domain()` / `from_domain()` converters. The domain layer remains free of SQLAlchemy imports.

## 2. Scope

### In Scope

- ORM models: `UserModel`, `UserAuthProviderModel`, `RefreshTokenModel`, `PasswordResetTokenModel`, `UserRetentionPreferenceModel`
- `to_domain()` / `from_domain()` mapping between ORM ↔ domain entities
- Repository implementations: `SqlAlchemyUserRepository`, `SqlAlchemyRefreshTokenRepository`, `SqlAlchemyPasswordResetTokenRepository`
- `SqlAlchemyRetentionPolicyRepository` (shared kernel port)
- `SqlAlchemyIamUnitOfWork` (exposes `users`, `refresh_tokens`, `password_reset_tokens`)
- Alembic migration for all IAM + shared kernel tables

### Out of Scope

- Auth adapters (password hasher, JWT, OIDC) — spec 023
- Core Finance persistence — spec 024
- FastAPI integration — spec 026

## 3. ORM Models

### 3.1 UserModel

**Table:** `iam_users`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `User.id` |
| email | VARCHAR(255) | No | UNIQUE, INDEX | `User.email.address` |
| username | VARCHAR(50) | Yes | UNIQUE, INDEX | `User.username.value` (if set) |
| hashed_password | VARCHAR(255) | Yes | — | `User._hashed_password` |
| full_name | VARCHAR(200) | No | — | `User.full_name.value` |
| status | VARCHAR(30) | No | — | `User.status.value` (enum name) |
| system_role | VARCHAR(20) | No | DEFAULT 'USER' | `User.system_role.value` |
| admin_permissions | JSON | No | DEFAULT '[]' | `User.admin_permissions` (frozenset → JSON list) |
| email_verified_at | TIMESTAMP(tz) | Yes | — | `User.email_verified_at` |
| version | INTEGER | No | DEFAULT 1 | `User.version` |
| created_at | TIMESTAMP(tz) | No | DEFAULT now | `User.created_at` |
| updated_at | TIMESTAMP(tz) | No | DEFAULT now | `User.updated_at` |
| deleted_at | TIMESTAMP(tz) | Yes | — | `User.deleted_at` |
| deleted_by | UUID | Yes | — | `User.deleted_by` |

**Indexes:**
- `ix_iam_users_email` — unique on `email`
- `ix_iam_users_username` — unique on `username` (partial: WHERE username IS NOT NULL)
- `ix_iam_users_status` — on `status`
- `ix_iam_users_system_role` — on `system_role`

### 3.2 UserAuthProviderModel

**Table:** `iam_user_auth_providers`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | (synthetic) |
| user_id | UUID | No | FK → iam_users.id | Parent user |
| provider_type | VARCHAR(20) | No | — | `AuthProvider.provider_type.value` |
| external_id | VARCHAR(255) | No | — | `AuthProvider.external_id` |
| linked_at | TIMESTAMP(tz) | No | — | `AuthProvider.linked_at` |

**Constraints:**
- UNIQUE(`user_id`, `provider_type`) — one link per provider per user
- UNIQUE(`provider_type`, `external_id`) — one user per external ID per provider
- FK `user_id` → `iam_users.id` ON DELETE CASCADE

### 3.3 RefreshTokenModel

**Table:** `iam_refresh_tokens`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `RefreshToken.id` |
| user_id | UUID | No | FK → iam_users.id, INDEX | `RefreshToken.user_id` |
| token_hash | VARCHAR(255) | No | UNIQUE | `RefreshToken.token_hash` |
| family_id | UUID | No | INDEX | `RefreshToken.family_id` |
| is_revoked | BOOLEAN | No | DEFAULT false | `RefreshToken.is_revoked` |
| revoked_at | TIMESTAMP(tz) | Yes | — | `RefreshToken.revoked_at` |
| expires_at | TIMESTAMP(tz) | No | — | `RefreshToken.expires_at` |
| created_at | TIMESTAMP(tz) | No | DEFAULT now | `RefreshToken.created_at` |

**Indexes:**
- `ix_iam_refresh_tokens_user_id` — on `user_id`
- `ix_iam_refresh_tokens_token_hash` — unique on `token_hash`
- `ix_iam_refresh_tokens_family_id` — on `family_id`

### 3.4 PasswordResetTokenModel

**Table:** `iam_password_reset_tokens`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `PasswordResetToken.id` |
| user_id | UUID | No | FK → iam_users.id, INDEX | `PasswordResetToken.user_id` |
| token_hash | VARCHAR(255) | No | UNIQUE | `PasswordResetToken.token_hash` |
| is_used | BOOLEAN | No | DEFAULT false | `PasswordResetToken.is_used` |
| used_at | TIMESTAMP(tz) | Yes | — | `PasswordResetToken.used_at` |
| expires_at | TIMESTAMP(tz) | No | — | `PasswordResetToken.expires_at` |
| created_at | TIMESTAMP(tz) | No | DEFAULT now | `PasswordResetToken.created_at` |

### 3.5 UserRetentionPreferenceModel

**Table:** `sk_user_retention_preferences`

| Column | Type | Nullable | Constraints | Maps To |
|--------|------|----------|-------------|---------|
| id | UUID | No | PK | `UserRetentionPreference.id` |
| user_id | UUID | No | FK → iam_users.id, UNIQUE | `UserRetentionPreference.user_id` |
| entity_type | VARCHAR(50) | No | — | `UserRetentionPreference.entity_type.value` |
| retention_days | INTEGER | No | — | `UserRetentionPreference.retention_period` |
| created_at | TIMESTAMP(tz) | No | DEFAULT now | Timestamp |
| updated_at | TIMESTAMP(tz) | No | DEFAULT now | Timestamp |

**Constraints:**
- UNIQUE(`user_id`, `entity_type`) — one preference per entity type per user

## 4. Domain ↔ ORM Mapping

### 4.1 Mapping Strategy

Each ORM model has two static/class methods:

```
@staticmethod
def from_domain(entity: DomainEntity) -> OrmModel:
    """Convert domain entity to ORM model for persistence."""

def to_domain(self) -> DomainEntity:
    """Reconstruct domain entity from ORM model."""
```

### 4.2 Key Mapping Challenges

**User.auth_providers (list[AuthProvider] → association rows):**
- `User.auth_providers` is a list of `AuthProvider` value objects
- Mapped to `UserAuthProviderModel` rows via relationship
- On save: sync provider rows (add new, keep existing, remove missing)

**User.admin_permissions (frozenset[AdminPermission] → JSON):**
- Stored as JSON array of permission name strings
- `from_domain`: `[p.value for p in user.admin_permissions]`
- `to_domain`: `frozenset(AdminPermission(p) for p in json_list)`

**User._hashed_password (private attribute):**
- Domain entity has private `_hashed_password` attribute
- ORM model stores it in `hashed_password` column
- Mapping must use `object.__setattr__` or reconstruction kwargs to set private field

**Email → str decomposition:**
- `User.email` is an `Email` value object
- ORM stores raw string, reconstructs `Email(address=row.email)` on `to_domain()`

## 5. Repository Implementations

### 5.1 SqlAlchemyUserRepository

Implements the `UserRepository` protocol from spec 002:

```
SqlAlchemyUserRepository:
    __init__(session: AsyncSession)

    async save(user: User) -> None
        Merges UserModel + syncs auth provider rows

    async find_by_id(user_id: UUID) -> User | None
        Eager-loads auth providers

    async find_by_email(email: Email) -> User | None
        Query by email string, eager-load providers

    async find_by_username(username: Username) -> User | None
        Query by username string

    async find_by_external_id(provider_type: AuthProviderType, external_id: str) -> User | None
        Join through auth_providers table

    async exists_by_email(email: Email) -> bool
        Efficient EXISTS query

    async exists_by_username(username: Username) -> bool
        Efficient EXISTS query

    async exists_by_role(role: SystemRole) -> bool
        Efficient EXISTS query
```

### 5.2 SqlAlchemyRefreshTokenRepository

Implements the `RefreshTokenRepository` protocol from spec 003:

```
SqlAlchemyRefreshTokenRepository:
    __init__(session: AsyncSession)

    async save(token: RefreshToken) -> None
    async find_by_token_hash(token_hash: str) -> RefreshToken | None
    async find_active_by_user(user_id: UUID) -> list[RefreshToken]
    async revoke_all_by_user(user_id: UUID) -> None
    async revoke_family(family_id: UUID) -> None
    async delete_expired() -> int
```

### 5.3 SqlAlchemyPasswordResetTokenRepository

Implements the `PasswordResetTokenRepository` protocol from spec 003:

```
SqlAlchemyPasswordResetTokenRepository:
    __init__(session: AsyncSession)

    async save(token: PasswordResetToken) -> None
    async find_by_token_hash(token_hash: str) -> PasswordResetToken | None
    async find_active_by_user(user_id: UUID) -> list[PasswordResetToken]
    async invalidate_all_by_user(user_id: UUID) -> None
```

### 5.4 SqlAlchemyRetentionPolicyRepository

Implements the `RetentionPolicyRepository` protocol from spec 006:

```
SqlAlchemyRetentionPolicyRepository:
    __init__(session: AsyncSession)

    async save(preference: UserRetentionPreference) -> None
    async find_by_user(user_id: UUID) -> list[UserRetentionPreference]
    async find_by_user_and_type(
        user_id: UUID, entity_type: DeletableEntityType
    ) -> UserRetentionPreference | None
```

## 6. IAM Unit of Work

### 6.1 SqlAlchemyIamUnitOfWork

Extends `SqlAlchemyUnitOfWork` from spec 021:

```
SqlAlchemyIamUnitOfWork(SqlAlchemyUnitOfWork):
    // Repositories created lazily per session
    @property
    users -> SqlAlchemyUserRepository

    @property
    refresh_tokens -> SqlAlchemyRefreshTokenRepository

    @property
    password_reset_tokens -> SqlAlchemyPasswordResetTokenRepository
```

**Rules:**
- Repositories are created when first accessed (lazy)
- All repositories within one UoW instance share the same session
- Implements `AbstractIamUnitOfWork` protocol from domain layer

## 7. Alembic Migration

### 7.1 Tables Created

This migration creates the following tables:

1. `iam_users` — User aggregate
2. `iam_user_auth_providers` — Auth provider links (FK → iam_users)
3. `iam_refresh_tokens` — Refresh tokens (FK → iam_users)
4. `iam_password_reset_tokens` — Password reset tokens (FK → iam_users)
5. `sk_user_retention_preferences` — Retention preferences (FK → iam_users)

### 7.2 Migration Order

- IAM tables first (users is the root)
- Provider, token, and preference tables after (they FK to users)

## 8. File Structure

```
src/emerald/infrastructure/
    persistence/
        iam/
            __init__.py
            models.py          # UserModel, UserAuthProviderModel, RefreshTokenModel, etc.
            user_repository.py
            refresh_token_repository.py
            password_reset_token_repository.py
            unit_of_work.py    # SqlAlchemyIamUnitOfWork
        shared_kernel/
            __init__.py
            retention_policy_repository.py
alembic/
    versions/
        001_iam_and_shared_kernel_tables.py
```

## 9. Acceptance Criteria

### ORM Models

- [ ] All ORM models map correctly to/from domain entities
- [ ] `UserModel.to_domain()` reconstructs full User aggregate including auth_providers
- [ ] `UserModel.from_domain()` handles optional username (None → NULL)
- [ ] `admin_permissions` round-trips through JSON correctly (frozenset ↔ JSON array)
- [ ] Auth provider rows are synced on user save (add/remove as needed)
- [ ] Timestamps are timezone-aware UTC

### User Repository

- [ ] `save()` creates new user with auth providers
- [ ] `save()` updates existing user (upsert semantics via merge)
- [ ] `find_by_id()` returns full User with providers eager-loaded
- [ ] `find_by_email()` performs case-insensitive lookup
- [ ] `find_by_username()` performs case-insensitive lookup
- [ ] `find_by_external_id()` joins through auth_providers table
- [ ] `exists_by_email()` returns bool without loading full entity
- [ ] `exists_by_username()` returns bool without loading full entity
- [ ] `exists_by_role()` returns bool without loading full entity
- [ ] Returns `None` when entity not found (not exception)

### Token Repositories

- [ ] `RefreshTokenRepository.save()` persists token
- [ ] `find_by_token_hash()` returns token or None
- [ ] `revoke_all_by_user()` revokes all user tokens in single query
- [ ] `revoke_family()` revokes all tokens in family
- [ ] `delete_expired()` removes expired tokens and returns count
- [ ] `PasswordResetTokenRepository.invalidate_all_by_user()` marks all as used

### Retention Repository

- [ ] `save()` creates or updates retention preference
- [ ] `find_by_user()` returns all preferences for user
- [ ] `find_by_user_and_type()` returns specific preference or None
- [ ] Unique constraint on (user_id, entity_type) prevents duplicates

### Unit of Work

- [ ] `SqlAlchemyIamUnitOfWork` creates all repos sharing same session
- [ ] Commit persists changes from all repos atomically
- [ ] Rollback discards changes from all repos
- [ ] Implements `AbstractIamUnitOfWork` protocol

### Migration

- [ ] Alembic migration creates all 5 tables
- [ ] Foreign keys reference correct parent tables
- [ ] Indexes created for query performance
- [ ] Unique constraints enforced at database level
- [ ] Migration is reversible (downgrade drops tables)
