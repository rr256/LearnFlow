---
title: "ADR-010: Deliver Features Through Pull Requests With Automated Gates"
status: accepted
owner: development-and-operations
last_updated: 2026-07-30
related:
  - ../00-project-context.md
  - ../deployment/ci-cd.md
  - ../development/git-workflow.md
  - ../ai/engineering-ai.md
  - ../development/documentation-standards.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
---

# ADR-010: Deliver Features Through Pull Requests With Automated Gates

## Status

Accepted — 2026-07-30

## Context

Three gaps had accumulated between LearnFlow's approved workflow documentation and how work
actually reaches `main`.

**The documented change flow had no pull request step.** `development/git-workflow.md` ends its
standard flow at "Merge into main after approval", while every integration commit on `main` is in
fact a merged pull request. The practice was sound; only the documentation was silent, which left
the review boundary undefined for a new contributor or assistant.

**CI readiness was met but unimplemented.** `deployment/ci-cd.md` defines four conditions for
adding the first workflow: committed dependency configuration, at least one documented
deterministic check command, `.env.example` and `.gitignore` guarding against leakage, and checks
that run without manual local state. The backend foundation satisfied all four. Nothing enforced
them, so a branch could reach review with failing tests or unformatted code.

**Documentation correctness was checked only by hand.** `development/documentation-standards.md`
mandates front matter with five required fields, two distinct status vocabularies, resolving
relative links, and `## Related Documents` sections. These are mechanical properties reviewed
manually on every change — the kind of check a human performs unevenly and a script performs
identically every time.

A fourth force is specific to how this project is built. Implementation is largely AI-assisted, and
`ai/engineering-ai.md` already fixes the required reading, the stop-and-ask conditions, and the
completion report format. That workflow was re-derived from prose on every task, so the gates it
describes were applied with varying rigour.

## Decision

### Changes reach `main` through a pull request

Work happens on one short-lived branch using the prefixes in `git-workflow.md`, and integrates
through a pull request against `main`. Direct commits to `main` are not part of the workflow.

### Continuous integration runs on pull requests and pushes to `main`

`.github/workflows/pull-request.yml` defines two independent jobs on Python 3.14:

| Job | Checks |
| --- | --- |
| `backend` | `python -m ruff check .`, `python -m ruff format --check .`, `python -m pytest` |
| `documentation` | `python -m ruff check --config backend/pyproject.toml scripts/`, `python -m ruff format --check --config backend/pyproject.toml scripts/`, `python scripts/validate_docs.py` |

Each job installs dependencies and then runs the verification commands above. Every verification
command comes from the canonical local check set in
[coding standards](../development/coding-standards.md#local-quality-checks), so a CI failure is
reproducible on a developer machine; the dependency installation is setup rather than a check. The
canonical local set is the stricter of the two, because it adds `-W error` to the test run. The jobs
share no state, need no services, consume no secrets, and publish no artifacts.

**There are no frontend, database, container, or security-scanning jobs.** Each is added in the
change that introduces the artifact it would check, per the ci-cd.md rule that no check is added
merely because it is common.

### Documentation validation is mechanical

`scripts/validate_docs.py` enforces the parts of the documentation standards that a script can
verify. That document owns the enumeration and the two deliberate exemptions; see
[mechanical validation](../development/documentation-standards.md#mechanical-validation).

It parses front matter with PyYAML, pinned in `backend/requirements-dev.txt` as a development-only
dependency. Judgement-based review — duplicated decisions, terminology drift, missing ADRs — stays
with the `documentation-reviewer` agent and the project owner.

### AI-assisted delivery follows one repeatable workflow

`.claude/skills/deliver-feature/SKILL.md` encodes the `engineering-ai.md` workflow as an executable
sequence: read required documentation, state the task brief, stop for decisions, branch, implement,
verify, update documentation, validate it mechanically, run the documentation reviewer, review the
diff, commit once, push, open a pull request, report.

Invoking the skill is the explicit project-owner authorization that `git-workflow.md` requires for
an assistant to commit and push. It authorizes exactly that sequence on one branch and nothing
else.

### One approval gate, and a hard stop at the open pull request

The skill has a single gate before delivery, Stop Gate 1. Its conditions are listed canonically in
[stop-and-ask conditions](../ai/engineering-ai.md#stop-and-ask-conditions); this ADR does not restate
them. The skill presents options and a recommendation; the owner decides.

After that gate the skill runs to an open pull request without further prompting, and stops there
permanently. The prohibited actions are listed canonically in
[actions the delivery workflow never performs](../ai/engineering-ai.md#actions-the-delivery-workflow-never-performs);
merging, history rewriting, and credential handling are among them.

### The GitHub CLI is never installed or authenticated automatically

When `gh` is absent or unauthenticated, the skill pushes the branch, prints the compare URL, and
reports that the pull request was not created. Installing `gh`, authenticating it, and managing any
token remain human actions.

## Consequences

### Positive

- A failing test, lint error, formatting drift, broken documentation link, or invalid front matter
  is caught before review rather than during it.
- The review boundary is explicit: automation prepares, a human approves and merges.
- Documentation and code are verified together, which is what the documentation-as-deliverable rule
  in `documentation-standards.md` requires.
- Delivery steps no longer depend on how thoroughly prose was re-read on a given day.
- Every CI verification command belongs to the canonical local check set, so a CI failure reproduces
  offline.

### Negative

- Every change now waits on CI, which adds latency to trivial documentation edits.
- The validator enforces a subset of the standards; passing it is not evidence that documentation
  is good, only that it is well-formed.
- `scripts/` sits outside the Ruff configuration in `backend/pyproject.toml`, so every invocation
  covering it must name that configuration explicitly.
- A development-only dependency was added, so the docs job installs the backend development set to
  obtain it.
- Pinned action major versions need occasional maintenance.

### Mitigations

- Both jobs are small and cacheable, and they run in parallel.
- The `documentation-reviewer` agent and human review remain responsible for everything the
  validator cannot judge.
- The documentation job lints and format-checks `scripts/` against `backend/pyproject.toml` before
  running the validator, so repository-level scripts are held to the backend standards under one
  shared configuration. A separate root-level Ruff configuration is therefore unnecessary.
- Sharing one pinned dependency file keeps a single source of truth for the PyYAML version.

## Alternatives Considered

### Keep integrating without a pull request

Commit to `main`, or merge branches locally without a pull request.

**Rejected:** it removes the only place where CI results and a reviewable diff meet before
integration, and it contradicts the branch policy already approved in `ci-cd.md`.

### Review documentation by hand only

Rely on the `documentation-reviewer` agent and human review, with no validator.

**Rejected:** front matter fields, status vocabularies, dates, and link resolution are exactly
checkable. Leaving them to judgement spends review attention on mechanical properties and still
misses some, and a broken link is discovered by the next reader rather than by CI.

### Hand-roll a front-matter parser to avoid the dependency

Parse the fixed front-matter subset with the standard library.

**Rejected:** a subset parser accepts malformed YAML that a real parser rejects, so a document that
breaks other tooling could pass validation. PyYAML is development-only, does not enter the runtime
dependency set, and never runs in the application process.

### Add frontend, container, and database CI jobs now

Configure the full pipeline described in `ci-cd.md` immediately.

**Rejected:** no `frontend/`, Dockerfile, `compose.yaml`, or migration exists. The jobs would
either be skipped or fail, which trains reviewers to ignore CI.

### Let automation merge once CI is green

Enable auto-merge for changes that pass all checks.

**Rejected:** CI verifies mechanical properties, not that a change matches approved product intent.
`engineering-ai.md` reserves review of consequential changes and scope for the project owner, and
merging is the point at which that judgement is applied.

## Implementation Notes

- Workflow: `.github/workflows/pull-request.yml` — `pull_request` and `push` on `main`,
  `permissions: contents: read`, concurrency cancellation for superseded runs.
- Validator: `scripts/validate_docs.py`, run from the repository root; `--root PATH` targets a
  different tree, which is how its failure cases are exercised against fixtures. It requires
  Python 3.14, matching the backend and the workflow.
- Dependency: `PyYAML==6.0.3` in `backend/requirements-dev.txt`.
- Skill: `.claude/skills/deliver-feature/SKILL.md`; the read-only reviewer it invokes is
  `.claude/agents/documentation-reviewer.md`.
- Branch protection on `main` is a repository setting, not a repository file. It is a separate
  owner decision and is not configured by this change.
- Recorded as DEC-023 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [CI/CD strategy](../deployment/ci-cd.md) — the pipeline policy this decision implements
- [Git workflow](../development/git-workflow.md) — branch, commit, and review rules
- [Engineering AI workflow](../ai/engineering-ai.md) — roles, gates, and reporting format
- [Documentation standards](../development/documentation-standards.md) — the rules the validator
  enforces
- [Coding standards](../development/coding-standards.md) — the canonical local quality checks
- [Repository and folder structure](../development/folder-structure.md) — where the workflow, skill,
  and validator files live
- [ADR-007: Use repository documentation and ADRs as shared project memory](ADR-007-documentation-and-adr-policy.md)
- [Architecture decision register](../architecture/decisions.md)
