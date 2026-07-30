# LearnFlow — Instructions for AI Assistants

LearnFlow is an AI-powered, extensible learning platform. GATE Computer Science is its first
learning program, not a product boundary.

This file is a pointer, not a handbook. The authoritative documentation lives in [`docs/`](docs/).

## Read before any meaningful work

**Start with [`docs/00-project-context.md`](docs/00-project-context.md).** It is the mandatory
entry point and master index, and it names the task-specific documents to read next.

Do not propose or implement a change based on this file alone.

## Non-negotiable rules

**Architecture.** Follow Clean Architecture as defined in
[`docs/architecture/clean-architecture.md`](docs/architecture/clean-architecture.md) and
[`docs/architecture/dependency-rules.md`](docs/architecture/dependency-rules.md). Dependencies point
inward: domain and application code must never import FastAPI, SQLAlchemy, Ollama, ChromaDB,
filesystem APIs, or configuration. Only the composition root selects concrete implementations.

**Documentation.** Follow
[`docs/development/documentation-standards.md`](docs/development/documentation-standards.md).
Documentation is part of the deliverable: update affected documents in the same change as the code.
Consequential, hard-to-reverse decisions need an ADR in [`docs/adr/`](docs/adr/) and an entry in
[`docs/architecture/decisions.md`](docs/architecture/decisions.md).

**Terminology.** Use the canonical vocabulary in
[`docs/domain/terminology.md`](docs/domain/terminology.md) in code, APIs, database names, and UI
copy — including the terms it tells you to avoid.

**Scope.** Keep each change narrow and reviewable. No large unrelated refactors inside a feature
task. Follow [`docs/development/git-workflow.md`](docs/development/git-workflow.md) for branches and
commit messages.

## Before you change anything

1. State conflicts, missing decisions, or scope questions **before** implementing.
2. Do not invent an architectural decision because a placeholder exists — a placeholder is not a
   decision.
3. Do not overwrite a document marked `approved`, or an `accepted` ADR, without explicit direction.
4. Do not mark anything `approved` or `accepted` yourself.

## Backend quick reference

```bash
cd backend
python -m pip install -r requirements-dev.txt   # runtime + test/lint tooling
python -m pytest                                # tests
python -m ruff check .                          # lint
python -m ruff format --check .                 # formatting
python -m app.main                              # serve on API_HOST / API_PORT
python -m uvicorn app.main:app --reload         # reload workflow (own --host/--port)
```

Python 3.14 is required. `GET /health` is an operational endpoint served outside `/api/v1`.
Configuration is validated at startup; see
[`docs/deployment/environments.md`](docs/deployment/environments.md) for the variable catalogue.

## Never commit

Virtual environments, `node_modules`, real `.env` files, learner PDFs or notes, database volumes,
vector indexes, or secrets. See [`.gitignore`](.gitignore) and
[`docs/development/folder-structure.md`](docs/development/folder-structure.md).
