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

## Dependency Graph

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

## Bounded Context Distribution

| Context | Specs | Description |
|---------|-------|-------------|
| **Shared Kernel** | 001 | Foundation types shared across all contexts |
| **IAM** | 002, 003, 004, 005 | Identity, authentication, system roles |
| **Core Finance** | 007, 008, 009, 010, 011, 012 | Accounts, transactions, cards, sharing |
| **Classification** | 013, 014 | Taxonomies, categorization |
| **Integrations** | 015 | Bank connections, sync, import |
| **Cross-Cutting** | 006, 016, 017, 018, 019, 020 | Lifecycle, audit, currency, search, notifications, export |

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
