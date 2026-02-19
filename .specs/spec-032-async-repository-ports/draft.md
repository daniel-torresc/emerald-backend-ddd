# Spec 032 — Async Repository Ports Migration

**Status:** DRAFT
**Priority:** P0 (Blocks infrastructure implementation)
**Dependencies:** spec-021 (Async UoW Foundation)
**Blocked by:** None
**Blocks:** spec-022, spec-023, spec-024, spec-025 (all persistence layers)

---

## 1. Problem Statement

Spec-021 migrated the Unit of Work to async (`async def commit()`, `async def rollback()`, `async with uow:`), and all application services now use `async def` methods. However, **all repository protocol methods remain synchronous**.

This creates a fundamental mismatch: services call sync repository methods inside async contexts, which means:

1. **SQLAlchemy async sessions require `await session.execute()`** — sync protocol methods cannot call async database operations without ugly `run_sync()` wrappers.
2. **The event loop is blocked** during every database read/write, defeating the purpose of async.
3. **Cross-context ports** (`TransactionAccessPort`, `TransactionImportPort`) are also sync, creating the same problem for infrastructure adapters that cross bounded contexts.

The longer this remains unaddressed, the more expensive the migration becomes — every new repository method, fake implementation, and service call compounds the debt.

---

## 2. Scope

### In Scope

- Convert all repository Protocol methods to `async def`
- Convert all cross-context port Protocol methods to `async def`
- Convert all infrastructure service port Protocol methods to `async def` (TokenService, OidcProvider, PasswordHasher, BankProviderAdapter, BankProviderAdapterRegistry, TransactionNormalizer)
- Update all application services to `await` repository and port calls
- Update all test fakes to `async def` implementations
- Update all existing tests to `await` fake calls (tests already use `async def` test methods)

### Out of Scope

- Domain layer changes (aggregates, value objects, domain events remain sync — correct by design)
- Domain services (e.g., `validate_password_strength`, `RetentionPolicyService`) — these are pure domain logic, no I/O
- Actual infrastructure implementations (those come in spec-022 through spec-025)

---

## 3. Affected Ports — Complete Inventory

### 3.1 Shared Kernel Ports (3 ports)

| Port | File | Methods to Convert |
|------|------|--------------------|
| `RetentionPolicyRepository` | `shared_kernel/application/ports/outbound/retention_policy_repository.py` | `find_user_preference`, `save_user_preference`, `delete_user_preference` |
| `ScheduledDeletionPort` | `shared_kernel/application/ports/outbound/scheduled_deletion_port.py` | `find_due_for_hard_delete`, `find_due_for_warning` |
| `TrashQueryPort` | `shared_kernel/application/ports/outbound/trash_query_port.py` | `list_trash`, `get_cascade_summary` |

### 3.2 IAM Ports (6 ports)

| Port | File | Methods to Convert |
|------|------|--------------------|
| `UserRepository` | `iam/application/ports/outbound/user_repository.py` | `add`, `find_by_id`, `find_by_email`, `find_by_username`, `exists_by_email`, `exists_by_username`, `exists_by_role` |
| `RefreshTokenRepository` | `iam/application/ports/outbound/refresh_token_repository.py` | `add`, `find_by_hash`, `find_active_families_by_user`, `revoke_family`, `revoke_all_for_user`, `count_active_families` |
| `PasswordResetTokenRepository` | `iam/application/ports/outbound/password_reset_token_repository.py` | `add`, `find_by_hash`, `invalidate_existing_for_user` |
| `TokenService` | `iam/application/ports/outbound/token_service.py` | `sign_access_token`, `verify_access_token`, `generate_refresh_token`, `hash_token` |
| `OidcProvider` | `iam/application/ports/outbound/oidc_provider.py` | `generate_authorization_url`, `exchange_code_for_claims` |
| `PasswordHasher` | `iam/domain/ports/password_hasher.py` | `hash`, `verify` |

### 3.3 Core Finance Ports (2 ports)

| Port | File | Methods to Convert |
|------|------|--------------------|
| `AccountRepository` | `core_finance/application/ports/outbound/account_repository.py` | `save`, `find_by_id`, `find_by_owner`, `exists_by_name_for_user`, `find_accessible_by_user` |
| `TransactionRepository` | `core_finance/application/ports/outbound/transaction_repository.py` | `save`, `save_many`, `find_by_id`, `find_by_account`, `find_by_account_in_range`, `find_by_external_id`, `count_by_account`, `sum_amounts`, `find_children`, `hard_delete_children` |

### 3.4 Classification Ports (4 ports)

| Port | File | Methods to Convert |
|------|------|--------------------|
| `TaxonomyRepository` | `classification/application/ports/outbound/taxonomy_repository.py` | `save`, `find_by_id`, `find_by_owner`, `exists_by_name_for_owner`, `find_by_term_id` |
| `TransactionTermAssignmentRepository` | `classification/application/ports/outbound/assignment_repository.py` | `save`, `delete`, `delete_by_term`, `delete_by_taxonomy`, `delete_by_transaction`, `find_by_transaction`, `find_by_transaction_and_taxonomy`, `find_by_term`, `find_transaction_ids_by_term`, `find_uncategorized_transaction_ids` |
| `TransactionAccessPort` | `classification/application/ports/outbound/transaction_access_port.py` | `verify_transaction_active`, `verify_editor_permission` |
| `CategorizationEventHandler` | `classification/application/ports/outbound/categorization_event_handler.py` | `handle_term_deleted`, `handle_taxonomy_soft_deleted`, `handle_transaction_soft_deleted` |

### 3.5 Integrations Ports (7 ports)

| Port | File | Methods to Convert |
|------|------|--------------------|
| `BankConnectionRepository` | `integrations/application/ports/outbound/bank_connection_repository.py` | `save`, `find_by_id`, `find_by_user`, `find_by_account`, `find_by_account_and_provider`, `find_due_for_sync` |
| `SyncHistoryRepository` | `integrations/application/ports/outbound/sync_history_repository.py` | `save`, `find_by_id`, `find_by_connection`, `find_latest_by_connection`, `find_in_progress_by_connection` |
| `PendingTransactionRepository` | `integrations/application/ports/outbound/pending_transaction_repository.py` | `save`, `save_many`, `find_by_id`, `find_by_connection`, `find_needs_review`, `find_by_sync`, `delete_by_connection` |
| `BankProviderAdapter` | `integrations/application/ports/outbound/bank_provider_adapter.py` | `fetch_transactions`, `verify_credentials`, `get_account_info` |
| `BankProviderAdapterRegistry` | `integrations/application/ports/outbound/provider_registry.py` | `get_adapter`, `get_normalizer` |
| `TransactionImportPort` | `integrations/application/ports/outbound/transaction_import_port.py` | `import_transaction`, `find_by_external_id`, `find_by_date_and_amount` |
| `TransactionNormalizer` | `integrations/domain/ports/transaction_normalizer.py` | `normalize` |

---

## 4. Migration Pattern

### 4.1 Protocol Definition (Before)

```python
class UserRepository(Protocol):
    def find_by_id(self, user_id: uuid.UUID) -> User | None: ...
    def add(self, user: User) -> None: ...
```

### 4.2 Protocol Definition (After)

```python
class UserRepository(Protocol):
    async def find_by_id(self, user_id: uuid.UUID) -> User | None: ...
    async def add(self, user: User) -> None: ...
```

### 4.3 Service Call Site (Before)

```python
async def login(self, cmd: LoginUser) -> LoginResult:
    async with self._uow:
        user = self._uow.users.find_by_email(EmailAddress(cmd.email))
        ...
```

### 4.4 Service Call Site (After)

```python
async def login(self, cmd: LoginUser) -> LoginResult:
    async with self._uow:
        user = await self._uow.users.find_by_email(EmailAddress(cmd.email))
        ...
```

### 4.5 Test Fake (Before)

```python
class FakeUserRepository:
    def find_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._store.get(user_id)
```

### 4.6 Test Fake (After)

```python
class FakeUserRepository:
    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._store.get(user_id)
```

---

## 5. Design Decision: PasswordHasher and TokenService

`PasswordHasher.hash()` and `PasswordHasher.verify()` are CPU-bound operations (Argon2id). In production, these should ideally run in a thread pool to avoid blocking the event loop. Making the port `async` enables infrastructure to use `asyncio.to_thread()` for CPU-bound work:

```python
class Argon2PasswordHasher:
    async def hash(self, plaintext: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, plaintext)
```

`TokenService.sign_access_token()` and `verify_access_token()` are also CPU-bound (JWT signing/verification). Same argument applies.

For test fakes, the async overhead is negligible — the in-memory operations complete instantly.

---

## 6. Estimation

| Component | Count | Effort |
|-----------|-------|--------|
| Protocol definitions to update | 22 ports, ~75 methods | Low (mechanical) |
| Service call sites to add `await` | ~14 services, ~150 call sites | Medium (must be careful) |
| Test fakes to update | ~20 fake classes, ~75 methods | Low (mechanical) |
| Test assertions to update | ~2600 tests (subset touch repos) | Medium (find-and-replace + manual review) |

**Total estimated method conversions:** ~75 protocol methods + ~75 fake methods + ~150 service call sites = ~300 changes.

---

## 7. Acceptance Criteria

1. All repository Protocol methods are `async def`
2. All cross-context port Protocol methods are `async def`
3. All infrastructure service port Protocol methods are `async def`
4. All application service methods `await` every port/repository call
5. All test fakes implement `async def` methods
6. All existing tests pass (`uv run pytest`)
7. All quality checks pass (`ruff check`, `ruff format`, `ty check`)
8. No sync repository/port method remains anywhere in `src/emerald/`
9. Domain layer (aggregates, value objects, domain events, domain services) remains fully synchronous

---

## 8. Risk Assessment

- **Risk:** Mechanical nature of changes means high chance of missing an `await`. Mitigation: `ty check` and `ruff` will catch unawaited coroutines.
- **Risk:** Test count is large (~2600). Mitigation: Most tests don't directly call repository methods — they call service methods which already use `async/await`.
- **Risk:** Breaking structural subtyping if fakes don't match protocol. Mitigation: `ty check` enforces Protocol compliance.
