# Spec 033 — Domain Event Dispatch

**Status:** DRAFT
**Priority:** P1
**Dependencies:** spec-001 (DomainEvent base), spec-006 (lifecycle events), all domain specs (001-015)
**Blocked by:** None (can be implemented before or after spec-032)
**Blocks:** spec-016 (Audit Logging), spec-019 (Notifications), spec-026 (Composition Root)

---

## 1. Problem Statement

Domain events are registered inside aggregates via `_register_event()` and collected via `collect_events()`. However, **no code in the application layer ever calls `collect_events()` or dispatches events to handlers**.

This means:

1. **Cross-context cascades don't fire.** When a taxonomy term is deleted, `TransactionCategorizationService.handle_term_deleted()` should be called to clean up assignments — but nothing connects them.
2. **The `CategorizationEventHandler` protocol exists but is never wired.** It defines 3 handler methods that `TransactionCategorizationService` implements via structural subtyping, but no dispatch mechanism invokes them.
3. **Audit logging (spec-016) has no event source.** The planned audit trail depends on domain events, but events are silently discarded after `uow.commit()`.
4. **Cascade rules defined in `shared_kernel/domain/constants.py`** (`SOFT_DELETE_CASCADE_RULES`, `HARD_DELETE_CASCADE_RULES`) are declarative configuration with no runtime enforcement.

---

## 2. Scope

### In Scope

- Define an `EventDispatcher` protocol in the shared kernel application layer
- Integrate event collection + dispatch into the UoW commit lifecycle
- Define handler registration mechanism (in-process, synchronous-within-transaction)
- Wire existing `CategorizationEventHandler` methods as concrete handlers
- Ensure events from all aggregates are collected after commit

### Out of Scope

- Async/background event processing (message queues, Celery, etc.) — future concern
- Event sourcing / event store persistence — not part of this system's architecture
- Saga/process manager patterns — addressed if needed in future specs
- Infrastructure implementation of the dispatcher — that belongs in spec-026

---

## 3. Architecture Decision: Where to Dispatch

### Option A: Dispatch Inside UoW.commit() (Recommended)

Events are collected from all "seen" aggregates and dispatched **after** the database transaction commits successfully.

```python
class AbstractUnitOfWork(ABC):
    async def commit(self) -> None:
        await self._do_commit()          # DB transaction commits
        events = self._collect_events()  # Gather from tracked aggregates
        await self._dispatch_events(events)  # Dispatch to handlers
```

**Pros:** Automatic, no service-level boilerplate, guarantees events are only dispatched on successful commit.
**Cons:** UoW needs to track which aggregates were modified ("seen" set).

### Option B: Dispatch in Services (Explicit)

Each service manually collects and dispatches after commit.

```python
async def soft_delete_account(self, cmd: SoftDeleteAccount) -> None:
    async with self._uow:
        account = await self._uow.accounts.find_by_id(cmd.account_id)
        account.soft_delete(...)
        await self._uow.commit()
    events = account.collect_events()
    await self._dispatcher.dispatch(events)
```

**Pros:** Explicit, easy to reason about.
**Cons:** Repetitive, easy to forget, every service must handle dispatch.

### Decision: **Option A** — dispatch inside UoW commit.

Rationale: The current codebase has 14 services with dozens of methods. Adding manual dispatch to each would be error-prone and repetitive. The UoW already owns the transaction boundary, making it the natural place to also own event dispatch.

---

## 4. Design

### 4.1 EventHandler Protocol

```python
# src/emerald/shared_kernel/application/ports/outbound/event_handler.py

from typing import Protocol
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


class EventHandler(Protocol):
    """Handler for a specific domain event type."""

    async def handle(self, event: DomainEvent) -> None: ...
```

### 4.2 EventDispatcher Protocol

```python
# src/emerald/shared_kernel/application/ports/outbound/event_dispatcher.py

from typing import Protocol
from emerald.shared_kernel.domain.events.domain_event import DomainEvent


class EventDispatcher(Protocol):
    """Dispatches domain events to registered handlers."""

    async def dispatch(self, events: list[DomainEvent]) -> None:
        """Dispatch a list of events to all registered handlers."""
        ...
```

### 4.3 UoW Integration

The base `AbstractUnitOfWork` gains:

1. An `_event_dispatcher: EventDispatcher | None` attribute (optional, for backward compatibility with tests)
2. A `_seen: list[AggregateRoot]` tracking list — aggregates register themselves when loaded/saved via repositories
3. Updated `commit()` flow that collects events from seen aggregates and dispatches after successful commit

```python
class AbstractUnitOfWork(ABC):
    _event_dispatcher: EventDispatcher | None

    def __init__(self, event_dispatcher: EventDispatcher | None = None) -> None:
        self._event_dispatcher = event_dispatcher
        self._seen: list[AggregateRoot] = []

    def register_seen(self, aggregate: AggregateRoot) -> None:
        """Track an aggregate for event collection after commit."""
        if aggregate not in self._seen:
            self._seen.append(aggregate)

    async def commit(self) -> None:
        await self._do_commit()
        if self._event_dispatcher is not None:
            events: list[DomainEvent] = []
            for aggregate in self._seen:
                events.extend(aggregate.collect_events())
            if events:
                await self._event_dispatcher.dispatch(events)

    @abstractmethod
    async def _do_commit(self) -> None:
        """Subclass implements actual DB commit."""
        ...

    @abstractmethod
    async def rollback(self) -> None: ...
```

### 4.4 Repository Integration

Repositories must call `self._uow.register_seen(aggregate)` when:
- An aggregate is loaded via `find_by_*` methods
- An aggregate is saved via `save()` / `add()` methods

This is an infrastructure concern — the Protocol definitions don't change, but fake and real implementations must track seen aggregates.

### 4.5 Transaction Entity Special Case

`Transaction` extends `AggregateRoot` and has its own `_register_event()` / `collect_events()`. Since it's persisted via its own `TransactionRepository`, it will be tracked as a "seen" aggregate independently from its parent `Account`. This is correct — Transaction events should be dispatched alongside Account events.

For bulk operations (`BulkTransactionService`), many transactions may be modified in a single UoW. Each must be registered as seen.

---

## 5. Handler Registration

### 5.1 In-Memory Dispatcher (for tests and initial implementation)

```python
class InMemoryEventDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Callable]] = {}

    def register(self, event_type: type[DomainEvent], handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def dispatch(self, events: list[DomainEvent]) -> None:
        for event in events:
            for handler in self._handlers.get(type(event), []):
                await handler(event)
```

### 5.2 Wiring Example: Classification Cascade

When a taxonomy term is soft-deleted, all transaction-term assignments for that term must be hard-deleted:

```python
# In composition root (spec-026)
dispatcher.register(
    TermDeleted,
    categorization_service.handle_term_deleted,
)
dispatcher.register(
    TaxonomySoftDeleted,
    categorization_service.handle_taxonomy_soft_deleted,
)
```

---

## 6. Events That Need Handlers (Current Codebase)

### 6.1 Cross-Context Cascades (Required)

| Source Event | Source Context | Handler | Target Context | Effect |
|-------------|---------------|---------|----------------|--------|
| `TaxonomySoftDeleted` | Classification | `TransactionCategorizationService.handle_taxonomy_soft_deleted` | Classification | Hard-delete all assignments for taxonomy |
| `TermDeleted` | Classification | `TransactionCategorizationService.handle_term_deleted` | Classification | Hard-delete all assignments for term |
| `TransactionSoftDeleted` | Core Finance | `TransactionCategorizationService.handle_transaction_soft_deleted` | Classification | Hard-delete all assignments for transaction |
| `AccountSoftDeleted` | Core Finance | *(see spec-034)* | Core Finance | Cascade soft-delete to transactions |

### 6.2 Future Handlers (Not in this spec)

| Source Event | Handler | Effect |
|-------------|---------|--------|
| Any state-change event | Audit Logger (spec-016) | Write audit log entry |
| Various events | Notification Service (spec-019) | Send notifications |

---

## 7. Impact on Test Fakes

### 7.1 FakeUnitOfWork Changes

All fake UoWs gain:
- `_seen: list[AggregateRoot]` tracking
- `register_seen()` method
- Updated `commit()` to collect + dispatch events (if dispatcher provided)
- `collected_events: list[DomainEvent]` for test assertions

```python
class FakeIamUnitOfWork(AbstractIamUnitOfWork):
    def __init__(self, dispatcher: EventDispatcher | None = None) -> None:
        super().__init__(event_dispatcher=dispatcher)
        self.users = FakeUserRepository(self)
        ...
        self.committed = False
        self.collected_events: list[DomainEvent] = []

    async def _do_commit(self) -> None:
        self.committed = True
```

### 7.2 Fake Repository Changes

All fake repositories must call `register_seen`:

```python
class FakeUserRepository:
    def __init__(self, uow: AbstractIamUnitOfWork) -> None:
        self._uow = uow
        ...

    async def add(self, user: User) -> None:
        self._store[user.id] = user
        self._uow.register_seen(user)

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        user = self._store.get(user_id)
        if user is not None:
            self._uow.register_seen(user)
        return user
```

---

## 8. Acceptance Criteria

1. `EventDispatcher` protocol defined in shared kernel
2. `AbstractUnitOfWork` collects events from seen aggregates after commit
3. Repositories (fake implementations) call `register_seen()` on load/save
4. `CategorizationEventHandler` methods are invocable through the dispatch mechanism
5. Events are dispatched **only** after successful commit (not on rollback)
6. Events are dispatched **in order** (registration order within each aggregate, then aggregate order)
7. Dispatcher is optional in UoW (None = no dispatch, for backward-compatible tests)
8. All existing tests pass
9. New tests verify event dispatch for at least one cross-context cascade
10. All quality checks pass (`ruff check`, `ruff format`, `ty check`)

---

## 9. Open Questions

1. **Should dispatch failures roll back the commit?** Recommendation: No. Events are "best effort" in this in-process model. Failures should be logged, not re-thrown. Transactional outbox can be added later if needed.

2. **Should we support event ordering guarantees?** Recommendation: Yes, within a single UoW commit. Events from aggregate A are dispatched before events from aggregate B if A was seen first. Within an aggregate, events maintain registration order.

3. **Should handlers run in the same transaction?** Recommendation: No. Handlers run after commit. If a handler needs its own transaction, it opens a new UoW. This prevents cascading rollbacks and keeps the model simple.
