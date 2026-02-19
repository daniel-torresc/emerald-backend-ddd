# Spec 032 — Async Repository Ports Migration

**Version:** 1.0
**Status:** Implemented
**Date:** 2026-02-18

---

## 1. Overview

Convert all synchronous repository Protocol methods, cross-context port methods, and infrastructure service port methods to `async def` across the entire codebase. This closes the sync/async mismatch left after spec-021 migrated the Unit of Work and application services to async, enabling proper non-blocking database I/O and CPU-offloading in infrastructure implementations.

---

## 2. Background & Context

### Problem Statement

Spec-021 migrated the Unit of Work to async (`async def commit()`, `async def rollback()`, `async with uow:`) and all application services now use `async def` methods. However, **all 22 repository and port Protocol definitions remain synchronous**, creating a fundamental mismatch:

1. **SQLAlchemy async sessions require `await session.execute()`** — sync protocol methods cannot call async database operations without ugly `run_sync()` wrappers.
2. **The event loop is blocked** during every database read/write, defeating the purpose of async.
3. **Cross-context ports** (`TransactionAccessPort`, `TransactionImportPort`) and **infrastructure service ports** (`TokenService`, `PasswordHasher`, `OidcProvider`) are also sync, preventing infrastructure adapters from using async I/O or `asyncio.to_thread()` for CPU-bound work.

### Business Goals

- Unblock all infrastructure persistence specs (022–025) which require async repository implementations.
- Enable non-blocking database operations for the entire application layer.
- Enable CPU-bound operations (Argon2 hashing, JWT signing) to be offloaded via `asyncio.to_thread()`.

### Success Metrics

- All 22 port Protocols define `async def` methods.
- All application services `await` every port/repository call.
- All test fakes implement `async def` methods.
- All ~2600 existing tests pass.
- All quality checks pass (`ruff check`, `ruff format`, `ty check`).

---

## 3. Scope

### In Scope

- Convert all repository Protocol methods to `async def`
- Convert all cross-context port Protocol methods to `async def`
- Convert all infrastructure service port Protocol methods to `async def` (including pure-computation ports like `TransactionNormalizer` and factory ports like `BankProviderAdapterRegistry` for consistency)
- Update all application services to `await` repository and port calls
- Update all test fakes to `async def` implementations
- Update all existing tests to `await` fake calls (tests already use `async def` test methods with `asyncio_mode = "auto"`)

### Out of Scope

- Domain layer changes (aggregates, value objects, domain events remain sync — correct by design)
- Domain services (e.g., `validate_password_strength`, `RetentionPolicyService`) — these are pure domain logic, no I/O
- Actual infrastructure implementations (those come in specs 022–025)
- UoW changes (already async from spec-021)

---

## 4. Requirements

### REQ-001: Protocol Definitions — All Methods Async

**Priority:** Must Have

All methods in all 22 Protocol port definitions must be converted from `def` to `async def`. Return types remain unchanged — the coroutine wrapper is implicit via `async def`.

**Acceptance Criteria:**
- [ ] Every method in every Protocol port file uses `async def`
- [ ] No sync `def` methods remain in any Protocol port file under `src/emerald/`
- [ ] `ty check` passes (verifies Protocol structural subtyping is maintained)

### REQ-002: Application Services — Await All Port Calls

**Priority:** Must Have

Every call to a repository or port method in application services must use `await`.

**Acceptance Criteria:**
- [ ] Every `self._uow.{repo}.{method}()` call is preceded by `await`
- [ ] Every `self._hasher.{method}()` call is preceded by `await`
- [ ] Every `self._token_service.{method}()` call is preceded by `await`
- [ ] Every `self._oidc_provider.{method}()` call is preceded by `await`
- [ ] Every cross-context port call is preceded by `await`
- [ ] `ty check` catches any unawaited coroutines

### REQ-003: Test Fakes — Async Implementation

**Priority:** Must Have

All test fake classes must implement `async def` methods matching the updated Protocol signatures.

**Acceptance Criteria:**
- [ ] All fake repository/port methods use `async def`
- [ ] Test helper methods on fakes (e.g., `set_claims_for_code`, `add_active_transaction`) may remain sync since they are test utilities, not Protocol methods
- [ ] `ty check` confirms fakes satisfy Protocol structural subtyping

### REQ-004: Test Updates — Await Fake Calls

**Priority:** Must Have

All test assertions that call fake methods directly (outside of service calls) must add `await`.

**Acceptance Criteria:**
- [ ] All direct fake repository/port calls in tests use `await`
- [ ] All ~2600 existing tests pass (`uv run pytest`)
- [ ] No `RuntimeWarning: coroutine was never awaited` warnings

### REQ-005: Domain Layer Untouched

**Priority:** Must Have

The domain layer (aggregates, value objects, domain events, domain services) must remain fully synchronous.

**Acceptance Criteria:**
- [ ] No `async def` in any file under `*/domain/models/`, `*/domain/events/`, `*/domain/services/` (except port definitions in `*/domain/ports/`)
- [ ] Domain port files (`password_hasher.py`, `transaction_normalizer.py`) are the only domain-layer files affected

---

## 5. Affected Ports — Complete Inventory

### 5.1 Shared Kernel Ports (3 ports, 7 methods)

| Port | File | Methods |
|------|------|---------|
| `RetentionPolicyRepository` | `shared_kernel/application/ports/outbound/retention_policy_repository.py` | `find_user_preference`, `save_user_preference`, `delete_user_preference` |
| `ScheduledDeletionPort` | `shared_kernel/application/ports/outbound/scheduled_deletion_port.py` | `find_due_for_hard_delete`, `find_due_for_warning` |
| `TrashQueryPort` | `shared_kernel/application/ports/outbound/trash_query_port.py` | `list_trash`, `get_cascade_summary` |

### 5.2 IAM Ports (6 ports, 22 methods)

| Port | File | Methods |
|------|------|---------|
| `UserRepository` | `iam/application/ports/outbound/user_repository.py` | `add`, `find_by_id`, `find_by_email`, `find_by_username`, `exists_by_email`, `exists_by_username`, `exists_by_role` |
| `RefreshTokenRepository` | `iam/application/ports/outbound/refresh_token_repository.py` | `add`, `find_by_hash`, `find_active_families_by_user`, `revoke_family`, `revoke_all_for_user`, `count_active_families` |
| `PasswordResetTokenRepository` | `iam/application/ports/outbound/password_reset_token_repository.py` | `add`, `find_by_hash`, `invalidate_existing_for_user` |
| `TokenService` | `iam/application/ports/outbound/token_service.py` | `sign_access_token`, `verify_access_token`, `generate_refresh_token`, `hash_token` |
| `OidcProvider` | `iam/application/ports/outbound/oidc_provider.py` | `generate_authorization_url`, `exchange_code_for_claims` |
| `PasswordHasher` | `iam/domain/ports/password_hasher.py` | `hash`, `verify` |

### 5.3 Core Finance Ports (2 ports, 15 methods)

| Port | File | Methods |
|------|------|---------|
| `AccountRepository` | `core_finance/application/ports/outbound/account_repository.py` | `save`, `find_by_id`, `find_by_owner`, `exists_by_name_for_user`, `find_accessible_by_user` |
| `TransactionRepository` | `core_finance/application/ports/outbound/transaction_repository.py` | `save`, `save_many`, `find_by_id`, `find_by_account`, `find_by_account_in_range`, `find_by_external_id`, `count_by_account`, `sum_amounts`, `find_children`, `hard_delete_children` |

### 5.4 Classification Ports (4 ports, 19 methods)

| Port | File | Methods |
|------|------|---------|
| `TaxonomyRepository` | `classification/application/ports/outbound/taxonomy_repository.py` | `save`, `find_by_id`, `find_by_owner`, `exists_by_name_for_owner`, `find_by_term_id` |
| `TransactionTermAssignmentRepository` | `classification/application/ports/outbound/assignment_repository.py` | `save`, `delete`, `delete_by_term`, `delete_by_taxonomy`, `delete_by_transaction`, `find_by_transaction`, `find_by_transaction_and_taxonomy`, `find_by_term`, `find_transaction_ids_by_term`, `find_uncategorized_transaction_ids` |
| `TransactionAccessPort` | `classification/application/ports/outbound/transaction_access_port.py` | `verify_transaction_active`, `verify_editor_permission` |
| `CategorizationEventHandler` | `classification/application/ports/outbound/categorization_event_handler.py` | `handle_term_deleted`, `handle_taxonomy_soft_deleted`, `handle_transaction_soft_deleted` |

### 5.5 Integrations Ports (7 ports, 20 methods)

| Port | File | Methods |
|------|------|---------|
| `BankConnectionRepository` | `integrations/application/ports/outbound/bank_connection_repository.py` | `save`, `find_by_id`, `find_by_user`, `find_by_account`, `find_by_account_and_provider`, `find_due_for_sync` |
| `SyncHistoryRepository` | `integrations/application/ports/outbound/sync_history_repository.py` | `save`, `find_by_id`, `find_by_connection`, `find_latest_by_connection`, `find_in_progress_by_connection` |
| `PendingTransactionRepository` | `integrations/application/ports/outbound/pending_transaction_repository.py` | `save`, `save_many`, `find_by_id`, `find_by_connection`, `find_needs_review`, `find_by_sync`, `delete_by_connection` |
| `BankProviderAdapter` | `integrations/application/ports/outbound/bank_provider_adapter.py` | `fetch_transactions`, `verify_credentials`, `get_account_info` |
| `BankProviderAdapterRegistry` | `integrations/application/ports/outbound/provider_registry.py` | `get_adapter`, `get_normalizer` |
| `TransactionImportPort` | `integrations/application/ports/outbound/transaction_import_port.py` | `import_transaction`, `find_by_external_id`, `find_by_date_and_amount` |
| `TransactionNormalizer` | `integrations/domain/ports/transaction_normalizer.py` | `normalize` |

**Total: 22 ports, 83 methods**

---

## 6. Affected Test Fakes — Complete Inventory

| Fake Class | File | Protocol Methods | Test Helpers (stay sync) |
|-----------|------|------------------|--------------------------|
| `FakeRetentionPolicyRepository` | `tests/unit/shared_kernel/fakes.py` | 3 | 0 |
| `FakeUserRepository` | `tests/unit/iam/fakes.py` | 7 | 0 |
| `FakePasswordHasher` | `tests/unit/iam/fakes.py` | 2 | 0 |
| `FakeTokenService` | `tests/unit/iam/fakes.py` | 4 | 0 |
| `FakeRefreshTokenRepository` | `tests/unit/iam/fakes.py` | 6 | 0 |
| `FakePasswordResetTokenRepository` | `tests/unit/iam/fakes.py` | 3 | 0 |
| `FakeOidcProvider` | `tests/unit/iam/fakes.py` | 2 | 2 (`set_claims_for_code`, `set_auth_url`) |
| `FakeAccountRepository` | `tests/unit/core_finance/fakes.py` | 5 | 0 |
| `FakeTransactionRepository` | `tests/unit/core_finance/fakes.py` | 10 | 0 |
| `FakeTaxonomyRepository` | `tests/unit/classification/fakes.py` | 5 | 0 |
| `FakeTransactionAccessPort` | `tests/unit/classification/fakes.py` | 2 | 2 (`add_active_transaction`, `grant_editor_permission`) |
| `FakeTransactionTermAssignmentRepository` | `tests/unit/classification/fakes.py` | 10 | 0 |
| `FakeBankConnectionRepository` | `tests/unit/integrations/fakes.py` | 6 | 0 |
| `FakeSyncHistoryRepository` | `tests/unit/integrations/fakes.py` | 5 | 0 |
| `FakePendingTransactionRepository` | `tests/unit/integrations/fakes.py` | 7 | 0 |
| `FakeBankProviderAdapter` | `tests/unit/integrations/fakes.py` | 3 | 2 (`set_transactions`, `set_auth_error/set_provider_error`) |
| `FakeTransactionNormalizer` | `tests/unit/integrations/fakes.py` | 1 | 0 |
| `FakeProviderRegistry` | `tests/unit/integrations/fakes.py` | 2 | 0 |
| `FakeTransactionImportPort` | `tests/unit/integrations/fakes.py` | 3 | 2 (`add_existing_external_id`, `add_match`) |

**Total: 19 fake classes, 86 protocol methods to convert, ~8 test helpers remain sync**

Note: Fake UoW classes (`FakeIamUnitOfWork`, `FakeCoreFinanceUnitOfWork`, `FakeClassificationUnitOfWork`, `FakeIntegrationsUnitOfWork`) already have async `commit()` and `rollback()` from spec-021 — no changes needed.

---

## 7. Migration Pattern

### 7.1 Protocol Definition

**Before:**
```python
class UserRepository(Protocol):
    def find_by_id(self, user_id: uuid.UUID) -> User | None: ...
    def add(self, user: User) -> None: ...
```

**After:**
```python
class UserRepository(Protocol):
    async def find_by_id(self, user_id: uuid.UUID) -> User | None: ...
    async def add(self, user: User) -> None: ...
```

### 7.2 Service Call Site

**Before:**
```python
async def login(self, cmd: LoginUser) -> LoginResult:
    async with self._uow:
        user = self._uow.users.find_by_email(EmailAddress(cmd.email))
        ...
```

**After:**
```python
async def login(self, cmd: LoginUser) -> LoginResult:
    async with self._uow:
        user = await self._uow.users.find_by_email(EmailAddress(cmd.email))
        ...
```

### 7.3 Test Fake

**Before:**
```python
class FakeUserRepository:
    def find_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._store.get(user_id)
```

**After:**
```python
class FakeUserRepository:
    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._store.get(user_id)
```

### 7.4 Test Direct Fake Call

**Before:**
```python
async def test_add_user(self):
    repo = FakeUserRepository()
    repo.add(user)
    assert repo.find_by_id(user.id) == user
```

**After:**
```python
async def test_add_user(self):
    repo = FakeUserRepository()
    await repo.add(user)
    assert await repo.find_by_id(user.id) == user
```

---

## 8. Design Decisions

### 8.1 CPU-Bound Ports Made Async

`PasswordHasher.hash()` and `PasswordHasher.verify()` are CPU-bound (Argon2id). Making the port `async` enables infrastructure to use `asyncio.to_thread()`:

```python
class Argon2PasswordHasher:
    async def hash(self, plaintext: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, plaintext)
```

`TokenService.sign_access_token()` and `verify_access_token()` (JWT signing/verification) follow the same pattern.

### 8.2 Pure-Computation Ports Made Async

`TransactionNormalizer.normalize()` (string → VO transformation) and `BankProviderAdapterRegistry.get_adapter()`/`get_normalizer()` (factory lookups) are made async for **consistency** — every port method is async with no exceptions, providing a simpler mental model. The async overhead on in-memory operations is negligible.

### 8.3 Test Helpers Remain Sync

Test utility methods on fakes (e.g., `FakeOidcProvider.set_claims_for_code()`, `FakeTransactionAccessPort.add_active_transaction()`) are not part of Protocol contracts and remain sync. They are test-only setup methods.

---

## 9. Estimation

| Component | Count | Effort |
|-----------|-------|--------|
| Protocol definitions to update | 22 ports, 83 methods | Low (mechanical `def` → `async def`) |
| Service call sites to add `await` | ~14 services, ~150 call sites | Medium (must be careful) |
| Test fakes to update | 19 fake classes, 86 methods | Low (mechanical `def` → `async def`) |
| Test assertions to update | Subset of ~2600 tests | Medium (only tests that call fakes directly) |

**Total estimated changes:** ~83 protocol methods + ~86 fake methods + ~150 service call sites + test `await` additions ≈ **~350 changes**.

---

## 10. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Missing an `await` in service code | Medium | `ty check` and `ruff` catch unawaited coroutines |
| Test fakes not matching Protocol | Low | `ty check` enforces Protocol structural subtyping |
| Large test count (~2600) | Low | Most tests call service methods (already async), not fakes directly |
| Breaking structural subtyping | Low | `ty check` is the safety net; run after each context migration |

---

## 11. Acceptance Criteria

1. All 22 repository/port Protocol definitions use `async def` for all methods
2. All application services `await` every port/repository call
3. All 19 test fake classes implement `async def` for Protocol methods
4. All existing tests pass (`uv run pytest`)
5. All quality checks pass (`ruff check`, `ruff format`, `ty check`)
6. No sync repository/port method remains anywhere in `src/emerald/` (except domain-layer non-port code)
7. Domain layer (aggregates, value objects, domain events, domain services) remains fully synchronous
8. No `RuntimeWarning: coroutine was never awaited` in test output

---

## 12. Dependencies

### Depends On
- **Spec-021** (Async UoW Foundation) — already implemented

### Blocks
- **Spec-022** (IAM Persistence Layer)
- **Spec-023** (Auth Infrastructure Adapters)
- **Spec-024** (Core Finance Persistence Layer)
- **Spec-025** (Classification & Integrations Persistence)

---

## 13. Constraints

- Python 3.13+ (native async/await, no compatibility shims)
- `typing.Protocol` structural subtyping (async methods in Protocol are matched by async methods in implementations)
- `pytest-asyncio` with `asyncio_mode = "auto"` (all test functions are auto-detected as async)
- `ty` type checker enforces Protocol compliance — primary safety net for this migration
