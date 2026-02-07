---
name: implement-spec
description: "Action-oriented skill for implementing features from specifications and plans. Use when: (1) A spec and plan exist and are ready for implementation, (2) Executing planned tasks following Clean Architecture, (3) Building features according to defined acceptance criteria, (4) Translating implementation plans into working code."
argument-hint: [spec-directory-name]
---

# Implement Specification

Execute an implementation plan to build a feature following Clean Architecture patterns.

**Purpose:** Take a spec and plan, then systematically implement the feature by executing each task in order, producing working, tested code.

**Input:**
- `.specs/$1/spec.md` (requirements)
- `.specs/$1/plan.md` (implementation plan)

**Output:** Working code implementing the specification

---

## ⚠️ CRITICAL: Implementation Rules

1. **Follow the plan** - Execute tasks in the order defined in the plan
2. **Respect layer boundaries** - Never violate Clean Architecture dependencies
3. **Meet acceptance criteria** - Every task must satisfy its defined criteria
4. **Test as you go** - Write tests for each component before moving on
5. **Update task status** - Track progress through the task list

---

## Process Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: LOAD CONTEXT                                               │
│  Read spec and plan, understand the full picture                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: VALIDATE READINESS                                         │
│  Ensure prerequisites are met, environment is ready                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: EXECUTE TASKS                                              │
│  Implement each task following the plan order                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  For each task:                                              │   │
│  │  1. Read task requirements                                   │   │
│  │  2. Implement the code                                       │   │
│  │  3. Write tests                                              │   │
│  │  4. Verify acceptance criteria                               │   │
│  │  5. Mark task complete                                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: VERIFY IMPLEMENTATION                                      │
│  Run all tests, validate against spec requirements                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: FINALIZE                                                   │
│  Update documentation, clean up, report completion                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Load Context

### 1.1 Read the Specification

Read `.specs/$1/spec.md` and internalize:

- **Requirements** - What must be built (functional and non-functional)
- **User Stories** - User-facing behaviors
- **Acceptance Criteria** - How to verify correctness
- **Edge Cases** - Error handling requirements
- **Constraints** - Limitations to respect

### 1.2 Read the Implementation Plan

Read `.specs/$1/plan.md` and understand:

- **Architecture Design** - Layer mapping and component structure
- **Technical Decisions** - Choices already made
- **Task List** - Ordered implementation steps
- **Dependencies** - Task ordering and blockers
- **Ports and Adapters** - Interfaces and implementations needed

### 1.3 Build Mental Model

Before coding, you should be able to answer:

- [ ] What are the core domain entities?
- [ ] What use cases need to be implemented?
- [ ] What external systems are involved?
- [ ] What is the task execution order?
- [ ] What does "done" look like?

---

## Step 2: Validate Readiness

### 2.1 Check Prerequisites

Before starting implementation:

- [ ] Spec file exists and is approved
- [ ] Plan file exists and is complete
- [ ] All blocking dependencies are resolved
- [ ] Development environment is ready
- [ ] Required external services are accessible

### 2.2 Verify Codebase State

- [ ] On correct branch (create feature branch if needed)
- [ ] No uncommitted changes that could conflict
- [ ] Dependencies are installed
- [ ] Existing tests pass

### 2.3 Create Task Tracking

Initialize task tracking using the plan's task list. Each task should be tracked with status:

- `pending` - Not started
- `in_progress` - Currently being worked on
- `completed` - Done and verified
- `blocked` - Waiting on something

---

## Step 3: Execute Tasks

### 3.1 Task Execution Loop

For each task in the plan (respecting dependency order):

```
┌─────────────────────────────────────────────────────────────────┐
│  1. SELECT TASK                                                 │
│     - Pick next task where all dependencies are complete        │
│     - Mark as in_progress                                       │
├─────────────────────────────────────────────────────────────────┤
│  2. UNDERSTAND TASK                                             │
│     - Read task description and acceptance criteria             │
│     - Identify files to create/modify                           │
│     - Review related existing code                              │
├─────────────────────────────────────────────────────────────────┤
│  3. IMPLEMENT                                                   │
│     - Write the code following Clean Architecture               │
│     - Follow existing codebase conventions                      │
│     - Keep changes focused on task scope                        │
├─────────────────────────────────────────────────────────────────┤
│  4. TEST                                                        │
│     - Write unit tests for new code                             │
│     - Ensure tests pass                                         │
│     - Verify edge cases are handled                             │
├─────────────────────────────────────────────────────────────────┤
│  5. VERIFY                                                      │
│     - Check all acceptance criteria                             │
│     - Ensure no regressions in existing tests                   │
│     - Validate layer boundaries are respected                   │
├─────────────────────────────────────────────────────────────────┤
│  6. COMPLETE                                                    │
│     - Mark task as completed                                    │
│     - Commit changes (if appropriate)                           │
│     - Move to next task                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Layer-Specific Implementation Guidelines

#### Domain Layer Tasks

```markdown
**Focus:** Pure business logic, no external dependencies

**DO:**
- Define entities with behavior, not just data
- Use value objects for concepts with no identity
- Implement domain validation rules
- Keep entities framework-agnostic

**DON'T:**
- Import anything from infrastructure or interface layers
- Use framework-specific decorators or annotations
- Depend on database or external services
- Add persistence concerns (IDs for ORM, etc.)
```

#### Application Layer Tasks

```markdown
**Focus:** Use cases and orchestration

**DO:**
- Define port interfaces for external dependencies
- Implement use cases as single-purpose handlers
- Use DTOs for input/output boundaries
- Handle transaction boundaries here

**DON'T:**
- Import infrastructure implementations directly
- Put business rules here (belongs in domain)
- Access HTTP request/response objects
- Depend on specific frameworks
```

#### Infrastructure Layer Tasks

```markdown
**Focus:** External world integration

**DO:**
- Implement repository interfaces from application layer
- Handle database operations and queries
- Integrate with external APIs and services
- Manage framework-specific configurations

**DON'T:**
- Contain business logic
- Be used directly by interface layer (go through application)
- Expose infrastructure details to inner layers
```

#### Interface Layer Tasks

```markdown
**Focus:** Entry points and presentation

**DO:**
- Handle HTTP requests/responses
- Validate input format (not business rules)
- Transform between external and internal representations
- Call application layer use cases

**DON'T:**
- Contain business logic
- Access infrastructure directly
- Bypass application layer
```

### 3.3 Code Quality Standards

For each piece of code written:

- [ ] Single responsibility - does one thing well
- [ ] Clear naming - intent is obvious
- [ ] Appropriate abstractions - not over or under-engineered
- [ ] Error handling - failures are handled gracefully
- [ ] Testable - can be unit tested in isolation
- [ ] Documented - complex logic is explained (but prefer clear code)

### 3.4 Testing Requirements

| Layer | Test Type | What to Test |
|-------|-----------|--------------|
| Domain | Unit | Entity behavior, value object validation, domain services |
| Application | Unit | Use case logic, with mocked ports |
| Infrastructure | Integration | Repository implementations, external service adapters |
| Interface | Integration/E2E | Request handling, response formatting, full flows |

---

## Step 4: Verify Implementation

### 4.1 Run Full Test Suite

```bash
# Run all tests
npm test  # or equivalent for your stack

# Ensure no regressions
# All existing tests should still pass
```

### 4.2 Validate Against Spec

Review each requirement from the spec:

```markdown
| Requirement | Status | Evidence |
|-------------|--------|----------|
| REQ-001 | ✅ Implemented | [How it's satisfied] |
| REQ-002 | ✅ Implemented | [How it's satisfied] |
```

### 4.3 Validate User Stories

For each user story, verify:

- [ ] The described behavior works as specified
- [ ] All acceptance criteria are met
- [ ] Edge cases are handled per spec

### 4.4 Architecture Compliance Check

Verify Clean Architecture rules are followed:

- [ ] Domain layer has no imports from outer layers
- [ ] Application layer only depends on domain
- [ ] Infrastructure implements application ports
- [ ] Interface only calls application layer
- [ ] No circular dependencies

---

## Step 5: Finalize

### 5.1 Code Cleanup

- [ ] Remove any debug code or temporary comments
- [ ] Ensure consistent formatting
- [ ] Remove unused imports
- [ ] Verify no TODO comments left unaddressed

### 5.2 Update Documentation

If needed, update:

- [ ] README with new feature documentation
- [ ] API documentation for new endpoints
- [ ] Configuration documentation for new settings

### 5.3 Update Spec Status

Update `.specs/$1/spec.md` status to reflect implementation:

```markdown
**Status:** Implemented
**Implementation Date:** [Date]
```

### 5.4 Completion Report

Provide summary to user:

```markdown
## Implementation Complete

**Feature:** [Feature Name]
**Spec:** `.specs/$1/spec.md`
**Plan:** `.specs/$1/plan.md`

### Tasks Completed
- [X] TASK-001: [Title]
- [X] TASK-002: [Title]
- ...

### Files Created/Modified
- `src/domain/entities/[Entity].ts` - Created
- `src/application/useCases/[UseCase].ts` - Created
- ...

### Tests Added
- X unit tests
- X integration tests

### Verification
- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Architecture compliance verified

### Ready For
- Code review
- QA testing
- Deployment to staging
```

---

## Handling Issues

### When a Task is Blocked

If you encounter a blocker:

1. Document the blocker clearly
2. Check if it's a dependency that should have been done first
3. If external blocker, notify user and pause
4. If solvable, resolve it and continue

### When Requirements Are Unclear

If spec or plan has gaps:

1. **DO NOT GUESS** - implementation should match spec exactly
2. Note the ambiguity
3. Ask user for clarification
4. Update spec/plan if needed before continuing

### When Tests Fail

If tests fail after implementation:

1. Determine if it's a regression (existing test) or new test
2. For regressions - fix the implementation, don't change the test
3. For new tests - verify test is correct, then fix implementation
4. Never skip or delete tests to make them pass

---

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Better Approach |
|--------------|---------|-----------------|
| **Skipping tests** | No verification of correctness | Write tests for each task |
| **Ignoring the plan** | Chaotic implementation | Follow task order strictly |
| **Layer violations** | Architecture degradation | Respect dependency rules |
| **Gold plating** | Adding unrequested features | Stick to spec requirements |
| **Big commits** | Hard to review and revert | Commit per task or logical unit |
| **Assuming intent** | Building wrong thing | Clarify spec ambiguities first |

---

## Output Checklist

When complete, you should have:

- [ ] All tasks from plan implemented
- [ ] All acceptance criteria met
- [ ] All tests passing (new and existing)
- [ ] Clean Architecture compliance verified
- [ ] Code cleaned up and formatted
- [ ] Documentation updated
- [ ] Completion report provided
- [ ] Ready for code review

---

## Quick Reference: Task States

```
pending ──► in_progress ──► completed
                │
                └──► blocked (resolve, then back to in_progress)
```

**Remember:** Follow the plan. When in doubt, ask. Quality over speed.