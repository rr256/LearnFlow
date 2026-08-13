---
title: LearnFlow Delivery Milestones
status: approved
owner: product-and-architecture
last_updated: 2026-08-13
related:
  - ../00-project-context.md
  - roadmap.md
  - ../requirements/mvp.md
  - ../development/git-workflow.md
  - ../deployment/ci-cd.md
  - ../deployment/docker.md
  - ../database/migrations.md
  - ../database/schema.md
  - ../adr/ADR-011-sqlalchemy-persistence-implementation.md
  - ../adr/ADR-012-curriculum-seed-and-reconciliation.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
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
  - ../adr/ADR-025-learner-postponement.md
  - ../adr/ADR-026-monthly-study-view.md
---

# LearnFlow Delivery Milestones

## Purpose

Define reviewable delivery checkpoints for LearnFlow. A milestone is complete only when its outcome is demonstrated and its documentation is aligned—not merely when files have been created.

## Milestone 0 — Documentation Foundation

**Outcome:** the repository contains a coherent, approved handbook for the MVP.

### Definition of Done

- [x] `docs/00-project-context.md` is the mandatory project entry point and links resolve.
- [x] Vision, MVP, functional, and non-functional requirements are approved.
- [x] Domain model, entities, and terminology are approved.
- [x] Architecture overview, Clean Architecture, provider pattern, and dependency rules are approved.
- [x] Database, API, RAG, AI workflow, development, deployment, and roadmap documentation is present and cross-linked.
- [x] Architecture decision register reflects approved and deferred decisions.
- [x] Required ADRs are created or explicitly scheduled before related implementation begins.
- [x] No duplicate documentation folder remains as a competing source of truth.
- [x] Documentation changes are committed in a reviewable Git commit.

## Milestone 1 — Local Platform Foundation

**Outcome:** a new contributor can run the technical base locally and obtain curated GATE CSE curriculum data.

### Definition of Done

- [ ] Repository skeleton follows `docs/development/folder-structure.md`. `backend/`, `frontend/`,
  `docker/`, `scripts/`, `.github/`, and `.claude/` all exist with the responsibilities that document
  assigns them. What is still absent is absent by that document's own rule that a folder is created
  when its first file needs it: `frontend/public/`, and the backend infrastructure subfolders for
  providers, storage, and RAG.
- [x] Backend starts through FastAPI application factory/composition root.
- [x] `GET /health` returns a safe readiness response.
- [ ] Docker Compose starts frontend, backend, PostgreSQL, and ChromaDB. The `frontend`, `backend`, and `postgres` services are implemented (`compose.yaml`, `docker/frontend.Dockerfile`, `docker/backend.Dockerfile`), and CI validates the topology and builds both images on every pull request. The backend image build and the topology validation first passed on pull request #7. On pull request #13, the topology validation covered the new `frontend` service from that service's first run, and the frontend image build first passed in run `30850601752`. **The stack was started for the first time on 2026-08-08**, on a Windows workstation with Docker Desktop: all three services came up healthy, the backend reached `postgres` and the frontend reached `backend` over the Compose network, migrations and both seeds ran against the container, and the home screen rendered the seeded goal. That run found and fixed one defect — the volume was mounted at the pre-18 `/var/lib/postgresql/data` while the image was pinned to `postgres:18-alpine`, so `postgres` refused to start. **The item remains open on one count**: `chromadb` joins Compose with the code that consumes it. See [Docker strategy](../deployment/docker.md#first-local-run-2026-08-08) for what that run did and did not demonstrate.
- [x] Backend configuration is validated from environment variables. Now includes `DATABASE_URL`, which has no default and is required.
- [x] Alembic initializes and applies an initial migration to a fresh PostgreSQL database. `20260731_01_create_curriculum_tables` creates the curriculum area, `20260731_02_add_topic_code_unique_constraint` amends it, and `20260801_01_create_examination_schedule_and_learner_goal_tables` adds the examination schedule area and the first two learner-planning tables; the CI `database` job applies them to an empty PostgreSQL service container, compares the models against the result, exercises the constraints, and downgrades back to empty on every pull request. The remaining schema areas are migrated with the milestones that use them, per [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md).
- [x] Curated GATE CSE curriculum seed/import is idempotent. `backend/scripts/seed_curriculum.py`
  loads the curated GATE CSE curriculum — 11 subjects and 65 topics and subtopics, transcribed from
  the official syllabus — matching every record on a natural key, writing only what differs, and
  never deleting. A repeat run writes nothing. Covered by
  unit tests against a fake and by integration tests that apply the seed twice to an ephemeral
  PostgreSQL database in the CI `database` job. See
  [the curriculum seed](../database/migrations.md#the-curriculum-seed) and
  [ADR-012](../adr/ADR-012-curriculum-seed-and-reconciliation.md).
- [x] Curriculum API endpoints return data-driven program/subject/topic hierarchy. CUR-001 to
  CUR-003 are implemented under `/api/v1/curriculum`: a paginated program list, one program with its
  active curriculum-version reference, and a version's subjects, topics, subtopics, and topic
  relationships, ordered by the syllabus positions. Nothing in the hierarchy is hardcoded — the
  responses are assembled from the seeded rows. Routes call an application use case through a
  read-only repository port and touch no session. Covered by unit tests against a fake, API tests
  over the real application factory, and integration tests that seed the bundled GATE CSE curriculum
  into an ephemeral PostgreSQL database in the CI `database` job and read it back over HTTP. See
  [endpoints](../api/endpoints.md#curriculum-endpoints).
- [ ] Setup instructions work from a clean local environment.
- [ ] Relevant tests/build checks pass.

## Milestone 2 — Learner Setup and Progress Baseline

**Outcome:** one learner can establish a GATE CSE goal and see meaningful topic progress.

Part of this milestone arrived early, in Milestone 1: `learners` and `study_goals` were created
alongside the examination schedule they reference, because a goal with nothing to aim at is not
persistable, and the schedule seed that fills it shipped with them. The curriculum-browsing item
arrived early too, with the frontend foundation — the curriculum read endpoints already existed, so
a read-only view of them needed nothing this milestone had yet to deliver. Those items are checked
below with their evidence. `availability_slots` deliberately stayed behind — it would have fixed the
`day_of_week` numbering convention that no requirement then constrained, which is what
[ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) exists to avoid. It has since
arrived with the change that needed it, in migration `20260806_01`, and the convention was retired
rather than chosen: the column stores a day name. See
[ADR-018](../adr/ADR-018-weekly-availability-slots.md).

The learner setup half of this milestone is now delivered: EXM-001, LRN-001, LRN-002, and GOAL-001 to
GOAL-004, and the `/setup` screen that consumes them, contracted by
[ADR-016](../adr/ADR-016-learner-onboarding-api-contracts.md) and needing no migration; GOAL-005,
which records weekly availability, contracted by
[ADR-018](../adr/ADR-018-weekly-availability-slots.md) and needing one; and the planning preferences
GOAL-001 and GOAL-004 now accept, contracted by
[ADR-019](../adr/ADR-019-study-goal-planning-preferences.md) and needing one more. The home
screen at `/` is a second consumer, reading that saved setup back over LRN-001, GOAL-002, and
EXM-001 — which is the acceptance criterion later added to
[FR-002](../requirements/functional.md#fr-002-initial-learner-setup); it needed no endpoint of its
own, and the saved week and the saved preferences both arrived on it the same way.

The first half of progress tracking has now arrived too: a learner can mark a trackable topic with a
learning stage and change it later, over PRG-004, and see the saved stage while browsing the
curriculum, over PRG-002. Contracted by
[ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md), with migration `20260805_01` creating
`learner_topic_progress`. Material status, study activities, and the progress overview are what
remain.

### Definition of Done

- [x] Published examination schedule seed/import is idempotent.
  `backend/scripts/seed_examination_schedule.py` loads the GATE 2027 schedule — six dated periods
  across registration, late registration, three examination weekends, and the results announcement —
  from `gate_cse_examination_schedule.json`, matching every record on a natural key the database
  enforces, writing only what differs, and never deleting. A repeat run writes nothing. It refuses to
  run before the curriculum seed, naming the command to run first. The schedule keeps its official
  source, the date that source was read, and a `provisional`/`confirmed` status, so a date is never
  presented as settled while its source says it may change. Covered by unit tests against a fake and
  by integration tests that apply the seed twice to an ephemeral PostgreSQL database in the CI
  `database` job. See [the examination schedule seed](../database/migrations.md#the-examination-schedule-seed)
  and [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md).
- [x] Learner profile/local identity is initialized safely. LRN-001 reads the local learner's profile
  and LRN-002 creates or updates it, contracted by
  [ADR-016](../adr/ADR-016-learner-onboarding-api-contracts.md). Safe initialization is what those
  contracts settle: a read returns `data: null` rather than creating the record it did not find, so no
  page load leaves a learner behind; the record is created by the learner's own action; the timezone
  comes from `APP_DEFAULT_TIMEZONE` rather than a database default; a partial update leaves an omitted
  field alone; no request accepts a `learner_id`, so no client can address another learner; and more
  than one stored learner is refused with a `409` rather than resolved by guessing. Covered by unit,
  API, and PostgreSQL integration tests.
- [x] Learner can select active GATE CSE curriculum, target date, and weekly availability. **Done
  through the frontend.** `/setup` reads the profile from LRN-001, the programs from CUR-001, the
  existing goal from GOAL-002, and the published cycles from EXM-001, then writes through LRN-002 and
  GOAL-001 or GOAL-004 — binding the learner to the program's active curriculum version and to an
  examination window, a target date, or both. `python -m scripts.set_study_goal` still does the same
  from the command line. The goal aims at an examination *window* rather than a guessed date; see
  [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md).
  **Weekly availability is now recorded too**, over GOAL-005 and the `availability_slots` table
  migration `20260806_01` creates, contracted by
  [ADR-018](../adr/ADR-018-weekly-availability-slots.md). One form saves the whole week: a day the
  learner enters is stored, a day they clear is removed, and a day of zero minutes is one deliberately
  kept free. A day is named rather than numbered, which retires the `day_of_week` convention that held
  this item open rather than answering it. The saved week reads back on `/setup` and on the home
  screen, off the goal response, so neither screen makes a further call. Nothing totals a week —
  planning arithmetic belongs to Milestone 3. **Basic planning preferences are now accepted too**, over
  GOAL-001 and GOAL-004 and the two columns migration `20260806_02` adds to `study_goals`, contracted
  by [ADR-019](../adr/ADR-019-study-goal-planning-preferences.md): a preferred session length and a
  topic order, each optional and neither given a default, so a preference nobody set never reads as one
  somebody chose. They are two controls on the same setup form and ride on the same goal write, so no
  endpoint and no further request were added, and they read back on `/setup` and on the home screen off
  the goal response. Both are now consumed by the plan PLN-001 generates, which arrived with the item
  below. That completes
  [FR-002](../requirements/functional.md#fr-002-initial-learner-setup)'s second criterion;
  [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries the count.
- [x] Learner can browse curriculum in the frontend without hardcoded topic data. `/curriculum` lists
  the learning programs from CUR-001, and `/curriculum/programs/{id}` reads one program from CUR-002
  and renders its active version's subjects, topics, nested subtopics, and topic relationships from
  CUR-003. No GATE CSE content appears in frontend code, and the frontend does not reorder what the
  backend returns — syllabus order is a curriculum rule. Loading, empty, error, and not-found states
  are all handled, with each loading boundary placed below the call that decides `404` so a mistyped
  program id still answers `404` rather than `200`. Covered
  by component and API-client tests, and exercised end to end against the
  production build with a contract-shaped stub API: the rendered hierarchy, a `404` for an unknown
  program id, and the API-unreachable panel were each confirmed. **Not yet exercised against the real
  backend**, which needs PostgreSQL; see [Docker strategy](../deployment/docker.md#verification-status).
- [ ] Learner can record material status, learning stage, and study activity. **The learning stage is
  done**: PRG-004 records one of the five approved stages against a trackable topic and rewrites it on
  a later submission, PRG-002 reads back what was recorded, and the `/curriculum/programs/{id}` screen
  offers a control beside each trackable topic. A topic with no record reads as *Not explored* rather
  than being written on the learner's behalf, and a grouping topic is refused, matching
  `topics.is_trackable`. Material status and study activity remain: `learner_topic_progress.material_status`
  is deliberately not created and `study_activities` does not exist, each waiting on the code that
  would write it, per [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) and
  [ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md).
- [ ] Progress overview shows subject/topic progress and priority focus areas. PRG-001 needs the
  revision records Milestone 3 brings, and nothing is built. The plan half of it now exists:
  `study_plans` and `plan_items` are created and PLN-002 reads them, so what PRG-001 still lacks is
  revision and the priority-focus evidence.
- [x] Supportive learning-stage labels and next actions are used in UI. The stored values are
  `snake_case`, and the screen renders the five labels
  [terminology](../domain/terminology.md) defines, each paired with a constructive next action rather
  than a verdict — which is [FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence)'s
  sixth acceptance criterion. A stage never reads as a score: a learner may move to any stage from
  any stage, including backwards, and nothing compares two of them. Covered by a test asserting that
  none of the wording terminology.md tells us to avoid appears in the labels or the next actions.
- [ ] API, domain, persistence, and frontend tests cover core progress state transitions. Covered for
  the learning stage: unit tests against a fake, API tests over the real application factory, and
  PostgreSQL integration tests that record a stage over HTTP against the seeded GATE CSE curriculum
  and verify the constraints. Exercised end to end against the production standalone frontend with a
  contract-shaped stub API — a no-JavaScript submission created a stage, a second updated it, the
  saved stage and its next action read back, and no API address appeared in any served page or client
  script. **The integration tests were not run against a live database locally when this item
  was delivered** — that workstation then had no PostgreSQL, so they skipped and the CI `database` job
  was their only run. They have since been run locally, on 2026-08-09; see the planning-test item in
  Milestone 3 below. The remaining
  transitions arrive with the records that have them.
- [x] Learner receives an initial study plan with no previous progress. PLN-001 generates a roadmap
  over every trackable topic and a plan for the coming week, from the curriculum, the goal's horizon,
  the saved study week, the planning preferences, and any recorded stages; PLN-002 and PLN-003 read
  them back, and `/plan` shows them with the reason for every item. That completes
  [FR-002](../requirements/functional.md#fr-002-initial-learner-setup)'s fifth and last acceptance
  criterion, so all five are now met;
  [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries the count. It also delivers
  part of Milestone 3 early, which is recorded there. Contracted by
  [ADR-020](../adr/ADR-020-initial-study-plan-generation.md).
- [ ] Requirements/API/schema docs are updated to match implementation.

## Milestone 3 — Planning and Revision

**Outcome:** LearnFlow provides an actionable study timeline and adapts it to learner progress.

Part of this milestone arrived early, with the change that completed
[FR-002](../requirements/functional.md#fr-002-initial-learner-setup)'s last acceptance criterion: a
learner cannot "start with no previous progress and still receive an initial plan" without a planner,
so PLN-001 to PLN-003, `study_plans`, `plan_items`, and the deterministic planning rules were
delivered in Milestone 2's closing change. They are checked below with their evidence. The first half
of plan adaptation has since followed, and then the second: PLN-004 lets a learner mark an item
completed, and PLN-005 rebuilds the plan around what they have and have not done — leaving out what is
finished and carrying forward what was missed. A **daily study view** has joined them at
`/plan/today`, built by reading the weekly plan rather than by generating a `daily` one, so it needed
no endpoint and no migration. **Skipping and then postponement have since completed the set**: a
learner can say a planned session will not happen, or will not happen yet, and either settles the item
without retiring its topic. All four of `plan_items.status`'s values are written, and **all three of
FR-004's verbs are learner actions**. A **monthly study view** has since joined the daily one at
`/plan/month`, built the same way — by reading the roadmap and the week rather than generating a
`monthly` plan — which meets **FR-003's second acceptance criterion in full**.
What remains is saying whether a learner's week can reach their horizon, and revision.

### Definition of Done

- [ ] Learner can generate roadmap, monthly, weekly, and daily plan views. **Roadmap and weekly are
  done**: PLN-001 generates both from the learner's curriculum, horizon, saved week, planning
  preferences, and recorded stages, PLN-002 and PLN-003 read them back, and `/plan` shows them.
  Contracted by [ADR-020](../adr/ADR-020-initial-study-plan-generation.md), with migration
  `20260806_03` creating the two tables. **A daily view is now done too, as a reading rather than a
  plan**: `/plan/today` shows the work the active weekly plan placed on the learner's own calendar
  date — taken from `learners.timezone`, never the server's — with the reason for each item and the
  same completion control the other panels carry, alongside work whose day has passed, which it shows
  and deliberately does not move. It needed **no endpoint and no migration**: it filters what PLN-003
  already returns. Contracted by [ADR-023](../adr/ADR-023-daily-study-view.md). **A monthly view
  completes the set, as a reading too**: `/plan/month` shows where the learner's own calendar month
  sits in their plan — the days that month already has dated work on, and the roadmap topics their
  week has not dated, openly undated. Because a weekly plan dates seven days, a month is mostly
  undated, and the screen says so rather than spreading the roadmap across days nothing placed work
  on: placing work is planning, which the backend owns. It is **read-only** — marking an item stays
  on `/plan/today` and `/plan` — and it needed **no endpoint, no migration, and no backend change at
  all**. Contracted by [ADR-026](../adr/ADR-026-monthly-study-view.md). **All four levels are now
  viewable**, which meets
  [FR-003](../requirements/functional.md#fr-003-study-timeline-and-plan)'s second acceptance
  criterion in full. The item stays open because two of the four are read rather than **generated**:
  a `monthly` and a `daily` *plan* are approved `plan_type` values that nothing writes, and what each
  contains is deliberately still undecided, so each is a use-case change rather than a migration.
- [x] Plan items link to topics and supported actions. Every generated item names a trackable topic
  and carries `action_type = 'study'`; `practice`, `revise`, and `review_mistakes` are constrained and
  unwritten, each waiting on the work it names — checkpoint quizzes, revision records, and mistake
  evidence.
- [x] Learner can complete, skip, or postpone plan items. **All three are now learner actions.**
  PLN-004 marks an item `completed`, `skipped`, or `postponed` and puts any of them back to
  `planned`, writing `plan_items.status` and `completed_at` — the two columns `20260806_03` created
  ahead of the code that writes them, so none of the three deliveries needed a migration.
  **`postponed` now has two writers**: the learner, saying the work is not happening yet, and
  adaptation, marking work whose day passed with nothing said about it on the plan it supersedes. The
  value means the same thing either way, and postponing **moves nothing on its own** — the work is
  placed again when the learner adapts.
  `/plan`'s two panels and `/plan/today` all offer the controls beside every item, and a settled item
  keeps its place rather than disappearing. **Every move is reversible**, as a learning stage is, and
  each moves that item alone: no plan, no other item, and no learning stage, because a plan item
  records whether planned work happened rather than that a topic is understood. Nothing is counted and
  nothing is re-planned. **Skipping and postponing settle the item, not the topic** — neither is ever
  overdue, so adaptation leaves both alone, and either topic is planned again, which is what keeps
  both reversible once the plan they sit on is superseded. Contracted by
  [ADR-021](../adr/ADR-021-plan-item-completion.md),
  [ADR-022](../adr/ADR-022-plan-adaptation.md),
  [ADR-024](../adr/ADR-024-plan-item-skipping.md), and
  [ADR-025](../adr/ADR-025-learner-postponement.md).
- [x] Learner can request plan adaptation after missed work or availability changes. **Done**:
  PLN-005 rebuilds a goal's active plans around what happened. A topic with a completed session
  anywhere on the goal is not planned again; work whose day passed with the task undone is marked
  `postponed` on the plan being set aside and re-placed on the new one. The learner asks — nothing
  adapts on its own. It supersedes as generation does, uses the same ordering and placement rules,
  and needed **no migration**. Contracted by [ADR-022](../adr/ADR-022-plan-adaptation.md).
  What FR-004's third criterion asks for — reporting that the
  learner's week cannot reach their horizon — is still not built, and is the item below.
- [ ] Revision records are generated, listed, and updateable by learner action. `revision_records`
  does not exist; nothing is built.
- [x] Planning works with deterministic rules when Ollama is unavailable. No AI provider is involved
  at all: the same goal, curriculum, week, preferences, and date produce the same plan every time, and
  the two rules that decide it — topic order and session placement — are pure functions in
  `backend/app/domain/study_planning.py`.
- [ ] Insufficient-time trade-offs are visible rather than hidden. Partly: a plan states what it was
  built from, what the planner chose for itself, when no week could be scheduled, and — since PLN-005 —
  how many topics remain and how much was carried forward. What it still does not say is whether the
  saved week can reach the horizon at all. That is FR-004's third acceptance criterion and the last
  part of it unbuilt; adaptation narrowed the gap without closing it.
- [ ] Core planning/revision rules have deterministic tests. **Covered for planning**: unit tests over
  the domain rules with no database or clock, unit tests over the use case against fakes with a fixed
  clock, API tests over the real application factory, and PostgreSQL integration tests that generate a
  plan over the seeded GATE CSE curriculum and read it back. **Completion is covered on three of
  those levels** — use case, API, and PostgreSQL integration — plus a frontend panel test. There is
  deliberately **no domain-level test** for it: deciding which status a learner may ask for is a
  contract check rather than a planning calculation, and `study_planning.py` is untouched. Those tests
  assert that completing one item moves no other row, that a refused status writes nothing, and that
  neither panel can drop the control. It was also exercised end to end against the production
  standalone frontend with a contract-shaped stub API and **JavaScript disabled**: 25 checks passed,
  covering a no-JavaScript completion reaching PLN-004 exactly once, the undo, the `409` for an item
  on a superseded plan, that only the item acted on moved, and that no API address appeared in any
  served page or client script. **Adaptation is covered on the same
  levels**, with a pure domain test for what makes an item overdue added beside them. **The daily
  study view is covered at the frontend level only**, which is where all of it lives: unit tests over
  the date conversion at a fixed instant across four timezones and its UTC fallback, over the
  overdue boundaries it mirrors from the domain, and a component test asserting that every item shows
  its reason and its control, that a completed item keeps its place, that nothing is counted, and that
  no copy on the screen describes the learner rather than an item. No backend test changed, because no
  backend code did. It was also exercised end to end against the production standalone frontend with
  a contract-shaped stub API and **JavaScript disabled**: **50 checks passed**, covering the
  learner-timezone date selection against a server running in UTC, the today and earlier-days
  grouping, a no-JavaScript completion reaching PLN-004 exactly once, the undo, that only the item
  acted on moved, all four empty states and the unreachable-API panel, the navigation in both
  directions, and that no API address appeared in any served page or client script.

  **The PostgreSQL integration tests have now been run locally**, for the first time in this
  repository's history — the verification ADR-021 recorded as outstanding is discharged. Docker
  Compose works since [the first local run](../deployment/docker.md#first-local-run-2026-08-08), so a
  disposable `learnflow_test` database was created beside the development one and the whole suite ran
  green: **923 passed, none skipped**. The revision half arrives with the records that have it, so the
  item stays open.

  **Skipping is covered on four levels**, one more than completion: the settled boundary is a pure
  domain test beside the overdue ones, and use-case, API, and PostgreSQL integration tests sit above
  it. They assert that skipping moves no other row, that a skip clears `completed_at`, that a skip
  whose day has passed is never written `postponed`, and that a skipped topic is planned again where a
  completed one is not. The frontend tests assert the control on all three screens, that a skipped
  item keeps its place and its reason, that it leaves *From earlier days*, and that nothing counts
  skips. Contracted by [ADR-024](../adr/ADR-024-plan-item-skipping.md).

  **Postponement is covered on the same four levels**, sharing the settled boundary with skipping. The
  use-case, API, and PostgreSQL integration tests assert that a learner may walk all four statuses in
  any direction, that postponing clears `completed_at`, re-dates nothing, and moves no other row, that
  a postponement whose day has passed is never re-marked by adaptation **nor reported in**
  `postponed_plan_item_ids`, and that its topic is planned again. The frontend tests assert the third
  control on all three screens, that a postponed item keeps its place, its day, and its reason, that it
  leaves *From earlier days*, that an unrecognised status does not, and that nothing counts
  postponements. **The scriptless standalone-frontend run was performed** — the one every planner
  change since ADR-015 has carried, and which mattered here because the control's rendered shape
  changed again, from two forms per item to three. **Sixty-one checks passed**, covering the three
  targets on every screen, a no-JavaScript postponement reaching PLN-004 exactly once with only
  `{"status":"postponed"}` and no date, the postponed item leaving *From earlier days*, the `409` for
  a superseded plan, adaptation reporting neither settled item as carried forward, and no API address
  in any served HTML or client script. Contracted by
  [ADR-025](../adr/ADR-025-learner-postponement.md).

  **The monthly study view is covered at the frontend level only**, which is where all of it lives, as
  the daily view is: unit tests over the month conversion at a fixed instant across zones and its UTC
  fallback, over the month boundaries including both Gregorian century rules, and over the selection
  including a week that straddles a month boundary; and a component test asserting that every item
  shows its reason, that a settled item keeps its place and is marked in words, that **no button of
  any kind is rendered** — the screen is read-only by decision — that nothing is counted, and that no
  copy describes the learner rather than an item or the plan. No backend test changed, because no
  backend code did. **The scriptless standalone-frontend run was performed** against a
  contract-shaped stub API with the server on `TZ=UTC`. Contracted by
  [ADR-026](../adr/ADR-026-monthly-study-view.md).

## Milestone 4 — Resources, RAG, and Mentor

**Outcome:** learner-owned GATE CSE notes become usable, grounded mentor context.

### Definition of Done

- [ ] Learner can register/link supported local resources to topics.
- [ ] Supported text-based PDF can be extracted and indexed.
- [ ] Ingestion shows queued/processing/completed/failed status.
- [ ] Mentor retrieves authorized relevant excerpts before grounded answers.
- [ ] Mentor response shows useful source references when retrieval succeeds.
- [ ] No-source and provider-unavailable states are honest and understandable.
- [ ] Original files, resource metadata, and derived vectors are stored separately.
- [ ] Retrieval is tested with representative GATE CSE resources/queries.

## Milestone 5 — Quiz and External Test Evidence

**Outcome:** practice and learner-entered test results improve recommendations transparently.

### Definition of Done

- [ ] Learner can generate/select a topic checkpoint quiz.
- [ ] Learner can submit answers and receive objective scoring where supported.
- [ ] Quiz attempts, feedback, and mistakes are stored.
- [ ] Learner can manually enter external test result data and optional private reference attachment.
- [ ] Subject/topic evidence is recorded only when the learner/test report provides it.
- [ ] Progress/revision recommendations incorporate evidence without claiming permanent mastery.
- [ ] No external test-platform scraping, login sharing, or direct integration exists.
- [ ] Assessment flows have API/domain/persistence tests.

## Milestone 6 — Daily-Use Hardening

**Outcome:** the local mentor is dependable enough for regular personal study.

### Definition of Done

- [ ] Critical domain/application/API tests run reliably.
- [ ] Errors, logging, and health/readiness behavior are documented and tested where practical.
- [ ] Database/resource backup and restore instructions are documented.
- [ ] `.env.example`, `.gitignore`, Docker setup, and README are validated.
- [x] CI configuration runs the checks enumerated in [CI/CD strategy](../deployment/ci-cd.md) on pull requests and pushes to `main` (`.github/workflows/pull-request.yml`), covering documentation, lint, backend tests, database migrations, and the container build. The Python checks were verified locally when they were added; the container checks as they then stood — topology validation and the backend image build — were verified in CI, where they first ran and passed on pull request #7, and the frontend image build joined them later; the database checks run only in CI, because that workstation has no PostgreSQL.
- [x] CI also covers frontend checks, once that artifact exists. The `frontend` job runs `npm ci`,
  ESLint, `tsc --noEmit`, Vitest, and the production build on Node 24, and the `containers` job now
  builds the frontend image too. All five `frontend` job commands were verified locally before they
  were added; see [CI/CD strategy](../deployment/ci-cd.md#the-frontend-job). The image build could
  not be verified locally, because Docker is not installed on that workstation, and was verified in
  CI instead — run `30850601752` on pull request #13; see
  [Docker strategy](../deployment/docker.md#verification-status), which holds the evidence and its
  limits.
- [ ] Major learner workflows have loading, empty, error, and success states.
- [ ] Known limitations are documented rather than hidden.

## Milestone 7 — Expansion Readiness

**Outcome:** future expansion decisions are made from real usage evidence, not assumptions.

### Definition of Done

- [ ] Local GATE CSE workflow has been used long enough to identify genuine pain points.
- [ ] Deferred ideas are reviewed against usage evidence and roadmap priorities.
- [ ] Multi-user/cloud/mobile/other-program work has explicit requirements and ADRs before implementation.
- [ ] Any provider/storage/agent-framework change has a data migration and compatibility plan.

## Milestone Review Rules

- Review one milestone at a time; do not start a later milestone merely because it is interesting.
- A checklist item is complete only with evidence: working behavior, passing test, reviewed documentation, or demonstrated setup.
- If a new idea does not support the current milestone, add it to `future-ideas.md`.
- Commit milestone completion in a clear Git change and optionally tag a usable release.

## Related Documents

- [Project context](../00-project-context.md)
- [Roadmap](roadmap.md)
- [MVP scope](../requirements/mvp.md)
- [Git workflow](../development/git-workflow.md)
- [CI/CD strategy](../deployment/ci-cd.md) — what CI verifies today and what remains pending
- [Docker strategy](../deployment/docker.md) — which Compose services exist today
- [Database migrations](../database/migrations.md) — the migrations applied so far and the seeds that fill them
- [Database schema](../database/schema.md) — which schema areas exist today
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — why part of Milestone 2's schema arrived in Milestone 1
- [ADR-015: Build the frontend on Next.js and reach the API from the server](../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the frontend decisions behind the items above, including the loading-boundary rule
- [ADR-016: Fix the learner setup API contracts](../adr/ADR-016-learner-onboarding-api-contracts.md) — the contracts behind the learner setup items in Milestone 2
- [ADR-017: Record manual topic progress as a learner-owned stage](../adr/ADR-017-topic-progress-api-and-schema.md) — the contracts and the migration behind the progress items in Milestone 2
- [ADR-018: Store weekly availability as named days replaced a week at a time](../adr/ADR-018-weekly-availability-slots.md) — the contract and the migration behind the weekly availability item in Milestone 2
- [ADR-019: Store planning preferences as typed columns replaced as a group](../adr/ADR-019-study-goal-planning-preferences.md) — the contract and the migration behind the planning-preference half of the same item
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](../adr/ADR-020-initial-study-plan-generation.md) — the contracts, the migration, and the planning rules behind the Milestone 3 items delivered early
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](../adr/ADR-021-plan-item-completion.md) — the contract behind the completion half of the plan-item item above, and why skipping and postponing wait
- [ADR-022: Adapt a study plan by rebuilding it around what happened](../adr/ADR-022-plan-adaptation.md) — the contract behind the adaptation item above, and the first write of `postponed`
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](../adr/ADR-023-daily-study-view.md) — the daily half of the plan-views item above, and why a `daily` plan type stays unwritten
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](../adr/ADR-024-plan-item-skipping.md) — the second of the three verbs in the complete/skip/postpone item above
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](../adr/ADR-025-learner-postponement.md) — the third verb, which closes that item, and the two verifications it records as outstanding
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](../adr/ADR-026-monthly-study-view.md) — the monthly half of the plan-views item above, which completes FR-003's second criterion, and why a `monthly` plan type stays unwritten
- [Deferred ideas](future-ideas.md)
