# Spec 034 — Cascade Completeness & Data Integrity

**Status:** DRAFT
**Priority:** P1
**Dependencies:** spec-006 (Data Lifecycle), spec-007 (Account), spec-009 (Transaction), spec-033 (Event Dispatch)
**Blocked by:** spec-033 (needs event dispatch to trigger cross-aggregate cascades)
**Blocks:** spec-024 (Core Finance Persistence — must know cascade behavior for FK constraints)

---

## 1. Problem Statement

The shared kernel defines declarative cascade rules in `SOFT_DELETE_CASCADE_RULES` and `HARD_DELETE_CASCADE_RULES`, but not all rules are enforced in the domain/application layer:

### 1.1 Missing: Account -> Transaction Soft-Delete Cascade

`Account.soft_delete()` cascades to cards (soft-delete) and shares (revoke non-owner), but **not to transactions**. There is an explicit TODO:

```python
# account.py, line ~421
# TODO(spec-009): Cascade soft-delete to Transactions
```

The cascade rule in `shared_kernel/domain/constants.py` declares:

```python
SOFT_DELETE_CASCADE_RULES = {
    DeletableEntityType.FINANCIAL_ACCOUNT: [
        DeletableEntityType.TRANSACTION,   # <-- NOT ENFORCED
        DeletableEntityType.CARD,          # Enforced in Account.soft_delete()
        DeletableEntityType.ACCOUNT_SHARE, # Enforced in Account.soft_delete()
    ],
}
```

**Consequence:** When a user deletes an account, all transactions remain active. Balance calculations still return values. Transaction queries return results for "deleted" accounts.

### 1.2 Missing: Account -> Transaction Hard-Delete Cascade

When an account is hard-deleted (retention period expires), its transactions must also be hard-deleted. This requires:
- The hard-delete job to cascade to all transactions
- Split children to be hard-deleted with their parents
- Transaction-term assignments to be cleaned up

### 1.3 Missing: User -> Account Cascade Awareness

When a user is soft-deleted, their owned accounts should be cascaded. The cascade rule:

```python
DeletableEntityType.USER_ACCOUNT: [
    DeletableEntityType.FINANCIAL_ACCOUNT,
],
```

This is a cross-context cascade (IAM -> Core Finance) that requires the event dispatch mechanism from spec-033.

---

## 2. Scope

### In Scope

- Implement Account -> Transaction soft-delete cascade (service-level, via event dispatch)
- Implement Account -> Transaction recovery cascade (service-level)
- Implement hard-delete cascade rules for Account -> Transaction -> Split Children
- Implement hard-delete cascade for Transaction -> TransactionTermAssignment
- Define the service-level handler for `AccountSoftDeleted` and `AccountRecovered` events
- Remove the TODO comment from `account.py`
- Verify all `SOFT_DELETE_CASCADE_RULES` and `HARD_DELETE_CASCADE_RULES` are enforced

### Out of Scope

- User -> Account cascade (requires IAM -> Core Finance cross-context, deferred to composition root)
- BankConnection cascades (already handled within Integrations context)
- Infrastructure-level cascade constraints (FK ON DELETE — those go in persistence specs)

---

## 3. Design

### 3.1 Why NOT in the Aggregate?

Account cannot cascade to transactions in its `soft_delete()` method because:

1. **Account doesn't hold a `_transactions` collection.** Transactions are a separate aggregate with their own repository. Account has no reference to them.
2. **Loading all transactions into memory for cascade would be expensive.** An account could have thousands of transactions.
3. **This is an application-layer concern.** The cascade crosses aggregate boundaries, so it belongs in a service or event handler.

### 3.2 Transaction Cascade Handler

A new handler responds to `AccountSoftDeleted` events and cascades to all transactions in the account:

```python
# src/emerald/core_finance/application/services/account_cascade_handler.py

class AccountCascadeHandler:
    """Handles cascade operations when accounts change lifecycle state."""

    def __init__(
        self,
        uow: AbstractCoreFinanceUnitOfWork,
        retention_policy_service: RetentionPolicyService,
    ) -> None:
        self._uow = uow
        self._retention_policy_service = retention_policy_service

    async def handle_account_soft_deleted(self, event: AccountSoftDeleted) -> None:
        """Cascade soft-delete to all active transactions in the account."""
        async with self._uow:
            transactions = await self._uow.transactions.find_by_account(
                account_id=event.account_id,
                include_deleted=False,
            )
            retention = self._retention_policy_service.get_effective_retention(
                DeletableEntityType.TRANSACTION,
                event.deleted_by,
            )
            for txn in transactions.items:
                txn.soft_delete(
                    deleted_by=event.deleted_by,
                    retention=retention,
                    reason=f"Cascade from account {event.aggregate_id} deletion",
                )
            await self._uow.commit()

    async def handle_account_recovered(self, event: AccountRecovered) -> None:
        """Cascade recovery to transactions that were cascade-deleted with this account."""
        async with self._uow:
            transactions = await self._uow.transactions.find_by_account(
                account_id=event.account_id,
                include_deleted=True,
            )
            for txn in transactions.items:
                if txn.is_deleted():
                    txn.recover()
            await self._uow.commit()
```

### 3.3 Pagination Concern

`find_by_account()` returns `PaginatedResult[Transaction]`. For cascade operations, we need **all** transactions, not just one page.

**Options:**
1. Add a `find_all_by_account()` method that returns a full list (no pagination)
2. Iterate through pages in the handler
3. Add a `soft_delete_by_account()` bulk method to the repository

**Recommendation:** Option 1 — add `find_all_by_account()` to `TransactionRepository`. The cascade handler needs all transactions to emit individual events. For the repository infrastructure layer, this translates to a streaming query.

```python
# Addition to TransactionRepository Protocol
async def find_all_by_account(
    self,
    account_id: uuid.UUID,
    include_deleted: bool = False,
) -> list[Transaction]: ...
```

### 3.4 Split Child Cascade

When a split parent is soft-deleted through account cascade:
- Children should also be soft-deleted (already handled by `TransactionManagementService.soft_delete_transaction()`)
- But the cascade handler operates directly on transactions, bypassing the service
- Solution: The cascade handler must also cascade to split children

```python
# Inside handle_account_soft_deleted, after soft-deleting each transaction:
if txn.is_split_parent:
    children = await self._uow.transactions.find_children(txn.id)
    for child in children:
        if not child.is_deleted():
            child.soft_delete(
                deleted_by=event.deleted_by,
                retention=retention,
                reason=f"Cascade from parent transaction {txn.id} deletion",
            )
```

### 3.5 Event Registration

In the composition root (spec-026), register cascade handlers:

```python
dispatcher.register(AccountSoftDeleted, cascade_handler.handle_account_soft_deleted)
dispatcher.register(AccountRecovered, cascade_handler.handle_account_recovered)
```

---

## 4. Hard-Delete Cascade

Hard-delete happens when retention period expires (background job, spec-021/031). The cascade order for account hard-delete:

1. Hard-delete all `TransactionTermAssignment` records for each transaction in the account
2. Hard-delete all split children for each split parent transaction
3. Hard-delete all transactions in the account
4. Hard-delete all cards in the account
5. Hard-delete all shares in the account
6. Hard-delete the account itself

This is an infrastructure/job concern, not a domain concern. The domain layer just needs to ensure the repository provides the necessary query methods.

### 4.1 Required Repository Extension

```python
# Addition to TransactionRepository Protocol
async def hard_delete_by_account(self, account_id: uuid.UUID) -> int:
    """Hard-delete all transactions (including deleted) for an account. Returns count."""
    ...
```

---

## 5. Cascade Rule Audit

| Rule (from constants.py) | Source | Target | Enforced? | Where |
|--------------------------|--------|--------|-----------|-------|
| `FINANCIAL_ACCOUNT -> TRANSACTION` | Account soft-delete | Transaction soft-delete | **NO** | **This spec fixes it** |
| `FINANCIAL_ACCOUNT -> CARD` | Account soft-delete | Card soft-delete | YES | `Account.soft_delete()` |
| `FINANCIAL_ACCOUNT -> ACCOUNT_SHARE` | Account soft-delete | Share revocation | YES | `Account.soft_delete()` |
| `TAXONOMY -> TAXONOMY_TERM` | Taxonomy soft-delete | Term soft-delete | YES | `Taxonomy.soft_delete()` |
| `TAXONOMY_TERM -> (assignments)` | Term delete | Assignment hard-delete | YES | `CategorizationEventHandler.handle_term_deleted()` (via event) |
| `TRANSACTION -> (split children)` | Transaction soft-delete | Child soft-delete | YES | `TransactionManagementService.soft_delete_transaction()` |
| `TRANSACTION -> (assignments)` | Transaction soft-delete | Assignment hard-delete | YES | `CategorizationEventHandler.handle_transaction_soft_deleted()` (via event) |
| `USER_ACCOUNT -> FINANCIAL_ACCOUNT` | User soft-delete | Account soft-delete | **DEFERRED** | Cross-context, requires composition root |

---

## 6. Acceptance Criteria

1. `AccountSoftDeleted` event triggers cascade soft-delete of all active transactions in the account
2. `AccountRecovered` event triggers cascade recovery of transactions that were cascade-deleted
3. Split children are included in the cascade (both delete and recover)
4. `TransactionRepository` gains `find_all_by_account()` method (no pagination)
5. `TransactionRepository` gains `hard_delete_by_account()` method
6. The TODO comment in `account.py` is removed
7. New tests verify cascade behavior (delete account -> verify all transactions deleted)
8. New tests verify recovery behavior (recover account -> verify transactions recovered)
9. New tests verify split child cascade
10. All existing tests pass
11. All quality checks pass (`ruff check`, `ruff format`, `ty check`)

---

## 7. Risk Assessment

- **Risk:** Cascade recovery is imprecise — recovering an account recovers ALL its deleted transactions, even ones the user manually deleted before the account deletion. Mitigation: Track cascade reason so recovery can distinguish manual vs cascade deletions. This can be added later; for now, "recover everything" is acceptable.
- **Risk:** Large accounts with thousands of transactions could make cascade slow. Mitigation: The handler processes in a single UoW transaction. For the in-memory fakes this is instant. For infrastructure, batch processing can be added in the persistence spec.
