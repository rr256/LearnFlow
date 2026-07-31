---
title: LearnFlow Git Workflow
status: approved
owner: development
last_updated: 2026-07-31
related:
  - ../00-project-context.md
  - coding-standards.md
  - documentation-standards.md
  - ../ai/engineering-ai.md
  - ../deployment/ci-cd.md
  - ../adr/ADR-010-feature-delivery-workflow.md
---

# LearnFlow Git Workflow

## Purpose

Define a lightweight, reviewable version-control workflow for LearnFlow.

The project is initially maintained by one developer with AI assistance. The workflow protects the stable project state without adding unnecessary team-process overhead.

## Branch Model

### `main`

`main` is the stable, integrated branch.

- It should always contain a coherent project state.
- Do not use it for unfinished experimental work when a feature branch is practical.
- Documentation and code on `main` should agree.

### Short-Lived Working Branches

Create one focused branch for each meaningful change:

```text
feat/study-goal-setup
feat/resource-ingestion
fix/revision-scheduling
docs/domain-model
chore/docker-local-setup
```

Branch prefixes:

| Prefix | Use |
| --- | --- |
| `feat/` | New learner-facing capability. Matches the `feat` Conventional Commit type and the repository's branch history. |
| `fix/` | Correct behavior or defect. |
| `docs/` | Documentation-only change. |
| `refactor/` | Internal restructuring without intended behavior change. |
| `test/` | Test-only or test-focused change. |
| `chore/` | Tooling, configuration, or maintenance work. |

Avoid long-lived `develop` branches in the early project. A stable `main` plus focused branches is easier to understand and review.

## Standard Change Flow

```text
Update local main
        ↓
Create focused branch
        ↓
Read required docs and define task scope
        ↓
Implement + test + update docs
        ↓
Review diff
        ↓
Commit focused change(s)
        ↓
Push branch and open a pull request
        ↓
CI runs the checks in the CI/CD strategy
        ↓
Review, then merge into main after approval
```

## Pull Requests

A change integrates into `main` through a pull request, not a direct commit.

- Open the pull request against `main` from the focused branch.
- Describe the outcome, the changed files, the verification performed, the documentation updated,
  the assumptions relied upon, and any open items. This is the Completion Report Format from
  [engineering AI workflow](../ai/engineering-ai.md).
- The checks in [CI/CD strategy](../deployment/ci-cd.md) run on every pull request targeting `main`
  and on every push to `main`. A failing check blocks merge until it is understood or the project
  owner makes an explicit decision.
- Reviewing and merging a pull request is a human action. It is never automated and never delegated
  to an AI assistant.

Branch protection on `main` is a repository setting rather than a repository file; it is a separate
project-owner decision.

## Commit Standards

Use concise Conventional Commit-style messages:

```text
feat(planner): generate daily plan items
fix(progress): preserve manual learning stage updates
docs(domain): define topic performance evidence
test(rag): cover failed ingestion retry
refactor(api): move mentor request mapping to presentation layer
chore(docker): add local postgres health check
```

### Commit Rules

- One commit should represent one understandable change.
- Do not mix unrelated formatting, refactoring, or generated files into a feature commit.
- Include migrations, affected schema docs, and relevant tests in the same logical change.
- Include documentation updates when implementation changes approved behavior.
- Never commit secrets, learner resources, database volumes, vector indexes, virtual environments, or model files.

## Review Checklist

Before merging or committing a meaningful change, check:

- [ ] The change traces to approved requirements/documentation.
- [ ] Scope is limited to the intended task.
- [ ] Architecture/dependency rules are respected.
- [ ] Relevant tests/checks pass.
- [ ] Errors and edge cases are handled appropriately.
- [ ] Schema/API/documentation changes are updated together.
- [ ] No secrets or private learner files are included.
- [ ] The diff contains no unintended generated or unrelated files.

## AI-Assisted Changes

AI assistants may create or modify files only within the assigned task scope.

Before accepting AI-assisted changes:

1. Review the changed-file list and diff.
2. Verify the reported tests/checks yourself or through a trusted repeatable command.
3. Confirm that no architecture or dependency decision was made silently.
4. Confirm documentation/ADR updates when applicable.

AI assistants must not create commits, force-push, rewrite history, or merge branches unless the project owner explicitly asks.

### Standing authorization for the delivery workflow

Invoking the `deliver-feature` skill in `.claude/skills/deliver-feature/SKILL.md` is the explicit
project-owner request required above. It authorizes exactly one sequence on one branch: create the
branch, implement, verify, update documentation, create one scoped commit, push that branch, and
open a pull request.

It authorizes nothing else. What the workflow must never do is listed canonically in
[Actions the delivery workflow never performs](../ai/engineering-ai.md#actions-the-delivery-workflow-never-performs)
— merging, history rewriting, credential handling, and the rest. That list is authoritative; this
document does not restate it.

The skill stops at the open pull request in every case, and the project owner still performs the four
review steps above before merging.

## Database Migration Changes

For any schema change:

- Use a dedicated focused branch.
- Include the Alembic migration, persistence mapping, tests, and `docs/database/schema.md` update.
- Never edit a migration that has already been committed/shared/applied; create a new migration.
- Review upgrade/downgrade or forward-recovery behavior before merge.

## Documentation Changes

- Use `docs/` branches when changes are documentation-only.
- Major architectural decisions require an ADR in the same branch or before related implementation begins.
- Keep `docs/00-project-context.md` and the decision register aligned with new approved decisions.

## Releases and Tags

Formal releases are not required during early architecture work.

When a usable milestone is reached, create an annotated Git tag such as:

```text
v0.1.0
v0.2.0
```

Release notes should summarize learner-facing changes, migrations/configuration steps, and known limitations.

## Recovery Rules

- Prefer a new corrective commit over rewriting shared history.
- Do not use destructive Git commands such as hard reset on a branch containing work that has not been safely reviewed/backed up.
- When a bad migration or production-like change occurs, follow the migration recovery policy rather than relying on Git rollback alone.

## Related Documents

- [Project context](../00-project-context.md)
- [Coding standards](coding-standards.md)
- [Documentation standards](documentation-standards.md)
- [CI/CD strategy](../deployment/ci-cd.md) — the checks that run on every pull request
- [ADR-010: Deliver features through pull requests with automated gates](../adr/ADR-010-feature-delivery-workflow.md)
- [Database migrations](../database/migrations.md)
- [Engineering AI workflow](../ai/engineering-ai.md)
