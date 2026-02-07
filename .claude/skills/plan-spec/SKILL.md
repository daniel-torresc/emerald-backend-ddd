---
name: plan-spec
description: "Action-oriented skill for generating implementation plans from specifications. Use when: (1) A spec file exists and needs to be turned into an actionable plan, (2) Breaking down requirements into implementation tasks, (3) Designing technical architecture for a feature, (4) Creating step-by-step development guidance following Clean Architecture patterns."
argument-hint: [spec-directory-name]
---

# Plan Specification Implementation

Transform a clarified specification into a detailed, actionable implementation plan following Clean Architecture patterns (read `architecture-patterns` skill).

**Purpose:** Take a spec file (WHAT to build) and produce an implementation plan (HOW to build it). This plan will guide developers through the implementation process with clear tasks, architecture decisions, and sequencing.

**Input:** `.specs/$1/spec.md`
**Output:** `.specs/$1/plan.md`

---

## ⚠️ CRITICAL: Architecture Compliance

**ALL implementation plans MUST follow Clean Architecture patterns.**

The plan must ensure:
- Clear separation between Domain, Application, Infrastructure, and Interface layers
- Dependencies point inward (outer layers depend on inner layers, never the reverse)
- Domain layer has zero external dependencies
- Business logic is isolated from frameworks and external concerns

---

## Process Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: ANALYZE SPEC                                               │
│  Read and understand the specification completely                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: EXPLORE CODEBASE                                           │
│  Understand existing patterns, conventions, and integration points  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: DESIGN ARCHITECTURE                                        │
│  Map requirements to Clean Architecture layers                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: DECOMPOSE INTO TASKS                                       │
│  Break down into ordered, implementable units of work               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: GENERATE PLAN FILE                                         │
│  Write the complete implementation plan                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Analyze Spec

### 1.1 Read the Specification

Read the spec file at `.specs/$1/spec.md` and extract:

- **Overview** - What is being built and why
- **Functional Requirements** - What the system must do
- **Non-Functional Requirements** - Performance, security, scalability constraints
- **User Stories** - User-facing behaviors and acceptance criteria
- **Edge Cases** - Error handling and boundary conditions
- **Dependencies** - External systems and integrations
- **Constraints** - Limitations to work within

### 1.2 Identify Key Components

From the spec, identify:

| Component Type | Questions to Answer |
|----------------|---------------------|
| **Entities** | What are the core domain objects? |
| **Use Cases** | What operations/actions does the system perform? |
| **Interfaces** | What APIs, UIs, or entry points are needed? |
| **External Systems** | What databases, services, or APIs are involved? |
| **Events** | Are there domain events or async operations? |

### 1.3 List Technical Decisions

Identify decisions that need to be made:

- Data storage approach
- API design choices
- Authentication/authorization strategy
- Error handling patterns
- Caching strategy (if applicable)
- Testing approach

---

## Step 2: Explore Codebase

### 2.1 Understand Existing Patterns

Explore the codebase to identify:

- **Project structure** - How code is organized
- **Existing architecture** - Current patterns in use
- **Conventions** - Naming, file organization, coding style
- **Similar features** - How comparable functionality was implemented
- **Shared utilities** - Reusable code that can be leveraged

### 2.2 Identify Integration Points

Determine where the new feature connects to existing code:

- Entry points (routes, controllers, handlers)
- Shared services or repositories
- Common data models
- Existing infrastructure (database, cache, queues)

### 2.3 Note Deviations

If existing patterns differ from Clean Architecture:

- Document current state
- Plan migration path if needed
- Ensure new code follows Clean Architecture even if legacy code doesn't

---

## Step 3: Design Architecture

### 3.1 Clean Architecture Layer Mapping

Map each requirement to the appropriate layer:

```
┌─────────────────────────────────────────────────────────────────┐
│                     INTERFACE LAYER                             │
│  Controllers, Presenters, Views, API Endpoints, CLI Commands    │
│  - Handles HTTP requests/responses                              │
│  - Input validation and formatting                              │
│  - Calls Application layer use cases                            │
├─────────────────────────────────────────────────────────────────┤
│                    APPLICATION LAYER                            │
│  Use Cases, Commands, Queries, Application Services, DTOs       │
│  - Orchestrates domain logic                                    │
│  - Defines ports (interfaces) for infrastructure                │
│  - Transaction boundaries                                       │
├─────────────────────────────────────────────────────────────────┤
│                      DOMAIN LAYER                               │
│  Entities, Value Objects, Domain Services, Domain Events        │
│  - Core business logic and rules                                │
│  - No dependencies on outer layers                              │
│  - Framework-agnostic                                           │
├─────────────────────────────────────────────────────────────────┤
│                   INFRASTRUCTURE LAYER                          │
│  Repositories, External APIs, Database, Messaging, Frameworks   │
│  - Implements ports defined by Application layer                │
│  - Handles persistence and external communication               │
│  - Framework-specific code lives here                           │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Design

For each major component, define:

```markdown
### [Component Name]

**Layer:** Domain | Application | Infrastructure | Interface
**Responsibility:** [Single responsibility description]
**Dependencies:** [What it depends on]
**Dependents:** [What depends on it]

**Key Elements:**
- [Classes, interfaces, or modules needed]
```

### 3.3 Define Ports and Adapters

Identify boundaries that need abstraction:

| Port (Interface) | Purpose | Adapter (Implementation) |
|------------------|---------|--------------------------|
| `UserRepository` | User persistence | `PostgresUserRepository` |
| `EmailService` | Send notifications | `SendGridEmailAdapter` |
| `PaymentGateway` | Process payments | `StripePaymentAdapter` |

---

## Step 4: Decompose into Tasks

### 4.1 Task Breakdown Principles

- **Single Responsibility** - Each task does one thing
- **Testable** - Each task can be verified independently
- **Ordered** - Tasks are sequenced by dependencies
- **Sized** - Tasks are small enough to complete in one session

### 4.2 Recommended Task Order

Follow this general sequence (inside-out):

1. **Domain Layer First**
   - Entities and value objects
   - Domain services
   - Domain events (if any)

2. **Application Layer Second**
   - Port interfaces (repository contracts, service interfaces)
   - Use cases / command handlers
   - DTOs and mappers

3. **Infrastructure Layer Third**
   - Repository implementations
   - External service adapters
   - Database migrations

4. **Interface Layer Last**
   - Controllers / API endpoints
   - Request/response models
   - Input validation

5. **Cross-Cutting Concerns**
   - Error handling
   - Logging
   - Authentication/authorization integration

6. **Testing**
   - Unit tests (domain, application)
   - Integration tests (infrastructure)
   - End-to-end tests (full flow)

### 4.3 Task Template

For each task:

```markdown
### TASK-XXX: [Task Title]

**Layer:** Domain | Application | Infrastructure | Interface
**Depends On:** [TASK-XXX, TASK-YYY]
**Blocked By:** [Any external dependencies]

**Description:**
[What needs to be done]

**Files to Create/Modify:**
- `path/to/file.ts` - [What changes]

**Acceptance Criteria:**
- [ ] [Specific, verifiable criterion]

**Testing:**
- [ ] [Test requirement]
```

---

## Step 5: Generate Plan File

### 5.1 File Location

```
.specs/$1/plan.md
```

### 5.2 Implementation Plan Template

```markdown
# [Feature Name] Implementation Plan

**Spec:** `.specs/$1/spec.md`
**Version:** 1.0
**Date:** [Date]

---

## 1. Overview

[Brief summary of what will be implemented and the approach]

---

## 2. Architecture Design

### 2.1 Layer Mapping

| Requirement | Layer | Components |
|-------------|-------|------------|
| [REQ-001] | Domain | `Entity`, `ValueObject` |
| [REQ-002] | Application | `UseCase`, `Port` |

### 2.2 Component Diagram

```
[ASCII diagram showing component relationships]
```

### 2.3 Ports and Adapters

| Port | Purpose | Adapter |
|------|---------|---------|
| [Interface] | [Why] | [Implementation] |

---

## 3. Technical Decisions

### 3.1 [Decision Area]
**Decision:** [What was decided]
**Rationale:** [Why this approach]
**Alternatives Considered:** [Other options]

---

## 4. Implementation Tasks

### Phase 1: Domain Layer

#### TASK-001: [Task Title]
**Layer:** Domain
**Depends On:** None

**Description:**
[What to implement]

**Files:**
- `src/domain/entities/[Entity].ts`

**Acceptance Criteria:**
- [ ] [Criterion]

**Tests:**
- [ ] Unit tests for [Entity]

---

#### TASK-002: [Task Title]
...

### Phase 2: Application Layer

#### TASK-003: [Task Title]
...

### Phase 3: Infrastructure Layer

#### TASK-004: [Task Title]
...

### Phase 4: Interface Layer

#### TASK-005: [Task Title]
...

### Phase 5: Testing & Polish

#### TASK-006: [Task Title]
...

---

## 5. Task Dependency Graph

```
TASK-001 ─┬─► TASK-003 ─┬─► TASK-005
          │             │
TASK-002 ─┘             └─► TASK-006
                              │
TASK-004 ────────────────────►┘
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk] | High/Med/Low | High/Med/Low | [Strategy] |

---

## 7. Definition of Done

- [ ] All tasks completed
- [ ] All acceptance criteria met
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] Deployed to staging
```

---

## Quality Checklist

Before finalizing the plan:

- [ ] Every requirement from spec has at least one task
- [ ] Tasks follow Clean Architecture layer order (inside-out)
- [ ] Dependencies between tasks are clear and correct
- [ ] Each task has clear acceptance criteria
- [ ] Testing requirements are included
- [ ] No circular dependencies exist
- [ ] Plan accounts for existing codebase patterns

---

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Better Approach |
|--------------|---------|-----------------|
| **Big Bang Tasks** | Tasks too large to complete | Break into smaller units |
| **Outside-In Order** | Building UI before domain | Start with domain layer |
| **Missing Ports** | Direct infrastructure dependencies | Define interfaces first |
| **Untestable Tasks** | Tasks with unclear verification | Add acceptance criteria |
| **Ignored Constraints** | Plan ignores spec constraints | Review NFRs and constraints |
| **Framework-First** | Designing around framework | Design around domain |

---

## Output Checklist

When complete, you should have:

- [ ] Spec fully analyzed and understood
- [ ] Codebase explored for patterns and integration points
- [ ] Architecture designed following Clean Architecture
- [ ] Tasks decomposed and ordered correctly
- [ ] Plan file created at `.specs/$1/plan.md`
- [ ] All requirements traced to tasks
- [ ] Dependencies clearly documented