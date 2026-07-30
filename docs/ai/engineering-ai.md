---
title: LearnFlow Engineering AI Workflow
status: approved
owner: project-governance
last_updated: 2026-07-30
related:
  - ../00-project-context.md
  - prompts.md
  - ../development/documentation-standards.md
  - ../development/git-workflow.md
  - ../deployment/ci-cd.md
  - ../adr/ADR-010-feature-delivery-workflow.md
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

## Automated Delivery Workflow

The workflow above is implemented as a Claude Code skill, `.claude/skills/deliver-feature/SKILL.md`,
so the same gates apply on every task instead of being re-derived from prose.

### Phases

| Phase | Action |
| --- | --- |
| 1 | Read `00-project-context.md`, the Required Context documents for the task, the development standards, terminology, and relevant accepted ADRs. |
| 2 | State the task brief in the Required Task Brief Format, including the files expected to change. |
| 3 | **Stop for decisions.** See below. |
| 4 | Create one focused branch from an updated `main`, using a prefix from the [git workflow](../development/git-workflow.md). |
| 5 | Implement inside the agreed scope, following the coding standards and folder structure. |
| 6 | Add or update tests, then run the backend commands in the canonical [local quality checks](../development/coding-standards.md#local-quality-checks). |
| 7 | Update every document the change affects, in the same change. |
| 8 | Run the remaining commands in that same canonical set: the `scripts/` lint and format checks, and the documentation validator. |
| 9 | Run the `documentation-reviewer` agent and report its findings. |
| 10 | Review the diff against the Review Checklist in the git workflow. |
| 11 | Create one scoped commit, push the branch, and open a pull request. |
| 12 | Report using the Completion Report Format. |

### The single approval gate

Phase 3 is the only gate before delivery. The assistant stops for every condition in
[Stop-and-Ask Conditions](#stop-and-ask-conditions), which is the canonical list. It presents options
and a recommendation; the project owner decides. After the gate the workflow runs to an open pull
request without further prompting.

### Actions the delivery workflow never performs

This is the canonical list. `.claude/skills/deliver-feature/SKILL.md` mirrors it exactly, and other
documents link here rather than restating it.

The workflow never:

- Merges a pull request — no `gh pr merge`, no auto-merge, no local merge into `main`.
- Force-pushes or rewrites history — no `--force`, `--force-with-lease`, `rebase`, `reset --hard`,
  `commit --amend`, or `filter-branch` on shared work.
- Deletes a branch, local or remote.
- Commits to `main`, or pushes a branch it did not create.
- Installs or authenticates the GitHub CLI, or handles credentials, tokens, or CI secrets.
- Reads, writes, or commits a real `.env` file. `.env.example` may be updated when a new variable is
  documented.
- Modifies `.claude/settings.json`.
- Commits virtual environments, `node_modules`, learner PDFs or notes, database volumes, vector
  indexes, model files, coverage output, or `__pycache__`.
- Marks a document `approved` or an ADR `accepted`, or drafts an ADR without direction.
- Adds a dependency that did not pass Stop Gate 1.
- Disables, skips, or weakens a test or check to make a step pass.
- Expands MVP scope into a deferred capability.

When the GitHub CLI is absent or unauthenticated, the workflow pushes the branch, prints the compare
URL, and reports that the pull request was not created.

Approving design decisions, reviewing and merging pull requests, and handling credentials or external
services remain human responsibilities.

### Review agent

`.claude/agents/documentation-reviewer.md` reviews the documentation set and returns findings only.
It has read-only tools, makes no decisions, resolves no conflicts, and drafts no ADRs. It complements
`scripts/validate_docs.py`, which checks the mechanical rules described in
[documentation standards](../development/documentation-standards.md).

Note the two unrelated senses of *agent* in this repository. A **product agent** is a LearnFlow
learning responsibility, described in [LearnFlow product agents](learnflow-agents.md) and
[ADR-006](../adr/ADR-006-custom-agent-orchestration.md). An **assistant subagent** is an engineering
review role defined under `.claude/agents/`, such as the documentation reviewer. They share a word,
not a concept; `docs/domain/terminology.md` remains product-domain vocabulary only.

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

This is the canonical list, and it is **Stop Gate 1** of the [automated delivery workflow](#automated-delivery-workflow). Other documents and the delivery skill refer to it or mirror it exactly; they do not restate it in different words.

The assistant must stop and ask the project owner for direction when a task touches:

- Clean Architecture layer boundaries or dependency direction.
- A new external dependency, framework, or provider.
- A new domain concept or entity, or a term absent from [terminology](../domain/terminology.md).
- A database schema change, including any migration that could lose or reinterpret learner data.
- A public HTTP API contract — a new endpoint, a changed shape, or changed status codes.
- Privacy, secrets, authentication, authorization, or learner-data handling.
- Security-relevant behavior of any kind.
- Cost or product behavior, where the choice changes either materially.
- Documentation that is missing, that conflicts with code or another document, or that records only a placeholder where the task needs an approved decision.
- MVP scope, where the request expands into a deferred capability.
- A high-impact change the assistant cannot verify safely.

The assistant presents options and a recommendation. The project owner decides.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-007: Use repository documentation and ADRs as shared project memory](../adr/ADR-007-documentation-and-adr-policy.md) — why assistants work from `docs/` rather than chat history
- [AI prompt library](prompts.md)
- [Documentation standards](../development/documentation-standards.md)
- [Git workflow](../development/git-workflow.md)
- [Coding standards](../development/coding-standards.md) — the canonical local quality checks the workflow runs
- [CI/CD strategy](../deployment/ci-cd.md) — the checks the delivery workflow must pass
- [ADR-010: Deliver features through pull requests with automated gates](../adr/ADR-010-feature-delivery-workflow.md) — why the workflow is automated to this boundary
- [Repository and folder structure](../development/folder-structure.md) — where `.claude/` definitions live
- [Architecture decision register](../architecture/decisions.md)
