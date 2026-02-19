# Emerald Finance Platform - Specification Index

## Overview

The Emerald Finance Platform is a comprehensive personal and family finance management system built with Domain-Driven Design. This directory contains incremental business specifications decomposed from the [Functional Requirements Document](../docs/functional-requirements.md).

Each specification represents a distinct business capability that can be implemented, tested, and delivered independently.

## Specification Catalog

### Recommended Implementation Order

| #   | Spec | Bounded Context | Summary | Dependencies |
|-----|------|-----------------|---------|--------------|
| 001 | [Shared Kernel](./spec-001-shared-kernel/) | Shared | Foundation value objects, base entity traits, domain event infrastructure | None |
| 002 | [User Registration & Identity](./spec-002-user-registration-and-identity/) | IAM | User entity, registration, email verification, lifecycle states | 001 |
| 003 | [Authentication & Sessions](./spec-003-authentication-and-sessions/) | IAM | Password auth, JWT tokens, refresh rotation, session management | 002 |
| 004 | [System Roles & Admin Permissions](./spec-004-system-roles-and-admin-permissions/) | IAM | Role hierarchy, admin permissions, portal access, SUPERADMIN handling | 002, 003 |
| 005 | [Federated Authentication](./spec-005-federated-authentication/) | IAM | OAuth 2.0 / OIDC with Google & Microsoft, account linking, social registration | 002, 003 |
| 006 | [Data Lifecycle Management](./spec-006-data-lifecycle-management/) | Cross-Cutting | Soft delete, hard delete, retention policies, trash, recovery, cascades | 001 |
| 007 | [Account Management](./spec-007-account-management/) | Core Finance | Account aggregate, CRUD, balance calculation, ACL (UserReference) | 001, 002, 006 |
| 008 | [Account Sharing & Domain Authorization](./spec-008-account-sharing-and-domain-authorization/) | Core Finance | AccountShare, PermissionLevel, share/revoke/transfer, resource access matrix | 007 |
| 009 | [Transaction Management](./spec-009-transaction-management/) | Core Finance | Transaction entity, CRUD, review workflow, import source tracking | 007, 008 |
| 010 | [Transaction Splitting](./spec-010-transaction-splitting/) | Core Finance | Split/join operations, split validation, cascade behavior | 009 |
| 011 | [Card Management](./spec-011-card-management/) | Core Finance | Card entity, types/networks, card-transaction linking | 007 |
| 012 | [Bulk Transaction Operations](./spec-012-bulk-transaction-operations/) | Core Finance | Bulk create, update, delete, recover with per-item error reporting | 009 |
| 013 | [Classification & Taxonomies](./spec-013-classification-and-taxonomies/) | Classification | Taxonomy aggregate, terms, hierarchy, cycle detection, system taxonomies | 001, 002, 006 |
| 014 | [Transaction Categorization](./spec-014-transaction-categorization/) | Classification | Transaction-term association, assignment rules, manual categorization | 009, 013 |
| 015 | [Bank Connections & Sync](./spec-015-bank-connections-and-sync/) | Integrations | BankConnection aggregate, sync lifecycle, import processing, deduplication | 007, 009 |
| 016 | [Audit Logging](./spec-016-audit-logging/) | Cross-Cutting | Immutable audit trail, state capture, audit actions catalog | 001 |
| 017 | [Multi-Currency Support](./spec-017-multi-currency-support/) | Cross-Cutting | Currency operations, exchange rates, display conversion, reporting | 001 |
| 018 | [Search & Filtering](./spec-018-search-and-filtering/) | Cross-Cutting | Transaction search, full-text search, filtering, fuzzy matching | 009 |
| 019 | [Notifications](./spec-019-notifications/) | Cross-Cutting | Notification types, channels, preferences, digest options | 001 |
| 020 | [Data Export](./spec-020-data-export/) | Cross-Cutting | CSV/JSON/PDF/OFX export, GDPR portability, scoped exports | 009 |

### Infrastructure Layer (Specs 021-031)

| #   | Spec | Layer | Summary | Dependencies |
|-----|------|-------|---------|--------------|
| 021 | [Configuration & Database Foundation](./spec-021-configuration-and-database-foundation/) | Infrastructure | Settings, SQLAlchemy engine, Alembic scaffold, base UoW | None |
| 022 | [IAM Persistence Layer](./spec-022-iam-persistence-layer/) | Infrastructure | ORM models + repos for User, tokens, retention prefs | 021 |
| 023 | [Auth Infrastructure Adapters](./spec-023-auth-infrastructure-adapters/) | Infrastructure | Argon2 hasher, JWT service, OIDC adapters | 021 |
| 024 | [Core Finance Persistence Layer](./spec-024-core-finance-persistence-layer/) | Infrastructure | ORM models + repos for accounts, transactions, cards, shares | 021, 022 |
| 025 | [Classification & Integrations Persistence](./spec-025-classification-and-integrations-persistence/) | Infrastructure | ORM models + repos for taxonomies, assignments, bank connections, sync | 021-024 |
| 026 | [Cross-Context Adapters & Composition Root](./spec-026-cross-context-adapters-and-composition-root/) | Infrastructure | ACL adapters, provider registry, FastAPI app factory, DI container | 022-025 |
| 027 | [API Middleware & Common HTTP](./spec-027-api-middleware-and-common-http/) | Infrastructure | Auth dependency, error handlers, CORS, health checks, shared schemas | 026 |
| 028 | [REST API — IAM Endpoints](./spec-028-rest-api-iam-endpoints/) | Presentation | Auth, registration, social login, user profile, admin routes | 027 |
| 029 | [REST API — Core Finance Endpoints](./spec-029-rest-api-core-finance-endpoints/) | Presentation | Accounts, sharing, transactions, bulk, cards routes | 027 |
| 030 | [REST API — Classification & Integrations Endpoints](./spec-030-rest-api-classification-and-integrations-endpoints/) | Presentation | Taxonomies, categorization, bank connections, trash routes | 027 |
| 031 | [Integration Tests & Docker](./spec-031-integration-tests-and-docker/) | Infrastructure | E2E test flows, Dockerfile, docker-compose | 028-030 |

## Dependency Graph

### Domain & Application Layer (Specs 001-020)

```
                         ┌─────────┐
                         │   001   │  Shared Kernel
                         │ (base)  │
                         └────┬────┘
                ┌─────────────┼─────────────┬──────────────┬──────────────┐
                ▼             ▼             ▼              ▼              ▼
          ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
          │   002   │   │   006   │   │   016   │   │   017   │   │   019   │
          │  User   │   │  Data   │   │  Audit  │   │  Multi  │   │  Notif  │
          │ Identity│   │Lifecycle│   │ Logging │   │Currency │   │ ications│
          └────┬────┘   └────┬────┘   └─────────┘   └─────────┘   └─────────┘
        ┌──────┤             │
        ▼      ▼             │
  ┌─────────┐ ┌─────────┐   │
  │   003   │ │   004   │   │
  │  Auth & │ │  Roles  │   │
  │Sessions │ │ & Admin │   │
  └────┬────┘ └─────────┘   │
       │                     │
       ▼                     │
  ┌─────────┐                │
  │   005   │                │
  │Federated│                │
  │  Auth   │                │
  └─────────┘                │
                             │
        ┌────────────────────┤
        ▼                    ▼
  ┌─────────┐          ┌─────────┐
  │   007   │◄─────────│   013   │
  │ Account │          │ Classif.│
  │  Mgmt   │          │ & Taxon.│
  └────┬────┘          └────┬────┘
  ┌────┼──────────┐         │
  ▼    ▼          ▼         │
┌────┐┌────┐ ┌─────────┐   │
│008 ││011 │ │   015   │   │
│Shar││Card│ │  Bank   │   │
│ing ││Mgmt│ │Connect. │   │
└──┬─┘└────┘ └─────────┘   │
   ▼                        │
┌─────────┐                 │
│   009   │                 │
│ Transac.│                 │
│  Mgmt   │                 │
└────┬────┘                 │
┌────┼──────────┬───────────┤
▼    ▼          ▼           ▼
┌────┐┌────┐ ┌────┐   ┌─────────┐
│010 ││012 │ │018 │   │   014   │
│Spli││Bulk│ │Sear│   │ Catego. │
│tting││Ops │ │ch  │   │  riz.   │
└────┘└────┘ └────┘   └─────────┘
                  ┌────┐
                  │020 │
                  │Expo│
                  │rt  │
                  └────┘
```

### Infrastructure Layer (Specs 021-031)

```
                     ┌───────┐
                     │  021  │  Config & DB Foundation
                     └───┬───┘
               ┌─────────┼─────────┐
               ▼         ▼         │
          ┌───────┐  ┌───────┐     │
          │  022  │  │  023  │     │
          │IAM DB │  │Auth   │     │
          └───┬───┘  └───┬───┘     │
              ▼          │         │
          ┌───────┐      │         │
          │  024  │      │         │
          │CoreFin│      │         │
          └───┬───┘      │         │
              ▼          │         │
          ┌───────┐      │         │
          │  025  │      │         │
          │Cls+Int│      │         │
          └───┬───┘      │         │
              └─────┬────┘         │
                    ▼              │
              ┌───────┐            │
              │  026  │ ◄──────────┘
              │Compose│
              └───┬───┘
                  ▼
              ┌───────┐
              │  027  │
              │API Mid│
              └───┬───┘
         ┌────────┼────────┐
         ▼        ▼        ▼
     ┌───────┐┌───────┐┌───────┐
     │  028  ││  029  ││  030  │
     │IAM API││CF API ││Cls API│
     └───┬───┘└───┬───┘└───┬───┘
         └────────┼────────┘
                  ▼
              ┌───────┐
              │  031  │
              │E2E+Dok│
              └───────┘
```

## Bounded Context Distribution

| Context | Specs | Description |
|---------|-------|-------------|
| **Shared Kernel** | 001 | Foundation types shared across all contexts |
| **IAM** | 002, 003, 004, 005 | Identity, authentication, system roles |
| **Core Finance** | 007, 008, 009, 010, 011, 012 | Accounts, transactions, cards, sharing |
| **Classification** | 013, 014 | Taxonomies, categorization |
| **Integrations** | 015 | Bank connections, sync, import |
| **Cross-Cutting** | 006, 016, 017, 018, 019, 020 | Lifecycle, audit, currency, search, notifications, export |
| **Infrastructure** | 021-027, 031 | Persistence, auth adapters, composition root, middleware, Docker |
| **Presentation** | 028, 029, 030 | REST API endpoints for all contexts |

## Phase 1 (Foundation) Coverage

Per the roadmap, Phase 1 covers specs **001 through 015** plus **016** (audit logging):

- Core account and transaction management (007-012)
- User authentication and authorization (002-005)
- Basic sharing and collaboration (008)
- Soft delete with retention (006)
- Bulk operations (012)
- Classification (013-014)
- Bank connectivity foundation (015)
- Audit trail (016)

Specs 017-020 (multi-currency, search, notifications, export) can be implemented incrementally alongside or after Phase 1 core.

### Pre-Infrastructure Cleanup (Specs 032-035)

| #   | Spec | Layer | Summary | Dependencies |
|-----|------|-------|---------|--------------|
| 032 | [Async Repository Ports](./spec-032-async-repository-ports/) | Domain/Application | Convert all sync repository/port Protocol methods to async | 021 |
| 033 | [Domain Event Dispatch](./spec-033-domain-event-dispatch/) | Application | Event collection in UoW, dispatcher protocol, handler registration | 001-015 |
| 034 | [Cascade Completeness](./spec-034-cascade-completeness/) | Application | Account→Transaction cascade, hard-delete cascades, cascade audit | 033 |
| 035 | [Domain Model Consistency](./spec-035-domain-model-consistency/) | Domain | Version init, embedded constants, missing events, frozen VOs, error codes | 001-015 |

## Phase 3 (Infrastructure) Coverage

Specs **021 through 031** implement the full infrastructure layer:

- Database foundation: settings, SQLAlchemy, Alembic, base UoW (021)
- Persistence layers: IAM (022), Core Finance (024), Classification + Integrations (025)
- Auth adapters: Argon2, JWT, OIDC (023)
- Composition root: DI container, cross-context adapters, FastAPI app factory (026)
- API layer: middleware (027), IAM endpoints (028), Core Finance endpoints (029), Classification + Integrations endpoints (030)
- Testing & deployment: E2E tests, Dockerfile, docker-compose (031)

This implements all 25 Protocol ports defined in specs 001-015 with real infrastructure adapters.
