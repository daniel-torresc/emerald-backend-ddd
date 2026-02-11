# Spec 006: Data Lifecycle Management

**Status:** Draft
**Bounded Context:** Cross-Cutting
**Dependencies:** 001 (Shared Kernel)
**Blocks:** 007, 013

---

## 1. Overview

This spec defines the complete data lifecycle for all entities in the Emerald Finance Platform: soft delete, trash management, recovery, hard delete, retention policies, and cascade behavior. It builds on the soft-deletable entity trait from the Shared Kernel (Spec 001) and adds the full lifecycle orchestration.

**Key Principle:** Users have complete control over their data. Deleted items are recoverable from trash until a configurable retention period expires, at which point they are permanently removed. Hard delete is always an explicit, confirmed action with safeguards.

## 2. Scope

### In Scope

- Soft delete orchestration and cascade rules
- Hard delete process with safeguards (confirmation, cooling-off, audit)
- Retention policies (configurable per entity type, hierarchy enforcement)
- Trash management (view, filter, sort, bulk operations)
- Recovery orchestration and cascade rules
- Automatic cleanup (scheduled hard delete after retention expiry)
- Retention policy entity and configuration

### Out of Scope

- Entity-specific delete/recover methods (defined in each entity's spec)
- Audit logging implementation (Spec 016 — this spec emits events that audit logging consumes)
- User-initiated hard delete confirmation UX (presentation layer)

## 3. Entity Lifecycle States

All soft-deletable entities follow this state model:

```
┌──────────┐      soft_delete()     ┌──────────────┐     hard_delete()     ┌───────────────┐
│  ACTIVE  │───────────────────────►│ SOFT DELETED │──────────────────────►│ HARD DELETED  │
│          │                        │   (in Trash) │                       │  (Permanent)  │
└──────────┘                        └──────────────┘                       └───────────────┘
     ▲                                    │
     │              recover()             │
     └────────────────────────────────────┘
```

| State | Visibility | Recoverable | In Queries | In Calculations |
|-------|-----------|-------------|------------|-----------------|
| Active | Normal views | N/A | Yes | Yes |
| Soft Deleted | Trash view only | Yes | Only with `include_deleted=True` | No |
| Hard Deleted | Gone | No | No | No |

## 4. Soft Delete

### 4.1 Soft Delete Operation

When an entity is soft deleted:

```
soft_delete(entity, deleted_by, reason?):
  1. Validate entity is not already deleted
     Raises: AlreadyDeletedError
  2. Set entity.deleted_at = now (UTC)
  3. Set entity.deleted_by = deleted_by
  4. Set entity.deletion_reason = reason
  5. Look up retention policy for entity type
  6. Set entity.hard_delete_scheduled_at = now + retention_period
  7. Apply cascade rules (see section 7)
  8. Emit EntitySoftDeleted event
```

### 4.2 Query Behavior

Soft deleted entities are excluded from normal queries by default.

| Query Type | Default Behavior | With `include_deleted=True` |
|-----------|-----------------|---------------------------|
| List / Search | Excludes deleted | Includes deleted (with `deleted_at` visible) |
| Get by ID | Returns if active | Returns regardless of state |
| Aggregations (balance, counts) | Excludes deleted | N/A — calculations always exclude deleted |

**Domain Rule:** Balance calculations and other domain aggregations **always** exclude soft-deleted entities, even when `include_deleted=True` is passed. The flag only affects visibility, not business calculations.

## 5. Hard Delete

### 5.1 Hard Delete Triggers

| Trigger | Description | Safeguards |
|---------|-------------|------------|
| User-Initiated | User explicitly requests permanent deletion from trash | Confirmation + cooling-off |
| Automatic | Retention period expires (`hard_delete_scheduled_at` reached) | Retention warning notification |
| Admin-Initiated | Compliance or support action | Admin confirmation + audit |

### 5.2 User-Initiated Hard Delete Process

```
User requests hard delete of entity:
     │
     ▼
  1. Validate entity is soft deleted
     Raises: NotDeletedError (can only hard-delete from trash)
     │
     ▼
  2. Calculate cascade impact:
     - List all dependent entities that will also be hard deleted
     - Return cascade summary to caller
     │
     ▼
  3. Require explicit confirmation:
     - Caller must acknowledge cascade with confirmation token
     Raises: ConfirmationRequiredError (with cascade_summary)
     │
     ▼
  4. Start cooling-off period (if applicable):
     - Entity type determines cooling-off duration
     - Schedule hard delete for after cooling-off
     - Emit HardDeleteScheduled event
     │
     ▼
  5. After cooling-off (or immediately if no cooling-off):
     a. Create final audit record (EntityHardDeleted event)
     b. Hard delete all cascade children (depth-first)
     c. Hard delete the entity
     d. Emit EntityHardDeleted event
     │
     ▼
  6. Send confirmation notification to user
```

### 5.3 Automatic Hard Delete (Retention Expiry)

```
Scheduled job runs periodically (e.g., hourly):
     │
     ▼
  1. Query entities where:
     - deleted_at IS NOT NULL
     - hard_delete_scheduled_at <= now
     │
     ▼
  2. For each entity:
     a. Create final audit record
     b. Apply hard delete cascade (depth-first)
     c. Permanently remove data
     d. Emit EntityHardDeleted event
```

### 5.4 Hard Delete Safeguards

| Safeguard | Description | Applies To |
|-----------|-------------|------------|
| Must be in Trash | Only soft-deleted entities can be hard deleted | All entities |
| Cascade Warning | Full list of affected children shown before confirmation | User-initiated |
| Confirmation Required | Explicit acknowledgment of permanent deletion | User-initiated |
| Cooling-Off Period | Delay before execution (configurable, see 5.5) | User-initiated |
| Non-Reversible Warning | Clear indication this cannot be undone | User-initiated |
| Final Audit Record | Audit entry created before data removal | All triggers |
| Retention Warning | Notification sent before automatic hard delete | Automatic |

### 5.5 Cooling-Off Periods

| Entity Type | Cooling-Off Period | Rationale |
|-------------|-------------------|-----------|
| User Account | 24 hours | High impact — cascades to everything |
| Financial Account | 24 hours | Contains financial history |
| Transaction | None | Already in trash, lower risk |
| Card | None | Low impact |
| Account Share | None | Low impact |
| Taxonomy | None | Low impact |
| Taxonomy Term | None | Low impact |
| Bank Connection | None | Low impact |

## 6. Retention Policies

### 6.1 Default Retention Periods

| Entity Type | Default Retention | Rationale |
|-------------|-------------------|-----------|
| User Account | 30 days | Allow recovery from accidental deletion |
| Financial Account | 7 years | Regulatory compliance (SOX, tax records) |
| Transaction | 7 years | Regulatory compliance |
| Card | 90 days | Lower recovery need |
| Account Share | 30 days | Access recovery window |
| Taxonomy | 7 days | Lower importance |
| Taxonomy Term | 7 days | Lower importance |
| Bank Connection | 7 days | Security consideration |

### 6.2 Retention Policy Entity

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| policy_id | UUID | No | Unique identifier |
| entity_type | str | No | Which entity type this policy applies to |
| retention_period | RetentionPeriod | Yes | How long to keep soft-deleted items |
| auto_hard_delete | bool | Yes | Whether to automatically hard delete after retention |
| requires_confirmation | bool | Yes | Whether user confirmation needed for hard delete |
| cooling_off_period | RetentionPeriod? | Yes | Delay before hard delete executes |
| compliance_reason | str? | Yes | Why this retention is required (regulatory reference) |
| regulatory_minimum | RetentionPeriod? | No | Minimum period that cannot be reduced |

### 6.3 Policy Hierarchy

Retention periods are resolved with a strict hierarchy — the longest applicable period wins:

```
Effective retention = max(
  1. Regulatory minimum (cannot be reduced by anyone)
  2. Platform default (set by admin)
  3. User preference (can only increase, never decrease)
)
```

**Rules:**

- Regulatory minimums are immutable and take precedence over everything
- Platform defaults can be changed by admins but cannot go below regulatory minimums
- Users can extend their own retention (e.g., keep transactions longer) but cannot shorten below platform default
- Admin can override retention for compliance reasons (with audit)

### 6.4 Retention Policy Domain Service

```
RetentionPolicyService:
  + get_effective_retention(entity_type: str, user_id: UUID?) -> RetentionPeriod
      Resolves the hierarchy: regulatory -> platform -> user preference
      Returns: the longest applicable period

  + calculate_hard_delete_date(entity_type: str, deleted_at: datetime, user_id: UUID?) -> datetime
      Returns: deleted_at + get_effective_retention(entity_type, user_id)

  + update_platform_default(entity_type: str, period: RetentionPeriod) -> None
      Validates: period >= regulatory_minimum
      Raises: BelowRegulatoryMinimumError

  + set_user_preference(entity_type: str, user_id: UUID, period: RetentionPeriod) -> None
      Validates: period >= platform_default
      Raises: BelowPlatformDefaultError
```

### 6.5 Retention Warning

Before automatic hard delete, users should be notified:

| Warning | Timing | Channel |
|---------|--------|---------|
| First warning | 7 days before hard delete | Email, In-App |
| Final warning | 24 hours before hard delete | Email, In-App, Push |

**Note:** Warning notifications are emitted as domain events (`RetentionWarningDue`). The notification system (Spec 019) handles delivery.

## 7. Cascade Behavior

### 7.1 Soft Delete Cascades

When a parent entity is soft deleted, its children are automatically soft deleted.

| Parent | Children Affected | Cascade Behavior |
|--------|-------------------|-----------------|
| User | Owned Accounts | Soft deleted |
| User | Owned Taxonomies | Soft deleted |
| Account | Transactions | Soft deleted |
| Account | Cards | Soft deleted |
| Account | Shares (non-owner) | Soft deleted |
| Taxonomy | Terms | Soft deleted |
| Transaction (parent) | Split children | Soft deleted |

**Cascade Rules:**

- Children inherit the parent's `deleted_by` and `deletion_reason`
- Children get their own `hard_delete_scheduled_at` based on their entity type's retention
- Cascade is applied recursively (e.g., User -> Account -> Transactions)
- Each cascaded entity emits its own `EntitySoftDeleted` event

### 7.2 Hard Delete Cascades

When a parent is hard deleted, all children in trash are also hard deleted.

| Parent | Children Affected | Cascade Behavior |
|--------|-------------------|-----------------|
| User | Everything owned | Hard deleted |
| Account | Transactions, Cards, Shares | Hard deleted |
| Taxonomy | Terms | Hard deleted |
| Transaction (parent) | Split children | Hard deleted |

**Cascade Rules:**

- Hard delete cascade is depth-first (children deleted before parent)
- Each cascaded entity gets its own final audit record
- Active children are NOT affected by parent hard delete (they were already soft deleted by the soft delete cascade, so they'll be in trash)

### 7.3 Recovery Cascades

Recovery does **not** automatically recover children.

```
Recovering a parent:
  1. Validate parent is soft deleted
  2. Clear parent's deletion fields
  3. Children REMAIN in trash
  4. User must recover children individually

Exception: Split transactions recover together
  - Recovering a split parent recovers all split children
  - Recovering a split child also recovers the parent and all siblings
```

**Recovery Preconditions:**

| Rule | Description | Raises |
|------|-------------|--------|
| Parent must be active | Cannot recover child if parent is deleted | `ParentDeletedError` |
| Entity must be soft deleted | Cannot recover an active entity | `NotDeletedError` |
| Within retention period | Cannot recover after hard delete | N/A (entity no longer exists) |

## 8. Trash Management

### 8.1 Trash View Capabilities

| Capability | Description |
|-----------|-------------|
| View All Deleted | See all soft-deleted items the user has access to |
| Filter by Type | Filter trash by entity type (accounts, transactions, etc.) |
| Sort by Deletion Date | Order by `deleted_at` ascending or descending |
| View Time Remaining | Display time until `hard_delete_scheduled_at` |
| Bulk Recovery | Recover multiple items at once |
| Bulk Hard Delete | Permanently delete multiple items at once |
| Search Deleted | Search within deleted items by name/description |

### 8.2 Trash Access Rules

| User Role (Domain) | Can View in Trash | Can Recover | Can Hard Delete |
|--------------------|-------------------|-------------|-----------------|
| Owner | All deleted items for owned accounts | Yes | Yes |
| Editor | Deleted transactions they created | No | No |
| Viewer | Nothing | No | No |

### 8.3 Trash Query Service

```
TrashQueryService:
  + list_trash(
      user_id: UUID,
      entity_type: str?,
      sort_by: str = "deleted_at",
      sort_order: str = "desc",
      page: int = 1,
      page_size: int = 20
    ) -> PaginatedResult[TrashItem]

  + get_cascade_summary(entity_id: UUID) -> CascadeSummary
      Returns: list of all entities that will be affected by hard delete
```

**TrashItem Value Object:**

| Attribute | Type | Description |
|-----------|------|-------------|
| entity_id | UUID | ID of the deleted entity |
| entity_type | str | Type of entity |
| display_name | str | Human-readable name/description |
| deleted_at | datetime | When deleted |
| deleted_by | UUID | Who deleted |
| deletion_reason | str? | Why deleted |
| hard_delete_scheduled_at | datetime | When auto hard delete occurs |
| time_remaining | timedelta | Time until hard delete |
| child_count | int | Number of cascade children also in trash |

**CascadeSummary Value Object:**

| Attribute | Type | Description |
|-----------|------|-------------|
| target_entity | TrashItem | The entity being hard deleted |
| affected_children | list[TrashItem] | All children that will cascade |
| total_affected_count | int | Total entities to be removed |

## 9. Domain Events

| Event | Trigger | Key Data |
|-------|---------|----------|
| `EntitySoftDeleted` | Any entity soft deleted | entity_type, entity_id, deleted_by, reason |
| `EntityRecovered` | Any entity recovered | entity_type, entity_id, recovered_by |
| `HardDeleteScheduled` | User initiates hard delete (cooling-off starts) | entity_type, entity_id, scheduled_at |
| `HardDeleteCancelled` | User cancels during cooling-off | entity_type, entity_id |
| `EntityHardDeleted` | Entity permanently removed | entity_type, entity_id, trigger (user/auto/admin) |
| `RetentionWarningDue` | Approaching automatic hard delete | entity_type, entity_id, user_id, hard_delete_at |

## 10. Domain Services

### 10.1 Soft Delete Service

```
SoftDeleteService:
  + soft_delete_entity(
      entity: SoftDeletable,
      deleted_by: UUID,
      reason: str?
    ) -> list[DomainEvent]
      1. Validate entity is active
      2. Get retention policy
      3. Apply soft delete to entity
      4. Resolve and apply cascades
      5. Return collected events
```

### 10.2 Hard Delete Service

```
HardDeleteService:
  + request_hard_delete(entity_id: UUID, entity_type: str, requested_by: UUID) -> CascadeSummary
      Returns cascade summary for confirmation

  + confirm_hard_delete(entity_id: UUID, entity_type: str, confirmed_by: UUID) -> list[DomainEvent]
      1. Validate confirmation
      2. Check cooling-off (schedule if applicable)
      3. Or execute immediately
      4. Return collected events

  + execute_hard_delete(entity_id: UUID, entity_type: str) -> list[DomainEvent]
      1. Create final audit event
      2. Hard delete cascade children (depth-first)
      3. Hard delete entity
      4. Return collected events
```

### 10.3 Recovery Service

```
RecoveryService:
  + recover_entity(entity_id: UUID, entity_type: str, recovered_by: UUID) -> list[DomainEvent]
      1. Validate entity is soft deleted
      2. Validate parent is active (if applicable)
      3. Clear deletion fields
      4. Handle split transaction exception
      5. Return collected events
```

## 11. Repository Interface

```
RetentionPolicyRepository (Protocol):
  + find_by_entity_type(entity_type: str) -> RetentionPolicy?
  + find_user_preference(entity_type: str, user_id: UUID) -> RetentionPeriod?
  + save(policy: RetentionPolicy) -> None
  + save_user_preference(entity_type: str, user_id: UUID, period: RetentionPeriod) -> None

ScheduledDeletionRepository (Protocol):
  + find_due_for_hard_delete(as_of: datetime) -> list[tuple[str, UUID]]
      Returns (entity_type, entity_id) pairs where hard_delete_scheduled_at <= as_of
```

## 12. Acceptance Criteria

### Soft Delete

- [ ] Soft deleting an active entity sets `deleted_at`, `deleted_by`, and `hard_delete_scheduled_at`
- [ ] Soft deleting an already-deleted entity raises `AlreadyDeletedError`
- [ ] Soft deleted entities are excluded from normal queries
- [ ] Soft deleted entities are included with `include_deleted=True`
- [ ] Soft deleted entities are excluded from balance calculations regardless of `include_deleted` flag
- [ ] Cascade: soft deleting a parent soft deletes all children
- [ ] Each cascaded child gets its own retention-based `hard_delete_scheduled_at`
- [ ] Each cascaded child emits its own `EntitySoftDeleted` event

### Hard Delete

- [ ] Hard delete only works on soft-deleted entities — raises `NotDeletedError` for active
- [ ] Hard delete returns cascade summary before execution
- [ ] Hard delete requires explicit confirmation
- [ ] Hard delete applies cooling-off period for User and Account entities (24 hours)
- [ ] Hard delete cascade is depth-first (children before parent)
- [ ] Each cascaded entity gets its own `EntityHardDeleted` audit event
- [ ] Data is permanently removed after hard delete (not retrievable)

### Automatic Cleanup

- [ ] Entities past `hard_delete_scheduled_at` are automatically hard deleted
- [ ] Retention warning events are emitted 7 days and 24 hours before auto hard delete

### Retention Policies

- [ ] Default retention periods match the specified values per entity type
- [ ] Regulatory minimum cannot be reduced by platform default or user preference
- [ ] Platform default cannot go below regulatory minimum
- [ ] User preference can only increase retention, not decrease below platform default
- [ ] Effective retention is the maximum of all three hierarchy levels

### Recovery

- [ ] Recovering a soft-deleted entity clears all deletion fields
- [ ] Recovering an active entity raises `NotDeletedError`
- [ ] Cannot recover if parent entity is deleted — raises `ParentDeletedError`
- [ ] Recovering a parent does NOT auto-recover children (children stay in trash)
- [ ] Exception: split transactions recover together (parent + all children)

### Trash Management

- [ ] Owner can view all deleted items for owned accounts
- [ ] Editor can only view deleted transactions they created
- [ ] Viewer cannot see trash
- [ ] Trash items show `time_remaining` until hard delete
- [ ] Trash supports filtering by entity type, sorting by deletion date
- [ ] Bulk recovery recovers multiple items (with parent validation for each)
- [ ] Bulk hard delete confirms cascade for all selected items
