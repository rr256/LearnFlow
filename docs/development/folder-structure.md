---
title: LearnFlow Repository and Folder Structure
status: approved
owner: architecture-and-development
last_updated: 2026-08-18
related:
  - ../00-project-context.md
  - tech-stack.md
  - ../architecture/clean-architecture.md
  - ../architecture/dependency-rules.md
  - ../api/endpoints.md
  - ../database/migrations.md
  - ../deployment/ci-cd.md
  - ../deployment/docker.md
  - ../adr/ADR-010-feature-delivery-workflow.md
  - ../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ../adr/ADR-016-learner-onboarding-api-contracts.md
  - ../adr/ADR-017-topic-progress-api-and-schema.md
  - ../adr/ADR-018-weekly-availability-slots.md
  - ../adr/ADR-019-study-goal-planning-preferences.md
  - ../adr/ADR-020-initial-study-plan-generation.md
  - ../adr/ADR-021-plan-item-completion.md
  - ../adr/ADR-022-plan-adaptation.md
  - ../adr/ADR-023-daily-study-view.md
  - ../adr/ADR-024-plan-item-skipping.md
  - ../adr/ADR-026-monthly-study-view.md
  - ../adr/ADR-028-revision-workflow.md
  - ../adr/ADR-027-plan-feasibility.md
  - ../adr/ADR-029-progress-overview.md
  - ../adr/ADR-030-learning-stages-by-subject-panel.md
  - ../adr/ADR-031-priority-focus-panel.md
  - ../adr/ADR-032-learning-resource-catalogue.md
  - ../adr/ADR-033-checkpoint-practice-workflow.md
  - ../adr/ADR-034-checkpoint-practice-history.md
  - ../adr/ADR-035-practice-question-correction.md
  - ../adr/ADR-036-topic-material-on-the-plan-screens.md
  - ../adr/ADR-036-topic-material-on-the-plan-screens.md
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
It must not import the application layer either: dependencies point inward, so a use case maps its
records onto these values rather than the other way round.

| Path | Responsibility |
| --- | --- |
| `checkpoint_marking.py` | The deterministic rules a checkpoint quiz is made of: how a question's options are keyed, which order a quiz asks its questions in, and whether one submitted answer matches the expected one. Pure functions over plain values — no clock, no session, no configuration, and **no AI provider**, which is what lets a learner who disagrees with a mark be shown why. It **counts, totals, ranks, and scores nothing**: a marked attempt is a sequence of per-question outcomes, and an unanswered question is `None` rather than wrong. See [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md). |
| `revision_scheduling.py` | The deterministic rules a revision is made of: how long after finished work a topic comes back, and which revisions are due on a day. Pure functions over plain values — no clock, no session, no configuration. The intervals are LearnFlow's own and are named as such wherever a revision explains itself; a longer wait is not a better mark. See [ADR-028](../adr/ADR-028-revision-workflow.md). |
| `study_planning.py` | The deterministic rules a study plan is made of: what order the topics are worked through, which day each session lands on, what makes an item overdue (ADR-022), and — since ADR-027 — whether a saved week holds enough time to reach the goal's horizon. Pure functions over plain values — no clock, no session, no configuration — which is what makes a plan replayable and exhaustively testable rather than merely observable. It knows nothing of day *names*, learning stages, or storage; a capacity arrives as a date and a number of minutes. See [ADR-020](../adr/ADR-020-initial-study-plan-generation.md), [ADR-022](../adr/ADR-022-plan-adaptation.md), and [ADR-027](../adr/ADR-027-plan-feasibility.md). |

The package exists from the change that first needed it, which is the folder-creation rule below.

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

One module sits at the root of `infrastructure/` rather than in a subfolder: `clock.py`, the system
clock behind the `Clock` port. The operating system's clock is not persistence, a provider, storage,
or RAG, and a four-line adapter does not earn a folder of its own under the rule below. It is an
adapter at all because every date in a generated plan derives from "now", so the application asks a
port and the composition root decides what answers.

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
├── page.tsx                                # Home — reads LRN-001, GOAL-002, EXM-001
├── page.module.css
├── not-found.tsx                           # Unmatched address, and notFound()
├── globals.css                             # Reset, colour tokens, focus styles
├── health/
│   └── route.ts                            # Static readiness probe; reaches nothing
├── curriculum/
│   ├── page.tsx                            # CUR-001, the learning-program list
│   ├── error.tsx                           # Last-resort render boundary
│   └── programs/[programId]/
│       ├── page.tsx                        # CUR-002, CUR-003, PRG-002, and
│       │                                   # RES-002; writes PRG-004 via a server
│       │                                   # action, and no resource control
│       └── page.module.css
├── plan/
│   ├── page.tsx                            # PLN-002 and PLN-003 over the learner's
│   │                                       # active goal, and RES-002 for the
│   │                                       # material each topic has; writes
│   │                                       # PLN-001, PLN-004, and PLN-005 via
│   │                                       # server actions, and no resource control
│   ├── page.module.css
│   ├── today/
│   │   ├── page.tsx                        # The daily study view: LRN-001 for the
│   │   │                                   # learner's timezone, GOAL-002, PLN-002,
│   │   │                                   # and PLN-003 for the active goal's weekly
│   │   │                                   # plan, and RES-002 for the material each
│   │   │                                   # topic has; writes PLN-004 only
│   │   └── page.module.css
│   └── month/
│       ├── page.tsx                        # The monthly study view: LRN-001 for the
│       │                                   # learner's timezone, GOAL-002, PLN-002,
│       │                                   # and PLN-003 for the active goal's roadmap
│       │                                   # and weekly plan; writes nothing at all
│       └── page.module.css
├── progress/
│   ├── page.tsx                            # The progress overview: LRN-001 for the
│   │                                       # learner's timezone, GOAL-002, PLN-002,
│   │                                       # PLN-003, PLN-006, REV-001, and PRG-002
│   │                                       # with CUR-003 for the recorded stages by
│   │                                       # subject; writes nothing at all, and adds
│   │                                       # no endpoint
│   └── page.module.css
├── revisions/
│   ├── page.tsx                            # The revision screen: REV-001 for the
│   │                                       # learner's reviews and RES-002 for the
│   │                                       # material each topic has; writes REV-003
│   │                                       # and REV-004 via server actions
│   └── page.module.css
├── resources/
│   ├── page.tsx                            # The learning-resource catalogue: RES-002
│   │                                       # for the learner's material, GOAL-002 and
│   │                                       # CUR-003 for the topics it may cover;
│   │                                       # adds over RES-001, and edits or archives
│   │                                       # over RES-004, via server actions
│   └── page.module.css
├── practice/
│   ├── page.tsx                            # Checkpoint practice: QZ-009 for the
│   │                                       # learner's questions, QZ-006 for their
│   │                                       # attempts, GOAL-002 and CUR-003 for the
│   │                                       # topics; writes over QZ-008, QZ-010, and
│   │                                       # QZ-001, via server actions
│   ├── page.module.css
│   ├── history/
│   │   ├── page.tsx                        # QZ-006 — the checkpoint practice
│   │   │                                   # history, a page at a time. Read-only,
│   │   │                                   # carries no score, and counts nothing
│   │   └── page.module.css
│   ├── quizzes/[quizId]/
│   │   ├── page.tsx                        # QZ-002 — the quiz, with no expected
│   │   │                                   # answers; one form post starts the attempt
│   │   │                                   # over QZ-003 and submits it over QZ-005
│   │   └── page.module.css
│   └── attempts/[attemptId]/
│       ├── page.tsx                        # QZ-007 — what became of each question.
│       │                                   # Read-only, and carries no score
│       └── page.module.css
└── setup/
    └── page.tsx                            # Reads LRN-001, CUR-001, GOAL-002, EXM-001;
                                            # writes LRN-002, GOAL-001/GOAL-004 — which
                                            # carry the planning preferences — and
                                            # GOAL-005, via server actions
```

Every home, curriculum, setup, plan, progress, revision, resource, and practice route sets
`dynamic = "force-dynamic"`, `practice/history` among them, because a learner's attempts are learner
data and the container build has no API to reach. The curriculum lives in the
database, so a build-time snapshot would go stale the moment the seed ran again; the profile and the
goal are learner data that changes on submission — and the container build has no API to reach.
`plan/today` needs it most strongly of all: it is a screen *about* the current date, so a cached copy
would be wrong from the first midnight after it was built. `plan/month` needs it for the same reason,
one period up: a cached copy would be wrong from the first month boundary after the build, and
`progress` needs it because it reports the same current date.

`health/route.ts` is the one deliberate exception: it is `force-static`, because it exists to answer
the container health check and must reach nothing. It asks only whether the frontend process is
responding; probing a page instead would generate backend requests every interval to render markup no
probe reads. See [Docker strategy](../deployment/docker.md#the-frontend-service).

**There is no `loading.tsx` segment file, deliberately.** A segment file also covers every nested
route, and a boundary over `programs/[programId]` commits a `200` before that page can call
`notFound()` — so a mistyped program id would answer `200` with a not-found body instead of `404`.
The rule binds hardest at the application root, where a `loading.tsx` beside `page.tsx` would cover
every route in the application at once.

Each page declares its own `<Suspense>` boundary inside `page.tsx` instead, placed to keep both
behaviours. The program page suspends only the curriculum-tree half: the program lookup that decides
`404` runs outside any boundary, and the slower tree fetch streams in behind a loading message. Put a
new boundary below whatever call can raise `notFound()`, never above it.

The home screen keeps its navigation links outside its boundary as well, so an unreachable API
leaves a learner a way forward rather than a dead first screen. The plan screen does the same.

### `frontend/features/`

Feature-oriented modules, for example:

```text
home/
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

Each feature owns its screens, view models, feature-specific components, and API interactions while using shared components/types where appropriate. `home/`, `curriculum/`, `onboarding/`, `planner/`, `progress/`, `revision/`, `resources/`, and `practice/` exist today.

`practice/` holds **checkpoint practice**: `QuestionForm.tsx` serving both writing and **correcting** — one component, as `ResourceForm` is for a resource, since both ask for the same five fields and differ only in whether they start filled and which endpoint they reach — `QuestionBank.tsx` and `QuestionStatusControl.tsx` for reading them back, correcting one behind a `<details>` disclosure, and setting one aside,
`StartQuizForm.tsx` for choosing topics, `QuizForm.tsx` for answering a quiz in one form post,
`AttemptResult.tsx` for what became of each question, `AttemptHistory.tsx` for the most recent
attempts on `/practice`, `PracticeHistory.tsx` for the whole history at `/practice/history`,
`history.ts` for the paging and entry-presentation rules both of those share, and
`submission.ts` and `actions.ts` for the form parsing and the writes. It reuses
`resources/topic-options.ts` for both topic pickers rather than copying it: flattening the CUR-003
tree into one level of `<optgroup>` is the same presentation problem, and a second copy would be a
second thing to keep in step with the curriculum contract. **No component here counts, totals, or
ranks anything**, and none renders a score. `history.ts` is plain functions, for the reason
`resources/by-topic.ts` is: they are testable without a running server. Its `HistoryPage` carries
exactly three fields — the attempts and the two offsets — so there is nowhere for a count to appear,
and `pagination.total` is never read. See
[ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md),
[ADR-034](../adr/ADR-034-checkpoint-practice-history.md), and
[ADR-035](../adr/ADR-035-practice-question-correction.md).

`resources/` holds the **learning-resource catalogue**, which supports **add, edit, and archive**:
`ResourceCatalogue.tsx` for the screen and `ResourceForm.tsx` for both the add and the edit form —
one component, since both ask for the same six fields and differ only in whether they start filled
and which endpoint they reach — `ResourceStatusControl.tsx` for putting material aside and back,
`TopicResources.tsx` for the read-only list shown beside a topic by the curriculum view, the
revision screen, `/plan`, and `/plan/today` — called from five components across four screens, so
the rules about ordering, archived material, and recommending nothing are enforced once rather than
restated in each — `by-topic.ts` and `topic-options.ts` for the joins and the topic picker, `actions.ts` for the
three writes, and `submission.ts` for the form state, which lives apart from the actions because a
`"use server"` module may export only async functions. See
[ADR-032](../adr/ADR-032-learning-resource-catalogue.md) and
[ADR-036](../adr/ADR-036-topic-material-on-the-plan-screens.md).

`onboarding/` holds the **learner setup** capability's screen. The module keeps the narrower name
because a module directory names a UI flow, which is the one use
[terminology](../domain/terminology.md) permits for *onboarding*; prose, endpoint groupings, and UI
copy say *learner setup*.

`home/` holds the home screen's read-only view of that same saved setup. It is a separate module
because it is not the first-time flow — a learner reading what they already saved is not being
onboarded — and it writes nothing.

| Path | Responsibility |
| --- | --- |
| `curriculum/LearningProgramList.tsx` | The program list CUR-001 returns, with its CSS Module. |
| `curriculum/CurriculumTree.tsx` | The subject and topic hierarchy CUR-003 returns, with its CSS Module. |
| `home/StudySetupOverview.tsx` | The saved profile and study goal, read-only, with its CSS Module. It does not reuse `onboarding/StudyGoalSummary.tsx`, whose empty state points at the form beneath it. |
| `home/ExaminationDates.tsx` | The goal's examination: its window, every published period, the source, and the provisional status — gathered in one panel so that status is stated once beside every date it qualifies. |
| `home/dates.ts` | Date and period-type presentation. Plain functions, so they are testable without a running server. Dates are printed as the API's own ISO strings; converting one to a `Date` would parse it as UTC midnight and could move a sitting day back by a day. |
| `home/WeeklyAvailability.tsx` | The study week saved against the goal, read-only, with its CSS Module. It comes off the goal GOAL-002 already returned, so it costs the home screen no further request. |
| `home/PlanningPreferences.tsx` | The planning preferences saved against the goal, read-only, with its CSS Module. Off the same goal response, so it costs no further request either. A preference the learner has not set is left out rather than shown as a default, and the panel says plainly what a plan does with one. |
| `onboarding/LearnerSetupForm.tsx` | The setup form, including the planning-preference controls, which ride on the same goal write rather than needing a form of their own. A client component only so it can show the last submission's result beside the field responsible; it calls no API itself. |
| `onboarding/StudyGoalSummary.tsx` | The goal the learner has already set, with its examination window, source, and provisional status. |
| `onboarding/AvailabilityForm.tsx` | The weekly availability form: one box per day, saved as a whole week. A separate form from the setup one above, because a week belongs to the goal that form creates. |
| `onboarding/submission.ts` | Reads the setup form into the two requests it makes — including the planning preferences that ride on the goal write — and owns that form's state shape. Plain functions, so they are testable without a running server. |
| `onboarding/availability.ts` | Reads the availability form into the request it makes, owns that form's state shape, and writes a saved week the way a learner reads it. Plain functions, for the same reason. |
| `onboarding/preferences.ts` | Writes a saved planning preference the way a learner reads it. Presentation only — the reading half lives in `submission.ts`, because preferences ride on the goal write that form already makes. Plain functions, for the same reason, and used by the home panel as well as the setup screen. |
| `onboarding/actions.ts` | The `"use server"` module holding both write paths. |
| `planner/StudyRoadmap.tsx` | The order the plan works through the curriculum, with its CSS Module. Every item shows the reason it is where it is, which is what FR-003 asks a recommendation to carry, and carries the control that says what became of it — completed, skipped, or back to planned. It reorders nothing: ordering is a planning rule, and a settled item keeps its place. It also shows the learner's own material for each item's topic, **read-only**, through `resources/TopicResources.tsx`; nothing is recommended and a topic with nothing linked renders nothing. Contracted by [ADR-036](../adr/ADR-036-topic-material-on-the-plan-screens.md). |
| `planner/PlanWeek.tsx` | The work the plan places on each of the coming days, with its CSS Module, each item carrying the control that says what became of it and the learner's own material for its topic, **read-only**, through `resources/TopicResources.tsx`. A day with no work is absent rather than shown empty; no day or week is totalled, and nothing counts how much of one is done — including its material. Contracted by [ADR-036](../adr/ADR-036-topic-material-on-the-plan-screens.md). |
| `planner/GeneratePlanForm.tsx` | The button that asks for a plan, with its CSS Module. A client component only so it can report the last submission's result; it calls no API itself. It says plainly that rebuilding keeps the previous plan. |
| `planner/PlanItemStatusControl.tsx` | The control beside one plan item that records what became of its work, with its CSS Module. It offers the **three statuses the item is not already in** — `completed`, `skipped`, `postponed`, and `planned` in any direction — as one form each, so the status travels in a hidden field and a scriptless submission carries it exactly as a hydrated one does. A client component only so it can report the last submission's result; it calls no API itself. An item in a status PLN-004 does not accept as a target is shown with no control rather than as something a learner can move; every stored status is now offered, so that branch is reached only by a value a later backend adds. Contracted by [ADR-024](../adr/ADR-024-plan-item-skipping.md) and [ADR-025](../adr/ADR-025-learner-postponement.md). |
| `planner/DailyStudyView.tsx` | The daily study view's two panels — the work the weekly plan placed on the learner's own date, and work whose day has passed — with its CSS Module. Each item shows its reason, the learner's own material for its topic **read-only**, and the same status control the other panels carry; one `PlanItemLine` serves both panels, so an item reads the same in each. It writes no plan and asks for none: rebuilding stays on `/plan`, and registering material stays on `/resources`. Contracted by [ADR-023](../adr/ADR-023-daily-study-view.md) and [ADR-036](../adr/ADR-036-topic-material-on-the-plan-screens.md). |
| `planner/PlanFeasibility.tsx` | Whether the learner's saved study week covers the work left before their horizon, with its CSS Module. It renders the sentence and the figures PLN-006 returned rather than computing any — totalling a week is planning arithmetic the backend owns — and carries **no control of any kind**. Counts and durations only: no percentage, no fraction, and no progress bar, which would be a percentage drawn. Contracted by [ADR-027](../adr/ADR-027-plan-feasibility.md). |
| `planner/MonthlyPlanView.tsx` | The monthly study view's two panels — the days this month the plan has already dated, and the roadmap topics the week has not reached — with its CSS Module. Each item shows its reason, and a settled item keeps its place marked in words. It deliberately carries **no status control and no plan control**: it writes nothing at all, so marking work stays on `plan/today` and rebuilding stays on `plan`. It is also the one plan panel that deliberately shows **no material**, because the month's value is its shape. Contracted by [ADR-026](../adr/ADR-026-monthly-study-view.md) and [ADR-036](../adr/ADR-036-topic-material-on-the-plan-screens.md). |
| `revision/RevisionList.tsx` | The revision screen's two panels — reviews ready now, and those still to come or already answered — with its CSS Module. Each shows the reason the schedule gave and carries the control that records what became of it. Contracted by [ADR-028](../adr/ADR-028-revision-workflow.md). |
| `revision/RevisionStatusControl.tsx` | The control beside one review that records what became of it, with its CSS Module. It offers the three statuses the review is not already in — reviewed, skipped, postponed, or back to due — deliberately mirroring `PlanItemStatusControl`, so a learner meets one vocabulary rather than two. |
| `revision/ScheduleRevisionsForm.tsx` | The button that asks for reviews to be scheduled from finished work, with its CSS Module. A client component only so it can report what the last run did; nothing schedules on its own, and asking twice adds nothing. |
| `revision/submission.ts` | Reads the revision forms into the requests they make, and owns their state shapes. It holds no scheduling rule and collects no date and no reason. |
| `revision/actions.ts` | The `"use server"` module holding the schedule and status paths. |
| `planner/month.ts` | Resolving the learner's own calendar month from their stored timezone, the month's boundaries, and splitting the roadmap and the week into the month's dated days and the topics ahead of them. Plain functions taking the instant as an argument, so they are testable at fixed moments across zones without a running server. `learnerMonth` delegates to `today.ts` rather than converting again, so one conversion and one UTC fallback serve both screens. Month boundaries are computed from the month's own numbers rather than through a `Date`, and the leap-year rule is the full Gregorian one. Nothing here places work on a day: that is planning, and the backend owns it. |
| `planner/today.ts` | Resolving the learner's own calendar date from their stored timezone, and splitting a weekly plan into today's work and work whose day has passed. Plain functions taking the instant as an argument, so they are testable at a fixed moment across zones without a running server. The overdue boundaries are mirrored from the domain rule `select_overdue`, which stays authoritative for what adaptation writes; nothing here writes anything. |
| `planner/plan.ts` | Grouping a dated plan by day, and describing an estimate and an action the way a learner reads them. Plain functions, so they are testable without a running server. Dates are printed as the API's own ISO strings, for the reason `home/dates.ts` records. It also decides the classes an item carries and the words beside it, so every panel marks a settled one — completed, skipped, or postponed — the same way, reading the one frontend copy of the settled set in `types/study-plan.ts`. |
| `planner/submission.ts` | Reads the planner's three forms into the requests they make, and owns their state shapes. It reads no preference and no completion time: a plan is built from what the learner stored, and *when* they marked an item completed is the server's record, never what a client sends. Nothing records when an item was skipped, or why. |
| `planner/AdaptPlanForm.tsx` | The button that asks for the plan to be rebuilt around what happened, with its CSS Module. A client component only so it can report the last submission's result; it calls no API itself. It says what adapting will do — what is dropped, what is carried forward, and that the old plan is kept — before it is pressed, and it is rendered only when a plan exists. |
| `planner/actions.ts` | The `"use server"` module holding the generate, plan-item status, and adapt paths. |
| `progress/StudyProgressOverview.tsx` | The progress overview's seven panels — what could use the learner's attention, what each active plan covers, today's work, whether the saved week reaches the horizon, what the learner has marked, the learning stages they recorded by subject, and the reviews ready now — with its CSS Module. It renders `PriorityFocus` first, then `PlanFeasibility` and `LearningStagesBySubject` unchanged and reuses `planner/plan.ts` and `planner/today.ts` rather than copying them. It carries **no control of any kind** and writes nothing: each panel names where its action lives and links to it. **It counts nothing of its own** — the only figures are ones the API reported. Contracted by [ADR-029](../adr/ADR-029-progress-overview.md), its stages panel by [ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md), and its priority focus panel by [ADR-031](../adr/ADR-031-priority-focus-panel.md). |
| `progress/overview.ts` | Grouping the plan items a learner has settled under the words for each status, naming a plan type, and selecting the reviews the backend says are due. Plain functions, so they are testable without a running server. It derives no figure that reaches the screen, and `is_due` is read rather than recomputed — what counts as due is a domain rule. |
| `progress/LearningStagesBySubject.tsx` | The progress overview's stages panel — the learning stages the learner recorded, under the subject each topic belongs to — with its CSS Module. It carries **no control of any kind**: recording a stage stays beside the topic in the curriculum view, which it links to. **It counts nothing and ranks nothing** — no figure beside a subject, and every stage styled identically, because a colour scale would order the five against each other. It says "could not be read" apart from "you have recorded nothing". Recorded in [ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md). |
| `progress/PriorityFocus.tsx` | The progress overview's priority focus panel — what could use the learner's attention, and why each entry is there — with its CSS Module. It carries **no control of any kind**: every group names where its action lives and links to it. **It counts nothing and ranks nothing** — no tally of what is outstanding, no numbering, no cap, and every group styled identically, because a warning colour on one would be a ranking drawn rather than written. A feasibility reading that could not be taken contributes no entry, rather than a claim in either direction. Recorded in [ADR-031](../adr/ADR-031-priority-focus-panel.md). |
| `progress/priority-focus.ts` | Gathering the three facts a backend rule already decided that could use attention: an item whose day has passed (through `planner/today.ts`'s existing partition, so `select_overdue` gains no second mirror), a review REV-001 reports as due, and PLN-006's shortfall or unanswerable verdict. Plain functions, so they are testable without a running server. It decides nothing itself, the recorded learning stage is deliberately not a signal, and the group lengths it uses to decide whether a group has content never reach the screen. |
| `progress/subject-stages.ts` | Gathering PRG-002's records under the subjects CUR-003 returns — the join `stages.ts` performs, read the other way round. Plain functions, so they are testable without a running server. The order is the curriculum's, arrived at by **walking** the tree and picking up a record where one exists rather than by sorting PRG-002's newest-first list, and the group lengths it uses to decide whether a subject has content never reach the screen. A stage this build does not recognise is skipped, as in `stages.ts`. |
| `progress/TopicStageControl.tsx` | The learning-stage control beside one trackable topic, with its CSS Module. A client component only so it can report the last submission's result; it calls no API itself. |
| `progress/stages.ts` | Joins PRG-002's records onto the topics CUR-003 returns, and reports the stage for one topic. Plain functions, so they are testable without a running server. A stage this build does not recognise is skipped rather than shown raw. |
| `progress/submission.ts` | Reads the stage form into the request it makes, and owns the control's state shape. |
| `progress/actions.ts` | The `"use server"` module holding the write path. |
| `practice/QuestionForm.tsx` | Where a learner writes one practice question of their own **and where they correct one**, with its CSS Module — one component for both, as `ResourceForm` is for a resource, since they ask for the same five fields and differ only in whether they start filled and which action they reach. A client component only so it can report the last submission; it offers no way to generate a question, because LearnFlow writes none. |
| `practice/QuestionBank.tsx` | The questions the learner has written, newest first, with the expected answer named in words. A question set aside is still listed, so it can be brought back. Nothing is counted or ranked. |
| `practice/QuestionStatusControl.tsx` | The control beside one question that sets it aside or brings it back, with its CSS Module. Nothing here deletes, and nothing here edits. |
| `practice/StartQuizForm.tsx` | Where a learner chooses the topics to practise, with its CSS Module. The quiz asks every question written for them, so nothing here picks a count or a difficulty. |
| `practice/QuizForm.tsx` | The quiz being answered, with its CSS Module. Pre-selects nothing, submits the whole attempt in one form post, and shows no expected answer — QZ-002 sends none. |
| `practice/AttemptResult.tsx` | What became of each question, with its CSS Module. **Renders no score and derives nothing**, and colours no outcome: the words carry the meaning. |
| `practice/AttemptHistory.tsx` | The quizzes the learner has taken, linking to each result. No attempt is set against another. |
| `practice/submission.ts` | Reads the five practice forms into the requests they make, and owns their state shapes. A correction is the same reading as a written question plus the question it corrects, so `readQuestionCorrection` reuses `readQuestionSubmission` rather than repeating it. It re-indexes the expected answer when a blank option is dropped, and leaves an unanswered question out of a submission rather than sending a blank. |
| `practice/actions.ts` | The `"use server"` module holding the write, **correct**, retire, assemble, and submit paths. The last two redirect, so the flow works with no JavaScript. |

A goal response carries the examination **window** but not the dated periods, per
[endpoints](../api/endpoints.md#learner-setup-and-goal-endpoints), so a screen wanting the
registration and results dates reads EXM-001 and matches the goal's cycle by id. That is why the home
screen makes a third call rather than a second, and why it skips it entirely for a goal aiming at a
target date alone. It carries the saved **week** and the saved **planning preferences**, however, so
neither needs a call of its own on either screen.

The home screen shows the learner's **active** goal, falling back to the most recent one when they
have none active — a paused or archived goal is history, and is shown only when it is all they have.

**A `"use server"` module may export only async functions.** Exporting a constant from one throws
`A "use server" file can only export async functions` on the first request that reaches it — a `500`
that neither `tsc --noEmit` nor `next build` reports. That is why the setup and availability state
shapes and their initial values live in `submission.ts` and `availability.ts` rather than beside the
actions, and why `frontend/tests/server-actions.test.ts` checks the rule for every such module.

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
| `api-client.ts` | Typed calls to the curriculum, learner, examination-schedule, study-goal, availability, topic-progress, study-plan, revision, and learning-resource endpoints. Checks each response against the documented envelope and raises `ApiError`. Runs on the server only, including for writes, which reach it from a server action. |

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

Vitest specs for the API client, the configuration reader, the curriculum, learner-setup, home,
progress, and planner components, the setup, availability, stage, and generate-plan forms' submission
parsing, the home screen's date presentation, the planning-preference presentation, the plan
presentation, the daily study view and the date and overdue rules behind it, the monthly study view
and the month conversion, boundary, and selection rules behind it, the stage-to-topic join, the
priority-focus gathering rules, and the `"use server"` export rule. They stub `fetch` and reach no live backend, so `npm test` needs
nothing running.

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
- [ADR-017: Record manual topic progress as a learner-owned stage](../adr/ADR-017-topic-progress-api-and-schema.md) — the contracts the `progress/` module implements, and why its control sits inside the curriculum view
- [ADR-018: Store weekly availability as named days replaced a week at a time](../adr/ADR-018-weekly-availability-slots.md) — the contract the availability form and panel implement, and why a week is saved all at once
- [ADR-019: Store planning preferences as typed columns replaced as a group](../adr/ADR-019-study-goal-planning-preferences.md) — the contract the preference controls and panel implement, and why they need no form or action of their own
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](../adr/ADR-020-initial-study-plan-generation.md) — why the planning rules live in the domain layer, and the contracts the `planner/` module implements
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](../adr/ADR-021-plan-item-completion.md) — the plan-item control the planner feature gained, and the write path it shares with generation
- [ADR-022: Adapt a study plan by rebuilding it around what happened](../adr/ADR-022-plan-adaptation.md) — the adapt control, and the third rule in the domain layer
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](../adr/ADR-023-daily-study-view.md) — the `plan/today` route, the two planner modules behind it, and why it is force-dynamic
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](../adr/ADR-026-monthly-study-view.md) — the `plan/month` route, the two planner modules behind it, and why it renders no control at all
- [ADR-027: Report whether the saved week reaches the horizon, as a read-only planning rule](../adr/ADR-027-plan-feasibility.md) — the fourth domain rule, and the `/plan` panel that renders it
- [ADR-029: Show the progress overview as a reading of what is stored, counting nothing of its own](../adr/ADR-029-progress-overview.md) — the `progress` route, the two modules behind it, and why it adds no endpoint
- [ADR-030: Gather the recorded learning stages by subject, listing them rather than counting them](../adr/ADR-030-learning-stages-by-subject-panel.md) — the two further modules that route gained, and the two reads they consume unchanged
- [ADR-031: Draw priority focus from facts backend rules already decided, ranking nothing](../adr/ADR-031-priority-focus-panel.md) — the two modules that route gained again, why the panel renders no control, and why it adds no read at all
- [ADR-033: Assemble checkpoint practice from the learner's own questions, and report outcomes rather than a score](../adr/ADR-033-checkpoint-practice-workflow.md) — `checkpoint_marking.py`, the `practice/` feature module, and the three practice routes
- [ADR-034: Show the checkpoint-practice history as a paged reading of stored attempts, counting nothing](../adr/ADR-034-checkpoint-practice-history.md) — the fourth practice route, and the `history.ts` module behind it
- [ADR-035: Let a practice question be corrected until a quiz has asked it](../adr/ADR-035-practice-question-correction.md) — why `QuestionForm.tsx` serves two jobs, and where the correction form sits
- [ADR-036: Show a topic's material beside the plan items that name it, read-only](../adr/ADR-036-topic-material-on-the-plan-screens.md) — the fourth and fifth surfaces `TopicResources.tsx` serves, and the plan panel deliberately left without it
- [Terminology](../domain/terminology.md) — why that module keeps the narrower name
- [API conventions](../api/conventions.md) — the contract `frontend/types/` is derived from
- [API endpoint catalog](../api/endpoints.md) — the endpoints each screen above reads, and the response fields they carry
- [Database migrations](../database/migrations.md) — the authoritative description of the curriculum seed named in `backend/scripts/`
- [Docker strategy](../deployment/docker.md) — what `compose.yaml`, `docker/`, and `.dockerignore` contain today
- [CI/CD strategy](../deployment/ci-cd.md) — what the workflow files in `.github/` verify
- [Engineering AI workflow](../ai/engineering-ai.md) — what the definitions in `.claude/` implement
- [ADR-010: Deliver features through pull requests with automated gates](../adr/ADR-010-feature-delivery-workflow.md) — the decision that introduced `scripts/`, `.github/workflows/`, and the delivery skill
- [ADR-028: Schedule revisions from finished work, on the learner's ask](../adr/ADR-028-revision-workflow.md) — the `revisions` route, the second domain module, and the feature module behind them
