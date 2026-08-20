---
title: LearnFlow Delivery Milestones
status: approved
owner: product-and-architecture
last_updated: 2026-08-20
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
  - ../adr/ADR-027-plan-feasibility.md
  - ../adr/ADR-028-revision-workflow.md
  - ../adr/ADR-029-progress-overview.md
  - ../adr/ADR-030-learning-stages-by-subject-panel.md
  - ../adr/ADR-031-priority-focus-panel.md
  - ../adr/ADR-032-learning-resource-catalogue.md
  - ../adr/ADR-033-checkpoint-practice-workflow.md
  - ../adr/ADR-034-checkpoint-practice-history.md
  - ../adr/ADR-035-practice-question-correction.md
  - ../adr/ADR-036-topic-material-on-the-plan-screens.md
  - ../adr/ADR-037-learner-written-resource-notes.md
  - ../adr/ADR-038-local-topic-note-retrieval.md
  - ../adr/ADR-039-source-grounded-study-answers.md
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
`learner_topic_progress`. A **progress overview** has since joined them at `/progress`, gathering
what the learner's plan covers, what today holds, whether their saved week reaches their date, what
they have marked, and which topics are ready to review — built as a *reading* of six existing
contracts, so it needed no endpoint and no migration, and it writes and counts nothing. Contracted by
[ADR-029](../adr/ADR-029-progress-overview.md). It has since gained a panel gathering the recorded
learning stages under the subject each topic belongs to, joining PRG-002 to CUR-003 in the client and
listing them rather than counting them, recorded in
[ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md). It now leads with a **priority focus**
panel as well, gathering three facts backend rules already decided — work whose day has passed,
reviews reported as due, and a saved week that falls short — with the reason each entry is there and
**no ranking of any kind**, proposed in
[ADR-031](../adr/ADR-031-priority-focus-panel.md). Material status, study activities, and the quiz,
test, and mistake evidence a fuller priority focus would draw on are what remain.

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
- [ ] Progress overview shows subject/topic progress and priority focus areas. **A progress overview
  screen now exists**, at `/progress`, gathering where a learner's study stands from six existing
  reads — LRN-001, GOAL-002, PLN-002, PLN-003, PLN-006, and REV-001. It is a **reading**, so it
  needed no endpoint, no column, no migration, and no backend change at all, which is the shape
  [ADR-026](../adr/ADR-026-monthly-study-view.md) used for the monthly view. **It writes nothing and
  counts nothing of its own**: the only figures on it are ones the API reported, because
  [terminology](../domain/terminology.md) forbids counting skips, postponements, and reviews by name,
  so what a learner has marked is listed rather than tallied. Contracted by
  [ADR-029](../adr/ADR-029-progress-overview.md).
  **The first of this item's two counts is now met**, and the screen now reads **eight** contracts
  rather than the six named above. *Subject/topic progress* **is** gathered: the
  overview lists the learning stages the learner recorded under the subject each topic belongs to, by
  joining PRG-002 to CUR-003 in the client — the join the curriculum view already performs, read the
  other way round — so it needed no endpoint, no column, no migration, and no backend change either.
  The panel **lists and never counts**: no figure beside a subject, no percentage of a subject
  recorded, and no ordering, grouping, or colouring by stage, because a learner may move to any stage
  from any stage. It **writes nothing**; recording a stage stays beside the topic in the curriculum
  view, which it links to. What is gathered is the *learning stage* alone, since `material_status` is
  not created and `study_activities` does not exist. Recorded in
  [ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md).
  **The item's second count is now partly met.** *Priority focus areas* **are** built, at the head of
  the same screen and as a third reading that adds no read at all: the panel gathers work whose day
  has passed with nothing said about it, reviews REV-001 reports as due, and a saved week PLN-006 says
  does not reach the horizon — three facts a **backend rule already decided** — and gives the reason
  each entry is there, in the sentence the record itself carries. **It ranks nothing**: its groups sit
  in a fixed presentation order that orders nothing, no entry is numbered or capped, and the recorded
  *learning stage* is deliberately not a signal, because selecting some of the five stages would rank
  them against each other. It writes nothing and counts nothing, as the rest of the screen does not.
  Contracted by [ADR-031](../adr/ADR-031-priority-focus-panel.md).
  **The item stays open** because the priority focus is drawn only from the evidence LearnFlow stores:
  no external test result or mistake evidence exists to draw one from, and the quiz outcomes that now exist are deliberately not a signal: nothing ranks or reads them, and material
  status and study activity are still not stored either. **PRG-001 is therefore still not
  implemented**, and now waits on that quiz, test, and mistake evidence alone. **FR-011 is not met in
  full** — two of its four acceptance criteria are met and a third is partly met, and
  [endpoints.md](../api/endpoints.md#prg-001-prg-003-act-001-and-act-002-not-implemented) carries
  the breakdown.
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
**Saying whether a learner's week can reach their horizon has since been delivered too**, over
PLN-006 and a fourth domain rule, which closes FR-004 in full. **Revision has now arrived as well**,
over REV-001 to REV-004, `revision_records`, and a second domain module — which delivers the built
part of [FR-006](../requirements/functional.md#fr-006-revision-guidance): revision scheduling, status
updates, and a view of what is due. It is the last of this milestone's requirements to be started.
**FR-006 is not met in full** — the resource-and-practice half of its second criterion is deferred to
FR-007 and FR-009, which do not exist, and its fourth criterion considers three of its four inputs
because no quiz or test evidence is stored. What remains of this milestone is a generated `monthly` or `daily` **plan**,
which keeps the plan-views item below open even though all four levels are now viewable.

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
  and carries `action_type = 'study'`; `practice` and `review_mistakes` are constrained and unwritten,
  each waiting on the work it names — checkpoint quizzes and mistake evidence. **`revise` is
  different**: `revision_records` now exists, and [ADR-028](../adr/ADR-028-revision-workflow.md)
  decides a revision is *not* a plan item, so that value stays unwritten permanently.
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
  learner's week cannot reach their horizon — has since been built, over PLN-006; see the
  insufficient-time item below.
- [x] Revision records are generated, listed, and updateable by learner action. **Done**: REV-004
  schedules revisions for topics the learner completed planned work on, REV-001 and REV-002 read them
  back, and REV-003 records what became of each — `completed`, `skipped`, `postponed`, or back to
  `due`, every move reversible. `revision_records` arrives in migration `20260813_01`, the first
  migration since `20260806_03`, creating one table and one index and altering nothing.
  **The learner asks; nothing schedules on its own**, and asking twice creates nothing the second
  time. A topic returns an interval after the work it follows, decided by the **learning stage the
  learner recorded** — LearnFlow's own intervals, named as its own — and a **completed review
  schedules the next**, which is FR-006's *prior revision history*. A revision is **not a plan item**:
  it survives the supersede adaptation performs on every active plan, and `action_type = 'revise'`
  stays unwritten. **Nothing writes a learning stage.** The screen is `/revisions`. This item is
  complete, but **FR-006 is not met in full**: the resource-and-practice half of its second criterion
  is deferred to FR-007 and FR-009, which do not exist. Contracted by
  [ADR-028](../adr/ADR-028-revision-workflow.md).
- [x] Planning works with deterministic rules when Ollama is unavailable. No AI provider is involved
  at all: the same goal, curriculum, week, preferences, and date produce the same plan every time, and
  the two rules that decide it — topic order and session placement — are pure functions in
  `backend/app/domain/study_planning.py`.
- [x] Insufficient-time trade-offs are visible rather than hidden. **Done**: PLN-006 reports whether
  the study time the learner saved covers the work left before their horizon, and `/plan` shows the
  verdict, the figures behind it, and — when time is short — how many topics that time does cover and
  what the learner could change. The arithmetic is a **pure domain rule**, `assess_horizon_coverage`,
  the fourth in `backend/app/domain/study_planning.py`: one session per remaining topic against the
  minutes the saved week offers between today and the horizon, both ends included. **It is a live read
  and writes nothing**, so the answer moves when the learner's week does. `unknown` is an answer, with
  its reason naming whether a date or a week is missing; a week saved and deliberately kept free is
  zero minutes rather than unknown. Everything is reported as **counts and durations, never a ratio**.
  It needed **no migration**. That closes **FR-004's third acceptance criterion**, so **all three of
  FR-004's criteria are now met**. Contracted by
  [ADR-027](../adr/ADR-027-plan-feasibility.md).
- [x] Core planning/revision rules have deterministic tests. **Covered for planning**: unit tests over
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
  green: **923 passed, none skipped**. The revision half has since arrived; see the revision coverage below.

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

  **Plan feasibility is covered on four levels**, the deepest of the planning features: pure domain
  tests over `assess_horizon_coverage` — the span boundaries, a horizon that has passed, a week kept
  entirely free, the flooring of a partial session, and an assertion that counting by weekday equals
  walking the days one by one over a six-month horizon — use-case tests against fakes with a fixed
  clock, API tests over the real application factory, and PostgreSQL integration tests over the
  seeded GATE CSE curriculum asserting 60 remaining topics. Three of those levels assert the
  **read-only** guarantee directly: asking twice moves no stored row, and the endpoint refuses a
  write method. The frontend tests cover the three verdicts, both unknown reasons, that the panel
  renders no control, and that no percentage or fraction appears. **The scriptless
  standalone-frontend run was performed** against a contract-shaped stub API with the server on
  `TZ=UTC`: **54 checks passed**, covering the three verdicts, both unknown states with their
  distinct next steps, the absence of any control in the panel, the absence of a percentage, a
  fraction, a `<progress>`, or a `<meter>`, that rendering the panel issued only `GET` requests and
  never reached PLN-001, PLN-004, or PLN-005, that the existing generate, adapt, and item controls
  are untouched, and that no API address appeared in any served page or client script. Contracted by
  [ADR-027](../adr/ADR-027-plan-feasibility.md).

  **Revision is covered on five levels**, one more than any planning change: pure domain tests over
  the intervals, the due-date arithmetic across month, year, and leap-day boundaries, and the three
  due boundaries; use-case tests against fakes with a fixed clock, asserting that asking twice creates
  nothing, that a completed review schedules the next, that a skipped or postponed one is left alone,
  that nothing else moves, and that no wording describes the learner; API contract tests over the real
  application factory for all four endpoints; **PostgreSQL integration tests over migration
  `20260813_01`**, its upgrade, its downgrade, every documented status and trigger, the constraints it
  refuses, and the index it creates; and frontend tests over the list, the control, the form parsing,
  and the API client. Contracted by [ADR-028](../adr/ADR-028-revision-workflow.md).

## Milestone 4 — Resources, RAG, and Mentor

**Outcome:** learner-owned GATE CSE notes become usable, grounded mentor context.

This milestone has been **opened** by the learning-resource catalogue: a learner can record where
their own study material is and which topics it covers, and find it again from the curriculum, from
a review, and from the plan items that name its topic. It has since gained the **first RAG
foundation**: a learner can keep their **own written notes and copied-out passages** against a piece
of that material, which is the first study material LearnFlow stores rather than points at. That is
**storage and nothing else** — no upload, no fetch, no extraction, no chunking, no embedding, and
no mentor — and it is **contracted by**
[ADR-037](../adr/ADR-037-learner-written-resource-notes.md) with migration `20260819_01`. Those
notes have since become **searchable**: a learner picks a topic and sees passages from them,
found by PostgreSQL full-text search running locally and only when they ask, which is the third
item below. Contracted by [ADR-038](../adr/ADR-038-local-topic-note-retrieval.md). **The mentor has
since arrived, narrowly**: a learner asks a question about one topic and receives an answer built
**only** from those passages, through a **locally running** AI provider — asked at all only where
retrieval found something, so LearnFlow never answers from a model's own training. Nothing is
stored, no credential exists, and suggested next actions are deliberately unbuilt. Contracted by
[ADR-039](../adr/ADR-039-source-grounded-study-answers.md). Those are the first items below, and
deliberately no more of the milestone — nothing is uploaded, extracted, chunked, embedded, or
vector-indexed. It also supplies the **resource
half** of [FR-006](../requirements/functional.md#fr-006-revision-guidance)'s second criterion, which
[ADR-028](../adr/ADR-028-revision-workflow.md) deferred; the practice half still waits on FR-009, so
**FR-006 is still not met in full**. Contracted by
[ADR-032](../adr/ADR-032-learning-resource-catalogue.md), with migration `20260816_01` creating
`resources` and `resource_topic_links`, and extended to `/plan` and `/plan/today` by
[ADR-036](../adr/ADR-036-topic-material-on-the-plan-screens.md), which amends ADR-032's
plan-screens-untouched sentence and needs no migration, endpoint, or backend change at all.

### Definition of Done

- [ ] Learner can register/link supported local resources to topics. **Registering and linking are
  done**: RES-001 to RES-004 record a title, a kind, where the material is, and the topics it covers,
  and `/resources` supports **add, edit, and archive** while the curriculum view, `/revisions`,
  `/plan`, and `/plan/today` show a topic's material read-only and link there for every change.
  `/plan/month` deliberately does not, because the month's value is its shape. Material put aside is read-only until it is put back. A resource may cover **any** topic, including a heading that groups subtopics, which is
  where this differs from the learning-stage control. **Nothing is recommended, ranked, or counted**,
  and **nothing is deleted** — material is put aside reversibly, so RES-005 stays unimplemented.
  **The item stays open on the word *local***: `external_reference` accepts an `http` or `https`
  address alone, because [endpoints.md](../api/endpoints.md#resource-and-ingestion-endpoints)
  forbids a resource endpoint returning an absolute local filesystem path, and material that is not
  on the web is described in the learner's own words instead. A **path** to a local file arrives with
  the storage change below, which gives a file somewhere to live and an opaque `storage_key` to name
  it. **FR-007 is not met in full**;
  [endpoints.md](../api/endpoints.md#fr-007-acceptance-criteria) carries the count.
- [ ] **A learner can keep their own written notes against a piece of material.** **Done**, by
  RES-009 to RES-012 with migration `20260819_01`: a learner writes or pastes their own notes and
  copied-out passages against a catalogued resource, corrects them in place, and puts them aside
  reversibly, all on `/resources`. This is the **first study material LearnFlow stores rather than points
  at** and the **first RAG foundation** — and it is **storage and nothing else**: nothing uploads,
  downloads, fetches an address, extracts, chunks, embeds, indexes, searches *(narrowed by the item
  below: a local topic search reads a note when the learner asks)*, ranks, recommends, or
  answers a question, and no AI, embedding, or retrieval provider is reached or configured. It
  **narrows** [ADR-032](../adr/ADR-032-learning-resource-catalogue.md)'s *metadata, never the
  material* rule on one point and leaves the rest standing: no file, no fetched page, and no location
  on the learner's own machine. Text is stored **exactly as written**, rendered as **plain text**, and
  **never deleted**. It adds a table beyond the approved schema, `resource_notes`, for the reason
  [the area review](../database/schema.md#resources-and-rag-metadata-area-second-partial-review-2026-08-19)
  records. **FR-007's four criteria are unchanged**; FR-008's count has since moved and is carried by
  [endpoints.md](../api/endpoints.md#fr-008-acceptance-criteria). Contracted by
  [ADR-037](../adr/ADR-037-learner-written-resource-notes.md).
- [ ] **A learner can find passages in their own notes for a topic.** **Done**, by RES-013 with
  migration `20260820_01`: the learner chooses a curriculum topic at `/resources/search` and sees
  passages from their own active notes on material they linked to it, each named with its note,
  material, and topic context. This is the **first retrieval in LearnFlow**, and it is **retrieval
  alone** — nothing is generated, summarised, or explained, and **no AI model, embedding service, or
  vector database is reached or configured**; the search is PostgreSQL's own full-text search,
  running locally and **only when the learner asks**. It **narrows**
  [ADR-037](../adr/ADR-037-learner-written-resource-notes.md)'s *nothing reads a note* promise on one
  point while leaving its correction argument intact, because nothing derived from a note is stored.
  The migration creates **one index and no column**. Contracted by
  [ADR-038](../adr/ADR-038-local-topic-note-retrieval.md).
- [x] A learner asks a question about a topic and receives an answer grounded in their own notes,
  with the passages it used shown beneath it (MNT-001). The screen is called **Ask your notes**;
  *mentor* names the service and the route, because only one of the Mentor Service's four
  responsibilities is built. **The provider is asked only where retrieval
  found something**; with nothing found, no prompt is composed and no request leaves the process.
  Only the question, the topic and subject names, and at most eight passages are sent — no
  identifier, no title, no whole note, and nothing about the learner's plan, progress, revisions, or
  practice. The provider is **Ollama running locally**, so **no API key, account, or billing
  exists**. **Nothing is stored**, so there is no migration. **FR-008 is not met in full**: five of
  its six criteria are met and the third is partly met, because suggested next actions are
  deliberately unbuilt and retrieval covers the learner's own notes alone;
  [endpoints.md](../api/endpoints.md#fr-008-acceptance-criteria) carries the count. Contracted by
  [ADR-039](../adr/ADR-039-source-grounded-study-answers.md).
- [ ] Supported text-based PDF can be extracted and indexed. **Still unbuilt**, and the note item
  above deliberately does not begin it: a note needs no file storage, no extractor, no chunking
  policy, no embedding provider, and no vector store, and none of the five exists.
- [ ] Ingestion shows queued/processing/completed/failed status. `resource_ingestions` is not
  created, and `resources.status` therefore permits neither `processing`, `ready`, nor `failed`: a
  resource could enter one and never leave it.
- [x] Mentor retrieves authorized relevant excerpts before grounded answers. RES-013 retrieves,
  filtered by learner ownership, topic linkage, and status, and MNT-001 generates **only** on the
  branch where it found something. Met over the learner's own notes; **no ingested resource is
  retrieved**, because none exists.
- [x] Mentor response shows useful source references when retrieval succeeds. `passages` names the
  note, material, and topic behind every extract the answer was built from — recorded from what was
  **sent**, never parsed out of the prose, so an answer cannot cite a note that was not consulted.
- [x] No-source and provider-unavailable states are honest and understandable. Three no-source
  outcomes are told apart, each naming a different next step, and **no model is asked on any of
  them**; three provider failures are told apart and **keep the retrieved passages**, because a
  provider that is switched off must not cost the learner the reading of their own notes.
- [ ] Original files, resource metadata, and derived vectors are stored separately. **No file and
  no vector is stored**, which is what this item is really about. Metadata is stored, and so now
  is the text a learner typed themselves — a *resource note* is neither a file nor a derived
  representation of one, so it separates from nothing: `storage_key` and `metadata` are not created, and nothing
  holds a file or a vector, so the separation is not yet tested by anything.
- [ ] Retrieval is tested with representative GATE CSE resources/queries.
- [ ] Catalogue behaviour has API/domain/persistence/frontend tests. **Done for the catalogue**:
  use-case tests against fakes, API contract tests over the real application factory, PostgreSQL
  integration tests over migration `20260816_01` — its upgrade, its downgrade, every permitted type,
  status, and link role, the constraints it refuses, its foreign keys, and both indexes — and the
  catalogue read back over HTTP against the seeded GATE CSE curriculum; plus frontend tests over the
  catalogue, the per-topic list, the form parsing, the topic grouping, and the API client. There is
  deliberately **no domain-level test**: nothing here is a planning or scheduling calculation, and
  `backend/app/domain/` is untouched. **The item stays open** for the rest of this milestone: no
  extraction, ingestion, or retrieval exists to test.

## Milestone 5 — Quiz and External Test Evidence

**Outcome:** practice and learner-entered test results improve recommendations transparently.

This milestone has been **opened** by checkpoint practice: a learner can write their own practice
questions, take a quiz assembled from them, and read an honest per-question result. That is the first
two items below, and deliberately no more of the milestone — no external test result can be entered,
no mistake is stored, and nothing incorporates quiz evidence into a recommendation. Contracted by
[ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md), with migration `20260818_01` creating the
whole *Assessment* schema area.

The **checkpoint practice history** since joined it: `/practice/history` shows every quiz a learner
has taken, a page at a time, with what became of each question, and opens each attempt's existing
result. It is a **reading** of QZ-006, opening the QZ-007 result view ADR-033 already built — no
endpoint, no column, no migration, and no backend change — and it **checks no further box here**: nothing is stored, marked, or incorporated by
it. **Nothing is counted, scored, or compared** on it, and the pages are not numbered. Contracted by
[ADR-034](../adr/ADR-034-checkpoint-practice-history.md).

A learner may also **correct a question until a quiz has asked it**, and sets it aside afterwards —
[ADR-035](../adr/ADR-035-practice-question-correction.md), which amends
[ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md) on that one point and needs **no endpoint,
column, table, or migration**. A question already set aside is **read-only until it is brought back**.
**No past result changes**, because only a question nothing references can be corrected. It **checks no further box here** either.

**No question content ships with LearnFlow.** The learner writes every question, which is the position
[ADR-032](../adr/ADR-032-learning-resource-catalogue.md) took for study material: no seed, no data
file, no bundled previous-year paper, and no external fetch, so no third-party licensing question
arises. `generated` waits on an AI provider; `verified_pyq` waits on a licensing position nobody has
taken.

### Definition of Done

- [x] Learner can generate/select a topic checkpoint quiz. **Done**, over QZ-001 with QZ-008 to
  QZ-010 behind it: the learner writes questions against topics, and a quiz asks **every** ready
  question for the topics they choose, in the order they wrote them. **Deterministic, with no AI
  provider** — the same topics over the same bank always give the same quiz. LearnFlow selects none
  and leaves none out, because choosing which few to ask is a ranking, so *short* is the learner's
  own decision. A quiz naming no topic is refused, which is
  [ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md)'s rule.
- [x] Learner can submit answers and receive objective scoring where supported. **Done**, over
  QZ-003, QZ-005, and QZ-007, and **with no score**: every objective answer is marked correct or not
  correct by a pure domain rule, and the result states those outcomes per question with the expected
  answer and the explanation. There is no total, no mark, and no percentage — the conflict between
  [terminology](../domain/terminology.md) and [schema.md](../database/schema.md), resolved in
  terminology's favour. **An unanswered question is not a wrong one.** QZ-004 is not implemented: a
  learner submits the whole attempt in one form post, which works with no JavaScript.
- [ ] Quiz attempts, feedback, and mistakes are stored. **Attempts and answers are stored.** The feedback a
  learner reads is the explanation held on the question itself, which is why no
  `quiz_attempt_answers.feedback` column exists: a question a quiz has asked is never edited, so its
  explanation cannot drift from an attempt marked against it, and one no quiz has asked has no
  attempt to drift from. **The item stays open on the word
  *mistakes***: `mistake_evidence` has four discovery-source foreign keys of which two reference
  `external_test_results` and `study_activities`, neither of which exists, so it cannot be created
  until they are. It arrives with FR-010, below.
- [ ] Learner can manually enter external test result data and optional private reference attachment.
- [ ] Subject/topic evidence is recorded only when the learner/test report provides it.
- [ ] Progress/revision recommendations incorporate evidence without claiming permanent mastery.
  **Nothing incorporates quiz evidence yet, deliberately**: a quiz writes no learning stage, no plan,
  no plan item, and no revision, which is FR-005's and FR-009's shared rule. PRG-001 still waits on
  the stored mistake evidence above.
- [x] No external test-platform scraping, login sharing, or direct integration exists. **Holds**, and
  nothing in this milestone's first half reaches any network at all.
- [ ] Assessment flows have API/domain/persistence tests. **Done for checkpoint practice**:
  domain-rule tests over the pure marking module, use-case tests against fakes, API contract tests
  over the real application factory — including that QZ-002 never sends an expected answer and that
  no response carries a score — PostgreSQL integration tests over migration `20260818_01`, its
  upgrade, its downgrade, every permitted value, the constraints it refuses, and the columns it
  deliberately does not create, plus the workflow read back over HTTP against the seeded GATE CSE
  curriculum; and frontend tests over the forms, the question bank, the quiz, the result, the
  practice screen's own attempt panel, and the **checkpoint practice history** — its paging rules as
  pure functions, and the screen's refusal of a score, a count, a page number, and a control.
  **The item stays open** for the external-evidence half.

**FR-009 is not met in full**; [endpoints.md](../api/endpoints.md#fr-009-acceptance-criteria) carries
the count. **FR-006 is still not met in full** either: its second criterion wants practice
suggestions on a revision, and surfacing a quiz there would mean recommending one, which nothing in
LearnFlow does.

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
- [ADR-027: Report whether the saved week reaches the horizon, as a read-only planning rule](../adr/ADR-027-plan-feasibility.md) — the trade-off item above, which closes FR-004's last criterion
- [Deferred ideas](future-ideas.md)
- [ADR-028: Schedule revisions from finished work, on the learner's ask](../adr/ADR-028-revision-workflow.md) — the revision item this closes, and Milestone 3's last unbuilt requirement
- [ADR-029: Show the progress overview as a reading of what is stored, counting nothing of its own](../adr/ADR-029-progress-overview.md) — the Milestone 2 progress-overview item this advances, and the two counts on which it stays open
- [ADR-030: Gather the recorded learning stages by subject, listing them rather than counting them](../adr/ADR-030-learning-stages-by-subject-panel.md) — the first of those two counts, now met, and why the second stayed open
- [ADR-031: Draw priority focus from facts backend rules already decided, ranking nothing](../adr/ADR-031-priority-focus-panel.md) — the second count, now partly met, and the evidence the item still waits on
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](../adr/ADR-032-learning-resource-catalogue.md) — the Milestone 4 item this opens, and the reasons the rest of that milestone stays closed
- [ADR-036: Show a topic's material beside the plan items that name it, read-only](../adr/ADR-036-topic-material-on-the-plan-screens.md) — the two plan screens that now show catalogued material, and the one deliberately left without it
- [ADR-033: Assemble checkpoint practice from the learner's own questions, and report outcomes rather than a score](../adr/ADR-033-checkpoint-practice-workflow.md) — the two Milestone 5 items this opens, and the reasons the rest of that milestone stays closed
- [ADR-034: Show the checkpoint-practice history as a paged reading of stored attempts, counting nothing](../adr/ADR-034-checkpoint-practice-history.md) — the history screen over those two items, which checks no further box here
- [ADR-035: Let a practice question be corrected until a quiz has asked it](../adr/ADR-035-practice-question-correction.md) — the correction rule over the same two items, which checks no further box either
