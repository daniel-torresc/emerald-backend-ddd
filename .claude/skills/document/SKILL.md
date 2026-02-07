---
name: document
description: ""
argument-hint:
---

Update the following files before marking the task as done.

### README.md

- Add new functionality to the Features section.
- Update Installation/Setup instructions if dependencies or configuration changed.
- Add or update Usage examples for any new APIs, endpoints, or CLI commands.
- Update Architecture diagrams or descriptions if structural changes were made.
- Keep the tone user-facing and concise.

### CLAUDE.md

- Add or update project conventions if new patterns were established.
- Update file/folder structure references if the project layout changed.
- Document any new commands (build, test, lint) relevant to the implemented feature.
- Record key decisions or constraints that emerged during implementation.
- Keep entries actionable — write them as instructions for future sessions.

### Rules

- Do not rewrite entire files. Only modify sections affected by the implemented spec.
- Keep changes minimal and accurate. Reflect what was actually built, not aspirational state.
- If a required section does not exist, create it following the existing document structure.
- Commit documentation updates in the same changeset as the implementation.