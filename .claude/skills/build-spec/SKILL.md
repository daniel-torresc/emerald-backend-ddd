---
name: build-spec
description: "Action-oriented skill for improving specifications using Spec Driven Design (SDD). Use when: (1) User provides an initial spec that needs refinement, (2) Creating new feature specifications from rough requirements, (3) Formalizing ideas into clear requirement documents, (4) Reviewing and enhancing existing specifications for completeness."
argument-hint: [spec-directory-name]
---

# Build Specification (Spec Driven Design)

Transform an initial specification into a clear, comprehensive requirements document using Spec Driven Design (SDD) principles.

**Purpose:** Produce a clarified spec file that defines WHAT needs to be built. This spec will later be consumed by an agent who determines HOW to build it.

---

## ⚠️ CRITICAL: Mandatory Clarification Phase

**YOU MUST NOT GENERATE THE FINAL SPEC FILE UNTIL ALL AMBIGUITIES ARE RESOLVED.**

Before writing any specification output, you MUST have complete and unambiguous understanding of:

- All functional and non-functional requirements
- Business context and goals
- User needs and acceptance criteria
- Constraints and boundaries
- Edge cases and error scenarios
- Dependencies and integration needs

**The clarification phase is NON-NEGOTIABLE.** Ask as many questions as needed across multiple rounds until you have zero ambiguity about what needs to be built.

---

## Process Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: RECEIVE & ANALYZE                                          │
│  Read the initial spec, identify gaps, categorize issues            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: CLARIFY (MANDATORY - ITERATE UNTIL COMPLETE)               │
│  Ask targeted questions, resolve ALL ambiguities                    │
│  ⚠️ DO NOT PROCEED UNTIL EVERYTHING IS CLEAR                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: GENERATE SPEC FILE                                         │
│  Write the clarified specification document                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: VALIDATE & CONFIRM                                         │
│  Review with user, get approval                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Receive & Analyze Initial Spec

### 1.1 Read the Input

Carefully read the user's initial specification defined in the following file:
- .specs/$1/draft.md

### 1.2 Perform Gap Analysis

Categorize what you find into:

| Category | What to Look For |
|----------|------------------|
| **Explicit** | Clearly stated requirements with no ambiguity |
| **Implicit** | Requirements implied but not stated (needs confirmation) |
| **Missing** | Critical information not present at all |
| **Ambiguous** | Statements that could be interpreted multiple ways |
| **Conflicting** | Requirements that contradict each other |

### 1.3 Evaluate Against Key Dimensions

Check the initial spec for coverage of:

1. **Business Context** - Why is this being built? What problem does it solve?
2. **Users & Personas** - Who will use this? What are their needs?
3. **Functional Requirements** - What should the system do?
4. **Non-Functional Requirements** - Performance, security, scalability expectations
5. **Constraints** - Budget, timeline, technology, regulatory limitations
6. **Acceptance Criteria** - How do we know it's done correctly?
7. **Edge Cases** - What happens in unusual situations?
8. **Dependencies** - What does this rely on or integrate with?

### 1.4 Output: Gap Analysis Summary

Present your analysis to the user:

```markdown
## Initial Spec Analysis

### What's Clear
- [List explicit, unambiguous requirements]

### What Needs Clarification
- [List implicit assumptions needing confirmation]
- [List ambiguous statements with possible interpretations]

### What's Missing
- [List critical gaps by category]

### Potential Conflicts
- [List any contradictions found]
```

---

## Step 2: Clarify (MANDATORY ITERATION)

### ⚠️ BLOCKING REQUIREMENT

**You CANNOT proceed to Step 3 until ALL of the following are true:**

- [ ] Every ambiguous statement has been clarified
- [ ] All implicit assumptions have been confirmed or corrected
- [ ] Missing critical information has been provided
- [ ] Conflicts have been resolved
- [ ] You can explain the full scope without using "probably" or "might"

### 2.1 Question Categories

Structure your clarifying questions by category:

#### Business & Context
- What is the business goal or problem being solved?
- What is the expected outcome or success metric?
- Why is this being built now?
- What happens if this isn't built?

#### Users & Personas
- Who are the primary users?
- What is their technical sophistication level?
- What are they trying to accomplish?
- What devices/platforms do they use?

#### Functional Requirements
- What exactly should happen when [action]?
- What is the expected output of [feature]?
- Are there variations or modes for [functionality]?
- What should NOT be included in scope?

#### Non-Functional Requirements
- What are the performance expectations?
- What security requirements apply?
- Are there compliance or regulatory constraints?
- What are the availability/uptime requirements?

#### Constraints & Boundaries
- What is explicitly out of scope?
- Are there technology constraints?
- What are the timeline expectations?
- Are there budget limitations?

#### Edge Cases & Errors
- What happens when [boundary condition]?
- How should the system behave when [failure scenario]?
- What error messages should users see?
- What are the recovery paths?

#### Acceptance Criteria
- How will we know this is complete?
- What specific scenarios must work?
- Who approves the final result?

#### Dependencies
- What existing systems does this interact with?
- Are there external services or APIs involved?
- What data sources are needed?
- Are there team dependencies?

### 2.2 Questioning Strategy

**Ask questions in batches.** Group related questions together:

```markdown
I need clarification on several aspects before I can create a complete spec:

### User Context
1. Who is the primary user persona for this feature?
2. What is their main goal when using this?
3. What devices will they access this from?

### Core Functionality
4. When a user does [action], what exactly should happen?
5. Are there different behaviors for different user types?
6. What should NOT happen (explicit exclusions)?

### Success Criteria
7. How will we measure if this is successful?
8. What are the must-have vs nice-to-have requirements?
```

### 2.3 Iterative Clarification

After receiving answers:

1. **Confirm understanding** - Restate complex answers to verify
2. **Follow up** - Ask deeper questions if answers reveal new gaps
3. **Check consistency** - Ensure new information doesn't conflict
4. **Update mental model** - Track what's now clear vs. still unclear

**Repeat until you have ZERO remaining questions.**

### 2.4 Clarification Completion Checklist

Before proceeding, verify:

- [ ] I can describe the feature without any "TBD" items
- [ ] I understand all user journeys from start to finish
- [ ] I know exactly what data is involved
- [ ] I can enumerate all error cases and their handling
- [ ] I know the acceptance criteria completely
- [ ] I have no remaining questions

**If any checkbox is unchecked, return to questioning.**

---

## Step 3: Generate Spec File

### 3.1 File Location

```
.specs/$1/spec.md
```

### 3.2 Specification Template

```markdown
# [Feature Name] Specification

**Version:** 1.0
**Status:** Draft | Approved
**Author:** [Name]
**Date:** [Date]

---

## 1. Overview

[One paragraph describing what this feature does and why it matters]

---

## 2. Background & Context

### Problem Statement
[What problem does this solve?]

### Business Goals
[What are the expected business outcomes?]

### Success Metrics
[How will success be measured?]

---

## 3. Scope

### In Scope
- [What IS included]

### Out of Scope
- [What is explicitly NOT included]

---

## 4. Users & Personas

### Primary Users
[Who are the main users and what are their characteristics?]

### User Goals
[What are users trying to accomplish?]

---

## 5. Requirements

### 5.1 Functional Requirements

#### REQ-001: [Requirement Title]
**Priority:** Must Have | Should Have | Could Have
**Description:** [What the system must do]
**Acceptance Criteria:**
- [ ] [Specific, testable criterion]
- [ ] [Another criterion]

[Repeat for each requirement]

### 5.2 Non-Functional Requirements

#### Performance
- [Performance expectations]

#### Security
- [Security requirements]

#### Scalability
- [Scalability expectations]

#### Availability
- [Uptime/availability requirements]

---

## 6. User Stories

### US-001: [Story Title]
**As a** [type of user]
**I want** [goal]
**So that** [benefit]

**Acceptance Criteria:**
- [ ] Given [context], when [action], then [outcome]

[Repeat for each user story]

---

## 7. Edge Cases & Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| [Edge case] | [How system should respond] |

---

## 8. Dependencies

### Internal Dependencies
- [Systems, teams, or components this depends on]

### External Dependencies
- [External services, APIs, or third parties]

---

## 9. Constraints

- [Technology constraints]
- [Timeline constraints]
- [Regulatory/compliance constraints]
- [Other limitations]

---

## 10. Open Questions

[Any remaining questions that couldn't be resolved - should be minimal]

---

## 11. Appendix

### Glossary
- **[Term]:** [Definition]

### References
- [Links to related documents, mockups, discussions]

---

```

### 3.3 Writing Guidelines

When filling in the template:

- **Be specific** - Avoid vague language like "should be fast" (say "response time < 200ms")
- **Be testable** - Every requirement should be verifiable
- **Be complete** - Cover happy paths AND edge cases
- **Be consistent** - Use the same terminology throughout
- **Be concise** - Don't repeat information across sections

---

## Step 4: Validate & Confirm

### 4.1 Self-Review Checklist

Before presenting to user:

- [ ] All sections of the template are filled in
- [ ] Requirements are numbered and prioritized
- [ ] Acceptance criteria are specific and testable
- [ ] Edge cases are documented
- [ ] No "TBD" or placeholder text remains
- [ ] Language is clear and unambiguous

### 4.2 User Confirmation

Present the completed spec to the user:

```markdown
I've created the specification document at [path].

**Summary:**
- [X] functional requirements covering [areas]
- [X] user stories with acceptance criteria
- [X] edge cases and error handling documented
- [X] dependencies and constraints identified

**Please review and confirm:**
1. Are all requirements captured correctly?
2. Is anything missing or unclear?
3. Are the priorities accurate?
4. Is this spec approved?
```

---

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Better Approach |
|--------------|---------|-----------------|
| **Spec by assumption** | Making decisions without user input | Ask clarifying questions |
| **Premature technical details** | Specifying HOW before clarifying WHAT | Focus on requirements, not implementation |
| **Vague acceptance criteria** | "Should work well" | Specific, measurable criteria |
| **Missing edge cases** | Only happy path | Explicitly cover error scenarios |
| **Skipping clarification** | Rushing to write spec | Iterate until zero ambiguity |
| **Over-specifying** | Including implementation details | Describe behavior, not mechanism |

---

## Output Checklist

When complete, you should have:

- [ ] Gap analysis shared with user
- [ ] All clarifying questions answered
- [ ] Spec file created at `.specs/$1/spec.md`
- [ ] Spec validated against checklist
- [ ] User confirmation received

**Remember: A spec written without full understanding leads to rework. The time spent clarifying is always worth it.**
