# Emerald Finance Platform - Functional Requirements Document v2

**Document Version:** 2.0
**Last Updated:** 2026-02-05
**Target Audience:** Product Managers, Business Analysts, Architects, Stakeholders
**Status:** Foundation Specification for New Implementation

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Domain Model Philosophy](#2-domain-model-philosophy)
3. [Bounded Context: Identity & Access Management](#3-bounded-context-identity--access-management)
4. [Data Lifecycle Management](#4-data-lifecycle-management)
5. [Core Domain: Financial Tracking](#5-core-domain-financial-tracking)
6. [Supporting Domain: Classification](#6-supporting-domain-classification)
7. [Supporting Domain: External Integrations](#7-supporting-domain-external-integrations)
8. [Cross-Cutting Concerns](#8-cross-cutting-concerns)
9. [Business Rules Catalog](#9-business-rules-catalog)
10. [Operational Requirements](#10-operational-requirements)
11. [Future Roadmap](#11-future-roadmap)
12. [Glossary / Ubiquitous Language](#12-glossary--ubiquitous-language)

---

## 1. System Overview

### 1.1 Vision Statement

Emerald Finance Platform is a **comprehensive personal and family finance management system** designed to provide complete visibility, control, and collaboration over financial life. The platform serves as the single source of truth for all financial accounts, transactions, and budgets, regardless of where those accounts are held.

**Core Principles:**
1. **Domain-Driven** - Business rules live in the domain, not in infrastructure
2. **Event-Sourced Ready** - Every state change can be reconstructed from events
3. **Multi-Tenant Capable** - Architecture supports future SaaS deployment
4. **API-First** - Every capability is available through APIs
5. **Privacy-Centric** - Users own their data; compliance is built-in

### 1.2 Target Users

| User Type              | Description                                   | Primary Use Cases                                                                   |
|------------------------|-----------------------------------------------|-------------------------------------------------------------------------------------|
| **Individual Users**   | Single person managing personal finances      | Track all accounts, monitor spending, categorize transactions, analyze trends       |
| **Couples & Partners** | Two people managing shared household finances | Joint account management, expense splitting, shared budgets, financial transparency |
| **Families**           | Extended household with multiple members      | Multi-generational visibility, allowance tracking, shared expense management        |
| **Financial Advisors** | Professionals helping clients (future)        | Read-only client portfolio views, consolidated reporting                            |

### 1.3 Platform Personas

The platform uses a **unified identity model** where every person has one account and one set of credentials. A hierarchical **system role** determines which parts of the platform the user can access:

| System Role    | Access                          | Capabilities                                                                        |
|----------------|---------------------------------|-------------------------------------------------------------------------------------|
| **USER**       | emerald.com                     | Full financial tracking, collaboration, bank connections                            |
| **ADMIN**      | emerald.com + admin.emerald.com | All USER capabilities + master data management, user support, compliance monitoring |
| **SUPERADMIN** | emerald.com + admin.emerald.com | All ADMIN capabilities + bootstrap, emergency access, create/manage admins          |

**Key Principle:** One person, one account, one login. An administrator automatically has full access to the financial application — no separate account needed. The `USER` role is the default; every authenticated user can use the main application regardless of their role, since higher roles inherit all lower-role capabilities.

### 1.4 Core Value Propositions

1. **Complete Financial Picture** - All accounts, all institutions, one view
2. **Intelligent Collaboration** - Share exactly what you want, with whom you want
3. **Flexible Organization** - Your categories, your way, unlimited depth
4. **Bank Connectivity** - Automatic transaction import from supported institutions
5. **Complete Control** - See deleted items, recover or permanently remove
6. **Compliance Ready** - Configurable retention, complete audit trail
7. **Multi-Currency Native** - Track accounts in any currency, convert for reporting

---

## 2. Domain Model Philosophy

### 2.1 Architecture Principles

This specification mandates a **Domain-Driven Design** approach with strict layer separation:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                              │
│  REST API, GraphQL, WebSocket handlers                                  │
│  - Input validation (format only, not business rules)                   │
│  - Authentication/Authorization enforcement                             │
│  - Response formatting                                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                                │
│  Use Cases, Application Services, Command/Query Handlers                │
│  - Orchestrates domain operations                                       │
│  - Transaction boundaries                                               │
│  - Publishes domain events to external systems                          │
│  - NO business rules                                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DOMAIN LAYER                                   │
│  Entities, Value Objects, Aggregates, Domain Services, Domain Events    │
│  ═══════════════════════════════════════════════════════════════════    │
│  ║  ALL BUSINESS RULES LIVE HERE - NO EXCEPTIONS                    ║   │
│  ║  - Validation rules                                              ║   │
│  ║  - Invariant enforcement                                         ║   │
│  ║  - Business calculations                                         ║   │
│  ║  - State transitions                                             ║   │
│  ═══════════════════════════════════════════════════════════════════    │
│  - Pure Python, no framework dependencies                               │
│  - No database knowledge                                                │
│  - No external service knowledge                                        │
│  - 100% unit testable without infrastructure                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       INFRASTRUCTURE LAYER                              │
│  Repositories, External Services, Message Queues, Caches                │
│  - Implements domain interfaces                                         │
│  - Database access (NO business logic in queries)                       │
│  - External API integrations                                            │
│  - Database constraints are SAFETY NETS, not business rules             │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Business Rules Mandate

**CRITICAL REQUIREMENT:** Every single business rule MUST be implemented in the Domain Layer.

**What this means:**
- Database constraints (CHECK, UNIQUE, NOT NULL) serve as **safety nets**, not as primary enforcement
- If the database is replaced, all business rules still work
- Domain objects are always in a valid state; invalid states cannot be created
- Business rule violations raise domain exceptions before any persistence attempt

**Examples:**

| Rule                                         | Implementation Location                        |
|----------------------------------------------|------------------------------------------------|
| "Account name must be unique per user"       | Domain Service checks before Account creation  |
| "Transaction currency must match account"    | Account Aggregate validates on transaction add |
| "Split amounts must sum to parent"           | Transaction Entity validates on split creation |
| "Password must meet complexity requirements" | User Entity validates on password change       |

### 2.3 Core Domain Concepts

#### Value Objects

Concepts defined entirely by their attributes. Immutable. No identity.

| Value Object              | Context        | Attributes                                                | Behavior                                              |
|---------------------------|----------------|-----------------------------------------------------------|-------------------------------------------------------|
| **Money**                 | Core Finance   | amount, currency                                          | Addition (same currency only), comparison, formatting |
| **Currency**              | Core Finance   | code, symbol, name, decimalPlaces                         | Validation, equality                                  |
| **EmailAddress**          | IAM            | value                                                     | Format validation, normalization                      |
| **Username**              | IAM            | value                                                     | Format validation, normalization                      |
| **Password**              | IAM            | hashedValue                                               | Strength validation, comparison                       |
| **AuthProvider**          | IAM            | provider, externalId?, linkedAt                           | Provider type validation, linking                     |
| **SystemRole**            | IAM            | role (USER, ADMIN, SUPERADMIN)                            | Hierarchy comparison, capability check                |
| **AuthenticatedIdentity** | IAM            | userId, email, displayName, systemRole, adminPermissions? | Identity contract exposed to other contexts           |
| **UserReference**         | Core Finance   | userId, displayName                                       | Lightweight identity for domain operations            |
| **IBAN**                  | Core Finance   | fullNumber, lastFour                                      | Checksum validation, masking                          |
| **PermissionLevel**       | Core Finance   | level (1-3)                                               | Hierarchy comparison                                  |
| **DateRange**             | Core Finance   | startDate, endDate                                        | Contains check, overlap detection                     |
| **RetentionPeriod**       | Cross-Cutting  | duration, unit                                            | Expiration calculation                                |
| **TaxonomyPath**          | Classification | segments                                                  | Depth calculation, parent extraction                  |

#### Entities

Concepts with unique identity that persist and change over time.

| Entity             | Context        | Identity      | Key Behaviors                                                     |
|--------------------|----------------|---------------|-------------------------------------------------------------------|
| **User**           | IAM            | userId        | Registration, authentication, profile management, role assignment |
| **Account**        | Core Finance   | accountId     | Balance calculation, sharing, transaction management              |
| **Transaction**    | Core Finance   | transactionId | Categorization, splitting, review workflow                        |
| **Card**           | Core Finance   | cardId        | Linking to transactions                                           |
| **Taxonomy**       | Classification | taxonomyId    | Term management, hierarchy operations                             |
| **TaxonomyTerm**   | Classification | termId        | Hierarchy navigation, path computation                            |
| **BankConnection** | Integrations   | connectionId  | Sync operations, credential management                            |

**Note:** The Core Finance context does not work with the full `User` entity. Instead, it receives an `AuthenticatedIdentity` from IAM and translates it to a `UserReference` value object containing only `userId` and `displayName`. This Anti-Corruption Layer ensures the finance domain has no dependency on IAM internals (credentials, roles, sessions).

#### Aggregates

Consistency boundaries that protect invariants.

| Aggregate                    | Context        | Root           | Contains                           | Key Invariants                                                 |
|------------------------------|----------------|----------------|------------------------------------|----------------------------------------------------------------|
| **User Aggregate**           | IAM            | User           | RefreshTokens, UserPreferences     | Token family integrity, role hierarchy, preference consistency |
| **Account Aggregate**        | Core Finance   | Account        | Transactions, Cards, AccountShares | Balance consistency, currency uniformity, single owner         |
| **Taxonomy Aggregate**       | Classification | Taxonomy       | TaxonomyTerms                      | Name uniqueness, no circular references                        |
| **BankConnection Aggregate** | Integrations   | BankConnection | SyncHistory, PendingTransactions   | Connection state consistency                                   |

#### Domain Events

Events that capture meaningful state changes.

| Event                       | Trigger               | Consumers                                         |
|-----------------------------|-----------------------|---------------------------------------------------|
| `UserRegistered`            | New user registration | Welcome email, analytics                          |
| `AccountCreated`            | New account creation  | Audit log                                         |
| `AccountShared`             | Share granted         | Notification to recipient                         |
| `AccountShareRevoked`       | Share removed         | Notification, access cleanup                      |
| `TransactionCreated`        | New transaction       | Balance recalculation, categorization suggestions |
| `TransactionSplit`          | Split operation       | Audit log                                         |
| `TransactionsImported`      | Bulk import complete  | User notification                                 |
| `BankConnectionEstablished` | Bank linked           | Initial sync trigger                              |
| `BankSyncCompleted`         | Sync finished         | User notification                                 |
| `EntitySoftDeleted`         | Soft delete           | Retention timer start                             |
| `EntityHardDeleted`         | Permanent deletion    | Audit log (final record)                          |
| `EntityRecovered`           | Undelete operation    | Audit log                                         |

### 2.4 Bounded Context Map

The platform is organized into distinct bounded contexts, each owning a specific part of the domain. Contexts communicate through well-defined integration contracts.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BOUNDED CONTEXT MAP                              │
│                                                                         │
│  ┌─────────────────────────┐        ┌─────────────────────────┐         │
│  │   IAM CONTEXT           │        │  CORE FINANCE CONTEXT   │         │
│  │   (Upstream/Supplier)   │        │  (Downstream/Customer)  │         │
│  │                         │        │                         │         │
│  │  • User identity        │        │  • Account management   │         │
│  │  • System roles         │        │  • Transactions         │         │
│  │  • Authentication       │        │  • Sharing/permissions  │         │
│  │  • Token lifecycle      │        │  • Balance calculation  │         │
│  │  • Password policies    │        │  • Cards                │         │
│  │  • Session management   │        │  • Bulk operations      │         │
│  │                         │        │                         │         │
│  └───────────┬─────────────┘        └────────────▲────────────┘         │
│              │                                   │                      │
│              │    AuthenticatedIdentity          │                      │
│              └──────────►┌───────────┐───────────┘                      │
│                          │    ACL    │                                  │
│                          │ (Anti-    │  Translates to                   │
│                          │ Corruption│  UserReference                   │
│                          │  Layer)   │  (userId, displayName)           │
│                          └───────────┘                                  │
│                                                                         │
│  ┌─────────────────────────┐        ┌─────────────────────────┐         │
│  │  CLASSIFICATION CONTEXT │        │  EXTERNAL INTEGRATIONS  │         │
│  │  (Supporting)           │        │  CONTEXT (Supporting)   │         │
│  │                         │        │                         │         │
│  │  • Taxonomies           │        │  • Bank connections     │         │
│  │  • Terms/hierarchy      │        │  • Sync management      │         │
│  │  • Categorization rules │        │  • Import processing    │         │
│  │  • Auto-categorization  │        │  • Provider adapters    │         │
│  │                         │        │                         │         │
│  └─────────────────────────┘        └─────────────────────────┘         │
│                                                                         │
│  SHARED KERNEL:                                                         │
│    • Base entity traits (soft delete, timestamps, audit fields)         │
│    • Common value objects (Money, Currency, DateRange)                  │
│                                                                         │
│  RELATIONSHIPS:                                                         │
│    IAM → Core Finance:          Customer/Supplier (ACL)                 │
│    Classification → Core Finance: Conformist (shared Transaction ref)   │
│    Integrations → Core Finance:  Conformist (imports into Account)      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Context Responsibilities:**

| Context                   | Owns                                                                                                                                                                  | Does NOT Own                                                    |
|---------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| **IAM**                   | User identity, credentials, system roles, admin permissions, authentication flows, token lifecycle, session management, password policies, MFA, user lifecycle states | Account-level permissions, financial data, domain authorization |
| **Core Finance**          | Accounts, transactions, balance calculation, sharing (Owner/Editor/Viewer), cards, bulk operations                                                                    | User credentials, authentication, system roles                  |
| **Classification**        | Taxonomies, terms, hierarchy, categorization rules                                                                                                                    | Transaction data, account data                                  |
| **External Integrations** | Bank connections, sync scheduling, import processing, provider adapters                                                                                               | Account ownership, transaction business rules                   |

---

## 3. Bounded Context: Identity & Access Management

### 3.1 Context Boundary

The IAM bounded context is responsible for **who users are** and **system-level access control**. It is explicitly NOT responsible for domain-level authorization (e.g., what a user can do with a specific financial account).

**IAM Context Owns:**
- User identity (credentials, email, password hash)
- System roles (SUPERADMIN, ADMIN, USER)
- Admin permissions (granular admin capabilities)
- Authentication flows (login, registration, password reset)
- Token lifecycle (issuance, rotation, revocation, theft detection)
- Session management (concurrent sessions, device binding)
- Password policies (complexity, history, expiration)
- MFA configuration
- User lifecycle states (PendingVerification, Active, Suspended, Deleted)

**IAM Context Does NOT Own:**
- Account-level permissions (Owner/Editor/Viewer) — these belong to the Account Aggregate in Core Finance
- Financial data of any kind
- Domain authorization decisions (e.g., "can this user edit this account?")
- Business rules about what users can do with accounts

### 3.2 Unified Identity Model

The platform uses a **single identity model** where every person has one user account, one set of credentials, and one system role that determines platform access.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        UNIFIED IDENTITY MODEL                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        ONE USER ENTITY                          │    │
│  │                                                                 │    │
│  │  userId, email, username, password (Argon2id)                   │    │
│  │  systemRole: USER | ADMIN | SUPERADMIN                          │    │
│  │  adminPermissions: Set<AdminPermission>? (ADMIN/SUPERADMIN only)│    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│              ┌───────────────┼───────────────┐                          │
│              │               │               │                          │
│              ▼               ▼               ▼                          │
│  ┌───────────────┐ ┌─────────────────┐ ┌─────────────────┐              │
│  │   USER Role   │ │   ADMIN Role    │ │ SUPERADMIN Role │              │
│  │   (default)   │ │                 │ │  (install only) │              │
│  ├───────────────┤ ├─────────────────┤ ├─────────────────┤              │
│  │ emerald.com   │ │ emerald.com     │ │ emerald.com     │              │
│  │ Full finance  │ │ + admin portal  │ │ + admin portal  │              │
│  │ features      │ │ + master data   │ │ + bootstrap     │              │
│  │               │ │ + user support  │ │ + emergency     │              │
│  │               │ │ + compliance    │ │ + create admins │              │
│  └───────────────┘ └─────────────────┘ └─────────────────┘              │
│                                                                         │
│  ROLE HIERARCHY: SUPERADMIN > ADMIN > USER                              │
│  Each higher role inherits ALL capabilities of lower roles.             │
│  Every user implicitly has USER access.                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Why Unified:**
- An administrator who also manages personal finances uses the SAME account — no separate login needed
- Email addresses are globally unique (no duplicate emails)
- Simpler authentication: one login flow, one token structure, role determines portal access
- Aligns with future multi-tenant SaaS (Phase 5) where tenant admins are also users

### 3.3 System Roles

#### Role Hierarchy

Roles are strictly hierarchical. A single `systemRole` field determines the user's access level. Higher roles inherit all capabilities of lower roles.

| Role           | Default | Access                              | Capabilities                                                          |
|----------------|---------|-------------------------------------|-----------------------------------------------------------------------|
| **USER**       | Yes     | emerald.com                         | Full financial tracking, collaboration, bank connections              |
| **ADMIN**      | No      | emerald.com + admin.emerald.com     | All USER + master data management, user support, compliance           |
| **SUPERADMIN** | No      | emerald.com + admin.emerald.com     | All ADMIN + bootstrap, emergency access, create/manage admins         |

**Hierarchy Rule:** Since roles are strictly hierarchical (`SUPERADMIN > ADMIN > USER`) and USER access is implicit, a single field suffices — no need for a set of roles.

#### SUPERADMIN Handling

- Provisioned at installation only — cannot be created or deleted via any API
- It is a regular User record with `systemRole = SUPERADMIN`
- Same user table, same credentials flow, same authentication mechanism
- SUPERADMIN implicitly has all admin permissions (no need to assign sub-permissions)
- All SUPERADMIN actions logged with enhanced detail
- Session timeout: 15 minutes (non-configurable)
- MFA required (when implemented)

**SUPERADMIN Capabilities:**

| Capability                | Description                               |
|---------------------------|-------------------------------------------|
| Create Admin Users        | Promote users to ADMIN role               |
| System Configuration      | Platform-wide settings                    |
| Emergency User Recovery   | Unlock accounts, reset access             |
| Audit Log Full Access     | View all system activity                  |
| Retention Policy Override | Extend or bypass retention for compliance |

#### Admin Permissions (Granular)

Users with `ADMIN` or `SUPERADMIN` role can have granular admin permissions for fine-grained access control within the admin portal:

| Admin Permission       | Capabilities                                                              |
|------------------------|---------------------------------------------------------------------------|
| **master_data_admin**  | Manage financial institutions, account types, currencies                  |
| **user_support_admin** | View user profiles (not financial data), unlock accounts, reset passwords |
| **compliance_admin**   | View audit logs, manage retention policies, export compliance reports     |
| **full_admin**         | All administrative permissions                                            |

**Rules:**
- SUPERADMIN implicitly has all admin permissions (no explicit assignment needed)
- ADMIN users must have at least one admin permission assigned
- ADMIN users cannot grant permissions they don't have
- `full_admin` is a convenience permission that encompasses all others

#### Portal Access Rules

| Portal              | Allowed Roles              | Behavior on Unauthorized Access |
|---------------------|----------------------------|---------------------------------|
| emerald.com         | All authenticated users    | Standard login flow             |
| admin.emerald.com   | ADMIN, SUPERADMIN          | 403 Forbidden                   |

### 3.4 User Entity

**Attributes:**

| Attribute             | Type                    | Mutable | Description                                                 |
|-----------------------|-------------------------|---------|-------------------------------------------------------------|
| userId                | UUID                    | No      | Unique identifier                                           |
| email                 | EmailAddress            | Yes     | Email address (globally unique)                             |
| username              | Username                | Yes     | Unique display name                                         |
| fullName              | String?                 | Yes     | Optional full name                                          |
| password              | Password?               | Yes     | Hashed password (null if social-only account)               |
| authProviders         | Set\<AuthProvider\>     | Yes     | Linked authentication methods (PASSWORD, GOOGLE, MICROSOFT) |
| systemRole            | SystemRole              | Yes     | USER (default), ADMIN, or SUPERADMIN                        |
| adminPermissions      | Set\<AdminPermission\>? | Yes     | Granular admin capabilities (null for USER role)            |
| status                | UserStatus              | Yes     | Active, Suspended, PendingVerification, Deleted             |
| emailVerified         | Boolean                 | Yes     | Whether email has been verified                             |
| preferences           | UserPreferences         | Yes     | User preferences (timezone, locale, currency display)       |
| createdAt             | Timestamp               | No      | Registration timestamp                                      |
| lastLoginAt           | Timestamp?              | Yes     | Last successful login                                       |
| deletedAt             | Timestamp?              | Yes     | Soft delete timestamp (null if active)                      |
| hardDeleteScheduledAt | Timestamp?              | Yes     | When permanent deletion will occur                          |

**User Lifecycle:**

```
                    ┌──────────────────┐
                    │  Registration    │
                    │  (role: USER)    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
     ┌─────────────►│ PendingVerify    │
     │              └────────┬─────────┘
     │                       │ Email verified
     │                       ▼
     │              ┌──────────────────┐
     │ Unsuspend    │     Active       │◄───────────────┐
     │              └────────┬─────────┘                │
     │                       │                          │
     │          ┌─────────────────────────┐             │
     │          │                         │             │
     │          ▼                         ▼             │
     │    ┌──────────┐               ┌──────────┐       │
     └────│ Suspended│               │ Deleted  │───────┘
          └──────────┘               │ (soft)   │  Recover
                                     └────┬─────┘
                                          │
                                          │ Retention period expires
                                          │ OR user requests hard delete
                                          ▼
                                     ┌──────────┐
                                     │ Deleted  │
                                     │ (Hard)   │
                                     └──────────┘
                                     Data anonymized
                                     or removed
```

**Business Rules:**
- Email must be globally unique (no duplicate emails anywhere in the system)
- Username must be unique (globally, including deleted users for 90 days)
- Password must meet complexity requirements when present (validated in domain)
- `password` is required when `authProviders` contains PASSWORD; null allowed for social-only accounts
- `authProviders` must contain at least one provider at all times
- Email verification required for full functionality (auto-verified for social provider registration)
- Suspended users cannot log in but data is preserved
- Soft deleted users enter retention period before hard delete
- `systemRole` defaults to USER on registration
- `adminPermissions` must be null when `systemRole` is USER
- `adminPermissions` must have at least one value when `systemRole` is ADMIN

### 3.5 Authentication

#### Password Authentication

| Aspect         | Specification                                                   |
|----------------|-----------------------------------------------------------------|
| Algorithm      | Argon2id                                                        |
| Minimum Length | 12 characters                                                   |
| Complexity     | At least 1 uppercase, 1 lowercase, 1 digit, 1 special character |
| History        | Cannot reuse last 5 passwords                                   |
| Expiration     | Optional, configurable (default: never)                         |

**Password validation is a DOMAIN rule:**
```
Password Value Object:
  - validate_strength() → raises PasswordTooWeakError
  - validate_not_in_history(history) → raises PasswordReusedError
  - hash() → returns hashed value
  - verify(plaintext) → returns boolean
```

#### Federated Authentication (OAuth 2.0 / OIDC)

The platform supports external identity providers for authentication via OpenID Connect:

| Provider      | Protocol | Status  | Notes                                   |
|---------------|----------|---------|-----------------------------------------|
| **Google**    | OIDC     | Planned | Google Sign-In via OAuth 2.0 + OIDC     |
| **Microsoft** | OIDC     | Planned | Microsoft Identity Platform (Azure AD)  |

**AuthProvider Value Object:**

```
AuthProvider:
  - provider: ProviderType (PASSWORD | GOOGLE | MICROSOFT)
  - externalId: String?  (provider's unique user ID; null for PASSWORD)
  - linkedAt: Timestamp   (when this provider was linked)
```

**Federated Authentication Flow:**

```
User clicks "Sign in with Google/Microsoft"
     │
     ▼
Redirect to provider (OAuth 2.0 Authorization Code Flow + PKCE)
     │
     ▼
Provider authenticates user, returns authorization code
     │
     ▼
Platform exchanges code for ID token
     │
     ▼
Extract email + provider user ID from ID token
     │
     ├── Email matches existing user? ──► Link provider to account
     │                                    (add to authProviders set)
     │
     └── No matching email? ──► Create new user
                                 (emailVerified = true, password = null,
                                  authProviders = {provider})
```

**Account Linking Rules:**
- If a user registers with email/password and later signs in with a social provider using the **same email**, the social provider is automatically linked to the existing account
- If a user registers via social provider and later wants to add a password, they go through a "set password" flow (not "reset" — there is no previous password)
- A user can have multiple auth providers linked simultaneously (e.g., PASSWORD + GOOGLE)
- Unlinking a provider is allowed only if at least one other provider remains
- The provider's email must match the user's email at link time

**Social Registration:**
- Users who register via social provider skip email verification (the provider has already verified the email)
- Username is still required and must be set during first social login (prompted in onboarding)
- `fullName` is pre-filled from provider profile data if available

#### Token-Based Sessions

The platform uses a unified token mechanism for all users regardless of authentication method. Token lifetimes can differ by portal context for security:

| Context      | Access Token | Refresh Token | Purpose                                                |
|--------------|--------------|---------------|--------------------------------------------------------|
| Regular App  | 15 minutes   | 7 days        | Standard API authorization                             |
| Admin Portal | 15 minutes   | 4 hours       | Admin API authorization (shorter refresh for security) |

**Access Token Claims:**
- `sub`: userId (UUID)
- `email`: user email
- `system_role`: USER, ADMIN, or SUPERADMIN
- `iat`, `exp`: standard JWT timestamps

**Token Security Features:**

1. **Token Rotation:** Each refresh issues new tokens, invalidates old
2. **Token Families:** Related tokens grouped for theft detection
3. **Reuse Detection:** Reusing revoked token invalidates entire family
4. **Device Binding:** Optional binding to device fingerprint
5. **Concurrent Sessions:** Configurable limit (default: 5)

### 3.6 Integration Contract

The IAM context exposes identity information to other bounded contexts through a well-defined value object. Other contexts MUST NOT access IAM internals (User entity, credentials, sessions) directly.

#### AuthenticatedIdentity (Value Object)

This is what IAM provides to downstream contexts after successful authentication:

```
AuthenticatedIdentity:
  - userId: UUID
  - email: EmailAddress
  - displayName: String
  - systemRole: SystemRole (USER | ADMIN | SUPERADMIN)
  - adminPermissions: Set<AdminPermission>?  (only for ADMIN/SUPERADMIN, null for USER)
```

#### Anti-Corruption Layer

The Core Finance context translates `AuthenticatedIdentity` into its own domain concept, discarding IAM-specific details that are irrelevant to financial operations:

```
UserReference (Value Object in Core Finance):
  - userId: UUID
  - displayName: String

  The finance domain doesn't need to know about system roles, email,
  or admin permissions. It only needs to know WHO is performing an action,
  then checks domain permissions via AccountShare.
```

#### System-Level Authorization Rules

| Authorization Type       | Context      | Decision Basis                                                           |
|--------------------------|--------------|--------------------------------------------------------------------------|
| System portal access     | IAM          | `systemRole` — can this user access admin.emerald.com?                   |
| Admin capabilities       | IAM          | `adminPermissions` — can this admin manage master data?                  |
| Account operations       | Core Finance | `AccountShare.permissionLevel` — can this user edit this account?        |
| Transaction operations   | Core Finance | `AccountShare.permissionLevel` — can this user create transactions here? |

**Key Insight:** System-level authorization (IAM) and domain-level authorization (Core Finance) are fundamentally different concerns. IAM determines *which portals you can access*. Core Finance determines *what you can do with specific financial resources*. Conflating them would violate bounded context boundaries.

---

## 4. Data Lifecycle Management

### 4.1 Deletion Philosophy

The platform provides users with **complete control** over their data lifecycle:

1. **Soft Delete** - Mark as deleted, hide from normal views, retain for recovery
2. **Trash View** - Users can see all their soft-deleted items
3. **Recovery** - Restore soft-deleted items to active state
4. **Hard Delete** - Permanently remove data (with appropriate safeguards)
5. **Automatic Cleanup** - Soft-deleted items are hard-deleted after retention period

### 4.2 Deletion States

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ENTITY LIFECYCLE STATES                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐      ┌──────────────┐      ┌───────────────┐              │
│  │  ACTIVE  │─────►│ SOFT DELETED │─────►│ HARD DELETED  │              │
│  │          │      │   (Trash)    │      │  (Permanent)  │              │
│  └──────────┘      └──────────────┘      └───────────────┘              │
│       ▲                   │                                             │
│       │                   │                                             │
│       └───────────────────┘                                             │
│            Recover                                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**State Definitions:**

| State        | Visibility      | Recoverable | Queryable | In Calculations |
|--------------|-----------------|-------------|-----------|-----------------|
| Active       | Normal views    | N/A         | Yes       | Yes             |
| Soft Deleted | Trash view only | Yes         | With flag | No              |
| Hard Deleted | Gone            | No          | No        | No              |

### 4.3 Soft Delete Implementation

**Entity Attributes for Soft Delete:**

| Attribute             | Type       | Description                               |
|-----------------------|------------|-------------------------------------------|
| deletedAt             | Timestamp? | When soft delete occurred (null = active) |
| deletedBy             | UserId?    | Who performed the deletion                |
| deletionReason        | String?    | Optional reason for deletion              |
| hardDeleteScheduledAt | Timestamp? | When automatic hard delete will occur     |

**Domain Rules:**
- Soft deleted entities are excluded from normal queries by default
- Soft deleted entities can be included with explicit `includeDeleted` flag
- Soft delete is reversible until hard delete occurs
- Child entities follow parent soft delete (cascade)

### 4.4 Hard Delete Implementation

**Hard Delete Options:**

1. **User-Initiated:** User explicitly requests permanent deletion from trash
2. **Automatic:** Retention period expires
3. **Admin-Initiated:** Compliance or support action (with audit)

**Hard Delete Safeguards:**

| Safeguard              | Description                                     |
|------------------------|-------------------------------------------------|
| Confirmation Required  | User must confirm with explicit action          |
| Cooling-Off Period     | 24-hour delay before execution (configurable)   |
| Audit Trail            | Final audit record created before deletion      |
| Cascade Warning        | User informed of all items that will be deleted |
| Non-Reversible Warning | Clear indication that action cannot be undone   |

**Hard Delete Process:**
1. User requests hard delete
2. System calculates cascade (all dependent entities)
3. User confirms with full cascade visibility
4. Cooling-off period begins (optional, based on entity type)
5. Final audit record created
6. Data permanently removed
7. Confirmation sent to user

### 4.5 Retention Policies

Retention periods are **configurable per entity type** and determine how long soft-deleted items are kept before automatic hard deletion.

**Default Retention Periods:**

| Entity Type       | Default Retention | Rationale                                |
|-------------------|-------------------|------------------------------------------|
| User Account      | 30 days           | Allow recovery from accidental deletion  |
| Financial Account | 7 years           | Regulatory compliance (SOX, tax records) |
| Transaction       | 7 years           | Regulatory compliance                    |
| Card              | 90 days           | Lower recovery need                      |
| Account Share     | 30 days           | Access recovery window                   |
| Taxonomy          | 7 days            | Lower importance                         |
| Taxonomy Term     | 7 days            | Lower importance                         |
| Bank Connection   | 7 days            | Security consideration                   |

**Retention Policy Entity:**

| Attribute            | Description                                      |
|----------------------|--------------------------------------------------|
| entityType           | Which entity type this policy applies to         |
| retentionPeriod      | Duration (RetentionPeriod value object)          |
| autoHardDelete       | Whether to automatically hard delete             |
| requiresConfirmation | Whether user confirmation needed for hard delete |
| coolingOffPeriod     | Delay before hard delete executes                |
| complianceReason     | Why this retention is required                   |

**Policy Hierarchy:**
1. Regulatory minimum (cannot be reduced)
2. Platform default
3. User preference (can only increase, not decrease)

### 4.6 Trash Management

**Trash View Capabilities:**

| Capability            | Description                                   |
|-----------------------|-----------------------------------------------|
| View All Deleted      | See all soft-deleted items user has access to |
| Filter by Type        | Filter trash by entity type                   |
| Sort by Deletion Date | Order by when deleted                         |
| View Time Remaining   | See when item will be hard deleted            |
| Bulk Recovery         | Recover multiple items at once                |
| Bulk Hard Delete      | Permanently delete multiple items             |
| Search Deleted        | Search within deleted items                   |

**Trash Domain Rules:**
- Only Owner can view deleted items for an account
- Editors can view deleted transactions they created
- Recovery restores to previous state (including shares)
- Cannot recover if parent is deleted (must recover parent first)
- Hard delete cascade: deleting parent hard-deletes children in trash

### 4.7 Cascade Behavior

When an entity is deleted (soft or hard), related entities are affected:

**Soft Delete Cascades:**

| Parent               | Children Affected | Behavior     |
|----------------------|-------------------|--------------|
| User                 | Accounts (owned)  | Soft deleted |
| User                 | Taxonomies        | Soft deleted |
| Account              | Transactions      | Soft deleted |
| Account              | Cards             | Soft deleted |
| Account              | Shares            | Soft deleted |
| Taxonomy             | Terms             | Soft deleted |
| Transaction (parent) | Split children    | Soft deleted |

**Hard Delete Cascades:**

| Parent               | Children Affected           | Behavior     |
|----------------------|-----------------------------|--------------|
| User                 | Everything owned            | Hard deleted |
| Account              | Transactions, Cards, Shares | Hard deleted |
| Taxonomy             | Terms                       | Hard deleted |
| Transaction (parent) | Split children              | Hard deleted |

**Recovery Cascades:**
- Recovering a parent does NOT automatically recover children
- Children must be recovered individually
- Exception: Split transactions recover together

---

## 5. Core Domain: Financial Tracking

### 5.1 Domain Authorization

Domain authorization in Core Finance is entirely separate from system-level authorization in IAM. The Core Finance context determines what a user can do with specific financial resources based on the **AccountShare** entity, not on system roles.

#### UserReference (Value Object)

The Core Finance context receives identity from IAM through the Anti-Corruption Layer and reduces it to a minimal value object:

```
UserReference:
  - userId: UUID
  - displayName: String

  No roles, no email, no credentials. The finance domain only needs
  to know WHO is performing an action, then checks domain permissions.
```

#### Permission Hierarchy

Account-level permissions define what users can do with shared accounts. This is a **business rule** of the Account Aggregate, not an IAM concern.

```
OWNER (3)
  └── Can: View, Edit, Delete, Share, Transfer Ownership
      │
      ▼
EDITOR (2)
  └── Can: View, Edit (transactions, cards)
      │   Cannot: Delete account, Share, Manage shares
      │
      ▼
VIEWER (1)
  └── Can: View only
      Cannot: Any modifications
```

**Permission Level is a Value Object with comparison logic:**
```
PermissionLevel:
  - OWNER = 3
  - EDITOR = 2
  - VIEWER = 1

  - has_at_least(required: PermissionLevel) → boolean
  - can_grant(level: PermissionLevel) → boolean (only owner can grant)
```

#### Resource Access Matrix

| Resource             | Owner | Editor   | Viewer   | No Share |
|----------------------|-------|----------|----------|----------|
| View Account         | ✓     | ✓        | ✓        | ✗        |
| Edit Account Details | ✓     | ✗        | ✗        | ✗        |
| Delete Account       | ✓     | ✗        | ✗        | ✗        |
| View Transactions    | ✓     | ✓        | ✓        | ✗        |
| Create Transaction   | ✓     | ✓        | ✗        | ✗        |
| Edit Transaction     | ✓     | ✓        | ✗        | ✗        |
| Delete Transaction   | ✓     | ✓        | ✗        | ✗        |
| View Cards           | ✓     | ✓        | ✓        | ✗        |
| Manage Cards         | ✓     | ✓        | ✗        | ✗        |
| View Shares          | ✓     | Own only | Own only | ✗        |
| Manage Shares        | ✓     | ✗        | ✗        | ✗        |
| View Deleted Items   | ✓     | ✓        | ✗        | ✗        |
| Recover Deleted      | ✓     | ✗        | ✗        | ✗        |
| Hard Delete          | ✓     | ✗        | ✗        | ✗        |

**Key Principle:** Domain authorization uses `AccountShare`, not IAM roles. A SUPERADMIN has no special financial access — they must be explicitly shared on an account like any other user.

### 5.2 Account Aggregate

The Account Aggregate is the central consistency boundary for financial data.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ACCOUNT AGGREGATE                                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      Account (ROOT)                               │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │  │
│  │  Identity: accountId (UUID)                                       │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │  │
│  │                                                                   │  │
│  │  Value Objects:                                                   │  │
│  │    • accountName: AccountName                                     │  │
│  │    • currency: Currency (IMMUTABLE after creation)                │  │
│  │    • openingBalance: Money                                        │  │
│  │    • iban: IBAN? (IMMUTABLE after creation)                       │  │
│  │                                                                   │  │
│  │  References:                                                      │  │
│  │    • accountTypeId: UUID (to master data)                         │  │
│  │    • financialInstitutionId: UUID (to master data)                │  │
│  │                                                                   │  │
│  │  Computed:                                                        │  │
│  │    • currentBalance: Money (openingBalance + Σ transactions)      │  │
│  │    • transactionCount: int                                        │  │
│  │                                                                   │  │
│  │  Domain Methods:                                                  │  │
│  │    • addTransaction(transaction) → validates currency match       │  │
│  │    • calculateBalance() → aggregates all active transactions      │  │
│  │    • shareWith(user, permission) → validates not already shared   │  │
│  │    • revokeShare(user) → validates user has share                 │  │
│  │    • transferOwnership(newOwner) → validates new owner exists     │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│         │                    │                    │                     │
│         ▼                    ▼                    ▼                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │ Transactions│    │   Cards     │    │Account      │                  │
│  │ (many)      │    │   (many)    │    │  Shares     │                  │
│  │             │    │             │    │   (many)    │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│                                                                         │
│  INVARIANTS:                                                            │
│    • Exactly ONE owner share must exist at all times                    │
│    • All transaction currencies MUST match account currency             │
│    • Balance is ALWAYS calculable from transactions                     │
│    • One active share per user maximum                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Account Entity

**Attributes:**

| Attribute              | Type        | Mutable | Description                           |
|------------------------|-------------|---------|---------------------------------------|
| accountId              | UUID        | No      | Unique identifier                     |
| accountName            | AccountName | Yes     | User-defined name                     |
| accountTypeId          | UUID        | Yes     | Reference to account type master data |
| financialInstitutionId | UUID        | Yes     | Reference to institution master data  |
| currency               | Currency    | No      | Account currency (immutable)          |
| openingBalance         | Money       | No      | Initial balance (immutable)           |
| iban                   | IBAN?       | No      | Bank account number (immutable)       |
| notes                  | String?     | Yes     | User notes                            |
| createdAt              | Timestamp   | No      | Creation time                         |
| updatedAt              | Timestamp   | Auto    | Last update time                      |
| deletedAt              | Timestamp?  | Yes     | Soft delete timestamp                 |

**Domain Methods:**

```
Account:
  // Transaction management
  + addTransaction(transaction: Transaction) → void
      Validates: currency matches, account is active
      Raises: CurrencyMismatchError, AccountNotActiveError

  + addTransactions(transactions: List<Transaction>) → BulkResult
      Validates: all currencies match, account is active
      Returns: success count, failure details

  + calculateBalance() → Money
      Returns: openingBalance + sum of all active transactions

  + getTransactionsInRange(range: DateRange) → List<Transaction>

  // Sharing management
  + shareWith(user: User, permission: PermissionLevel) → AccountShare
      Validates: not already shared, permission not OWNER
      Raises: AlreadySharedError, CannotGrantOwnerError

  + updateSharePermission(user: User, newPermission: PermissionLevel) → void
      Validates: share exists, not changing owner permission

  + revokeShare(user: User) → void
      Validates: share exists, not revoking owner

  + transferOwnership(newOwner: User) → void
      Validates: new owner exists, has at least EDITOR share

  // Card management
  + addCard(card: Card) → void
  + removeCard(cardId: UUID) → void

  // Lifecycle
  + softDelete(deletedBy: User, reason: String?) → void
  + recover() → void
      Validates: is soft deleted
```

### 5.4 Transaction Entity

**Attributes:**

| Attribute           | Type          | Mutable | Description                    |
|---------------------|---------------|---------|--------------------------------|
| transactionId       | UUID          | No      | Unique identifier              |
| accountId           | UUID          | No      | Parent account                 |
| transactionDate     | Date          | Yes     | When transaction occurred      |
| valueDate           | Date?         | Yes     | When value applied             |
| amount              | Money         | Yes     | Amount (currency from account) |
| originalDescription | String        | No      | Immutable original description |
| userDescription     | String?       | Yes     | User-edited description        |
| merchant            | String?       | Yes     | Merchant name                  |
| comments            | String?       | Yes     | User notes                     |
| reviewStatus        | ReviewStatus  | Yes     | To Review / Reviewed           |
| cardId              | UUID?         | Yes     | Card used (optional)           |
| parentTransactionId | UUID?         | No      | Parent if this is a split      |
| importSource        | ImportSource? | No      | Where transaction came from    |
| externalId          | String?       | No      | ID from external system        |
| createdAt           | Timestamp     | No      | Creation time                  |
| createdBy           | UUID          | No      | Who created                    |
| deletedAt           | Timestamp?    | Yes     | Soft delete timestamp          |

**Import Source Value Object:**

| Attribute  | Description                              |
|------------|------------------------------------------|
| sourceType | Manual, BankImport, BulkImport, API      |
| sourceId   | Identifier of import batch or connection |
| importedAt | When imported                            |

**Domain Methods:**

```
Transaction:
  // Splitting
  + split(splits: List<SplitRequest>) → List<Transaction>
      Validates:
        - At least 2 splits
        - Split amounts sum exactly to this.amount
        - This is not already a split child
        - All splits have same currency
      Returns: Created child transactions
      Raises: InvalidSplitError, AlreadySplitChildError

  + joinSplits() → void
      Validates: This is a split parent with children
      Effect: Hard deletes all child transactions

  + isSplitParent() → boolean
  + isSplitChild() → boolean
  + getSplitChildren() → List<Transaction>

  // Review workflow
  + markAsReviewed() → void
  + markForReview() → void

  // Lifecycle
  + softDelete(deletedBy: User) → void
      Effect: If parent, soft deletes children too
```

### 5.5 Card Entity

**Attributes:**

| Attribute            | Type         | Mutable | Description             |
|----------------------|--------------|---------|-------------------------|
| cardId               | UUID         | No      | Unique identifier       |
| accountId            | UUID         | No      | Parent account          |
| cardType             | CardType     | No      | Credit or Debit         |
| cardName             | String       | Yes     | Display name            |
| lastFourDigits       | CardLastFour | No      | Last 4 digits           |
| cardNetwork          | CardNetwork? | Yes     | Visa, Mastercard, etc.  |
| expiryMonth          | Int          | Yes     | Expiration month (1-12) |
| expiryYear           | Int          | Yes     | Expiration year         |
| creditLimit          | Money?       | Yes     | For credit cards        |
| issuingInstitutionId | UUID?        | Yes     | Card issuer             |
| notes                | String?      | Yes     | User notes              |
| deletedAt            | Timestamp?   | Yes     | Soft delete timestamp   |

**Card Types:** CreditCard, DebitCard
**Card Networks:** Visa, Mastercard, AmericanExpress, Discover, Other

### 5.6 Account Share Entity

**Attributes:**

| Attribute       | Type            | Mutable | Description                |
|-----------------|-----------------|---------|----------------------------|
| shareId         | UUID            | No      | Unique identifier          |
| accountId       | UUID            | No      | Account being shared       |
| userId          | UUID            | No      | User with access           |
| permissionLevel | PermissionLevel | Yes     | Access level               |
| grantedBy       | UUID            | No      | Who granted                |
| grantedAt       | Timestamp       | No      | When granted               |
| updatedAt       | Timestamp       | Auto    | Last permission change     |
| deletedAt       | Timestamp?      | Yes     | When revoked (soft delete) |

**Domain Rules:**
- Each account MUST have exactly one OWNER share
- Owner share cannot be deleted (only transferred)
- Maximum one active share per user per account
- Cannot grant OWNER permission (use transferOwnership)
- Revoking is soft delete (preserves history)

### 5.7 Bulk Transaction Operations

**Bulk Create:**

```
BulkTransactionRequest:
  + accountId: UUID
  + transactions: List<TransactionInput> (max 1000)

BulkTransactionResult:
  + successCount: int
  + failureCount: int
  + createdTransactions: List<Transaction>
  + failures: List<BulkFailure>

BulkFailure:
  + index: int (position in input list)
  + input: TransactionInput
  + errorCode: String
  + errorMessage: String
```

**Domain Processing:**
1. Validate account exists and user has EDITOR+ permission
2. Validate all transaction currencies match account
3. Process in batches of 100 (configurable)
4. Return detailed results with per-item status
5. Emit `TransactionsBulkCreated` event

**Bulk Operations Support:**
- Bulk create (up to 1000 at once)
- Bulk update (review status, category)
- Bulk delete (soft delete)
- Bulk recover (from trash)

### 5.8 Balance Calculation

**Balance is ALWAYS calculated, never stored:**

```
Domain Rule: Account Balance Calculation

currentBalance = openingBalance + Σ(transaction.amount)
  where transaction.deletedAt IS NULL
  and transaction.parentTransactionId IS NULL (exclude split parents from double-counting)

Note: Split children are counted, parent is excluded when split exists
```

**Why calculated, not stored:**
- Single source of truth (transactions)
- No sync issues
- Audit trail automatic
- Easier recovery from errors

**Performance consideration:** Cache balance in application layer with invalidation on transaction changes.

---

## 6. Supporting Domain: Classification

### 6.1 Taxonomy Aggregate

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       TAXONOMY AGGREGATE                                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      Taxonomy (ROOT)                              │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │  │
│  │  Identity: taxonomyId (UUID)                                      │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │  │
│  │                                                                   │  │
│  │  Attributes:                                                      │  │
│  │    • name: TaxonomyName (unique per user)                         │  │
│  │    • description: String?                                         │  │
│  │    • ownerId: UUID                                                │  │
│  │    • isSystem: boolean (system-provided, not deletable)           │  │
│  │                                                                   │  │
│  │  Domain Methods:                                                  │  │
│  │    • addTerm(name, parentId?) → validates uniqueness              │  │
│  │    • moveTerm(termId, newParentId) → validates no cycles          │  │
│  │    • renameTerm(termId, newName) → validates uniqueness           │  │
│  │    • deleteTerm(termId) → cascade deletes children                │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Taxonomy Terms (hierarchical tree)                 │    │
│  │                                                                 │    │
│  │    Root Terms (parentId = null)                                 │    │
│  │      └── Child Terms                                            │    │
│  │            └── Grandchild Terms                                 │    │
│  │                  └── ... (unlimited depth)                      │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  INVARIANTS:                                                            │
│    • Term names unique within taxonomy (case-insensitive)               │
│    • No circular references in hierarchy                                │
│    • Parent term must belong to same taxonomy                           │
│    • System taxonomies cannot be deleted by users                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Taxonomy Entity

**Attributes:**

| Attribute   | Type         | Mutable | Description                 |
|-------------|--------------|---------|-----------------------------|
| taxonomyId  | UUID         | No      | Unique identifier           |
| ownerId     | UUID         | No      | User who owns this taxonomy |
| name        | TaxonomyName | Yes     | Display name                |
| description | String?      | Yes     | Optional description        |
| isSystem    | Boolean      | No      | System-provided (immutable) |
| createdAt   | Timestamp    | No      | Creation time               |
| deletedAt   | Timestamp?   | Yes     | Soft delete timestamp       |

**System Taxonomies:**
- Categories (default spending categories)

### 6.3 Taxonomy Term Entity

**Attributes:**

| Attribute    | Type       | Mutable | Description                  |
|--------------|------------|---------|------------------------------|
| termId       | UUID       | No      | Unique identifier            |
| taxonomyId   | UUID       | No      | Parent taxonomy              |
| name         | TermName   | Yes     | Display name                 |
| description  | String?    | Yes     | Optional description         |
| parentTermId | UUID?      | Yes     | Parent term (null = root)    |
| sortOrder    | Int        | Yes     | Display order among siblings |
| createdAt    | Timestamp  | No      | Creation time                |
| deletedAt    | Timestamp? | Yes     | Soft delete timestamp        |

**Computed Properties:**
- `path: TaxonomyPath` - Full path from root ("Food > Restaurants > Italian")
- `depth: Int` - Level in tree (0 = root)
- `hasChildren: Boolean` - Whether has child terms
- `childCount: Int` - Number of direct children

**Domain Rules for Hierarchy:**

```
Taxonomy.addTerm(name, parentId?):
  1. Normalize name (trim, consistent casing)
  2. Validate name unique within taxonomy
  3. If parentId provided:
     a. Validate parent exists in this taxonomy
     b. Validate parent is not deleted
  4. Create term with next sortOrder among siblings

Taxonomy.moveTerm(termId, newParentId):
  1. Validate term exists and belongs to this taxonomy
  2. If newParentId is not null:
     a. Validate new parent exists in this taxonomy
     b. Validate new parent is not the term itself
     c. Validate new parent is not a descendant of term (no cycles)
  3. Update parentTermId
  4. Recalculate sortOrder for siblings

Taxonomy.detectCycle(termId, newParentId):
  current = newParentId
  while current is not null:
    if current == termId:
      return true // Cycle detected!
    current = terms[current].parentTermId
  return false
```

### 6.4 Transaction Categorization

**Transaction-Term Association:**

| Attribute     | Description                               |
|---------------|-------------------------------------------|
| transactionId | Transaction being categorized             |
| termId        | Term being applied                        |
| taxonomyId    | Which taxonomy the term belongs to        |
| assignedAt    | When assigned                             |
| assignedBy    | Who assigned (user or system)             |
| confidence    | For auto-categorization: confidence score |

**Rules:**
- A transaction can have multiple terms from DIFFERENT taxonomies
- A transaction can have only ONE term from each taxonomy
- Terms can be assigned manually or automatically (rules/ML)
- Assigning term to split child does not affect parent

**Auto-Categorization (Future):**
- Rule-based: "If merchant contains 'Amazon' → Shopping"
- ML-based: Learn from user's categorization patterns
- Suggestion mode: Suggest but don't auto-apply

---

## 7. Supporting Domain: External Integrations

### 7.1 Bank Connection Aggregate

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BANK CONNECTION AGGREGATE                            │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                   BankConnection (ROOT)                           │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │  │
│  │  Identity: connectionId (UUID)                                    │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │  │
│  │                                                                   │  │
│  │  Attributes:                                                      │  │
│  │    • userId: UUID (owner)                                         │  │
│  │    • accountId: UUID (linked Emerald account)                     │  │
│  │    • provider: BankProvider (Plaid, Teller, etc.)                 │  │
│  │    • status: ConnectionStatus                                     │  │
│  │    • externalAccountId: String (ID at provider)                   │  │
│  │    • lastSyncAt: Timestamp?                                       │  │
│  │    • nextSyncScheduledAt: Timestamp?                              │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│         │                    │                                          │
│         ▼                    ▼                                          │
│  ┌─────────────┐    ┌─────────────────────┐                             │
│  │SyncHistory  │    │PendingTransactions  │                             │
│  │  (many)     │    │    (staging)        │                             │
│  └─────────────┘    └─────────────────────┘                             │
│                                                                         │
│  Connection Statuses:                                                   │
│    • Active - Connected and syncing                                     │
│    • Pending - Awaiting user authentication                             │
│    • NeedsReauth - Credentials expired                                  │
│    • Error - Sync failing                                               │
│    • Disconnected - User disconnected                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Bank Connection Entity

**Attributes:**

| Attribute           | Type             | Description                     |
|---------------------|------------------|---------------------------------|
| connectionId        | UUID             | Unique identifier               |
| userId              | UUID             | User who owns this connection   |
| accountId           | UUID             | Emerald account to sync to      |
| provider            | BankProvider     | Which aggregation provider      |
| status              | ConnectionStatus | Current state                   |
| externalAccountId   | String           | Account ID at provider          |
| institutionId       | UUID             | Financial institution reference |
| accessToken         | EncryptedToken   | Provider access credentials     |
| lastSyncAt          | Timestamp?       | Last successful sync            |
| lastSyncError       | String?          | Last error message              |
| nextSyncScheduledAt | Timestamp?       | Next scheduled sync             |
| syncFrequency       | Duration         | How often to sync               |
| createdAt           | Timestamp        | When connected                  |
| deletedAt           | Timestamp?       | Soft delete                     |

**Bank Providers:**
- Plaid
- Teller
- MX
- Yodlee
- Manual (for manual imports)

**Connection Status Flow:**

```
                    ┌──────────────┐
      User starts   │   Pending    │
      connection    └──────┬───────┘
                           │ User completes auth
                           ▼
                    ┌──────────────┐
                    │    Active    │◄────────────────┐
                    └──────┬───────┘                 │
                           │                         │ User reauths
              ┌────────────┼────────────┐            │
              │            │            │            │
    Sync fails│     Creds  │   User     │            │
    repeatedly│     expire │ disconnects│            │
              ▼            ▼            ▼            │
       ┌──────────┐ ┌───────────┐ ┌──────────────┐   │
       │  Error   │ │NeedsReauth│ │ Disconnected │   │
       └──────────┘ └─────┬─────┘ └──────────────┘   │
                          │                          │
                          └──────────────────────────┘
```

### 7.3 Sync History

**Attributes:**

| Attribute             | Type       | Description              |
|-----------------------|------------|--------------------------|
| syncId                | UUID       | Unique identifier        |
| connectionId          | UUID       | Parent connection        |
| startedAt             | Timestamp  | Sync start time          |
| completedAt           | Timestamp? | Sync completion time     |
| status                | SyncStatus | Success, Failed, Partial |
| transactionsFound     | Int        | Total from provider      |
| transactionsImported  | Int        | New transactions created |
| transactionsDuplicate | Int        | Skipped as duplicates    |
| transactionsUpdated   | Int        | Existing updated         |
| errorMessage          | String?    | If failed, why           |

### 7.4 Pending Transactions (Staging)

When transactions are imported, they go to a staging area first:

**Attributes:**

| Attribute            | Type             | Description                 |
|----------------------|------------------|-----------------------------|
| pendingId            | UUID             | Staging record ID           |
| connectionId         | UUID             | Source connection           |
| externalId           | String           | ID from provider            |
| rawData              | JSON             | Original data from provider |
| normalizedData       | TransactionInput | Converted to our format     |
| matchStatus          | MatchStatus      | New, Duplicate, NeedsReview |
| matchedTransactionId | UUID?            | If duplicate, which one     |
| createdAt            | Timestamp        | When received               |

**Match Statuses:**
- **New** - No matching transaction found, will be imported
- **Duplicate** - Exact match found, will be skipped
- **NeedsReview** - Possible match, user should verify
- **UserApproved** - User confirmed as new
- **UserRejected** - User confirmed as duplicate

### 7.5 Import Processing

**Import Flow:**

```
Provider API
     │
     ▼
┌─────────────────┐
│ Raw Transactions│
│   from Bank     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Normalizer    │  Convert to internal format
│   (per provider)│  Handle currency, dates, amounts
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Deduplication  │  Check for existing transactions
│    Service      │  by externalId, date+amount+description
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌──────────┐
│ New   │ │Duplicate │
└───┬───┘ └────┬─────┘
    │          │
    ▼          ▼
┌───────────┐ ┌──────────┐
│  Create   │ │  Skip or │
│Transaction│ │  Update  │
└───────────┘ └──────────┘
```

**Deduplication Rules:**
1. ExternalId match (same provider) → Definite duplicate
2. Same date + amount + description → Likely duplicate
3. Same date + amount (within $0.01) → Possible duplicate
4. User-defined rules for specific merchants

---

## 8. Cross-Cutting Concerns

### 8.1 Audit Logging

**Every state change is recorded:**

| Attribute  | Description                    |
|------------|--------------------------------|
| auditId    | Unique identifier              |
| timestamp  | When action occurred           |
| actorType  | User, System                   |
| actorId    | Who performed action           |
| action     | What was done                  |
| entityType | What type of entity            |
| entityId   | Which entity                   |
| oldState   | State before (JSON)            |
| newState   | State after (JSON)             |
| metadata   | Additional context             |
| ipAddress  | Client IP                      |
| userAgent  | Client info                    |
| requestId  | Correlation ID                 |
| result     | Success, Failure, Partial      |

**Audit Actions:**

| Category           | Actions                                                                                       |
|--------------------|-----------------------------------------------------------------------------------------------|
| Authentication     | Login, Logout, LoginFailed, PasswordChanged, TokenRefreshed, TokenRevoked                     |
| User Lifecycle     | Registered, Verified, Updated, Suspended, Deleted, Recovered, HardDeleted                     |
| Account Operations | Created, Updated, Deleted, Recovered, HardDeleted, Shared, ShareRevoked, OwnershipTransferred |
| Transactions       | Created, Updated, Deleted, Recovered, Split, Joined, BulkCreated, Imported                    |
| Bank Connection    | Connected, Synced, SyncFailed, Disconnected, ReauthRequired                                   |
| Admin Actions      | MasterDataCreated, MasterDataUpdated, UserSuspended, PolicyChanged                            |

**Audit Rules:**
- Audit logs are IMMUTABLE (write-once)
- Audit logs are NEVER deleted (archived after retention)
- All entities have `createdBy`, `updatedBy` fields populated from audit context
- Audit captures BEFORE and AFTER states for all updates

### 8.2 Notification System

**Notification Types:**

| Type                 | Trigger                           | Channels            |
|----------------------|-----------------------------------|---------------------|
| AccountShared        | Someone shares account with you   | Email, Push, In-App |
| ShareRevoked         | Access removed                    | Email, In-App       |
| TransactionsImported | Bank sync complete                | Push, In-App        |
| SyncFailed           | Bank connection issue             | Email, Push         |
| RetentionWarning     | Item will be hard-deleted soon    | Email, In-App       |
| SecurityAlert        | Suspicious login, password change | Email, Push         |

**Notification Preferences:**
- Per-notification-type settings
- Per-channel settings
- Quiet hours
- Digest options (immediate, daily, weekly)

### 8.3 Multi-Currency Support

**Currency Operations:**

| Operation                   | Behavior                                             |
|-----------------------------|------------------------------------------------------|
| Same Currency Addition      | Direct arithmetic                                    |
| Different Currency Addition | Error - must convert first                           |
| Currency Conversion         | Requires explicit exchange rate                      |
| Display Conversion          | Convert to user's display currency using latest rate |

**Exchange Rates:**
- Sourced from official APIs (ECB, etc.)
- Updated daily minimum
- Historical rates NOT stored (only current)
- Conversion for display only; actual amounts unchanged

**Multi-Currency Reporting:**
- Total net worth in user's preferred currency
- Per-account balances in native currency
- Clear indication of converted vs. native amounts

### 8.4 Search & Filtering

**Transaction Search:**

| Filter         | Description                    |
|----------------|--------------------------------|
| dateRange      | Transactions within date range |
| amountRange    | Min and/or max amount          |
| accounts       | Specific accounts              |
| reviewStatus   | To Review, Reviewed            |
| hasCategory    | Categorized or not             |
| categories     | Specific taxonomy terms        |
| merchants      | Specific merchants             |
| description    | Text search in descriptions    |
| cards          | Specific cards used            |
| importSource   | Manual, bank import, etc.      |
| includeDeleted | Include soft-deleted           |

**Full-Text Search:**
- Search across descriptions, merchants, comments
- Fuzzy matching for typos
- Suggestions based on history

### 8.5 Data Export

**Export Formats:**
- CSV (transactions, accounts)
- JSON (full data export)
- PDF (reports, statements)
- OFX/QFX (financial software compatibility)

**Export Scopes:**
- All data (GDPR portability)
- Specific accounts
- Date range
- Specific entity types

---

## 9. Business Rules Catalog

### 9.1 IAM Context Rules

**All rules enforced in Domain Layer:**

| Rule ID | Rule                                                    | Domain Location                       |
|---------|---------------------------------------------------------|---------------------------------------|
| ID-001  | Email must be valid format                              | EmailAddress value object             |
| ID-002  | Email globally unique (one identity space)              | User aggregate / domain service       |
| ID-003  | Username unique globally (including 90-day deleted)     | User aggregate / domain service       |
| ID-004  | Password minimum 12 characters                          | Password value object                 |
| ID-005  | Password must have uppercase, lowercase, digit, special | Password value object                 |
| ID-006  | Password cannot match last 5 passwords                  | User aggregate                        |
| ID-007  | SUPERADMIN cannot be deleted or demoted                 | User aggregate invariant              |
| ID-008  | SUPERADMIN provisioned at install only (no API create)  | User domain service                   |
| ID-009  | At least one SUPERADMIN must exist at all times         | User domain service                   |
| ID-010  | ADMIN cannot grant permissions they don't have          | User aggregate                        |
| ID-011  | User must verify email for full functionality           | User aggregate state machine          |
| ID-012  | systemRole defaults to USER on registration             | User aggregate                        |
| ID-013  | adminPermissions must be null when systemRole is USER   | User aggregate invariant              |
| ID-014  | ADMIN must have at least one admin permission           | User aggregate invariant              |
| ID-015  | Non-ADMIN/SUPERADMIN cannot access admin portal         | IAM authorization (403 Forbidden)     |
| ID-016  | User must have at least one auth provider at all times  | User aggregate invariant              |
| ID-017  | Password required when authProviders contains PASSWORD  | User aggregate invariant              |
| ID-018  | Social login with matching email links to existing user | User domain service (account linking) |
| ID-019  | Cannot unlink last remaining auth provider              | User aggregate invariant              |
| ID-020  | Social registration auto-verifies email                 | User aggregate state machine          |

### 9.2 Account Aggregate Rules

| Rule ID | Rule                                            | Domain Location                    |
|---------|-------------------------------------------------|------------------------------------|
| ACC-001 | Account name unique per user (case-insensitive) | Account aggregate / domain service |
| ACC-002 | Currency cannot change after creation           | Account entity (immutable field)   |
| ACC-003 | Opening balance cannot change after creation    | Account entity (immutable field)   |
| ACC-004 | IBAN cannot change after creation               | Account entity (immutable field)   |
| ACC-005 | Account must have exactly one OWNER share       | Account aggregate invariant        |
| ACC-006 | One active share per user per account           | Account aggregate                  |
| ACC-007 | Cannot grant OWNER permission (use transfer)    | Account.shareWith()                |
| ACC-008 | Owner cannot revoke own ownership               | Account.revokeShare()              |
| ACC-009 | Balance = openingBalance + sum(transactions)    | Account.calculateBalance()         |
| ACC-010 | Only owner can transfer ownership               | Account.transferOwnership()        |
| ACC-011 | New owner must have existing share              | Account.transferOwnership()        |

### 9.3 Transaction Rules

| Rule ID | Rule                                             | Domain Location          |
|---------|--------------------------------------------------|--------------------------|
| TXN-001 | Transaction currency must match account currency | Account.addTransaction() |
| TXN-002 | Original description is immutable                | Transaction entity       |
| TXN-003 | Split amounts must sum exactly to parent         | Transaction.split()      |
| TXN-004 | Minimum 2 splits required                        | Transaction.split()      |
| TXN-005 | Cannot split a split child                       | Transaction.split()      |
| TXN-006 | Soft deleting parent soft deletes children       | Transaction.softDelete() |
| TXN-007 | Zero amount transactions allowed                 | (No rule against)        |
| TXN-008 | External ID unique per connection (for imports)  | Account.addTransaction() |

### 9.4 Card Rules

| Rule ID | Rule                                          | Domain Location           |
|---------|-----------------------------------------------|---------------------------|
| CRD-001 | Card must belong to an account                | Card entity invariant     |
| CRD-002 | Last four digits exactly 4 numeric characters | CardLastFour value object |
| CRD-003 | Expiry month 1-12                             | Card entity validation    |
| CRD-004 | Credit limit positive if specified            | Card entity validation    |

### 9.5 Sharing Rules

| Rule ID | Rule                                          | Domain Location                        |
|---------|-----------------------------------------------|----------------------------------------|
| SHR-001 | Only OWNER can share                          | Account.shareWith() permission check   |
| SHR-002 | Only OWNER can revoke                         | Account.revokeShare() permission check |
| SHR-003 | Cannot share with yourself                    | Account.shareWith()                    |
| SHR-004 | Permission hierarchy: Owner > Editor > Viewer | PermissionLevel value object           |
| SHR-005 | Higher permission includes lower capabilities | PermissionLevel.hasAtLeast()           |

### 9.6 Taxonomy Rules

| Rule ID | Rule                                | Domain Location                     |
|---------|-------------------------------------|-------------------------------------|
| TAX-001 | Taxonomy name unique per user       | Taxonomy aggregate / domain service |
| TAX-002 | Term name unique within taxonomy    | Taxonomy.addTerm()                  |
| TAX-003 | Term cannot be its own parent       | Taxonomy.moveTerm()                 |
| TAX-004 | No circular references in hierarchy | Taxonomy.moveTerm() cycle detection |
| TAX-005 | Parent must be in same taxonomy     | Taxonomy.moveTerm()                 |
| TAX-006 | System taxonomies cannot be deleted | Taxonomy.softDelete()               |

### 9.7 Deletion Rules

| Rule ID | Rule                                                   | Domain Location             |
|---------|--------------------------------------------------------|-----------------------------|
| DEL-001 | Soft delete sets deletedAt timestamp                   | Entity.softDelete()         |
| DEL-002 | Soft delete schedules hard delete per retention policy | Entity.softDelete()         |
| DEL-003 | Children soft deleted with parent                      | Parent.softDelete() cascade |
| DEL-004 | Recovery clears deletedAt                              | Entity.recover()            |
| DEL-005 | Cannot recover if parent is deleted                    | Entity.recover()            |
| DEL-006 | Hard delete removes data permanently                   | Domain service              |
| DEL-007 | Hard delete requires confirmation                      | Application layer           |
| DEL-008 | Final audit record before hard delete                  | Domain event                |

### 9.8 Bank Connection Rules

| Rule ID | Rule                                            | Domain Location               |
|---------|-------------------------------------------------|-------------------------------|
| BNK-001 | One connection per account per provider         | BankConnection domain service |
| BNK-002 | Credentials encrypted at rest                   | BankConnection aggregate      |
| BNK-003 | Sync requires active connection status          | BankConnection.sync()         |
| BNK-004 | Disconnecting soft deletes pending transactions | BankConnection.disconnect()   |

---

## 10. Operational Requirements

### 10.1 Performance Targets

| Operation           | Target  | Notes                                   |
|---------------------|---------|-----------------------------------------|
| API Response (p95)  | < 200ms | Excluding bulk operations               |
| Balance Calculation | < 50ms  | For accounts with < 10,000 transactions |
| Transaction Search  | < 500ms | Across all user accounts                |
| Bulk Import (1000)  | < 30s   | With full validation                    |
| Bank Sync           | < 60s   | Depends on provider                     |

### 10.2 Scalability Considerations

| Aspect                   | Design              | Limit             |
|--------------------------|---------------------|-------------------|
| Transactions per account | Partitioned by date | No hard limit     |
| Accounts per user        | Indexed             | Recommended < 100 |
| Users                    | Shardable           | No hard limit     |
| Concurrent syncs         | Queue-based         | 10 per user       |

### 10.3 Availability

| Component     | Target | Recovery                       |
|---------------|--------|--------------------------------|
| API           | 99.9%  | Auto-scaling, multi-region     |
| Database      | 99.99% | Replication, failover          |
| Bank Sync     | 99%    | Retry with backoff             |
| Audit Logging | 99.99% | Async with guaranteed delivery |

### 10.4 Security Requirements

| Requirement           | Implementation               |
|-----------------------|------------------------------|
| Encryption at Rest    | AES-256 for sensitive fields |
| Encryption in Transit | TLS 1.3                      |
| Password Storage      | Argon2id                     |
| Token Storage         | SHA-256 hash                 |
| Session Management    | JWT with rotation            |
| Rate Limiting         | Per-user, per-endpoint       |
| Input Validation      | Domain layer                 |
| SQL Injection         | Parameterized queries        |
| XSS Prevention        | Output encoding              |

### 10.5 Compliance

| Regulation | Relevant Features                |
|------------|----------------------------------|
| GDPR       | Data export, deletion, consent   |
| SOX        | 7-year retention, audit trail    |
| PCI DSS    | No full card numbers, encryption |
| CCPA       | Data disclosure, deletion        |

---

## 11. Future Roadmap

### 11.1 Phase 1: Foundation (Current)
- Core account and transaction management
- User authentication and authorization
- Basic sharing and collaboration
- Soft delete with retention
- Bulk operations

### 11.2 Phase 2: Intelligence
- Auto-categorization with ML
- Spending insights and trends
- Anomaly detection
- Budget planning

### 11.3 Phase 3: Collaboration
- Family accounts
- Allowance management
- Shared budgets
- Financial advisor access

### 11.4 Phase 4: Connectivity
- Bank connection integrations (Plaid, Teller)
- Real-time sync
- Multi-bank aggregation
- Open Banking support

### 11.5 Phase 5: Platform
- Multi-tenant SaaS
- White-label capabilities
- API marketplace
- Third-party integrations

---

## 12. Glossary / Ubiquitous Language

### Domain Modeling Terms

| Term               | Definition                                              |
|--------------------|---------------------------------------------------------|
| **Value Object**   | Immutable object defined by its attributes, no identity |
| **Entity**         | Object with unique identity that persists over time     |
| **Aggregate**      | Cluster of entities treated as a unit for data changes  |
| **Aggregate Root** | Entry point entity that controls access to aggregate    |
| **Domain Event**   | Record of something meaningful that happened            |
| **Domain Service** | Operation that doesn't belong to a single entity        |
| **Invariant**      | Rule that must always be true within an aggregate       |
| **Repository**     | Abstraction for aggregate persistence                   |

### Identity & Access Terms

| Term                         | Definition                                                                                            |
|------------------------------|-------------------------------------------------------------------------------------------------------|
| **User**                     | Single identity entity — every person has one account with one set of credentials                     |
| **System Role**              | Hierarchical role (USER, ADMIN, SUPERADMIN) determining platform access level                         |
| **USER (role)**              | Default role — full access to emerald.com financial application                                       |
| **ADMIN (role)**             | Elevated role — all USER capabilities plus admin.emerald.com access                                   |
| **SUPERADMIN (role)**        | Highest role — all ADMIN capabilities plus bootstrap and emergency access; install-only               |
| **Admin Permission**         | Granular capability within admin portal (master_data, user_support, compliance, full)                 |
| **AuthenticatedIdentity**    | Value object IAM exposes to other contexts (userId, email, displayName, systemRole, adminPermissions) |
| **UserReference**            | Value object Core Finance uses internally (userId, displayName only — no IAM details)                 |
| **Auth Provider**            | External authentication method linked to a user (PASSWORD, GOOGLE, MICROSOFT)                         |
| **Account Linking**          | Automatically connecting a social login to an existing user when emails match                         |
| **Federated Authentication** | Delegating authentication to an external identity provider (Google, Microsoft) via OIDC               |

### Financial Terms

| Term                  | Definition                                                |
|-----------------------|-----------------------------------------------------------|
| **Account**           | Financial account being tracked (checking, savings, etc.) |
| **Transaction**       | Single financial movement (debit or credit)               |
| **Balance**           | Current amount in account (opening + transactions)        |
| **Opening Balance**   | Initial balance when account created                      |
| **Split Transaction** | Transaction divided into sub-transactions                 |
| **Bank Connection**   | Link to external bank for automatic import                |

### Access Control Terms

| Term                 | Definition                                 |
|----------------------|--------------------------------------------|
| **Owner**            | User with full control over an account     |
| **Editor**           | User who can view and modify               |
| **Viewer**           | User with read-only access                 |
| **Account Share**    | Permission grant to a user                 |
| **Permission Level** | Degree of access (Owner > Editor > Viewer) |

### Data Lifecycle Terms

| Term                 | Definition                        |
|----------------------|-----------------------------------|
| **Soft Delete**      | Mark as deleted but retain data   |
| **Hard Delete**      | Permanently remove data           |
| **Trash**            | View of soft-deleted items        |
| **Recovery**         | Restore soft-deleted item         |
| **Retention Period** | Time before automatic hard delete |
| **Retention Policy** | Rules for how long to keep data   |

### Classification Terms

| Term                | Definition                               |
|---------------------|------------------------------------------|
| **Taxonomy**        | Classification system (e.g., Categories) |
| **Term**            | Label within a taxonomy (e.g., Food)     |
| **Taxonomy Path**   | Full hierarchy path (Food > Restaurants) |
| **System Taxonomy** | Platform-provided, not deletable         |

### Architecture Terms

| Term                        | Definition                                                                               |
|-----------------------------|------------------------------------------------------------------------------------------|
| **Bounded Context**         | Explicit boundary within which a domain model applies; each context has its own language |
| **Anti-Corruption Layer**   | Translation layer that prevents one context's model from leaking into another            |
| **Context Map**             | Diagram showing relationships between bounded contexts                                   |
| **Customer/Supplier**       | Relationship where downstream (customer) context depends on upstream (supplier) context  |
| **Shared Kernel**           | Small set of shared concepts (e.g., base entity traits) used across contexts             |
| **Integration Contract**    | Well-defined interface a context exposes to other contexts                               |

---

*This document serves as the foundation specification for the Emerald Finance Platform. All implementations should reference this document for business rules and domain behavior. For technical architecture details, see the companion architecture documentation.*
