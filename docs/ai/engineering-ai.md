---
title: LearnFlow Engineering AI Workflow
status: approved
owner: project-governance
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - prompts.md
  - ../development/documentation-standards.md
  - ../development/git-workflow.md
---

# LearnFlow Engineering AI Workflow

## Purpose

Define how AI assistants help build LearnFlow while keeping the learner's product vision, architecture, documentation, and codebase consistent.

AI assistants are collaborators, not the source of product authority. The repository documentation and approved ADRs are the shared project memory; individual chat histories are temporary working context.

## Roles

### Project Owner / Tech Lead — Learner/Developer

The project owner makes final product, architecture, scope, privacy, and release decisions.

**Responsibilities:**

- Approve durable decisions and ADRs.
- Decide what enters the current milestone.
- Review consequential file changes and test results.
- Prevent scope expansion that conflicts with the MVP.

### Architecture and Documentation Assistant — ChatGPT/Codex

Used for product reasoning, architecture design, documentation drafting, requirement review, and design/code review.

**Responsibilities:**

- Help clarify trade-offs and identify missing decisions.
- Update or propose documentation that reflects approved conclusions.
- Review plans and changes against Clean Architecture and project constraints.
- Avoid silently imposing unsupported technology choices.

### Implementation Assistant — Claude Code and/or Codex

Used for focused, repository-scoped implementation tasks.

**Responsibilities:**

- Read required project context before editing.
- Implement only the assigned task.
- Run relevant checks/tests where available.
- Report changed files, verification performed, assumptions, and unresolved issues.

### Product Runtime — Ollama

Used by LearnFlow itself for local AI generation, not as the primary engineering authority for the project.

**Responsibilities:**

- Power local mentor explanations and supported generated practice content.
- Be tested through LearnFlow's provider interfaces.

## Shared Source of Truth

Before design or implementation work, every assistant must treat these as authoritative:

1. `docs/00-project-context.md`
2. The task-specific documents linked by the Required Reading table.
3. Approved ADRs and the architecture decision register.
4. Existing code and tests, when they do not conflict with approved documentation.

If documentation, code, and a chat instruction conflict, stop and report the conflict. Do not silently choose one.

## Required Context by Task

| Task type | Required documents |
| --- | --- |
| Product/MVP scope | `00-project-context.md`, `vision/vision.md`, `requirements/` |
| Backend/domain use case | `00-project-context.md`, `domain/`, `architecture/`, relevant API/database docs |
| Database change | `00-project-context.md`, `domain/`, `database/`, `architecture/decisions.md` |
| Frontend feature | `00-project-context.md`, `requirements/`, `api/`, `development/folder-structure.md` |
| RAG/AI work | `00-project-context.md`, `rag/`, `ai/`, `architecture/provider-pattern.md` |
| Docker/deployment work | `00-project-context.md`, `deployment/`, `development/tech-stack.md` |
| Documentation/ADR work | `00-project-context.md`, `development/documentation-standards.md`, `adr/` |

## Standard AI Task Workflow

```text
Read task brief and required documentation
        ↓
State scope, assumptions, files likely to change, and verification plan
        ↓
Make only the approved scoped changes
        ↓
Run relevant validation/tests
        ↓
Report result, changed files, tests, and open questions
        ↓
Update relevant docs/ADR when the change alters an approved behavior
```

## Required Task Brief Format

Every meaningful implementation task should provide:

```text
Role
Goal
Required reading
Allowed scope/files
Requirements and acceptance criteria
Constraints / prohibited changes
Verification required
Stop condition / approval gate
```

Reusable examples belong in `prompts.md`.

## Scope Rules

AI assistants may:

- Read relevant documentation and source files.
- Propose improvements or identify gaps.
- Implement approved, focused tasks.
- Add tests and update directly affected documentation.

AI assistants must not, without explicit approval:

- Redesign the architecture or substitute core technologies.
- Add dependencies/frameworks because they are popular or convenient.
- Change database schema without a migration and related documentation.
- Make destructive file/database changes.
- Expose secrets, credentials, learner data, or private resources.
- Expand the MVP with future features.
- Modify unrelated files merely for cleanup.

## Parallel/Subagent Work

Specialized AI roles may be used later for architecture, documentation, backend, database, frontend, RAG, testing, and DevOps.

Until the repository has stable code boundaries:

- Do not allow multiple agents to edit the same files concurrently.
- Prefer one implementation owner per bounded task.
- Use parallel work first for read-only review, research, testing, or non-overlapping documentation.
- Integrate one completed change set at a time.

The project does not need a custom engineering-agent orchestrator now. Claude Code/Codex task delegation and the documentation workflow are sufficient.

## Change and Review Policy

- Architecture changes require updated documentation and an ADR when durable.
- Functional behavior changes require updated requirements/API/domain documentation as applicable.
- Database changes require updated schema documentation and an Alembic migration.
- Provider changes require architecture/provider documentation and evaluation of data-migration effects.
- Each change should be small enough to review and commit independently.

## Completion Report Format

An implementation assistant should end a task with:

```text
Outcome: what is now complete
Changed: files created/modified
Verified: commands/tests/checks run and results
Documentation: docs/ADRs updated
Assumptions: decisions relied upon
Open items: anything requiring project-owner direction
```

## Stop-and-Ask Conditions

The assistant must stop for direction when:

- Required documentation is missing or conflicts with code.
- A task needs a new external dependency or provider.
- A schema change could lose or reinterpret learner data.
- A request expands the MVP into a deferred capability.
- A choice materially changes privacy, security, cost, or product behavior.
- The assistant cannot verify a high-impact change safely.

## Related Documents

- [Project context](../00-project-context.md)
- [AI prompt library](prompts.md)
- [Documentation standards](../development/documentation-standards.md)
- [Git workflow](../development/git-workflow.md)
- [Architecture decision register](../architecture/decisions.md)
