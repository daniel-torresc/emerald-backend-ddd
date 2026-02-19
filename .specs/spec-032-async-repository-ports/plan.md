# Spec 032 — Async Repository Ports Migration — Implementation Plan

**Spec:** `.specs/spec-032-async-repository-ports/spec.md`
**Version:** 1.0
**Date:** 2026-02-18

---

## 1. Overview

Mechanical migration of all 22 Protocol port definitions from `def` to `async def`, propagating `await` through all application services, test fakes, and test files. The migration is organized **context-by-context** with a strict protocol→fake→service→test order within each context, running quality checks after each context to catch issues early.

### Key Finding: Sync Helpers Must Become Async

Several services have **private sync helper methods** that call repository methods. These must become `async def` and their callers must `await` them:

| Service | Helper | Calls |
|---------|--------|-------|
| `AuthenticationService` | `_issue_tokens()` | `uow.refresh_tokens.*`, `token_service.*` |
| `AccountManagementService` | `_load_account()` | `uow.accounts.find_by_id()` |
| `AccountSharingService` | `_load_account()` | `uow.accounts.find_by_id()` |
| `TransactionManagementService` | `_load_account()`, `_load_transaction()` | `uow.accounts.find_by_id()`, `uow.transactions.find_by_id()` |
| `BulkTransactionService` | `_load_account()` | `uow.accounts.find_by_id()` |
| `CardManagementService` | `_load_account()` | `uow.accounts.find_by_id()` |
| `TaxonomyManagementService` | `_load_taxonomy()` | `uow.taxonomies.find_by_id()` |
| `BankConnectionService` | `_load_connection()` | `uow.bank_connections.find_by_id()` |
| `BankSyncService` | `_load_connection()` | `uow.bank_connections.find_by_id()` |

### Key Finding: DeduplicationService Must Become Async

`DeduplicationService.check()` is currently fully sync but calls `TransactionImportPort.find_by_external_id()` and `find_by_date_and_amount()`. Since the port goes async, `check()` must become `async def` and `BankSyncService` must `await self._dedup.check(...)`.

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Layer | What Changes | What Stays Sync |
|-------|-------------|-----------------|
| **Domain** | Port definitions only (`password_hasher.py`, `transaction_normalizer.py`) | Aggregates, VOs, events, domain services |
| **Application** | All port Protocol definitions, all services, all service helpers | Commands, DTOs |
| **Test** | All fake Protocol methods, all tests with direct fake calls | Test helpers on fakes, domain-layer tests |

### 2.2 Change Pattern Per File Type

**Protocol files:** `def method(self, ...) -> T: ...` → `async def method(self, ...) -> T: ...`

**Service files:** `result = self._uow.repo.method(...)` → `result = await self._uow.repo.method(...)`

**Service helpers:** `def _load_x(self, ...) -> T:` → `async def _load_x(self, ...) -> T:` + callers add `await`

**Fake files:** `def method(self, ...) -> T:` → `async def method(self, ...) -> T:` (body unchanged)

**Test files:** `repo.method(...)` → `await repo.method(...)` (only direct fake calls, not test helpers)

---

## 3. Technical Decisions

### 3.1 Context-by-Context Ordering
**Decision:** Migrate one bounded context at a time, running `uv run pytest` + `ty check` after each.
**Rationale:** Isolates failures. If a context breaks, the blast radius is contained.

### 3.2 Protocol-First Within Each Context
**Decision:** Update Protocol → Fake → Service → Tests in that order.
**Rationale:** `ty check` will immediately flag mismatches between Protocol and fake/service.

### 3.3 DeduplicationService Becomes Async
**Decision:** Convert `DeduplicationService.check()` to `async def`.
**Rationale:** It calls `TransactionImportPort` methods which are going async. Cannot remain sync.

### 3.4 `__init__.py` Re-exports
**Decision:** Update any `__all__` lists only if new public types are added (none expected).
**Rationale:** Converting `def` to `async def` doesn't change the exported type names.

---

## 4. Implementation Tasks

### Phase 1: Shared Kernel (3 ports, 1 fake file, 1 test file)

#### TASK-001: Convert Shared Kernel Protocol Ports to Async
**Layer:** Application
**Depends On:** None

**Description:**
Add `async` keyword to all method definitions in 3 Protocol port files.

**Files to Modify:**
- `src/emerald/shared_kernel/application/ports/outbound/retention_policy_repository.py` — 3 methods
- `src/emerald/shared_kernel/application/ports/outbound/scheduled_deletion_port.py` — 2 methods
- `src/emerald/shared_kernel/application/ports/outbound/trash_query_port.py` — 2 methods

**Acceptance Criteria:**
- [ ] All 7 methods use `async def`
- [ ] No other changes to these files

---

#### TASK-002: Convert Shared Kernel Test Fakes to Async
**Layer:** Test
**Depends On:** TASK-001

**Description:**
Add `async` keyword to all Protocol methods in `FakeRetentionPolicyRepository`.

**Files to Modify:**
- `tests/unit/shared_kernel/fakes.py` — 3 methods on `FakeRetentionPolicyRepository`

**Acceptance Criteria:**
- [ ] All 3 Protocol methods use `async def`
- [ ] Method bodies unchanged (just add `async`)

---

#### TASK-003: Update Shared Kernel Tests
**Layer:** Test
**Depends On:** TASK-002

**Description:**
Add `await` to direct fake repository calls in `test_retention_policy_service.py`. Note: `RetentionPolicyService` is a **domain service** (pure sync logic). The tests that call `repo.save_user_preference()` and `repo.find_user_preference()` directly must `await` these since the fake is now async.

**Files to Modify:**
- `tests/unit/shared_kernel/domain/services/test_retention_policy_service.py` — ~4 direct fake calls

**Acceptance Criteria:**
- [ ] All direct `repo.save_user_preference()` and `repo.find_user_preference()` calls use `await`
- [ ] `uv run pytest tests/unit/shared_kernel/` passes
- [ ] `uv run ty check` passes

---

### Phase 2: IAM Context (6 ports, 6 fake classes, 13 test files)

#### TASK-004: Convert IAM Protocol Ports to Async
**Layer:** Application + Domain
**Depends On:** None

**Description:**
Add `async` keyword to all method definitions in 6 Protocol port files.

**Files to Modify:**
- `src/emerald/iam/application/ports/outbound/user_repository.py` — 7 methods
- `src/emerald/iam/application/ports/outbound/refresh_token_repository.py` — 6 methods
- `src/emerald/iam/application/ports/outbound/password_reset_token_repository.py` — 3 methods
- `src/emerald/iam/application/ports/outbound/token_service.py` — 4 methods
- `src/emerald/iam/application/ports/outbound/oidc_provider.py` — 2 methods
- `src/emerald/iam/domain/ports/password_hasher.py` — 2 methods

**Acceptance Criteria:**
- [ ] All 24 methods (including PasswordHasher's 2 domain-layer methods) use `async def`

---

#### TASK-005: Convert IAM Test Fakes to Async
**Layer:** Test
**Depends On:** TASK-004

**Description:**
Add `async` keyword to all Protocol methods in 6 fake classes. Test helpers (`set_claims_for_code`, `set_auth_url`) stay sync.

**Files to Modify:**
- `tests/unit/iam/fakes.py` — 24 Protocol methods across 6 fake classes

**Acceptance Criteria:**
- [ ] All 24 Protocol methods use `async def`
- [ ] `set_claims_for_code` and `set_auth_url` remain sync

---

#### TASK-006: Convert IAM Application Services to Async
**Layer:** Application
**Depends On:** TASK-004

**Description:**
Add `await` to all repository/port calls in 4 IAM services. Critical: `AuthenticationService._issue_tokens()` must become `async def` and all its callers must `await` it.

**Files to Modify:**
- `src/emerald/iam/application/services/user_registration.py` — ~4 `await` additions
- `src/emerald/iam/application/services/authentication.py` — ~30 `await` additions + `_issue_tokens` → `async def`
- `src/emerald/iam/application/services/role_management.py` — ~8 `await` additions
- `src/emerald/iam/application/services/superadmin_provisioning.py` — ~5 `await` additions

**Acceptance Criteria:**
- [ ] Every repo/port call preceded by `await`
- [ ] `_issue_tokens` is `async def` and all callers `await` it
- [ ] No unawaited coroutines

---

#### TASK-007: Update IAM Tests
**Layer:** Test
**Depends On:** TASK-005, TASK-006

**Description:**
Add `await` to all direct fake calls in 13 IAM test files. Primary patterns: `uow.users.add(user)` → `await uow.users.add(user)`, `token_service.hash_token(...)` → `await token_service.hash_token(...)`.

**Files to Modify:**
- `tests/unit/iam/application/services/test_auth_login.py`
- `tests/unit/iam/application/services/test_auth_logout.py`
- `tests/unit/iam/application/services/test_auth_password_reset_request.py`
- `tests/unit/iam/application/services/test_auth_password_reset_submit.py`
- `tests/unit/iam/application/services/test_auth_refresh.py`
- `tests/unit/iam/application/services/test_auth_verify_token.py`
- `tests/unit/iam/application/services/test_authentication_superadmin_ttl.py`
- `tests/unit/iam/application/services/test_onboarding_username.py`
- `tests/unit/iam/application/services/test_provider_management.py`
- `tests/unit/iam/application/services/test_role_management.py`
- `tests/unit/iam/application/services/test_social_login.py`
- `tests/unit/iam/application/services/test_superadmin_provisioning.py`
- `tests/unit/iam/application/services/test_user_registration.py`

**Acceptance Criteria:**
- [ ] All direct fake calls use `await`
- [ ] `uv run pytest tests/unit/iam/` passes
- [ ] `uv run ty check` passes

---

### Phase 3: Core Finance Context (2 ports, 2 fake classes, 14 test files)

#### TASK-008: Convert Core Finance Protocol Ports to Async
**Layer:** Application
**Depends On:** None

**Description:**
Add `async` keyword to all method definitions in 2 Protocol port files.

**Files to Modify:**
- `src/emerald/core_finance/application/ports/outbound/account_repository.py` — 5 methods
- `src/emerald/core_finance/application/ports/outbound/transaction_repository.py` — 10 methods

**Acceptance Criteria:**
- [ ] All 15 methods use `async def`

---

#### TASK-009: Convert Core Finance Test Fakes to Async
**Layer:** Test
**Depends On:** TASK-008

**Description:**
Add `async` keyword to all Protocol methods in 2 fake classes.

**Files to Modify:**
- `tests/unit/core_finance/fakes.py` — 15 Protocol methods across `FakeAccountRepository` (5) and `FakeTransactionRepository` (10)

**Acceptance Criteria:**
- [ ] All 15 Protocol methods use `async def`

---

#### TASK-010: Convert Core Finance Application Services to Async
**Layer:** Application
**Depends On:** TASK-008

**Description:**
Add `await` to all repository calls in 5 Core Finance services. Critical: all `_load_account()` and `_load_transaction()` helpers must become `async def` and callers must `await` them.

**Files to Modify:**
- `src/emerald/core_finance/application/services/account_management.py` — `_load_account` → `async def` + ~10 `await` additions
- `src/emerald/core_finance/application/services/account_sharing.py` — `_load_account` → `async def` + ~5 `await` additions
- `src/emerald/core_finance/application/services/transaction_management.py` — `_load_account` + `_load_transaction` → `async def` + ~25 `await` additions
- `src/emerald/core_finance/application/services/bulk_transaction.py` — `_load_account` → `async def` + ~15 `await` additions
- `src/emerald/core_finance/application/services/card_management.py` — `_load_account` → `async def` + ~15 `await` additions

**Acceptance Criteria:**
- [ ] All `_load_account()` and `_load_transaction()` helpers are `async def`
- [ ] Every repo call preceded by `await`
- [ ] No unawaited coroutines

---

#### TASK-011: Update Core Finance Tests
**Layer:** Test
**Depends On:** TASK-009, TASK-010

**Description:**
Add `await` to direct fake calls in 10 of 14 Core Finance test files (4 files are service-only and need no changes).

**Files to Modify:**
- `tests/unit/core_finance/application/services/test_account_create.py`
- `tests/unit/core_finance/application/services/test_account_soft_delete.py`
- `tests/unit/core_finance/application/services/test_bulk_transaction_service.py`
- `tests/unit/core_finance/application/services/test_card_management_service.py`
- `tests/unit/core_finance/application/services/test_transaction_create.py`
- `tests/unit/core_finance/application/services/test_transaction_lifecycle.py`
- `tests/unit/core_finance/application/services/test_transaction_query.py`
- `tests/unit/core_finance/application/services/test_transaction_review.py`
- `tests/unit/core_finance/application/services/test_transaction_split.py`
- `tests/unit/core_finance/application/services/test_transaction_update.py`

**No changes needed:**
- `test_account_recover.py`, `test_account_rename.py`, `test_account_sharing.py`, `test_account_update.py` (service-only calls)

**Acceptance Criteria:**
- [ ] All direct fake calls use `await`
- [ ] `uv run pytest tests/unit/core_finance/` passes
- [ ] `uv run ty check` passes

---

### Phase 4: Classification Context (4 ports, 3 fake classes, 12 test files)

#### TASK-012: Convert Classification Protocol Ports to Async
**Layer:** Application
**Depends On:** None

**Description:**
Add `async` keyword to all method definitions in 4 Protocol port files.

**Files to Modify:**
- `src/emerald/classification/application/ports/outbound/taxonomy_repository.py` — 5 methods
- `src/emerald/classification/application/ports/outbound/assignment_repository.py` — 10 methods
- `src/emerald/classification/application/ports/outbound/transaction_access_port.py` — 2 methods
- `src/emerald/classification/application/ports/outbound/categorization_event_handler.py` — 3 methods

**Acceptance Criteria:**
- [ ] All 20 methods use `async def`

---

#### TASK-013: Convert Classification Test Fakes to Async
**Layer:** Test
**Depends On:** TASK-012

**Description:**
Add `async` keyword to all Protocol methods in 3 fake classes. Test helpers (`add_active_transaction`, `grant_editor_permission`) stay sync.

**Files to Modify:**
- `tests/unit/classification/fakes.py` — 17 Protocol methods across `FakeTaxonomyRepository` (5), `FakeTransactionAccessPort` (2), `FakeTransactionTermAssignmentRepository` (10)

**Acceptance Criteria:**
- [ ] All 17 Protocol methods use `async def`
- [ ] `add_active_transaction` and `grant_editor_permission` remain sync

---

#### TASK-014: Convert Classification Application Services to Async
**Layer:** Application
**Depends On:** TASK-012

**Description:**
Add `await` to all repository/port calls in 2 Classification services. `TaxonomyManagementService._load_taxonomy()` must become `async def`.

**Files to Modify:**
- `src/emerald/classification/application/services/taxonomy_management.py` — `_load_taxonomy` → `async def` + ~10 `await` additions
- `src/emerald/classification/application/services/transaction_categorization.py` — ~20 `await` additions

**Acceptance Criteria:**
- [ ] `_load_taxonomy()` is `async def` and callers `await` it
- [ ] Every repo/port call preceded by `await`

---

#### TASK-015: Update Classification Tests
**Layer:** Test
**Depends On:** TASK-013, TASK-014

**Description:**
Add `await` to direct fake calls in 4 of 12 Classification test files (8 taxonomy/term files are service-only).

**Files to Modify:**
- `tests/unit/classification/application/services/test_categorization_assign.py`
- `tests/unit/classification/application/services/test_categorization_remove.py`
- `tests/unit/classification/application/services/test_categorization_cascades.py`
- `tests/unit/classification/application/services/test_categorization_queries.py`

**No changes needed:**
- All 8 taxonomy/term test files (service-only calls)

**Acceptance Criteria:**
- [ ] All direct fake calls use `await`
- [ ] `uv run pytest tests/unit/classification/` passes
- [ ] `uv run ty check` passes

---

### Phase 5: Integrations Context (7 ports, 7 fake classes, 8 test files)

#### TASK-016: Convert Integrations Protocol Ports to Async
**Layer:** Application + Domain
**Depends On:** None

**Description:**
Add `async` keyword to all method definitions in 7 Protocol port files.

**Files to Modify:**
- `src/emerald/integrations/application/ports/outbound/bank_connection_repository.py` — 6 methods
- `src/emerald/integrations/application/ports/outbound/sync_history_repository.py` — 5 methods
- `src/emerald/integrations/application/ports/outbound/pending_transaction_repository.py` — 7 methods
- `src/emerald/integrations/application/ports/outbound/bank_provider_adapter.py` — 3 methods
- `src/emerald/integrations/application/ports/outbound/provider_registry.py` — 2 methods
- `src/emerald/integrations/application/ports/outbound/transaction_import_port.py` — 3 methods
- `src/emerald/integrations/domain/ports/transaction_normalizer.py` — 1 method

**Acceptance Criteria:**
- [ ] All 27 methods use `async def`

---

#### TASK-017: Convert Integrations Test Fakes to Async
**Layer:** Test
**Depends On:** TASK-016

**Description:**
Add `async` keyword to all Protocol methods in 7 fake classes. Test helpers (`set_transactions`, `set_auth_error`, `set_provider_error`, `add_existing_external_id`, `add_match`) stay sync.

**Files to Modify:**
- `tests/unit/integrations/fakes.py` — 27 Protocol methods across 7 fake classes

**Acceptance Criteria:**
- [ ] All 27 Protocol methods use `async def`
- [ ] All test helpers remain sync

---

#### TASK-018: Convert Integrations Application Services to Async
**Layer:** Application
**Depends On:** TASK-016

**Description:**
Add `await` to all repository/port calls in 3 Integrations services. Critical changes:
1. `DeduplicationService.check()` → `async def check()` (calls `TransactionImportPort` async methods)
2. `BankSyncService` must `await self._dedup.check(...)`
3. `BankSyncService` must also `await adapter.fetch_transactions(...)`, `await normalizer.normalize(...)`, `await self._registry.get_adapter(...)`, `await self._registry.get_normalizer(...)`
4. `_load_connection()` helpers → `async def` in both services

**Files to Modify:**
- `src/emerald/integrations/application/services/bank_connection.py` — `_load_connection` → `async def` + ~10 `await` additions
- `src/emerald/integrations/application/services/bank_sync.py` — `_load_connection` → `async def` + ~15 `await` additions
- `src/emerald/integrations/application/services/deduplication.py` — `check` → `async def` + ~2 `await` additions

**Acceptance Criteria:**
- [ ] `DeduplicationService.check()` is `async def`
- [ ] All `_load_connection()` helpers are `async def`
- [ ] Every repo/port/adapter call preceded by `await`

---

#### TASK-019: Update Integrations Tests
**Layer:** Test
**Depends On:** TASK-017, TASK-018

**Description:**
Add `await` to direct fake calls in all 8 Integrations test files.

**Files to Modify:**
- `tests/unit/integrations/application/services/test_connection_initiate.py`
- `tests/unit/integrations/application/services/test_connection_config.py`
- `tests/unit/integrations/application/services/test_connection_lifecycle.py`
- `tests/unit/integrations/application/services/test_connection_queries.py`
- `tests/unit/integrations/application/services/test_deduplication.py`
- `tests/unit/integrations/application/services/test_sync_error_handling.py`
- `tests/unit/integrations/application/services/test_sync_execute.py`
- `tests/unit/integrations/application/services/test_sync_pending_review.py`

**Acceptance Criteria:**
- [ ] All direct fake calls use `await`
- [ ] `uv run pytest tests/unit/integrations/` passes
- [ ] `uv run ty check` passes

---

### Phase 6: Final Verification

#### TASK-020: Full Test Suite and Quality Checks
**Layer:** Cross-cutting
**Depends On:** TASK-003, TASK-007, TASK-011, TASK-015, TASK-019

**Description:**
Run the complete test suite and all quality checks to verify the migration is complete.

**Commands:**
```bash
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

**Acceptance Criteria:**
- [ ] All ~2600 tests pass
- [ ] `ruff check` clean
- [ ] `ruff format` clean
- [ ] `ty check` clean
- [ ] No `RuntimeWarning: coroutine was never awaited`

---

#### TASK-021: Update Context `__init__.py` Exports (if needed)
**Layer:** Application
**Depends On:** TASK-020

**Description:**
Verify that each context's `__init__.py` still correctly re-exports all public types. Converting `def` → `async def` shouldn't change exported names, but verify no breakage.

**Files to Check:**
- `src/emerald/shared_kernel/__init__.py`
- `src/emerald/iam/__init__.py`
- `src/emerald/core_finance/__init__.py`
- `src/emerald/classification/__init__.py`
- `src/emerald/integrations/__init__.py`

**Acceptance Criteria:**
- [ ] All `__all__` lists are still correct
- [ ] No import errors

---

## 5. Task Dependency Graph

```
Phase 1 (Shared Kernel):
  TASK-001 ──► TASK-002 ──► TASK-003

Phase 2 (IAM):
  TASK-004 ──┬──► TASK-005 ──┐
             │               ├──► TASK-007
             └──► TASK-006 ──┘

Phase 3 (Core Finance):
  TASK-008 ──┬──► TASK-009 ──┐
             │               ├──► TASK-011
             └──► TASK-010 ──┘

Phase 4 (Classification):
  TASK-012 ──┬──► TASK-013 ──┐
             │               ├──► TASK-015
             └──► TASK-014 ──┘

Phase 5 (Integrations):
  TASK-016 ──┬──► TASK-017 ──┐
             │               ├──► TASK-019
             └──► TASK-018 ──┘

Phase 6 (Verification):
  TASK-003 + TASK-007 + TASK-011 + TASK-015 + TASK-019 ──► TASK-020 ──► TASK-021
```

**Note:** Phases 1–5 are **independent of each other** at the Protocol level. However, since all contexts share the same test runner and type checker, migrating sequentially and verifying after each phase is recommended.

---

## 6. Change Count Summary

| Phase | Protocols | Fake Methods | Service `await`s | Test `await`s | Files Modified |
|-------|-----------|-------------|-----------------|---------------|----------------|
| 1. Shared Kernel | 7 | 3 | 0 | ~4 | 3 |
| 2. IAM | 24 | 24 | ~47 | ~100+ | 20 |
| 3. Core Finance | 15 | 15 | ~70 | ~60 | 17 |
| 4. Classification | 20 | 17 | ~30 | ~20 | 8 |
| 5. Integrations | 27 | 27 | ~27 | ~30 | 12 |
| **Total** | **93** | **86** | **~174** | **~214** | **~60** |

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Missing `await` in service | Medium | High (silent bug) | `ty check` flags unawaited coroutines; run after each phase |
| Sync helper not converted | Medium | High (type error) | Checklist of all 9 helpers above; `ty check` catches |
| `DeduplicationService` missed | Low | High (breaks sync tests) | Explicitly tracked in TASK-018 |
| Test helper accidentally made async | Low | Low (tests still pass) | Only convert Protocol methods, not setup helpers |
| Ruff format changes | Low | Low | Run `ruff format .` after each phase |

---

## 8. Definition of Done

- [ ] All 22 Protocol ports define `async def` methods (93 methods total)
- [ ] All 19 fake classes implement `async def` Protocol methods (86 methods)
- [ ] All 14 application services `await` every port/repository call (~174 sites)
- [ ] All 9 sync helper methods converted to `async def`
- [ ] `DeduplicationService.check()` converted to `async def`
- [ ] All ~2600 tests pass
- [ ] `ruff check .` clean
- [ ] `ruff format .` clean
- [ ] `ty check` clean
- [ ] Domain layer (aggregates, VOs, events, domain services) untouched
- [ ] No `RuntimeWarning: coroutine was never awaited`
