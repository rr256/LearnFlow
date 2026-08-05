---
title: LearnFlow Repository and Folder Structure
status: approved
owner: architecture-and-development
last_updated: 2026-08-05
related:
  - ../00-project-context.md
  - tech-stack.md
  - ../architecture/clean-architecture.md
  - ../architecture/dependency-rules.md
  - ../database/migrations.md
  - ../deployment/ci-cd.md
  - ../deployment/docker.md
  - ../adr/ADR-010-feature-delivery-workflow.md
  - ../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ../adr/ADR-016-learner-onboarding-api-contracts.md
  - ../domain/terminology.md
---

# LearnFlow Repository and Folder Structure

## Purpose

Define where source code, configuration, tests, documentation, containers, scripts, and generated/local data belong.

The structure reflects Clean Architecture without creating unnecessary folders before code requires them. Empty folders should not be committed merely to match this diagram.

## Target Repository Layout

```text
learnflow/
├── README.md
├── CLAUDE.md                    # Project instructions for implementation assistants
├── compose.yaml                 # Local Docker Compose entry point
├── .env.example                 # Safe configuration-variable template
├── .gitignore
├── docs/                        # Authoritative engineering documentation
├── backend/
│   ├── requirements.txt         # Direct runtime dependencies
│   ├── requirements-dev.txt     # Runtime plus test/lint tooling
│   ├── pyproject.toml           # Python requirement, pytest and Ruff configuration
│   ├── alembic.ini              # Alembic configuration; no database URL is stored in it
│   ├── app/
│   │   ├── domain/
│   │   ├── application/
│   │   │   ├── ports/
│   │   │   ├── use_cases/
│   │   │   └── dto/
│   │   ├── presentation/
│   │   │   └── api/
│   │   ├── infrastructure/
│   │   │   ├── persistence/
│   │   │   ├── providers/
│   │   │   ├── storage/
│   │   │   └── rag/
│   │   └── composition/
│   ├── migrations/              # Alembic configuration and revisions
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── api/
│   └── scripts/                 # Backend-only seed/import utilities and their data
├── frontend/
│   ├── package.json             # Dependencies, scripts, and the Node requirement
│   ├── package-lock.json        # Exact resolved dependency tree; CI installs from it
│   ├── tsconfig.json            # TypeScript configuration, strict mode on
│   ├── next.config.ts           # Next.js build/runtime configuration
│   ├── eslint.config.mjs        # ESLint flat configuration
│   ├── vitest.config.mts        # Test runner configuration
│   ├── app/                     # Next.js routes/pages
│   ├── features/                # Learner-facing feature modules
│   ├── components/              # Reusable UI components
│   ├── lib/                     # API client and frontend-only utilities
│   ├── types/                   # Frontend types derived from API contracts
│   ├── tests/
│   └── public/                  # Static assets; added with the first one
├── .dockerignore                # Build-context exclusions for all images
├── docker/
│   ├── backend.Dockerfile
│   └── frontend.Dockerfile
├── scripts/
│   └── validate_docs.py         # Documentation front-matter and link validation
├── .claude/
│   ├── agents/                  # Read-only review agents
│   ├── skills/                  # Repeatable assistant workflows
│   └── settings.json            # Local Claude Code permissions
└── .github/
    └── workflows/               # CI workflow definitions
```

## Root Files

| Path | Responsibility |
| --- | --- |
| `README.md` | Project introduction, quick start, and links to documentation. |
| `CLAUDE.md` | Concise repository instructions for Claude Code and compatible implementation assistants. It links to `docs/00-project-context.md`; it does not duplicate the handbook. |
| `compose.yaml` | Local service composition for frontend, backend, PostgreSQL, and ChromaDB. Currently defines the `frontend`, `backend`, and `postgres` services; see [Docker strategy](../deployment/docker.md). |
| `.dockerignore` | Build-context exclusions shared by every image: secrets, `.env` files, learner data, volumes, virtual environments, documentation, and CI configuration. |
| `.env.example` | Safe environment-variable names/examples; no secrets. |
| `.gitignore` | Excludes virtual environments, node modules, local data, secrets, generated artifacts, and model/index data. |
| `docs/` | The authoritative project context, design, ADRs, and workflow documentation. |

## Backend Structure

### Backend Root Files

| Path | Responsibility |
| --- | --- |
| `requirements.txt` | Direct runtime dependencies only. Transitive packages are resolved by pip and are not pinned, so upgrading one dependency does not require reconciling unrelated pins. |
| `requirements-dev.txt` | Includes `requirements.txt` and adds test and tooling dependencies. This is the file contributors install. |
| `pyproject.toml` | Python version requirement, pytest configuration, and Ruff lint/format configuration. |
| `alembic.ini` | Alembic configuration. It carries no `sqlalchemy.url`: the target database comes from `DATABASE_URL` through the application's validated settings, so no credential lives in a committed file. See [database migrations](../database/migrations.md). |

### `backend/app/domain/`

Contains framework-independent learning concepts and rules.

Examples:

- Entities/value objects for topics, plans, progress, revisions, quizzes, and test evidence.
- Domain invariants and calculations.
- Domain exceptions.

Must not contain FastAPI, SQLAlchemy, provider SDKs, filesystem code, or environment configuration.

### `backend/app/application/`

Contains use cases and the ports they need.

| Subfolder | Responsibility |
| --- | --- |
| `ports/` | Repository/provider interfaces used by application services. |
| `use_cases/` | Feature workflows: create plan, record progress, ingest resource, mentor question, submit quiz, record test result. |
| `dto/` | Framework-independent input/output structures for use cases. |

Application code depends on domain concepts and ports, not on FastAPI or concrete providers.

### `backend/app/presentation/api/`

Contains FastAPI-specific delivery code.

Examples:

- Route modules.
- Request/response schemas.
- Dependency extraction for effective learner context.
- HTTP exception/error mapping.

Routes remain thin: validate, map, call a use case, map result to response.

### `backend/app/infrastructure/`

Contains concrete technology adapters.

| Subfolder | Responsibility |
| --- | --- |
| `persistence/` | SQLAlchemy models, repository implementations, database/session setup. |
| `providers/` | Ollama, embeddings, ChromaDB/retrieval adapters, future cloud adapters. |
| `storage/` | Local filesystem storage adapter and future cloud storage adapters. |
| `rag/` | PDF extraction, chunking, indexing, and retrieval implementation details. |

### `backend/app/composition/`

Contains application wiring only.

Examples:

- Validated configuration.
- Provider/repository construction.
- Dependency-injection setup.
- FastAPI application factory/lifecycle wiring.

Business rules do not belong here.

### `backend/migrations/`

Contains the Alembic environment (`env.py`), the revision template (`script.py.mako`), and immutable migration revisions under `versions/`. Schema changes are documented in `docs/database/` and follow the migration workflow.

`env.py` imports every persistence model, because a model it does not import is invisible to autogenerate and would be silently omitted from a generated migration.

### `backend/tests/`

| Folder | Test focus |
| --- | --- |
| `unit/` | Domain and application behavior with no live external dependencies. Also holds persistence tests that only compile SQL, since those need no database, and the fakes application tests use in place of a port. |
| `integration/` | PostgreSQL, storage, provider-adapter, and RAG boundary tests. These need a live dependency and skip when it is not configured. |
| `api/` | FastAPI request/response and contract tests. |

The database tests under `integration/` read `TEST_DATABASE_URL` and skip when it is unset, so the default `python -m pytest` run needs no PostgreSQL. CI runs them against an ephemeral service container; see [CI/CD strategy](../deployment/ci-cd.md).

## Frontend Structure

### Frontend Root Files

| Path | Responsibility |
| --- | --- |
| `package.json` | Direct dependencies, the check scripts CI runs, and the minimum Node version. |
| `package-lock.json` | The exact resolved dependency tree. Committed, because `npm ci` installs from it and fails when it disagrees with `package.json`. |
| `tsconfig.json` | TypeScript configuration. `strict` is on, per [coding standards](coding-standards.md#type-safety). `next build` maintains the `jsx` setting and the generated-type includes; leave those as it writes them. |
| `next.config.ts` | Next.js configuration. `output: "standalone"` is what lets the runtime image ship a self-contained server. |
| `eslint.config.mjs` | ESLint flat configuration, extending `eslint-config-next`, which carries the `jsx-a11y` accessibility rules. |
| `vitest.config.mts` | Test runner configuration. The `.mts` extension keeps the file ESM, which Vite's native config loader requires. |

`next-env.d.ts` is generated by `next build` and is ignored by Git, as are `node_modules/` and `.next/`.

### `frontend/app/`

Next.js routes/layouts only. It composes feature modules; it should not become the home for all UI business logic.

Implemented today:

```text
app/
├── layout.tsx                              # Document shell, skip link, header
├── layout.module.css
├── page.tsx                                # Home
├── page.module.css
├── not-found.tsx                           # Unmatched address, and notFound()
├── globals.css                             # Reset, colour tokens, focus styles
├── curriculum/
│   ├── page.tsx                            # CUR-001, the learning-program list
│   ├── error.tsx                           # Last-resort render boundary
│   └── programs/[programId]/
│       ├── page.tsx                        # CUR-002 and CUR-003
│       └── page.module.css
└── setup/
    └── page.tsx                            # Reads LRN-001, CUR-001, GOAL-002, EXM-001;
                                            # writes LRN-002 and GOAL-001/GOAL-004 via a server action
```

Every curriculum and setup route sets `dynamic = "force-dynamic"`. The curriculum lives in the
database, so a build-time snapshot would go stale the moment the seed ran again; the profile and the
goal are learner data that changes on submission — and the container build has no API to reach.

**There is no `loading.tsx` segment file, deliberately.** A segment file also covers every nested
route, and a boundary over `programs/[programId]` commits a `200` before that page can call
`notFound()` — so a mistyped program id would answer `200` with a not-found body instead of `404`.

Each page declares its own `<Suspense>` boundary inside `page.tsx` instead, placed to keep both
behaviours. The program page suspends only the curriculum-tree half: the program lookup that decides
`404` runs outside any boundary, and the slower tree fetch streams in behind a loading message. Put a
new boundary below whatever call can raise `notFound()`, never above it.

### `frontend/features/`

Feature-oriented modules, for example:

```text
onboarding/
curriculum/
planner/
progress/
revisions/
resources/
mentor/
quizzes/
external-tests/
```

Each feature owns its screens, view models, feature-specific components, and API interactions while using shared components/types where appropriate. `curriculum/` and `onboarding/` exist today.

`onboarding/` holds the **learner setup** capability's screen. The module keeps the narrower name
because a module directory names a UI flow, which is the one use
[terminology](../domain/terminology.md) permits for *onboarding*; prose, endpoint groupings, and UI
copy say *learner setup*.

| Path | Responsibility |
| --- | --- |
| `curriculum/LearningProgramList.tsx` | The program list CUR-001 returns, with its CSS Module. |
| `curriculum/CurriculumTree.tsx` | The subject and topic hierarchy CUR-003 returns, with its CSS Module. |
| `onboarding/LearnerSetupForm.tsx` | The setup form. A client component only so it can show the last submission's result beside the field responsible; it calls no API itself. |
| `onboarding/StudyGoalSummary.tsx` | The goal the learner has already set, with its examination window, source, and provisional status. |
| `onboarding/submission.ts` | Reads the form into the two requests it makes, and owns the form's state shape. Plain functions, so they are testable without a running server. |
| `onboarding/actions.ts` | The `"use server"` module holding the write path. |

**A `"use server"` module may export only async functions.** Exporting a constant from one throws
`A "use server" file can only export async functions` on the first request that reaches it — a `500`
that neither `tsc --noEmit` nor `next build` reports. That is why the setup state shape and its
initial value live in `submission.ts` rather than beside the action, and why
`frontend/tests/server-actions.test.ts` checks the rule for every such module.

A server action is still the Next.js server calling the API, so a write does not make the browser
reach the backend and introduces no CORS; see
[ADR-016](../adr/ADR-016-learner-onboarding-api-contracts.md).

### `frontend/components/`

Reusable presentation components that are not specific to one learner workflow. `Notice.tsx` — the panel an empty or failed view renders — is the first.

### `frontend/lib/`

Frontend-only utilities, including the typed API client, request/error helpers, formatting, and configuration access. It must not contain backend/domain rules.

| Path | Responsibility |
| --- | --- |
| `config.ts` | Resolves and validates `API_BASE_URL`. Takes the environment as a parameter so validation is testable without mutating `process.env`. |
| `api-client.ts` | Typed calls to the curriculum, learner, examination-schedule, and study-goal endpoints. Checks each response against the documented envelope and raises `ApiError`. Runs on the server only, including for writes, which reach it from a server action. |

When the API answers with a failure, `ApiError.code` is the API's own code from the closed catalogue
in [API conventions](../api/conventions.md#error-codes). Two client-side codes cover what the
catalogue cannot describe, because no API produced them: `api_unreachable` when the request never
reached a server, and `malformed_response` when a `200` did not match the documented envelope. They
are transport and parsing failures local to this client, not wire codes, and nothing sends them over
HTTP — so they add nothing to the catalogue [ADR-014](../adr/ADR-014-api-response-contract.md)
closed.

### `frontend/types/`

TypeScript types based on public API contracts. Do not copy database/ORM types into the frontend. Field names stay `snake_case` because that is what [API conventions](../api/conventions.md#json-naming-and-data-formats) puts on the wire; renaming them would hide the contract behind a translation layer.

### `frontend/tests/`

Vitest specs for the API client, the configuration reader, the curriculum and learner-setup
components, the setup form's submission parsing, and the `"use server"` export rule. They stub
`fetch` and reach no live backend, so `npm test` needs nothing running.

## Docker and Scripts

### `docker/`

Contains Dockerfiles and small container build assets. Runtime configuration remains in `compose.yaml` and environment files.

| Path | Responsibility |
| --- | --- |
| `backend.Dockerfile` | Backend runtime image, built from the repository root so it can copy `backend/`. [Docker strategy](../deployment/docker.md) records the image decisions. |
| `frontend.Dockerfile` | Frontend runtime image, built from the repository root so it can copy `frontend/`. Multi-stage: install, build, then a runtime stage carrying only the standalone server. |

### `scripts/`

Contains repository-level repeatable utilities, such as documentation validation, development setup checks, or release helpers. Scripts must be documented and must not contain personal paths/secrets.

| Path | Responsibility |
| --- | --- |
| `validate_docs.py` | Validates documentation front matter and links; [mechanical validation](documentation-standards.md#mechanical-validation) defines exactly what it checks. Run from the repository root; CI runs the same command. |

Ruff is configured in `backend/pyproject.toml`, so running it from `backend/` does not cover
`scripts/`. Repository-level scripts are held to the same standards and are linted against that same
configuration explicitly. The commands are defined once, in the canonical
[local quality checks](coding-standards.md#local-quality-checks); the documentation CI job runs them
before running the validator, so `scripts/` is covered by CI.

### `backend/scripts/`

Contains backend/domain-specific utilities. A module here does composition-root work under the
existing rule in [dependency rules](../architecture/dependency-rules.md): it may read configuration
and construct concrete adapters, which application and domain code must not. It holds wiring, not
business rules — those stay in the use case it calls. Run them from `backend/` as modules —
`python -m scripts.<name>` — so the `app` package resolves.

| Path | Responsibility |
| --- | --- |
| `seed_curriculum.py` | Idempotent curriculum seed/import. Wires the seed use case to PostgreSQL and reports what changed; see [database migrations](../database/migrations.md#the-curriculum-seed). |
| `curriculum_seed_file.py` | Reads a curriculum seed JSON file into application DTOs, reporting the field at fault when the file is malformed. |
| `gate_cse_curriculum.json` | The curated GATE CSE curriculum. Data, not code: its `$comment` block records the official source and the transcription rules. |
| `seed_examination_schedule.py` | Idempotent examination schedule seed. Runs after the curriculum seed; see [database migrations](../database/migrations.md#the-examination-schedule-seed). |
| `examination_schedule_file.py` | Reads an examination schedule JSON file into application DTOs, reporting the field at fault when the file is malformed. |
| `gate_cse_examination_schedule.json` | The published GATE 2027 schedule. Data, not code: its `$comment` block records the official source, the transcription rules, and the one inference it makes. |
| `set_study_goal.py` | Sets the local learner's curriculum and examination goal, idempotently; see [setting the local learner's study goal](../database/migrations.md#setting-the-local-learners-study-goal). |

## Automation and Assistant Configuration

### `.claude/`

Contains configuration for Claude Code and compatible assistants. It holds workflow definitions, not
project decisions: authority stays in `docs/` and the ADRs.

| Path | Responsibility |
| --- | --- |
| `agents/` | Subagent definitions. `documentation-reviewer.md` is read-only and reports findings without editing files. |
| `skills/` | Repeatable assistant workflows, one directory per skill with a `SKILL.md`. `deliver-feature/` encodes the end-to-end delivery workflow. |
| `settings.json` | Local Claude Code permission settings. |

`CLAUDE.md` at the repository root remains the entry-point instruction file and points to
`docs/00-project-context.md`.

### `.github/`

Contains GitHub configuration. `workflows/pull-request.yml` defines the checks enumerated in
[CI/CD strategy](../deployment/ci-cd.md), which is their authoritative description. Workflow files
must not contain credentials, tokens, or deployment steps.

## Local and Generated Data

The following must stay outside Git or in ignored directories/volumes:

- Python virtual environments.
- `node_modules`.
- `.env` files with real values.
- PostgreSQL data volume.
- ChromaDB/vector-index data.
- Learner PDFs, notes, attachments, screenshots, and local storage contents.
- Downloaded Ollama models.
- Runtime logs containing private learner data.
- Generated build artifacts and coverage reports unless a tool explicitly requires otherwise.

Local data locations are configured through environment variables and Docker volumes; no source code may assume a developer-specific absolute path.

## Folder-Creation Rules

- Create a folder only when the first related file is added.
- Keep modules focused; do not create generic `utils`, `helpers`, or `common` folders as a dumping ground.
- Add a new cross-cutting folder only after documenting why existing boundaries do not fit.
- Mirror documentation terminology in code where practical: `study_plan`, `topic_progress`, `external_test_result`.

## Related Documents

- [Project context](../00-project-context.md)
- [Clean Architecture](../architecture/clean-architecture.md)
- [Dependency rules](../architecture/dependency-rules.md)
- [Technology stack](tech-stack.md)
- [Coding standards](coding-standards.md)
- [ADR-015: Build the frontend on Next.js and reach the API from the server](../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the decisions the frontend structure implements
- [ADR-016: Fix the learner setup API contracts](../adr/ADR-016-learner-onboarding-api-contracts.md) — the server-action write path the `onboarding/` module implements
- [Terminology](../domain/terminology.md) — why that module keeps the narrower name
- [API conventions](../api/conventions.md) — the contract `frontend/types/` is derived from
- [Database migrations](../database/migrations.md) — the authoritative description of the curriculum seed named in `backend/scripts/`
- [Docker strategy](../deployment/docker.md) — what `compose.yaml`, `docker/`, and `.dockerignore` contain today
- [CI/CD strategy](../deployment/ci-cd.md) — what the workflow files in `.github/` verify
- [Engineering AI workflow](../ai/engineering-ai.md) — what the definitions in `.claude/` implement
- [ADR-010: Deliver features through pull requests with automated gates](../adr/ADR-010-feature-delivery-workflow.md) — the decision that introduced `scripts/`, `.github/workflows/`, and the delivery skill
