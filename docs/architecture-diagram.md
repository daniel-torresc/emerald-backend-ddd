# Emerald Backend — Ports & Adapters Architecture

## Full System Overview

```mermaid
graph TB
    subgraph INFRA["🔧 Infrastructure Layer (not yet implemented)"]
        direction TB
        DB[(PostgreSQL)]
        JWT[JWT Library]
        OIDC_EXT[Google/Microsoft OIDC]
        BANK_EXT[Bank APIs]
    end

    subgraph APP["Application Layer"]
        direction TB

        subgraph IAM_APP["IAM Services"]
            URS[UserRegistrationService]
            AUS[AuthenticationService]
            RMS[RoleManagementService]
            SPS[SuperadminProvisioningService]
        end

        subgraph CF_APP["Core Finance Services"]
            AMS[AccountManagementService]
            ASS[AccountSharingService]
            TMS[TransactionManagementService]
            TBMS[TransactionBulkManagementService]
            CMS[CardManagementService]
        end

        subgraph CL_APP["Classification Services"]
            TXMS[TaxonomyManagementService]
            TCS[TransactionCategorizationService]
        end

        subgraph INT_APP["Integrations Services"]
            BCS[BankConnectionService]
            BSS[BankSyncService]
            DDS[DeduplicationService]
        end
    end

    subgraph DOMAIN["Domain Layer"]
        direction TB

        subgraph SK_DOMAIN["Shared Kernel"]
            RPS[RetentionPolicyService]
            SK_BASE["Entity / AggregateRoot\nTimestamped / Auditable\nSoftDeletable Mixins"]
            SK_VO["Money · Currency\nRetentionPeriod · DateRange\nPaginatedResult · TrashItem\nDeletableEntityType"]
        end

        subgraph IAM_DOMAIN["IAM Domain"]
            USER["👤 User\n(AggregateRoot)"]
            RT["RefreshToken\n(Entity)"]
            PRT["PasswordResetToken\n(Entity)"]
            IAM_VO["EmailAddress · Username\nHashedPassword · AuthProvider\nSystemRole · AdminPermission\nAccessTokenClaims\nAuthenticatedIdentity\nOidcClaims · UserPreferences"]
            PV["password_validation\n(domain service)"]
        end

        subgraph CF_DOMAIN["Core Finance Domain"]
            ACCOUNT["🏦 Account\n(AggregateRoot)"]
            SHARE["AccountShare\n(child Entity)"]
            CARD["Card\n(child Entity)"]
            TXN["💳 Transaction\n(AggregateRoot)"]
            CF_VO["AccountName · IBAN\nPermissionLevel · UserReference\nImportSource · ReviewStatus\nSplitRequest · CardNumber\nCardType · CardNetwork\nBulkResult · TransactionInput"]
        end

        subgraph CL_DOMAIN["Classification Domain"]
            TAXONOMY["📂 Taxonomy\n(AggregateRoot)"]
            TERM["TaxonomyTerm\n(child Entity)"]
            ASSIGN["TransactionTermAssignment\n(Entity)"]
            CL_VO["TaxonomyName · TermName\nTaxonomyPath"]
        end

        subgraph INT_DOMAIN["Integrations Domain"]
            BANKCONN["🔗 BankConnection\n(AggregateRoot)"]
            PENDING["PendingTransaction\n(Entity)"]
            SYNCH["SyncHistory\n(Entity)"]
            INT_VO["ProviderName · ProviderCredentials\nConnectionStatus · NormalizedTransaction\nMatchStatus · DeduplicationResult\nSyncResult · SyncStatus"]
        end
    end

    %% Domain composition
    USER --> RT
    USER --> PRT
    ACCOUNT --> SHARE
    ACCOUNT --> CARD
    TXN -.->|parent/child split| TXN
    TAXONOMY --> TERM
    BANKCONN --> PENDING
    BANKCONN --> SYNCH
    ASSIGN -.->|cross-context link| TXN
    ASSIGN -.->|cross-context link| TERM

    %% Services → Domain
    URS --> USER
    AUS --> USER
    AUS --> RT
    AUS --> PRT
    RMS --> USER
    SPS --> USER
    AMS --> ACCOUNT
    ASS --> ACCOUNT
    TMS --> TXN
    TBMS --> TXN
    CMS --> ACCOUNT
    TXMS --> TAXONOMY
    TCS --> ASSIGN
    BCS --> BANKCONN
    BSS --> BANKCONN
    BSS --> SYNCH
    BSS --> PENDING
    DDS -.-> BSS

    %% Shared Kernel injection
    RPS -.->|injected into| AMS
    RPS -.->|injected into| TMS
    RPS -.->|injected into| TBMS
    RPS -.->|injected into| CMS
    RPS -.->|injected into| TXMS
    RPS -.->|injected into| BCS

    classDef aggregate fill:#4a90d9,stroke:#2c5f8a,color:white
    classDef entity fill:#7fb3d8,stroke:#4a90d9,color:white
    classDef vo fill:#b8d4e8,stroke:#7fb3d8,color:#333
    classDef service fill:#f5a623,stroke:#d4891a,color:white
    classDef domainService fill:#e8c547,stroke:#c4a636,color:#333
    classDef infra fill:#888,stroke:#555,color:white

    class USER,ACCOUNT,TXN,TAXONOMY,BANKCONN aggregate
    class RT,PRT,SHARE,CARD,TERM,ASSIGN,PENDING,SYNCH entity
    class SK_VO,IAM_VO,CF_VO,CL_VO,INT_VO vo
    class URS,AUS,RMS,SPS,AMS,ASS,TMS,TBMS,CMS,TXMS,TCS,BCS,BSS,DDS service
    class RPS,PV,SK_BASE domainService
    class DB,JWT,OIDC_EXT,BANK_EXT infra
```

---

## Ports & Adapters (Hexagonal) — Port Contracts

```mermaid
graph LR
    subgraph PORTS_IAM["IAM Outbound Ports"]
        P_UR["UserRepository\n· add · find_by_id\n· find_by_email\n· find_by_username\n· exists_by_email\n· exists_by_username\n· exists_by_role"]
        P_TS["TokenService\n· sign_access_token\n· verify_access_token\n· generate_refresh_token\n· hash_token"]
        P_RTR["RefreshTokenRepository\n· add · find_by_hash\n· find_active_families_by_user\n· revoke_family\n· revoke_all_for_user\n· count_active_families"]
        P_PRTR["PasswordResetTokenRepository\n· add · find_by_hash\n· invalidate_existing_for_user"]
        P_PH["PasswordHasher\n(domain port)\n· hash · verify"]
        P_OIDC["OidcProvider\n· generate_authorization_url\n· exchange_code_for_claims"]
    end

    subgraph PORTS_CF["Core Finance Outbound Ports"]
        P_AR["AccountRepository\n· save · find_by_id\n· find_by_owner\n· exists_by_name_for_user\n· find_accessible_by_user"]
        P_TR["TransactionRepository\n· save · save_many\n· find_by_id · find_by_account\n· find_by_account_in_range\n· find_by_external_id\n· count · sum_amounts\n· find_children\n· hard_delete_children"]
    end

    subgraph PORTS_CL["Classification Outbound Ports"]
        P_TXR["TaxonomyRepository\n· save · find_by_id\n· find_by_owner\n· exists_by_name_for_owner\n· find_by_term_id"]
        P_TTAR["AssignmentRepository\n· save · delete\n· delete_by_term/taxonomy/txn\n· find_by_transaction\n· find_by_txn_and_taxonomy\n· find_by_term\n· find_txn_ids_by_term\n· find_uncategorized"]
        P_TAP["TransactionAccessPort\n(ACL → Core Finance)\n· verify_transaction_active\n· verify_editor_permission"]
        P_CEH["CategorizationEventHandler\n· handle_term_deleted\n· handle_taxonomy_soft_deleted\n· handle_transaction_soft_deleted"]
    end

    subgraph PORTS_INT["Integrations Outbound Ports"]
        P_BCR["BankConnectionRepository\n· save · find_by_id\n· find_by_user\n· find_by_account\n· find_by_account_and_provider\n· find_due_for_sync"]
        P_SHR["SyncHistoryRepository\n· save · find_by_id\n· find_by_connection\n· find_latest · find_in_progress"]
        P_PTR["PendingTransactionRepository\n· save · save_many\n· find_by_id/connection/sync\n· find_needs_review\n· delete_by_connection"]
        P_BPA["BankProviderAdapter\n· fetch_transactions\n· verify_credentials\n· get_account_info"]
        P_BPAR["ProviderAdapterRegistry\n· get_adapter\n· get_normalizer"]
        P_TIP["TransactionImportPort\n(ACL → Core Finance)\n· import_transaction\n· find_by_external_id\n· find_by_date_and_amount"]
        P_TN["TransactionNormalizer\n(domain port)\n· normalize"]
    end

    subgraph PORTS_SK["Shared Kernel Outbound Ports"]
        P_RPR["RetentionPolicyRepository\n· find_user_preference\n· save_user_preference\n· delete_user_preference"]
        P_SDP["ScheduledDeletionPort\n· find_due_for_hard_delete\n· find_due_for_warning"]
        P_TQP["TrashQueryPort\n· list_trash\n· get_cascade_summary"]
    end

    classDef port fill:#9b59b6,stroke:#7d3c98,color:white
    classDef acl fill:#e74c3c,stroke:#c0392b,color:white

    class P_UR,P_TS,P_RTR,P_PRTR,P_PH,P_OIDC port
    class P_AR,P_TR port
    class P_TXR,P_TTAR,P_CEH port
    class P_BCR,P_SHR,P_PTR,P_BPA,P_BPAR,P_TN port
    class P_RPR,P_SDP,P_TQP port
    class P_TAP,P_TIP acl
```

---

## Unit of Work Composition

```mermaid
graph TD
    subgraph UOW_BASE["AbstractUnitOfWork (Shared Kernel)"]
        UOW_COMMIT["async commit()"]
        UOW_ROLLBACK["async rollback()"]
        UOW_CTX["__aenter__ / __aexit__\n(auto-rollback)"]
    end

    subgraph UOW_IAM["AbstractIamUnitOfWork"]
        IAM_USERS["users: UserRepository"]
        IAM_RT["refresh_tokens: RefreshTokenRepository"]
        IAM_PRT["password_reset_tokens: PasswordResetTokenRepository"]
    end

    subgraph UOW_CF["AbstractCoreFinanceUnitOfWork"]
        CF_ACCOUNTS["accounts: AccountRepository"]
        CF_TRANSACTIONS["transactions: TransactionRepository"]
    end

    subgraph UOW_CL["AbstractClassificationUnitOfWork"]
        CL_TAXONOMIES["taxonomies: TaxonomyRepository"]
        CL_ASSIGNMENTS["assignments: AssignmentRepository"]
    end

    subgraph UOW_INT["AbstractIntegrationsUnitOfWork"]
        INT_CONNECTIONS["bank_connections: BankConnectionRepository"]
        INT_SYNC["sync_history: SyncHistoryRepository"]
        INT_PENDING["pending_transactions: PendingTransactionRepository"]
    end

    UOW_IAM --> UOW_BASE
    UOW_CF --> UOW_BASE
    UOW_CL --> UOW_BASE
    UOW_INT --> UOW_BASE

    classDef uow fill:#27ae60,stroke:#1e8449,color:white
    classDef repo fill:#2ecc71,stroke:#27ae60,color:white

    class UOW_BASE,UOW_IAM,UOW_CF,UOW_CL,UOW_INT uow
    class IAM_USERS,IAM_RT,IAM_PRT,CF_ACCOUNTS,CF_TRANSACTIONS,CL_TAXONOMIES,CL_ASSIGNMENTS,INT_CONNECTIONS,INT_SYNC,INT_PENDING repo
```

---

## Cross-Context Boundaries (Anti-Corruption Layer)

```mermaid
graph LR
    subgraph IAM["IAM Context"]
        AI["AuthenticatedIdentity\n(Value Object)"]
    end

    subgraph CF["Core Finance Context"]
        UR_VO["UserReference\n(ACL Value Object)"]
        CF_TXN["Transaction"]
        CF_ACCT["Account"]
    end

    subgraph CL["Classification Context"]
        TAP["TransactionAccessPort\n(Protocol)"]
        TCS2["TransactionCategorizationService"]
    end

    subgraph INT["Integrations Context"]
        TIP2["TransactionImportPort\n(Protocol)"]
        BSS2["BankSyncService"]
        DDS2["DeduplicationService"]
    end

    subgraph SK["Shared Kernel"]
        RPS2["RetentionPolicyService"]
        MONEY["Money · Currency"]
        BASE["Entity · AggregateRoot"]
        MIXINS["Timestamped · Auditable\nSoftDeletable Mixins"]
        EVENTS["DomainEvent base"]
        COMMANDS["Command base"]
        EXCEPTIONS["Exception hierarchy"]
    end

    AI -->|"TYPE_CHECKING import\nfrom_identity()"| UR_VO
    TAP -->|"verify_transaction_active\nverify_editor_permission"| CF_TXN
    TAP -->|"verify_editor_permission"| CF_ACCT
    TIP2 -->|"import_transaction\nfind_by_external_id"| CF_TXN

    TCS2 --> TAP
    BSS2 --> TIP2
    DDS2 --> TIP2

    SK -.->|"shared types"| IAM
    SK -.->|"shared types"| CF
    SK -.->|"shared types"| CL
    SK -.->|"shared types"| INT

    RPS2 -.->|"injected"| CF
    RPS2 -.->|"injected"| CL
    RPS2 -.->|"injected"| INT

    classDef acl fill:#e74c3c,stroke:#c0392b,color:white
    classDef context fill:#3498db,stroke:#2980b9,color:white
    classDef shared fill:#f39c12,stroke:#e67e22,color:white

    class TAP,TIP2,UR_VO acl
    class AI,CF_TXN,CF_ACCT,TCS2,BSS2,DDS2 context
    class RPS2,MONEY,BASE,MIXINS,EVENTS,COMMANDS,EXCEPTIONS shared
```

---

## Service Dependency Graph

```mermaid
graph TD
    subgraph IAM_SVC["IAM Application Services"]
        URS2["UserRegistrationService"]
        AUS2["AuthenticationService"]
        RMS2["RoleManagementService"]
        SPS2["SuperadminProvisioningService"]
    end

    subgraph CF_SVC["Core Finance Application Services"]
        AMS2["AccountManagementService"]
        ASS2["AccountSharingService"]
        TMS2["TransactionManagementService"]
        TBMS2["TransactionBulkManagementService"]
        CMS2["CardManagementService"]
    end

    subgraph CL_SVC["Classification Application Services"]
        TXMS2["TaxonomyManagementService"]
        TCS3["TransactionCategorizationService"]
    end

    subgraph INT_SVC["Integrations Application Services"]
        BCS2["BankConnectionService"]
        BSS3["BankSyncService"]
        DDS3["DeduplicationService"]
    end

    %% IAM dependencies
    URS2 -->|"uow"| UOW_I["AbstractIamUnitOfWork"]
    URS2 -->|"hasher"| PH["PasswordHasher"]
    AUS2 -->|"uow"| UOW_I
    AUS2 -->|"hasher"| PH
    AUS2 -->|"token_service"| TS["TokenService"]
    AUS2 -.->|"oidc_provider?"| OP["OidcProvider"]
    RMS2 -->|"uow"| UOW_I
    SPS2 -->|"uow"| UOW_I
    SPS2 -->|"hasher"| PH

    %% Core Finance dependencies
    AMS2 -->|"uow"| UOW_C["AbstractCoreFinanceUnitOfWork"]
    AMS2 -->|"retention"| RPS3["RetentionPolicyService"]
    ASS2 -->|"uow"| UOW_C
    TMS2 -->|"uow"| UOW_C
    TMS2 -->|"retention"| RPS3
    TBMS2 -->|"uow"| UOW_C
    TBMS2 -->|"retention"| RPS3
    CMS2 -->|"uow"| UOW_C
    CMS2 -->|"retention"| RPS3

    %% Classification dependencies
    TXMS2 -->|"uow"| UOW_CL2["AbstractClassificationUnitOfWork"]
    TXMS2 -->|"retention"| RPS3
    TCS3 -->|"uow"| UOW_CL2
    TCS3 -->|"acl"| TAP2["TransactionAccessPort"]

    %% Integrations dependencies
    BCS2 -->|"uow"| UOW_INT2["AbstractIntegrationsUnitOfWork"]
    BCS2 -->|"retention"| RPS3
    BSS3 -->|"uow"| UOW_INT2
    BSS3 -->|"acl"| TIP3["TransactionImportPort"]
    BSS3 -->|"registry"| BPAR["ProviderAdapterRegistry"]
    DDS3 -->|"acl"| TIP3

    %% RetentionPolicyService dependency
    RPS3 -->|"repo"| RPR["RetentionPolicyRepository"]

    classDef svc fill:#f5a623,stroke:#d4891a,color:white
    classDef uow fill:#27ae60,stroke:#1e8449,color:white
    classDef port fill:#9b59b6,stroke:#7d3c98,color:white
    classDef acl fill:#e74c3c,stroke:#c0392b,color:white
    classDef dSvc fill:#e8c547,stroke:#c4a636,color:#333

    class URS2,AUS2,RMS2,SPS2,AMS2,ASS2,TMS2,TBMS2,CMS2,TXMS2,TCS3,BCS2,BSS3,DDS3 svc
    class UOW_I,UOW_C,UOW_CL2,UOW_INT2 uow
    class PH,TS,OP,RPR,BPAR port
    class TAP2,TIP3 acl
    class RPS3 dSvc
```

---

## Legend

| Color | Meaning |
|-------|---------|
| 🔵 Blue | Aggregate Roots |
| 🔵 Light Blue | Child Entities |
| 🟠 Orange | Application Services |
| 🟡 Yellow | Domain Services |
| 🟣 Purple | Protocol Ports (outbound) |
| 🔴 Red | ACL / Anti-Corruption Layer Ports |
| 🟢 Green | Unit of Work abstractions |
| ⬜ Gray | Infrastructure (not yet implemented) |

## Key Architectural Principles

1. **All ports are `typing.Protocol`** — structural subtyping, no ABC inheritance
2. **All port methods are `async def`** — prepared for async infrastructure
3. **No cross-context domain imports at runtime** — only via ACL ports or `TYPE_CHECKING` guards
4. **Shared Kernel provides base types** — Entity, AggregateRoot, mixins, Money, exceptions, events
5. **Events born only inside aggregates** — via `_register_event()`, collected via `collect_events()`
6. **Each UoW composes its context's repositories** — services receive UoW, not individual repos
7. **RetentionPolicyService is the only shared domain service** — injected across all contexts that do soft-delete
