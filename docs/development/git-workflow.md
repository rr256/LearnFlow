---
title: LearnFlow Git Workflow
status: approved
owner: development
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - coding-standards.md
  - documentation-standards.md
  - ../ai/engineering-ai.md
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
feature/study-goal-setup
feature/resource-ingestion
fix/revision-scheduling
docs/domain-model
chore/docker-local-setup
```

Branch prefixes:

| Prefix | Use |
| --- | --- |
| `feature/` | New learner-facing capability. |
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
Merge into main after approval
```

## Commit Standards

Use concise Conventional Commit-style messages:

```text
feat(planner): generate daily plan items
fix(progress): preserve manual learning stage updates
docs(domain): define external test performance evidence
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
- [Database migrations](../database/migrations.md)
- [Engineering AI workflow](../ai/engineering-ai.md)
