# Spec 019: Notifications

**Status:** Draft
**Bounded Context:** Cross-Cutting
**Dependencies:** 001 (Shared Kernel)
**Blocks:** None

---

## 1. Overview

This spec defines the notification system — the mechanism by which the platform informs users about meaningful events (shares, imports, security alerts, retention warnings). Notifications are triggered by domain events, routed through user preferences, and delivered via multiple channels (email, push, in-app).

**Key Principle:** Notifications are event-driven and preference-aware. Users control which notifications they receive and through which channels. The notification system consumes domain events and never calls into domain logic — it is a pure downstream consumer.

## 2. Scope

### In Scope

- Notification types catalog (all notifiable events)
- Delivery channels (Email, Push, In-App)
- User notification preferences (per-type, per-channel)
- Quiet hours configuration
- Digest options (immediate, daily, weekly)
- In-app notification entity (read/unread state)
- Notification dispatch pipeline (event → preferences → delivery)

### Out of Scope

- Email template design and rendering (infrastructure)
- Push notification provider integration (Firebase, APNs — infrastructure)
- SMS channel (not in Phase 1)
- Notification analytics (open rates, click rates — future)

## 3. Notification Types

### 3.1 Catalog

| Type | Trigger Event | Default Channels | Urgency |
|------|---------------|-----------------|---------|
| `ACCOUNT_SHARED` | `AccountShared` | Email, Push, In-App | Normal |
| `SHARE_REVOKED` | `AccountShareRevoked` | Email, In-App | Normal |
| `OWNERSHIP_TRANSFERRED` | `AccountOwnershipTransferred` | Email, Push, In-App | High |
| `TRANSACTIONS_IMPORTED` | `TransactionsImported` | Push, In-App | Low |
| `BANK_SYNC_FAILED` | `BankSyncFailed` | Email, Push | High |
| `BANK_NEEDS_REAUTH` | `BankConnectionNeedsReauth` | Email, Push, In-App | High |
| `RETENTION_WARNING` | `RetentionWarningDue` | Email, In-App | Normal |
| `RETENTION_FINAL_WARNING` | `RetentionWarningDue` (24h) | Email, In-App, Push | High |
| `SECURITY_LOGIN_NEW_DEVICE` | `UserLoggedIn` (new device) | Email, Push | High |
| `SECURITY_PASSWORD_CHANGED` | `PasswordChanged` | Email | High |
| `SECURITY_ALL_SESSIONS_REVOKED` | `AllSessionsRevoked` | Email | High |
| `SECURITY_PROVIDER_LINKED` | `AuthProviderLinked` | Email, In-App | Normal |
| `SECURITY_PROVIDER_UNLINKED` | `AuthProviderUnlinked` | Email, In-App | Normal |
| `PENDING_REVIEW_TRANSACTIONS` | `BankSyncCompleted` (has NEEDS_REVIEW) | In-App | Low |

### 3.2 Urgency Levels

| Level | Description | Delivery Behavior |
|-------|-------------|-------------------|
| HIGH | Security or action-required | Always immediate, ignores quiet hours |
| NORMAL | Important but not urgent | Respects quiet hours, eligible for digest |
| LOW | Informational | Respects quiet hours, eligible for digest |

## 4. Delivery Channels

### 4.1 Channel Definitions

| Channel | Description | Delivery Model |
|---------|-------------|---------------|
| EMAIL | Email to user's registered address | Asynchronous, queued |
| PUSH | Mobile/browser push notification | Asynchronous, real-time attempt |
| IN_APP | In-application notification center | Synchronous write, user polls/subscribes |

### 4.2 Channel Capabilities

| Capability | Email | Push | In-App |
|-----------|-------|------|--------|
| Rich content | Yes (HTML) | No (title + short body) | Yes (structured) |
| Action links | Yes | Yes (deep link) | Yes |
| Offline delivery | Yes | Queued by provider | Available on next login |
| Read tracking | No | No | Yes (read/unread) |
| Digest support | Yes | No | No |

## 5. User Notification Preferences

### 5.1 NotificationPreferences Entity

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| user_id | UUID | No | User these preferences belong to |
| type_preferences | dict[NotificationType, TypePreference] | Yes | Per-type settings |
| quiet_hours | QuietHours? | Yes | Suppression window |
| digest_preference | DigestPreference | Yes | How to batch non-urgent |
| updated_at | datetime | Auto | Last update |

### 5.2 TypePreference (Value Object)

Per-notification-type channel configuration:

| Attribute | Type | Description |
|-----------|------|-------------|
| notification_type | NotificationType | Which notification |
| enabled | bool | Whether this type is enabled at all |
| channels | set[Channel] | Which channels to deliver through |

**Default Preferences:**

On user registration, preferences are initialized with the defaults from the notification type catalog (section 3.1). Users can then customize.

### 5.3 QuietHours (Value Object)

| Attribute | Type | Description |
|-----------|------|-------------|
| start_time | time | Start of quiet period (e.g., 22:00) |
| end_time | time | End of quiet period (e.g., 08:00) |
| timezone | str | User's timezone (IANA) |

**Rules:**

- During quiet hours, NORMAL and LOW urgency notifications are held
- HIGH urgency notifications are delivered immediately regardless of quiet hours
- Held notifications are delivered when quiet hours end (or included in next digest)
- Quiet hours can span midnight (e.g., 22:00 → 08:00)

### 5.4 DigestPreference

| Value | Description |
|-------|-------------|
| IMMEDIATE | Deliver all notifications as they occur |
| DAILY | Batch non-urgent into daily digest email (sent at configurable time) |
| WEEKLY | Batch non-urgent into weekly digest email (sent on configurable day) |

**Rules:**

- Digest only applies to EMAIL channel
- Digest only applies to NORMAL and LOW urgency
- HIGH urgency always delivered immediately
- Push and In-App are always immediate (not digestable)
- Digest delivery time respects user's timezone

## 6. In-App Notification Entity

### 6.1 Attributes

| Attribute | Type | Mutable | Description |
|-----------|------|---------|-------------|
| notification_id | UUID | No | Unique identifier |
| user_id | UUID | No | Recipient |
| notification_type | NotificationType | No | Type of notification |
| title | str | No | Short title |
| body | str | No | Notification body |
| action_url | str? | No | Deep link for action |
| metadata | dict | No | Structured data for rendering |
| is_read | bool | Yes | Read/unread state |
| read_at | datetime? | Yes | When marked as read |
| created_at | datetime | No | When created |

### 6.2 Domain Methods

```
InAppNotification:
  + mark_as_read() -> None
      Sets: is_read = True, read_at = now

  + mark_as_unread() -> None
      Sets: is_read = False, read_at = None
```

### 6.3 Notification Center Queries

```
NotificationCenterService:
  + get_notifications(
      user_id: UUID,
      is_read: bool? = None,
      page: int = 1,
      page_size: int = 20
    ) -> PaginatedResult[InAppNotification]

  + get_unread_count(user_id: UUID) -> int

  + mark_as_read(notification_id: UUID, user_id: UUID) -> None

  + mark_all_as_read(user_id: UUID) -> None

  + delete_notification(notification_id: UUID, user_id: UUID) -> None
      Hard deletes — in-app notifications don't need soft delete
```

## 7. Notification Dispatch Pipeline

### 7.1 Pipeline Overview

```
Domain Event (e.g., AccountShared)
     │
     ▼
┌─────────────────────┐
│  Event Handler       │  Maps domain event → notification
│  (per event type)    │  Determines recipient(s)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Preference Resolver │  Load user preferences
│                      │  Determine channels for this type
│                      │  Check if enabled
└──────────┬──────────┘
           │
           ├── Not enabled → discard
           │
           ▼
┌─────────────────────┐
│  Delivery Router     │  Apply quiet hours
│                      │  Apply digest batching
│                      │  Route to channel dispatchers
└──────────┬──────────┘
           │
     ┌─────┼─────────┐
     ▼     ▼         ▼
┌───────┐┌──────┐┌────────┐
│ Email ││ Push ││ In-App │
│Dispatch││Dispatch│Dispatch│
└───────┘└──────┘└────────┘
```

### 7.2 Recipient Resolution

| Event | Recipient(s) |
|-------|-------------|
| `AccountShared` | The user being shared with |
| `AccountShareRevoked` | The user whose access was revoked |
| `AccountOwnershipTransferred` | Both old and new owner |
| `TransactionsImported` | Account owner |
| `BankSyncFailed` | Connection owner |
| `BankConnectionNeedsReauth` | Connection owner |
| `RetentionWarningDue` | Entity owner |
| `PasswordChanged` | The user whose password changed |
| `AllSessionsRevoked` | The affected user |
| `AuthProviderLinked/Unlinked` | The affected user |

### 7.3 Notification Content

Each notification type has a content template:

```
NotificationContentBuilder:
  + build(type: NotificationType, context: dict) -> NotificationContent

NotificationContent:
  - title: str           (short, for push and in-app)
  - body: str            (medium, for in-app and email summary)
  - email_body: str?     (rich HTML, for email only)
  - action_url: str?     (deep link)
  - metadata: dict       (structured data for rendering)
```

**Example — AccountShared:**

```
title: "New account shared with you"
body: "Alice shared 'Savings Account' with you as Editor"
action_url: "/accounts/{account_id}"
metadata: {
    "account_id": "...",
    "account_name": "Savings Account",
    "shared_by": "Alice",
    "permission_level": "EDITOR"
}
```

## 8. Digest Service

### 8.1 Digest Aggregation

```
DigestService:
  + collect_pending_digest(user_id: UUID) -> list[InAppNotification]
      Returns notifications queued for digest since last delivery

  + send_daily_digest(user_id: UUID) -> None
      1. Collect pending notifications (NORMAL + LOW urgency)
      2. Group by type
      3. Generate digest email content
      4. Send via email channel
      5. Mark notifications as included in digest

  + send_weekly_digest(user_id: UUID) -> None
      Same as daily but for weekly preference users
```

### 8.2 Digest Scheduling

```
Digest scheduler (background job):
  Daily at user's preferred time (default: 08:00 local):
    For each user with digest_preference = DAILY:
      send_daily_digest(user_id)

  Weekly on user's preferred day (default: Monday 08:00 local):
    For each user with digest_preference = WEEKLY:
      send_weekly_digest(user_id)
```

## 9. Channel Dispatcher Interfaces

```
EmailDispatcher (Protocol):
  + send(
      to_email: str,
      subject: str,
      html_body: str,
      text_body: str
    ) -> None

PushDispatcher (Protocol):
  + send(
      user_id: UUID,
      title: str,
      body: str,
      action_url: str?,
      data: dict?
    ) -> None

InAppDispatcher:
  + send(notification: InAppNotification) -> None
      Persists to in-app notification store
      (No external service call — direct write)
```

## 10. Repository Interfaces

```
NotificationPreferencesRepository (Protocol):
  + find_by_user(user_id: UUID) -> NotificationPreferences?
  + save(preferences: NotificationPreferences) -> None

InAppNotificationRepository (Protocol):
  + save(notification: InAppNotification) -> None
  + find_by_user(
      user_id: UUID,
      is_read: bool? = None,
      page: int = 1,
      page_size: int = 20
    ) -> PaginatedResult[InAppNotification]
  + count_unread(user_id: UUID) -> int
  + mark_as_read(notification_id: UUID) -> None
  + mark_all_as_read(user_id: UUID) -> None
  + delete(notification_id: UUID) -> None

DigestQueueRepository (Protocol):
  + enqueue(user_id: UUID, notification: InAppNotification) -> None
  + dequeue_pending(user_id: UUID) -> list[InAppNotification]
  + find_users_due_for_digest(
      digest_type: DigestPreference,
      as_of: datetime
    ) -> list[UUID]
```

## 11. Acceptance Criteria

### Notification Dispatch

- [ ] Domain events trigger corresponding notification types
- [ ] Correct recipient(s) resolved for each event type
- [ ] Notifications delivered through channels configured in user preferences
- [ ] Disabled notification types are not delivered
- [ ] Disabled channels are not used

### Urgency and Quiet Hours

- [ ] HIGH urgency notifications delivered immediately, ignoring quiet hours
- [ ] NORMAL and LOW urgency notifications held during quiet hours
- [ ] Held notifications delivered when quiet hours end
- [ ] Quiet hours span midnight correctly (e.g., 22:00 → 08:00)

### Digest

- [ ] IMMEDIATE preference delivers all notifications as they occur
- [ ] DAILY digest batches NORMAL/LOW notifications into daily email
- [ ] WEEKLY digest batches NORMAL/LOW notifications into weekly email
- [ ] HIGH urgency always immediate regardless of digest preference
- [ ] Digest only applies to EMAIL channel (Push and In-App always immediate)
- [ ] Digest delivery respects user's timezone

### In-App Notifications

- [ ] In-app notifications created with title, body, action_url, metadata
- [ ] Notifications default to `is_read = False`
- [ ] `mark_as_read()` sets `is_read = True` and `read_at`
- [ ] `mark_all_as_read()` marks all user's notifications as read
- [ ] Unread count accurately reflects current state
- [ ] Notifications paginated (default 20, max configurable)
- [ ] In-app notifications can be hard deleted by user

### Default Preferences

- [ ] New users get default preferences matching the notification type catalog
- [ ] Users can override channels per notification type
- [ ] Users can disable specific notification types entirely
- [ ] Users can configure quiet hours with timezone
- [ ] Users can choose digest preference (IMMEDIATE, DAILY, WEEKLY)

### Security Notifications

- [ ] Password change sends email notification (always, regardless of preference)
- [ ] All sessions revoked sends email notification (always)
- [ ] New device login sends email + push (always for HIGH urgency)
- [ ] Security notifications cannot be disabled by users
