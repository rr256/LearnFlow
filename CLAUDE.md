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
python -m app.main                              # serve on API_HOST / API_PORT
python -m uvicorn app.main:app --reload         # reload workflow (own --host/--port)
python -m alembic upgrade head                  # apply the database schema
python -m scripts.seed_curriculum               # load the curated curriculum, idempotently
python -m scripts.seed_examination_schedule     # load the published examination schedule
python -m scripts.set_study_goal                # bind the local learner to both
```

Tests, lint, and formatting are part of the repository check set below.

Database — PostgreSQL through SQLAlchemy and Alembic. `DATABASE_URL` is required and has no default.
Migrations are never applied automatically, by startup or by a container entrypoint. The schema is
migrated one area per milestone; the curriculum tables, the examination schedule tables, `learners`
and `study_goals` — including its two planning-preference columns — `learner_topic_progress`,
`availability_slots`, `study_plans`, and `plan_items` exist today, which completes the
learner-planning area, `revision_records` arrives with `20260813_01` — the first migration since
`20260806_03`, creating one table and one index and altering nothing — and `resources` and
`resource_topic_links` arrive with `20260816_01`, the first two tables of the resource area,
creating two tables and two indexes and altering nothing. Curated content is loaded by idempotent seeds, not by
migrations — each matches records on a natural key and never deletes, so both are safe to repeat.
Run them in the order above; each refuses to run ahead of its predecessor. See
[`docs/database/migrations.md`](docs/database/migrations.md).

An examination is stored as a dated **window**, never as a single guessed date, and a published
schedule keeps its source and its `provisional`/`confirmed` status. See
[`docs/adr/ADR-013-examination-schedule-and-study-goal.md`](docs/adr/ADR-013-examination-schedule-and-study-goal.md).

The learner and study-goal endpoints are contracted by
[`docs/adr/ADR-016-learner-onboarding-api-contracts.md`](docs/adr/ADR-016-learner-onboarding-api-contracts.md),
weekly availability by
[`docs/adr/ADR-018-weekly-availability-slots.md`](docs/adr/ADR-018-weekly-availability-slots.md),
planning preferences by
[`docs/adr/ADR-019-study-goal-planning-preferences.md`](docs/adr/ADR-019-study-goal-planning-preferences.md),
the topic-progress endpoints by
[`docs/adr/ADR-017-topic-progress-api-and-schema.md`](docs/adr/ADR-017-topic-progress-api-and-schema.md),
study-plan generation by
[`docs/adr/ADR-020-initial-study-plan-generation.md`](docs/adr/ADR-020-initial-study-plan-generation.md),
plan-item completion by
[`docs/adr/ADR-021-plan-item-completion.md`](docs/adr/ADR-021-plan-item-completion.md), plan
adaptation by [`docs/adr/ADR-022-plan-adaptation.md`](docs/adr/ADR-022-plan-adaptation.md), the
daily study view by
[`docs/adr/ADR-023-daily-study-view.md`](docs/adr/ADR-023-daily-study-view.md), and plan-item skipping
by [`docs/adr/ADR-024-plan-item-skipping.md`](docs/adr/ADR-024-plan-item-skipping.md), learner
postponement by
[`docs/adr/ADR-025-learner-postponement.md`](docs/adr/ADR-025-learner-postponement.md), and the
monthly study view by
[`docs/adr/ADR-026-monthly-study-view.md`](docs/adr/ADR-026-monthly-study-view.md), and plan
feasibility by [`docs/adr/ADR-027-plan-feasibility.md`](docs/adr/ADR-027-plan-feasibility.md), and the
revision workflow by [`docs/adr/ADR-028-revision-workflow.md`](docs/adr/ADR-028-revision-workflow.md) —
which is **accepted** — and the progress overview by
[`docs/adr/ADR-029-progress-overview.md`](docs/adr/ADR-029-progress-overview.md), and its
learning-stages-by-subject panel by
[`docs/adr/ADR-030-learning-stages-by-subject-panel.md`](docs/adr/ADR-030-learning-stages-by-subject-panel.md),
which changes no contract, and its priority-focus panel by
[`docs/adr/ADR-031-priority-focus-panel.md`](docs/adr/ADR-031-priority-focus-panel.md), which is
**accepted** and changes no contract either, and the learning-resource catalogue by
[`docs/adr/ADR-032-learning-resource-catalogue.md`](docs/adr/ADR-032-learning-resource-catalogue.md),
which is **accepted** and adds RES-001 to RES-004 with migration `20260816_01`.
No request accepts a `learner_id`; the effective learner is resolved server-side.

A **learning stage** is stored and sent as `snake_case` — `not_explored`, `building_foundation`,
`developing_confidence`, `practice_ready`, `strong_understanding` — and rendered from the labels in
[`docs/domain/terminology.md`](docs/domain/terminology.md). A topic with no record has no stage and
reads as *Not explored*; nothing creates a record on a learner's behalf, and there is no way to clear
one. Only a topic with `is_trackable` may hold a stage.

A **day of the week** is stored and sent as its `snake_case` name — `monday` to `sunday` — never as an
index; there is deliberately no numbering convention, because Python, JavaScript, and PostgreSQL
disagree about which day is zero. **Weekly availability** belongs to a study goal and is replaced a
week at a time: the days GOAL-005 names become the week, a day left out is removed, and an empty list
clears it. Zero minutes is a day deliberately kept free, which is not the same as a day with no row.
Nothing totals a week except the feasibility rule below — a plan places sessions on the days a week names and reports no total either.

A **planning preference** also belongs to a study goal, and is a session length
(`preferred_session_minutes`, 15 to 480) or a topic order (`topic_sequencing`, `syllabus_order` or
`prerequisites_first`). GOAL-001 and GOAL-004 accept them as one `planning_preferences` object and
every goal response carries it, always as an object whose members may be null. A supplied group
**replaces** the stored one, so a member left out of it is unset; omitting the field leaves the group
alone. A preference the learner has not set is `NULL`, never a default — nothing is invented on their
behalf. A session length is a duration, not a time of day. Nothing ranks or scores a preference.

A **study plan** is generated by PLN-001 from the goal, the curriculum, the saved week, the
preferences, and any recorded stages — **deterministically, with no AI provider**: the same inputs
produce the same plan. One generation writes a `roadmap` ordering every trackable topic across the
goal's horizon, and a `weekly` plan dating the first of them, when the learner's week has room. The
rules that decide a plan — topic order, session placement, and what makes an item overdue — are
pure functions in `backend/app/domain/study_planning.py`, the first of the domain layer's two
modules — `revision_scheduling.py` is the second. Generating again
**supersedes** the goal's active plans and keeps them; nothing is deleted, and a superseded plan's
content and reasons read back exactly as written — only an overdue item's `status` may move, to
`postponed`, when adaptation sets the plan aside. An unset session length becomes 60 minutes *chosen by the planner and named
as its own* — nothing is stored against the goal. A recorded stage explains an item and never reorders
one; `priority` is an order, not a score; and nothing totals a day, a week, or a plan — the sole
exception being the PLN-006 feasibility rule described below.
`prerequisites_first` currently yields syllabus order, because the curated curriculum stores no
prerequisite link, and the plan says so.

**PLN-004 records what became of one plan item** — `completed`, `skipped`, `postponed`, or
`planned`, in any direction. **All four values the column holds are things a learner may ask for**, so
FR-004's first acceptance criterion is now met **in full**; do not write that a learner cannot
postpone. **Nothing is one-way.** `completed_at` is read from the server's clock rather than accepted
from a caller and is cleared by any move off `completed`; there is deliberately **no `skipped_at`**,
**no `postponed_at`**, and no reason field for either.
**Only the named item moves**: no plan, no other item — including a roadmap item naming the same
topic — and no learning stage, because a plan item records whether planned work happened, not that a
topic is understood. Nothing is counted and nothing is re-planned. An item on a superseded plan is
refused with `409`, whatever status is asked for. It needed **no migration** any of the three times:
`plan_items.status` and `completed_at` were created ahead of it, and the `CHECK` has carried all four
values since `20260806_03`.

**Skipping and postponing settle the item, not the topic.** Neither is ever *overdue*, so adaptation
leaves each exactly as the learner left it rather than writing `postponed` over their statement — and
the **topic is planned again** either way, unlike a completed one, which is excluded from every plan
that follows. That difference is deliberate: a mark lives on the plan it was made on, so retiring the
topic would make it irreversible the moment the learner adapted. Both **stay in place** on both
`/plan` panels and in the daily view, marked in words, and are **left out of *From earlier days***.
Say a *skipped item*, never that a learner abandoned or gave up a topic, and never record or ask why
for either. **A skip says the work will not happen; a postponement says not yet** — a difference in
what the record states, not in what the next plan does with the topic. **Postponing moves nothing on
its own**: it takes no date, re-dates nothing, and triggers no adaptation. Contracted by
[`docs/adr/ADR-024-plan-item-skipping.md`](docs/adr/ADR-024-plan-item-skipping.md) and
[`docs/adr/ADR-025-learner-postponement.md`](docs/adr/ADR-025-learner-postponement.md).

**PLN-005 rebuilds a plan around what happened** — `POST /api/v1/study-goals/{study_goal_id}/adapt`,
which **departs from the catalogued** `/study-plans/{plan_id}/adapt` because adaptation supersedes and
rewrites every active plan of a goal. **The learner asks; nothing adapts on its own** — completing an
item re-plans nothing, saving a study week re-plans nothing, and postponing an item re-plans nothing.
A topic with a completed session anywhere on the goal is **not planned again**, the exclusion applied
before the ordering and placement rules run. Work whose day passed with nothing said about it is
marked **`postponed`** on the plan being set aside and re-placed on the new one — the answer to what
postponing moves work *to*, and the same status a learner writes through PLN-004.
`postponed_plan_item_ids` names only what **adaptation itself** set aside, never a learner's own
postponement. What counts as behind is a pure domain rule (`select_overdue`, over
`DatedItem.is_settled`): today is not behind, an undated roadmap item is never behind, and a
**settled** item — completed, skipped, or postponed — is never behind. It takes **no request
body**, refuses a goal with no active plan with `409`, and needed **no migration**.

**The daily study view is a reading of the weekly plan, not a `daily` plan** — `/plan/today`, which
adds **no endpoint, no column, and no migration**. It filters what PLN-003 already returns to one
date and moves items through PLN-004; a `daily` `plan_type` is still never written, and what one
*contains* is deliberately still undecided. **"Today" is the learner's own calendar date**, resolved
on the Next.js server from `learners.timezone` with the same UTC fallback the backend applies — never
the server's own zone. Work the plan placed on days that have **passed** and which the learner has
not settled is shown under its own heading and **nothing moves it**: no status is written and no
adaptation is triggered, so the learner still asks. A **skipped** or **postponed** item is settled, so
neither appears there; a status this build does not recognise is treated as outstanding and does. The overdue boundaries are mirrored from `select_overdue`
for display only; that domain rule stays authoritative for what adaptation writes. Say an **item** is
overdue, never that the learner is behind. Nothing is counted, totalled, ranked, or scored.

**The monthly study view is a reading of the roadmap and the week, not a `monthly` plan** —
`/plan/month`, which adds **no endpoint, no column, no migration, and no backend change at all**. It
groups what PLN-003 already returns to the learner's own calendar month — resolved from
`learners.timezone` through the same `learnerToday` the daily view uses, never the server's zone — and
lists the roadmap topics the weekly plan has not dated. A `monthly` `plan_type` is still never
written, and what one *contains* is deliberately still undecided.
**Because a weekly plan dates seven days, a month is mostly undated, and the screen says so.** It does
**not** project the saved study week across the month's remaining days or place the roadmap onto them:
placing work on a day is `schedule_sessions`, a backend rule, and dates existing in no stored record
would disagree with the plan at the first adaptation. **The screen is read-only** — no status control,
no generate control, no adapt control — which departs from the daily view deliberately: marking work
stays on `/plan/today` and `/plan`. A settled item keeps its place, marked in words. `select_overdue`
is neither read nor mirrored, because this screen makes no claim about what is overdue. **Only the
learner's current month is reachable.** Nothing is counted, totalled, ranked, or scored. This meets
FR-003's second acceptance criterion **in full**.

**PLN-006 says whether the saved week reaches the horizon** —
`GET /api/v1/study-goals/{study_goal_id}/plan-feasibility`, which meets **FR-004's third acceptance
criterion**, the last one unmet. **It is a live read and writes nothing**: no plan, no availability,
no preference, no item status, and no adaptation, so a learner may ask as often as they like and the
answer moves when their week does. A sentence stored in `generation_reason` was rejected because a
plan's reasons are never rewritten, so it would go stale the moment the learner edited their week.
**The arithmetic is a pure domain rule** — `assess_horizon_coverage`, the **fourth** in
`backend/app/domain/study_planning.py` — because terminology reserves totalling a week for *the
planner* rather than a screen, which is where this departs from the monthly view's frontend-only
shape. One session per remaining topic, against the minutes the saved week offers from today to the
horizon **with both ends included**, counted by weekday rather than walked day by day. **Only a
completed topic is excluded**, exactly as adaptation excludes it; a skipped or postponed topic still
needs time. **Three verdicts**: `sufficient`, `insufficient`, and `unknown` — the last an answer, not
a failure, with `unknown_reason` distinguishing a goal aiming at no date from one with no saved week.
**A week saved and deliberately kept free is neither**: that is zero minutes. An unset session length
is named as the planner's own choice, never a default. **Counts and durations only — never a
percentage, a ratio, or a proportion**, and a shortfall is never a negative surplus. The panel sits on
`/plan` above the week and carries **no control**. It needed **no column, no table, and no
migration**.

**REV-001 to REV-004 bring finished topics back for review** — the built part of FR-006, and the last
of Milestone 3's requirements to be started. **FR-006 is not met in full**: seeing what is due and
recording a completion or skip are, its fourth criterion considers three of its four inputs because
no quiz or test evidence is stored, and the **resource-and-practice half of its second criterion is
deferred** to FR-007 and FR-009. Do not write that FR-006 is complete. **The learner asks; nothing schedules on its own**: completing a plan item creates no
revision, and neither does completing a revision. Asking twice creates nothing the second time — a
topic with a review already waiting, or one the learner has **skipped or postponed**, is left alone,
because they have answered and every status is reversible. A topic returns an **interval after the
work it follows**, decided by the **learning stage the learner recorded**: 7 days with none, rising to
21 at `strong_understanding`. **These are LearnFlow's intervals, named as its own** in every
revision's frozen `recommendation_reason`; a longer wait is **not a better mark**, and this does not
disturb ADR-020's refusal to let a stage reorder a *plan*. **A revision is not a plan item**:
`plan_items.action_type = 'revise'` stays unwritten, no revision enters a plan, and PLN-005 is
untouched — a review must survive the supersede adaptation performs. **Nothing writes a learning
stage.** REV-003 mirrors PLN-004 exactly — `due`, `completed`, `skipped`, `postponed`, any direction,
`completed_at` from the server clock, **no `skipped_at`, no date, no reason field**; `scheduled` is
refused because nothing collects the date it needs. It lives at `/revisions`, its own route, and the
roadmap, week, day, and month views are unchanged. It needed **the first migration since
`20260806_03`**, and `revision_records` carries a **`recommendation_reason` the approved table does
not list**, so a due date computed from a stage cannot drift from the sentence explaining it.

**The progress overview gathers where a learner's study stands** — `/progress`, which adds **no
endpoint, no column, no migration, and no backend change at all**. It reads eight existing contracts —
LRN-001, GOAL-002, PLN-002, PLN-003, PLN-006, REV-001, and PRG-002 with CUR-003 — and shows what
could use the learner's attention and why, what each
active plan covers, what today holds, whether the saved week reaches the date, what the learner has
marked, the learning stages they recorded gathered **by subject**, and which topics are ready to
review. **It writes nothing at all**: no status, generate, adapt, scheduling, or stage
control, and no `<button>` and no `<form>` — the read-only shape ADR-026 fixed, with every panel
naming where its action lives and linking to it. **It counts nothing of its own.** The only figures
on it are ones the API reported — a plan's `item_count`, and PLN-006's counts and durations — because
terminology forbids counting skips, postponements, and reviews **by name**; what the learner has
marked is **listed** under the words for each status, never tallied. No percentage, ratio, streak, or
progress bar. Only the goal's **active** plans are read, since a superseded one cannot be written to.
The date comes from the same `learnerToday` and `selectDailyWork` the daily view uses, so **no new
timezone conversion and no new mirror of `select_overdue`** is written. **This is the screen the word
*dashboard* was reserved for**; its canonical name is **progress overview**, and the home screen at
`/` is unchanged and is still not a dashboard. **PRG-001 stays unimplemented**, waiting on the
quiz, external-test, and mistake evidence alone. **FR-011 is not met in full** — two of its four criteria are met and a third is
partly met; do not write that it is complete.

**The stages panel is a reading of PRG-002 and CUR-003, joined in the client** — the join the
curriculum view already performs, read the other way round, so **no filter and no subject name is
added to PRG-002** and no backend file changes. **Only topics the learner recorded something against
appear**; a topic with no record still reads as *Not explored* and stays in the curriculum view, and a
subject holding no record is left out entirely rather than shown empty. **A subject never carries a
count**, a percentage, or a bar — a figure beside a subject name measures the learner, not a plan —
and the panel is **never ordered, grouped, or coloured by stage**, because a learner may move to any
stage from any stage. The order is the **curriculum's own**, arrived at by walking the CUR-003 tree
rather than sorting PRG-002's newest-first list. An unreadable read empties **that panel alone**, said
apart from "you have recorded nothing". Contracted by
[`docs/adr/ADR-030-learning-stages-by-subject-panel.md`](docs/adr/ADR-030-learning-stages-by-subject-panel.md).

**The priority focus panel leads the overview and ranks nothing** — a third reading, adding **no
endpoint, no read, no column, no migration, and no backend change**. It gathers exactly three facts a
**backend rule already decided**: a plan item whose day has passed with nothing said about it (through
`selectDailyWork`, so `select_overdue` gains no second frontend mirror), a review REV-001 reports
`is_due`, and PLN-006's `insufficient` or `unknown` verdict — a `sufficient` verdict and a verdict this
build does not recognise both yield nothing. Each entry carries a neutral fact naming the record and
then **the sentence the backend wrote**, rendered unchanged. **The recorded learning stage is
deliberately not a signal**: selecting some of the five stages as priorities ranks them against each
other, which ADR-017 and ADR-030 both refuse; where a stage explains an item it is already inside that
item's frozen `recommendation_reason`. **Priorities are named items and reviews, never subjects** — a
subject-level claim needs a count or a comparison. **Nothing is ranked**: the groups sit in a fixed
presentation order that orders nothing and the copy says so, no entry is numbered, no group is styled
as more urgent, and the list is **never capped**, because choosing which few to show is a ranking.
**Nothing is counted** and **nothing is written**. An unreadable feasibility check is reported **apart
from** a week that reaches the date. This **partly meets** FR-011's third criterion — for the evidence
LearnFlow stores — and **supersedes ADR-029's and ADR-030's "not buildable" row on that narrow
ground**, leaving everything else in both intact. **PRG-001 now waits on quiz, external-test, and
mistake evidence alone.** Do not write that FR-011 is complete. Proposed by
[`docs/adr/ADR-031-priority-focus-panel.md`](docs/adr/ADR-031-priority-focus-panel.md).

**RES-001 to RES-004 catalogue the learner's own study material against topics** — the first change to
open **Milestone 4**, and it opens **that milestone's first item only**: nothing is uploaded,
downloaded, extracted, embedded, indexed, or retrieved, and no mentor exists. **A resource is a record
of where material is, never the material.** `storage_key`, `metadata`, and `resource_ingestions` are
all **absent**, each waiting on the code that would maintain it. **No location on the learner's own
machine is stored**: `external_reference` accepts an `http` or `https` address and nothing else,
because a resource endpoint may never return an absolute local filesystem path — the path is refused
on the way in rather than filtered on the way out. Material that is not on the web is carried by
`source_label`, in the learner's own words, and a resource must name **at least one** of the two.
**FR-007's "references/paths to local video resources" is therefore only partly met**; do not write
that FR-007 is complete. **Nothing curated ships** — no seed, no data file, no external content in the
repository — and `owner_learner_id` stays nullable for curated content nothing writes yet. **Nothing
is deleted**: RES-005 is unimplemented, and a learner puts material aside with `status: archived`,
reversibly. **Nothing is recommended, ranked, or counted**: a topic's material is what the learner
linked to it, in the API's order, and no figure appears beside a subject, a topic, or a review. Only
`primary` of the four link roles is written, though the `CHECK` carries all four; `resource_type`
permits five of seven and `status` two of five, because the missing values need storage that does not
exist. **A resource may cover any stored topic, including a grouping heading** — deliberately unlike
PRG-004, which refuses a stage on one. **Writing lives on `/resources` alone** — add, edit, and archive — while the curriculum view
and `/revisions` show a topic's material **read-only** and link there. This supplies the **resource
half** of FR-006's second criterion, which ADR-028 deferred — the **practice half still waits on
FR-009**, so **FR-006 is still not met in full**. Contracted by
[`docs/adr/ADR-032-learning-resource-catalogue.md`](docs/adr/ADR-032-learning-resource-catalogue.md).

**Learner setup** is the canonical name for this capability — in prose, API documentation, and UI
copy. **Onboarding** names only the first-time UI flow, which is why `frontend/features/onboarding/`
keeps that name. See [`docs/domain/terminology.md`](docs/domain/terminology.md).

## Frontend quick reference

```bash
cd frontend
npm ci                                          # install the committed lockfile
npm run dev                                     # http://localhost:3000
```

Node.js 24 or later is required. Next.js + TypeScript, App Router, CSS Modules. The frontend calls the
API from its own server — learner-facing pages are React Server Components and writes go through a
server action, so the browser never reaches the backend, no CORS configuration exists, and
`API_BASE_URL` is server-side only. Today it serves a curriculum view over CUR-001 to CUR-003 that
also reads the learner's recorded stages over PRG-002 and writes one over PRG-004, a `/setup` screen
over EXM-001, LRN-001, LRN-002, and GOAL-001 to GOAL-005, a home screen at `/` that reads the
saved setup back over LRN-001, GOAL-002, and EXM-001, a `/plan` screen that reads the current plan
over PLN-002 and PLN-003, generates one over PLN-001, marks an item completed, skipped, or postponed over PLN-004, adapts the plan over PLN-005, and reads whether the saved week reaches the horizon over PLN-006, a `/plan/today` daily study view that reads the same weekly plan over
PLN-002 and PLN-003, takes the learner's date from LRN-001, and moves items over PLN-004 —
generating and adapting stay on `/plan`, where the learner asks for them — and a `/plan/month` monthly
study view that reads both active plans over PLN-002 and PLN-003, takes the learner's month from
LRN-001, and **writes nothing at all**, and a `/revisions` screen that reads the learner's reviews
over REV-001, schedules them over REV-004, and records what became of each over REV-003, and a
`/progress` progress overview that gathers LRN-001, GOAL-002, PLN-002, PLN-003, PLN-006, REV-001, and
PRG-002 with CUR-003 for the recorded learning stages by subject, leads with a priority focus panel
drawn from those same reads, and **writes nothing at all** either, and a `/resources`
learning-resource catalogue that lists the learner's own study material over RES-002, registers it
over RES-001, and **corrects** it or puts it aside and back over RES-004 — reading GOAL-002 and
CUR-003 to offer the topics it may be linked to. It supports **add, edit, and archive**; material
put aside is read-only, so a learner puts it back before correcting it, and the edit form never
sends `status` while the archive control sends nothing else. The curriculum view and `/revisions` also read RES-002 and show a
topic's material **read-only**, linking to `/resources` for every change. A goal response carries the saved study week
and the saved planning preferences, so neither setup nor home calls anything extra to show them.

The frontend serves its own static `/health` for the container health check, distinct from the
backend's `GET /health`. It reaches nothing, so the probe asks only whether the frontend process is
responding rather than generating backend requests every interval.

A `"use server"` module may export only async functions. A constant exported from one fails at
runtime with a `500` that neither `tsc` nor `next build` reports; `frontend/tests/server-actions.test.ts`
checks the rule.

Local containers — `compose.yaml` defines the `frontend`, `backend`, and `postgres` services;
ChromaDB joins them with the code that uses it:

```bash
docker compose up --build                       # build and start
docker compose logs -f backend                  # follow logs
docker compose down                             # stop, preserving volumes
docker compose config -q                        # validate the topology
docker build -f docker/backend.Dockerfile .     # validate the backend image build
docker build -f docker/frontend.Dockerfile .    # validate the frontend image build
```

`docker compose down -v` deletes named volumes and is destructive — `postgres_data` holds learner
data; never present it as a routine stop command. See
[`docs/deployment/docker.md`](docs/deployment/docker.md).

Python 3.14 is required. `GET /health` is an operational endpoint served outside `/api/v1`.
Configuration is validated at startup; see
[`docs/deployment/environments.md`](docs/deployment/environments.md) for the variable catalogue.

## Repository checks

The canonical local check set is *Local Quality Checks* in
[`docs/development/coding-standards.md`](docs/development/coding-standards.md). Run all of it before
committing:

```bash
cd backend
python -m pytest -W error                                              # tests; warnings fail the run
python -m ruff check .                                                 # backend lint
python -m ruff format --check .                                        # backend formatting
cd ../frontend
npm ci                                                                 # install the committed lockfile
npm run lint                                                           # frontend lint
npm run typecheck                                                      # frontend types
npm test                                                               # frontend tests
npm run build                                                          # frontend production build
cd ..
python -m ruff check --config backend/pyproject.toml scripts/          # repository scripts lint
python -m ruff format --check --config backend/pyproject.toml scripts/ # repository scripts formatting
python scripts/validate_docs.py                                        # documentation front matter and links
```

CI runs these same checks on every pull request, except that the workflow runs `python -m pytest`
without `-W error`, and additionally builds both container images; see
[`docs/deployment/ci-cd.md`](docs/deployment/ci-cd.md). Changes reach `main`
through a pull request, per
[`docs/development/git-workflow.md`](docs/development/git-workflow.md).

The database migration tests are outside this set because they need PostgreSQL. They skip unless
`TEST_DATABASE_URL` names a disposable database, and must never be pointed at `DATABASE_URL`. CI runs
them against an ephemeral service container.

## Never commit

Virtual environments, `node_modules`, real `.env` files, learner PDFs or notes, database volumes,
vector indexes, or secrets. See [`.gitignore`](.gitignore) and
[`docs/development/folder-structure.md`](docs/development/folder-structure.md).
