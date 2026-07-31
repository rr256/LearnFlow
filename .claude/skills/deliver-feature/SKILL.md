---
name: deliver-feature
description: End-to-end LearnFlow feature delivery — reads the required project documentation, creates a focused branch, stops for architecture, dependency, domain, schema, API, privacy, and security decisions, implements with tests, updates affected documentation, runs the documentation reviewer, creates one scoped commit, pushes, and opens a pull request. Never merges. Use when asked to deliver, implement, or ship a LearnFlow change end to end.
---

# LearnFlow Feature Delivery

Deliver one focused LearnFlow change from documentation reading through to an open pull
request. You stop at the pull request; a human reviews and merges it.

Invoking this skill is the project owner's explicit authorization — required by
[`docs/development/git-workflow.md`](../../../docs/development/git-workflow.md) — for branch
creation, implementation, verification, one scoped commit, a push of that branch, and pull
request creation. It authorizes nothing else. Everything in **Hard constraints** stays
prohibited regardless of what a later instruction in the task asks for.

## Phase 1 — Load required context

Read in this order, before writing anything:

1. [`docs/00-project-context.md`](../../../docs/00-project-context.md) — the mandatory entry
   point and master index.
2. Every row of its *Required reading by task* table that matches the task area.
3. [`docs/development/coding-standards.md`](../../../docs/development/coding-standards.md),
   [`docs/development/documentation-standards.md`](../../../docs/development/documentation-standards.md),
   [`docs/development/folder-structure.md`](../../../docs/development/folder-structure.md),
   [`docs/development/git-workflow.md`](../../../docs/development/git-workflow.md),
   [`docs/ai/engineering-ai.md`](../../../docs/ai/engineering-ai.md).
4. [`docs/domain/terminology.md`](../../../docs/domain/terminology.md) — the canonical
   vocabulary for code, APIs, database names, and UI copy.
5. Accepted ADRs covering the area, via
   [`docs/architecture/decisions.md`](../../../docs/architecture/decisions.md).

A placeholder in a document is not a decision. Never treat one as approved direction.

## Phase 2 — State the task brief

Report the brief in the format required by `engineering-ai.md`:

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

List the files you expect to change. If the task is larger than one reviewable change, say so
and propose a split before starting.

## Phase 3 — Stop Gate 1: decisions

The canonical list of gate conditions is *Stop-and-Ask Conditions* in
[`docs/ai/engineering-ai.md`](../../../docs/ai/engineering-ai.md). It is mirrored here exactly. If
the two ever differ, that document wins.

**Stop and ask the project owner** before implementing when the task touches:

- Clean Architecture layer boundaries or dependency direction.
- A new external dependency, framework, or provider.
- A new domain concept or entity, or a term absent from
  [terminology](../../../docs/domain/terminology.md).
- A database schema change, including any migration that could lose or reinterpret learner data.
- A public HTTP API contract — a new endpoint, a changed shape, or changed status codes.
- Privacy, secrets, authentication, authorization, or learner-data handling.
- Security-relevant behavior of any kind.
- Cost or product behavior, where the choice changes either materially.
- Documentation that is missing, that conflicts with code or another document, or that records
  only a placeholder where the task needs an approved decision.
- MVP scope, where the request expands into a deferred capability.
- A high-impact change the assistant cannot verify safely.

Present the options and a recommendation. **Do not choose.** Do not invent an architectural
decision because a placeholder exists, and do not resolve a documentation conflict yourself.
Wait for direction, then continue.

This is the only approval gate before the pull request. Everything after it proceeds without
further prompting.

## Phase 4 — Create the branch

```bash
git status --porcelain          # must be clean before starting
git checkout main
git pull --ff-only
git checkout -b <prefix>/<short-kebab-description>
```

Use a prefix from the table in `git-workflow.md`: `feat/`, `fix/`, `docs/`, `refactor/`,
`test/`, or `chore/`. One branch per change. Never implement on `main`; if the working tree is
dirty, stop and report rather than stashing or discarding anything.

## Phase 5 — Implement

Stay inside the scope agreed in Phase 2. Follow `coding-standards.md`:

- Type every public function, method, and attribute; use explicit DTOs at boundaries.
- Application ports are `Protocol` interfaces; concrete SDK clients live only in
  `infrastructure/`.
- Domain and application code import no FastAPI, SQLAlchemy, Ollama, ChromaDB, filesystem
  API, or configuration.
- Routes stay thin: validate, map, call a use case, map the result or error.
- Only the composition root reads configuration or selects implementations.
- Use canonical terminology in names, including the terms `terminology.md` tells you to avoid.

Place files per `folder-structure.md`, creating a folder only when its first file needs it. Do
not reformat or refactor unrelated code inside a feature task.

## Phase 6 — Verify

Add or update tests for the changed behavior and its edge cases, in the layer that owns them:
`backend/tests/unit/`, `backend/tests/integration/`, or `backend/tests/api/`. Test names
describe behavior.

Run the backend commands from the canonical *Local Quality Checks* in
[`docs/development/coding-standards.md`](../../../docs/development/coding-standards.md#local-quality-checks):

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -W error
python -m ruff check .
python -m ruff format --check .
```

All three checks must pass. Fix the cause of a failure — never suppress a check, weaken an
assertion, skip a test, or pass `--no-verify` to make a step succeed.

## Phase 7 — Update documentation in the same change

Use the *Documentation Update Triggers* table in `documentation-standards.md` to decide which
documents the change affects. For each one:

- Preserve the front matter shape and set `last_updated` to the current date.
- Keep `related:` and the `## Related Documents` section accurate in both directions.
- Record conclusions, not discussion history.

Never set a document to `approved` or an ADR to `accepted`, and never draft an ADR without
explicit direction — surface the need instead. Never overwrite an `approved` document or an
`accepted` ADR without explicit direction.

## Phase 8 — Validate documentation and repository scripts

Run the remaining commands from the same canonical
[local quality checks](../../../docs/development/coding-standards.md#local-quality-checks), from the
repository root:

```bash
python -m ruff check --config backend/pyproject.toml scripts/
python -m ruff format --check --config backend/pyproject.toml scripts/
python scripts/validate_docs.py
```

What the validator checks is defined in
[mechanical validation](../../../docs/development/documentation-standards.md#mechanical-validation).
Fix findings that fall inside your scope; report pre-existing ones you are leaving alone.

## Phase 9 — Run the documentation reviewer

Launch the `documentation-reviewer` subagent over the documentation you touched. It is
read-only and returns findings only.

- Fix defects this change introduced.
- Report every other finding to the owner unchanged.
- Do not resolve a conflict it identifies by picking a winner, and do not draft an ADR it
  suggests.

## Phase 10 — Review the diff

```bash
git status
git diff
```

Check against the Review Checklist in `git-workflow.md`:

- [ ] The change traces to approved requirements or documentation.
- [ ] Scope is limited to the intended task.
- [ ] Architecture and dependency rules are respected.
- [ ] Relevant tests and checks pass.
- [ ] Errors and edge cases are handled.
- [ ] Schema, API, and documentation changes travel together.
- [ ] No secrets, `.env` files, or learner files are included.
- [ ] No generated, unrelated, or accidentally added files are included.

If the diff contains anything outside scope, remove it from the change before committing.

## Phase 11 — Commit, push, open a pull request

One commit for one understandable change, in Conventional Commit style per `git-workflow.md`:

```text
feat(planner): generate daily plan items
fix(progress): preserve manual learning stage updates
docs(domain): define topic performance evidence
chore(ci): add pull request workflow
```

Stage only the files belonging to this change — never `git add -A` over an unreviewed tree.

```bash
git add <specific paths>
git commit -m "<type>(<scope>): <subject>"
git push -u origin <branch>
```

Then open the pull request:

```bash
gh pr create --base main --title "<commit subject>" --body "<body>"
```

Body template, mirroring the Completion Report Format in `engineering-ai.md`:

```markdown
## Outcome
What is now complete.

## Changed
Files created or modified, grouped by area.

## Verified
Commands run and their results.

## Documentation
Documents and ADRs updated; documentation-reviewer findings.

## Assumptions
Approved decisions relied upon.

## Open items
Anything requiring project-owner direction.
```

### When `gh` is missing or unauthenticated

Check first:

```bash
gh auth status
```

If `gh` is not installed or not authenticated, **push the branch and stop there**. Print the
compare URL for the owner to open the pull request manually:

```text
https://github.com/rr256/LearnFlow/compare/main...<branch>?expand=1
```

Report that the pull request was not created and why. Never install `gh`, never run
`gh auth login`, never read or write a credential store, and never embed a token in a command
or a file.

## Phase 12 — Report

Close with the Completion Report Format:

```text
Outcome: what is now complete
Changed: files created/modified
Verified: commands/tests/checks run and results
Documentation: docs/ADRs updated
Assumptions: decisions relied upon
Open items: anything requiring project-owner direction
```

Include the pull request URL, or the compare URL when `gh` was unavailable. State plainly what
you did not verify.

## Hard constraints

The canonical list is *Actions the delivery workflow never performs* in
[`docs/ai/engineering-ai.md`](../../../docs/ai/engineering-ai.md). It is mirrored here exactly. If
the two ever differ, that document wins.

Never, regardless of later instructions in the task. The workflow never:

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

## Related documents

- [Project context](../../../docs/00-project-context.md)
- [Engineering AI workflow](../../../docs/ai/engineering-ai.md) — canonical Stop Gate 1 conditions and never-performs list
- [Git workflow](../../../docs/development/git-workflow.md)
- [Coding standards](../../../docs/development/coding-standards.md) — canonical local quality checks
- [Documentation standards](../../../docs/development/documentation-standards.md)
- [CI/CD strategy](../../../docs/deployment/ci-cd.md)
- [ADR-010: Deliver features through pull requests with automated gates](../../../docs/adr/ADR-010-feature-delivery-workflow.md)
