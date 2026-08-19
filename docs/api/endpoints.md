---
title: LearnFlow API Endpoint Catalog
status: approved
owner: architecture-and-api
last_updated: 2026-08-19
related:
  - ../00-project-context.md
  - conventions.md
  - ../requirements/functional.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../roadmap/milestones.md
  - ../adr/ADR-011-sqlalchemy-persistence-implementation.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
  - ../adr/ADR-014-api-response-contract.md
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
  - ../adr/ADR-037-learner-written-resource-notes.md
  - ../adr/ADR-038-local-topic-note-retrieval.md
  - ../adr/ADR-033-checkpoint-practice-workflow.md
  - ../adr/ADR-034-checkpoint-practice-history.md
  - ../adr/ADR-035-practice-question-correction.md
  - ../adr/ADR-036-topic-material-on-the-plan-screens.md
---

# LearnFlow API Endpoint Catalog

## Purpose

Map approved MVP requirements to the initial `/api/v1` HTTP API surface.

This catalog defines endpoint intent and primary contracts. Exact Pydantic request/response schemas are created during implementation and must conform to `conventions.md`.

## Identity Assumption

The MVP has one local learner. Learner-owned endpoints resolve the effective learner server-side and do not expose an arbitrary client-controlled `learner_id` parameter.

## Operational Endpoints

| ID | Method and path | Purpose | Notes |
| --- | --- | --- | --- |
| OPS-001 | `GET /health` | Report API readiness for local environment checks. | Operational endpoint; intentionally outside `/api/v1` so health probes stay stable across API major versions. Returns flat `{"status": "ok"}` with `200`, exempt from the `data` envelope. Does not expose learner data or provider secrets. |

## Curriculum Endpoints

Supports **FR-001 — Curated GATE CSE Learning Program**.

| ID | Method and path | Purpose | Primary response |
| --- | --- | --- | --- |
| CUR-001 | `GET /api/v1/curriculum/programs` | List available learning programs. | Programs, including GATE CSE. |
| CUR-002 | `GET /api/v1/curriculum/programs/{program_id}` | Read program metadata and active curriculum-version reference. | Program details. |
| CUR-003 | `GET /api/v1/curriculum/versions/{curriculum_version_id}/tree` | Read subjects, topics, subtopics, and supported relationships. | Data-driven curriculum hierarchy. |

The frontend must use these endpoints rather than embedding GATE CSE topic data in code.

All three are **implemented**. Curriculum data is reference data, so none of them
resolves a learner identity, none is learner-owned, and all three are synchronous. They read
through the `ReadCurriculum` application use case and a read-only curriculum repository port; the
curated rows they return are written by the seed described in
[database migrations](../database/migrations.md#the-curriculum-seed).

### CUR-001 — `GET /api/v1/curriculum/programs`

Query parameters `limit` (1–100, default 25) and `offset` (0 or greater, default 0). Returns `200`
with the `data` array and the `pagination` block described in
[conventions](conventions.md#success-response-shapes). Each item carries `id`, `code`, `name`,
`description`, and `active_curriculum_version`, which is `null` while a program has only draft or
retired versions. Errors: `422` `validation_error` for a `limit` or `offset` outside those bounds.

### CUR-002 — `GET /api/v1/curriculum/programs/{program_id}`

`program_id` is a UUID. Returns `200` with one program under `data`, in the same shape CUR-001
returns per item. Errors: `404` `not_found` when no such program is stored; `422`
`validation_error` when the path segment is not a UUID.

### CUR-003 — `GET /api/v1/curriculum/versions/{curriculum_version_id}/tree`

`curriculum_version_id` is a UUID. Returns `200` with `curriculum_version`, `subjects`, and
`topic_relationships` under `data`. Each subject carries its root `topics`, and each topic nests its
own `subtopics` to whatever depth the curriculum uses; `is_trackable` says whether learner progress
can be recorded directly against a topic, which a topic that merely groups subtopics is not.
Subjects and topics are ordered by `position`, the order the syllabus teaches them in.

Relationships are listed beside the tree rather than inlined on a topic, because an edge relates two
topics and nesting it under one would make the tree assert which end owns it.

A version with no subjects returns an empty tree rather than an error, and a `draft` or `retired`
version is readable — `curriculum_version.status` says which it is. Errors: `404`
`not_found` when no such version is stored; `422` `validation_error` when the path segment
is not a UUID.

Related entities: [learning program](../domain/entities.md#learning-program),
[curriculum version](../domain/entities.md#curriculum-version),
[subject](../domain/entities.md#subject), [topic](../domain/entities.md#topic), and
[topic relationship](../domain/entities.md#topic-relationship). Related tables:
[curriculum schema area](../database/schema.md#schema-areas). The rows they return are loaded by
[the curriculum seed](../database/migrations.md#the-curriculum-seed).

## Examination Schedule Endpoints

Supports **FR-002 — Initial Learner Setup**.

| ID | Method and path | Purpose | Primary response |
| --- | --- | --- | --- |
| EXM-001 | `GET /api/v1/examination-schedules` | List the published examination schedules a learner can aim at. | Schedules, each with its examination window, provenance, and dated periods. |

An examination schedule is reference data, like the curriculum, so this endpoint resolves no learner
identity and is synchronous. It exists because a learner setting a first goal has to *choose* a
cycle: before it, a schedule reached a client only through a goal that already named one.

### EXM-001 — `GET /api/v1/examination-schedules`

Query parameters `learning_program_id` (a UUID, optional), `limit` (1–100, default 25), and `offset`
(0 or greater, default 0). Returns `200` with the `data` array and the `pagination` block described
in [conventions](conventions.md#success-response-shapes), ordered by descending `cycle_label`.

Each item carries `id`, `learning_program_id`, `cycle_label`, `name`, `organising_body`,
`source_reference`, `source_checked_on`, `schedule_status`, `examination_window`, and `periods`.

`examination_window` is `{starts_on, ends_on}` spanning the first published sitting day to the last,
derived from the `examination` periods alone; it is `null` when a stored schedule publishes no
sitting day. There is deliberately no single examination date field: an examining body that publishes
several sitting days has not named the learner's day. `schedule_status` is `provisional` or
`confirmed` and travels with the dates wherever they are shown.

`periods` lists every dated period — `registration`, `late_registration`, `examination`, and
`results` — because the registration deadlines are the nearest actionable dates a learner has.

An unknown `learning_program_id` returns an empty page rather than `404`: a filter that matches
nothing is an empty result, not a missing record. Errors: `422` `validation_error` for a `limit`,
`offset`, or `learning_program_id` outside those bounds or shapes.

Related entities: [examination schedule](../domain/entities.md#examination-schedule) and
[examination period](../domain/entities.md#examination-period). The rows it returns are loaded by
[the examination schedule seed](../database/migrations.md#the-examination-schedule-seed).

## Learner Setup and Goal Endpoints

Supports **FR-002 — Initial Learner Setup**.

| ID | Method and path | Purpose | Primary request/result | State |
| --- | --- | --- | --- | --- |
| LRN-001 | `GET /api/v1/learner/profile` | Read local learner profile/preferences. | Current learner summary. | Implemented |
| LRN-002 | `PATCH /api/v1/learner/profile` | Update learner display preferences/timezone. | Updated profile. | Implemented |
| GOAL-001 | `POST /api/v1/study-goals` | Create a study goal for a selected program, aiming at an examination cycle, a target date, or both. | Goal data, including the examination window when a cycle is named. | Implemented |
| GOAL-002 | `GET /api/v1/study-goals` | List the learner's goals. | Goal collection. | Implemented |
| GOAL-003 | `GET /api/v1/study-goals/{goal_id}` | Read one study goal. | Goal. | Implemented |
| GOAL-004 | `PATCH /api/v1/study-goals/{goal_id}` | Update the examination cycle, target date, status, or planning preferences. | Updated goal. | Implemented |
| GOAL-005 | `PUT /api/v1/study-goals/{goal_id}/availability` | Replace recurring weekly available study time. | Saved availability slots. | Implemented |

A goal aims at an examination cycle, a target date, or both, and never at neither — a rule the
database enforces and the application refuses before the database sees it. A response reports an
examination as a **window** spanning the published sitting days, together with the source it came
from and whether those dates are still provisional; it never reports a single examination date the
examining body has not published.

None of these endpoints accepts a `learner_id`: the effective learner is resolved server-side, per
the [identity assumption](#identity-assumption) above. All are synchronous.

The deferral [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md) recorded is
**discharged in full**. LRN-001, LRN-002, and GOAL-001 to GOAL-004 are contracted by
[ADR-016](../adr/ADR-016-learner-onboarding-api-contracts.md); GOAL-005, which waited on a schema
decision rather than on a caller, is contracted by
[ADR-018](../adr/ADR-018-weekly-availability-slots.md). The `planning_preferences` group GOAL-001 and
GOAL-004 accept, and every goal response carries, is contracted by
[ADR-019](../adr/ADR-019-study-goal-planning-preferences.md).

### LRN-001 — `GET /api/v1/learner/profile`

Returns `200` with the learner under `data`: `id`, `display_name`, and `timezone`.

`data` is `null` before setup has created a learner. That is a real state of a fresh installation
rather than a failure, so it is not a `404` a client would have to special-case — and a read never
creates the record it did not find. Errors: `409` `conflict` when more than one learner is stored,
because LearnFlow is single-learner until accounts exist and choosing one arbitrarily would show a
learner somebody else's profile.

### LRN-002 — `PATCH /api/v1/learner/profile`

Request body: `display_name` (string or `null`) and `timezone` (an IANA zone name). Both are
optional; an unknown field is rejected. Returns `200` with the updated profile in the shape LRN-001
returns.

This is where the local learner record comes into existence, on the learner's own action. A field the
request omits is left alone, so a form that did not include the timezone cannot move every future
plan by hours. `display_name: null` removes the stored name — absence deliberately cannot express
that. `timezone: null` is rejected: a learner always has one.

Errors: `422` `validation_error` for an unknown timezone, a `null` timezone, a request naming no
field to change, or an unknown field; `409` `conflict` when more than one learner is stored.

### GOAL-001 — `POST /api/v1/study-goals`

Request body: `learning_program_id` (a UUID), `examination_schedule_id` (a UUID or `null`),
`target_date` (`YYYY-MM-DD` or `null`), and `planning_preferences` (an object or `null`). An unknown
field is rejected. Returns `201` with the goal under `data`.

There is no `curriculum_version_id`. A goal binds to the program's **active** curriculum version, so
a client cannot attach a learner to a draft or retired syllabus by naming its identifier. Accepting
one later, once a reason exists to study an older version, is a compatible addition.

A goal response carries `id`, `learner_id`, `status`, `target_date`, `learning_program`
(`id`, `code`, `name`), `curriculum_version` (`id`, `version_label`, `status`), `examination` —
`null` for a goal aiming at a target date alone, and otherwise the schedule's `id`, `cycle_label`,
`name`, `organising_body`, `source_reference`, `source_checked_on`, `schedule_status`, and
`examination_window` — plus `availability` and `planning_preferences`.

`availability` is `{slots: [...]}`, the week GOAL-005 writes, in week order with Monday first. Each
slot is `day_of_week` and `available_minutes`, and nothing else: GOAL-005 addresses a week rather than
a row, so no slot identifier is reported. A goal whose availability has never been saved carries
`{"slots": []}` rather than `null` or an absent key, so no client needs a branch for a goal created
before a week was. There is deliberately **no weekly total**; see GOAL-005 below.

`planning_preferences` is `{preferred_session_minutes, topic_sequencing}` — how the learner wants a
plan built, contracted by [ADR-019](../adr/ADR-019-study-goal-planning-preferences.md). It is **always
an object, never `null`**: a learner who has set no preference gets one whose members are both `null`,
so no client needs a branch for a goal stored before preferences existed.

- `preferred_session_minutes` is how long one study block should be, from 15 to 480. It is a
  **duration, not a time of day** — nothing records when in a day a session falls, which is the
  position [ADR-018](../adr/ADR-018-weekly-availability-slots.md) took for an availability slot.
- `topic_sequencing` is which order a plan works through the curriculum: `syllabus_order`, following
  the stored position of subjects and topics, or `prerequisites_first`, following the topics'
  prerequisite links. There is deliberately no order that ranks topics by evidence, because no
  evidence is stored to rank them by.

**A `null` member is "the learner has not said", not a default.** Nothing invents a preference on a
learner's behalf, so an unset one stays distinguishable from one set to the value the product would
have guessed — the distinction PRG-002 draws between an explicit `not_explored` and a topic with no
record, and GOAL-005 draws between zero minutes and a day with no entry. A planner meeting `null`
chooses its own default rather than reading one nobody set.

On this endpoint, omitting `planning_preferences` and sending `null` mean the same thing: a new goal
has nothing stored to leave alone, so both create a goal with no preferences. They differ on GOAL-004.

**No preference is totalled, ranked, or scored**, on this response or anywhere else. Preferences are
planning inputs beside availability, and both are now consumed by the plan PLN-001 generates — a
session length decides how long an item runs, and a topic order decides the sequence — which
[the FR-002 criteria](#fr-002-acceptance-criteria) records.

Errors: `422` `validation_error` when the request aims at neither a cycle nor a date, when the
program or schedule is not stored, when the schedule belongs to another program, when the program
has no active curriculum version, or when a preference falls outside the values above — `details`
names the offending field in each case, as `body.planning_preferences.<member>` for a preference, and
never echoes the rejected value. `409` `conflict` when no learner exists yet, or when the learner
already has an **active** goal for that program: the existing goal is what any plan was built from, so
a repeated form submission must not replace it. Goals that are paused, completed, or archived are
history and do not conflict.

### GOAL-002 — `GET /api/v1/study-goals`

Query parameters `limit` (1–100, default 25) and `offset` (0 or greater, default 0). Returns `200`
with the `data` array and the `pagination` block, newest first, in the per-item shape GOAL-001
returns.

An installation where setup has not run has no learner and therefore no goals, which is an empty page
rather than a failure. Errors: `422` `validation_error` for a window outside those bounds; `409`
`conflict` when more than one learner is stored.

### GOAL-003 — `GET /api/v1/study-goals/{goal_id}`

`goal_id` is a UUID. Returns `200` with one goal under `data`, in the shape GOAL-001 returns —
including the `availability` summary this catalogue's original intent line promised, which
[ADR-018](../adr/ADR-018-weekly-availability-slots.md) supplies.

Errors: `404` `not_found` when no such goal is stored *or it belongs to another learner* —
`conventions.md` treats "not visible to the caller" as a `404`, and saying "that exists but is not
yours" would confirm a record the caller may not read. `422` `validation_error` when the path segment
is not a UUID; `409` `conflict` when more than one learner is stored.

### GOAL-004 — `PATCH /api/v1/study-goals/{goal_id}`

Request body: `examination_schedule_id` (a UUID or `null`), `target_date` (`YYYY-MM-DD` or `null`),
`status` (`active`, `paused`, `completed`, or `archived`), and `planning_preferences` (an object or
`null`). All optional; an unknown field is rejected. Returns `200` with the updated goal.

A field the request omits is left alone; an explicit `null` clears it. `status: null` is rejected: a
goal always has one. The result must still aim at an examination cycle, a target date, or both.

**Planning preferences are now accepted**, which is what this catalogue's original intent line
promised and what [ADR-019](../adr/ADR-019-study-goal-planning-preferences.md) supplies. They were
withheld while `study_goals.planning_preferences` did not exist; two typed columns now hold them, and
[schema.md](../database/schema.md#study_goals) records the shape.

**A supplied group replaces the whole group.** The preferences it names become the goal's preferences,
so a member left out of a supplied group is **unset** rather than left at its stored value, and an
empty object clears every preference — as an explicit `null` does. Omitting the field entirely leaves
the stored preferences alone.

That is GOAL-005's whole-week replace applied to a group of fields, and for the same reason: a form
shows every preference at once, so a control the learner cleared has to reach the API as a clearance. A
merge would let a cleared control keep its old value. It is also why no separate "clear" spelling is
needed — an empty group and an absent field are already different requests.

Saving the preferences already stored is accepted and writes nothing, as saving an unchanged week is
under GOAL-005 and recording an unchanged stage is under PRG-004.

Errors: `404` `not_found` as for GOAL-003; `422` `validation_error` when the update would leave the
goal aiming at nothing, names an unknown status, names no field to change, names a schedule that
is not stored or belongs to another program, or names a preference outside the values GOAL-001
documents — `details` reports a preference as `body.planning_preferences.<member>` and never echoes the
rejected value; `409` `conflict` when more than one learner is stored.

### GOAL-005 — `PUT /api/v1/study-goals/{goal_id}/availability`

`goal_id` is a UUID. Request body: `slots`, a list of at most seven entries, each carrying
`day_of_week` and `available_minutes`. An unknown field is rejected. Returns `200` with the saved week
under `data`, as `{"slots": [...]}` in week order with Monday first.

`day_of_week` is a **day name** — `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`,
or `sunday` — never an index. Python, JavaScript, and PostgreSQL disagree about which day is zero, and
a client that guesses wrong would misfile a whole week with no error anywhere, so
[ADR-018](../adr/ADR-018-weekly-availability-slots.md) removed the numbering rather than documenting
one. `available_minutes` is 0 to 1440, the number of minutes in a day.

**This replaces the week; it does not merge into it.** The days named become the learner's
availability, and any day the request does not name is removed. Adding a day, changing a day, and
removing a day are therefore the same request, and each is one transaction — an edit spanning three
days cannot leave one saved and two lost. Saving the week that is already stored is accepted and
writes nothing, as recording an unchanged stage is under PRG-004.

`slots` is **required**. An explicit `[]` clears the goal's availability, which is how a learner takes
it all back; a body that omitted the field would otherwise clear it by accident, so that is a `422`.

**Zero minutes is a day the learner deliberately keeps free**, and it is stored. A day with no entry
is one they have not set, and it is absent from the week entirely. The two are different claims — the
same distinction PRG-002 draws between an explicit `not_explored` and a topic with no record — which
is why the stored constraint is `>= 0` rather than `> 0`.

**No total is reported**, on this response or on a goal. Availability is a planning input, and
[terminology](../domain/terminology.md) calls it "not a measure of commitment or ability"; turning a
week into an hours figure is planning work. PLN-001 now performs the part of that work a plan needs —
it places sessions on the days a week names — and deliberately reports no total either. Whether a
week can reach a goal's horizon is a trade-off judgement, and
[PLN-006](#pln-006-get-apiv1study-goalsstudy_goal_idplan-feasibility) is what makes it — never this
response, which reports the days the learner saved and nothing derived from them.

The response is an object rather than a bare array, per
[ADR-014](../adr/ADR-014-api-response-contract.md), and carries **no `pagination` block**: a week
holds at most seven days belonging to one goal, so there is no window to page through.

Errors: `404` `not_found` when no such goal is stored *or it belongs to another learner*, as for
GOAL-003; `422` `validation_error` when a day is not one of the seven, when a day is named more than
once, when `available_minutes` falls outside 0 to 1440, when `slots` is absent or holds more than
seven entries, or when the request names an unknown field — `details` names `body.slots` and never
echoes the rejected value; `409` `conflict` when more than one learner is stored.

Related entity: [availability slot](../domain/entities.md#availability-slot). Related table:
[`availability_slots`](../database/schema.md#availability_slots).

Related entities: [learner](../domain/entities.md#learner),
[study goal](../domain/entities.md#study-goal), and
[availability slot](../domain/entities.md#availability-slot). Related tables:
[learner planning schema area](../database/schema.md#schema-areas). These endpoints read and write
through the `ManageLearnerProfile` and `ManageStudyGoals` application use cases; the same rows are
also maintained from the command line by
[`scripts.set_study_goal`](../database/migrations.md#setting-the-local-learners-study-goal), which
upserts the learner's active goal rather than refusing a second one and does not touch availability.

### FR-002 acceptance criteria

**All five of [FR-002](../requirements/functional.md#fr-002-initial-learner-setup)'s acceptance
criteria are met in full.** This section is authoritative for the count; documents that cite it link
here rather than repeating it.

Met in full: setting a target examination schedule or completion date; setting available study time and
basic planning preferences; confirming the active learning program; reviewing the saved setup
without re-entering it, which the home screen reads back over LRN-001, GOAL-002, and EXM-001; and
receiving an initial plan with no previous progress, which PLN-001 generates.

- *"The learner can set available study time and basic planning preferences"* — **met in full**, having
  been partly met since GOAL-005 arrived. Available study time is set through GOAL-005; planning
  preferences are set through GOAL-001 and GOAL-004, contracted by
  [ADR-019](../adr/ADR-019-study-goal-planning-preferences.md), which creates the two columns
  [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md) had held back. Both are read back on
  the setup screen and on the home screen.

  **Both are now consumed**, by the plan PLN-001 generates: a week decides which days hold work, and a
  session length decides how long each item runs. Nothing still totals a week or ranks a preference —
  a plan places work on days, which is the arithmetic
  [ADR-018](../adr/ADR-018-weekly-availability-slots.md) said belonged to a planner, and no more of it.
- *"The learner can start with no previous progress and still receive an initial plan"* — **met in
  full.** PLN-001 generates a roadmap over the whole curriculum and a plan for the coming week,
  deterministically and with no AI provider, from the goal's horizon, the saved availability, the
  planning preferences, and any recorded stages. A learner who has recorded no progress receives the
  same plan they would with it — a stage explains an item, it does not rank one. Contracted by
  [ADR-020](../adr/ADR-020-initial-study-plan-generation.md).

## Planning Endpoints

Supports **FR-003 — Study Timeline and Plan** and **FR-004 — Plan Adaptation**, and completes
**FR-002**'s last acceptance criterion.

| ID | Method and path | Purpose | Primary request/result | State |
| --- | --- | --- | --- | --- |
| PLN-001 | `POST /api/v1/study-plans/generate` | Generate a goal's study plan: a `roadmap` always, and a `weekly` plan when the saved week has room for a session. | The plans written, the reason for each, and what was superseded. | Implemented |
| PLN-002 | `GET /api/v1/study-plans` | List plans, filterable by goal, type, status, and period. | Plan collection. | Implemented |
| PLN-003 | `GET /api/v1/study-plans/{plan_id}` | Read one plan and its ordered items. | Plan + plan items. | Implemented |
| PLN-004 | `PATCH /api/v1/plan-items/{plan_item_id}` | Mark a plan item completed, skipped, or postponed, or return it to `planned`. | Updated plan item. | Implemented |
| PLN-005 | `POST /api/v1/study-goals/{study_goal_id}/adapt` | Rebuild a goal's active plans around completed and missed work. | New plans; what was superseded, postponed, and left out. | Implemented |
| PLN-006 | `GET /api/v1/study-goals/{study_goal_id}/plan-feasibility` | Report whether the saved study week covers the work left before the goal's horizon. | A verdict, the counts and durations behind it, and the reason. | Implemented |

PLN-001 to PLN-003 are implemented, and their contracts are fixed by
[ADR-020](../adr/ADR-020-initial-study-plan-generation.md); PLN-004 by
[ADR-021](../adr/ADR-021-plan-item-completion.md), extended to accept `skipped` by
[ADR-024](../adr/ADR-024-plan-item-skipping.md) and `postponed` by
[ADR-025](../adr/ADR-025-learner-postponement.md); and PLN-005 by
[ADR-022](../adr/ADR-022-plan-adaptation.md); and PLN-006 by
[ADR-027](../adr/ADR-027-plan-feasibility.md). None of them
accepts a `learner_id`: the effective learner is resolved server-side, per the
[identity assumption](#identity-assumption) above. All six are synchronous and all six go through the `ManageStudyPlans` application use case —
**except that PLN-006 only reads**; it writes nothing at all.

**PLN-005 does not use the path this catalogue first held.** It was listed as
`POST /api/v1/study-plans/{plan_id}/adapt`; it is implemented as
`POST /api/v1/study-goals/{study_goal_id}/adapt`, because adaptation supersedes and rewrites every
active plan of a goal, so a path naming one plan would misdescribe what moves. ADR-022 records the
departure.

**A plan is deterministic.** The same goal, curriculum, week, preferences, and date produce the same
plan every time, and no AI provider is involved — which is what
[LearnFlow product agents](../ai/learnflow-agents.md) requires of the planner. **A plan is also
explainable**: every plan carries `generation_reason` and every item `recommendation_reason`, written
when the plan was generated and never rewritten, which is
[FR-003](../requirements/functional.md#fr-003-study-timeline-and-plan)'s fourth acceptance criterion.

**Nothing here judges a learner.** A recorded learning stage appears in an item's reason and changes
neither the order nor the time allowed; `priority` is a position in a list, not a score; and no total
is reported for a day, a week, or a plan. The one exception is
[PLN-006](#pln-006-get-apiv1study-goalsstudy_goal_idplan-feasibility), which totals the saved week
across the horizon precisely because judging whether it is enough is the planner's work rather than a
screen's — and which describes the plan and the time, never the learner.

**The daily study view adds no endpoint.** The `/plan/today` screen showing what a learner should
study today is a *reading* of the goal's active `weekly` plan: it filters PLN-003's items to the
learner's own calendar date, taken from `learners.timezone` on
[LRN-001](#lrn-001-get-apiv1learnerprofile), and completes them through PLN-004. Nothing about the
five contracts above changes, and **no `daily` plan is generated or read** — that `plan_type` stays
constrained and unwritten. Contracted by [ADR-023](../adr/ADR-023-daily-study-view.md).

**The monthly study view adds no endpoint either.** The `/plan/month` screen showing where a
learner's calendar month sits in their plan is a *reading* of the goal's two active plans: it groups
PLN-003's dated items to the learner's own month, taken from `learners.timezone` on
[LRN-001](#lrn-001-get-apiv1learnerprofile), and lists the roadmap topics the weekly plan has not
dated. It **writes nothing** — it does not call PLN-004, PLN-001, or PLN-005. Nothing about the five
contracts above changes, and **no `monthly` plan is generated or read** — that `plan_type` stays
constrained and unwritten, as `daily` does. Because a weekly plan dates seven days, a month is mostly
undated, and the screen says so rather than inventing dates no response carries. Contracted by
[ADR-026](../adr/ADR-026-monthly-study-view.md).

### PLN-001 — `POST /api/v1/study-plans/generate`

Request body: `study_goal_id` (a UUID). It is required, and an unknown field is rejected. Returns
`201` with the generation under `data`.

**Only the goal is named.** Everything a plan is built from — the curriculum and its topic
relationships, the goal's horizon, the saved weekly availability, the planning preferences, and the
recorded learning stages — is read from what the learner has already stored, so no client can plan
with a preference the learner never set. A body carrying `preferred_session_minutes` is a `422`, not
a silently ignored field.

`data` carries `study_goal_id`, `generated_on`, `plans`, and `superseded_plan_ids`.

- `generated_on` is the date in the **learner's own timezone**, from `learners.timezone`, not the
  server's. A plan generated late on a Sunday evening in `Asia/Kolkata` starts on Sunday.
- `plans` holds what was written, each with its items. **A `roadmap` always**, ordering every
  trackable topic across the goal's horizon with no dates; and a **`weekly`** plan when the learner's
  saved week has room for at least one session, placing the first of those topics onto the next seven
  days. **Those two are the only plan types anything writes.** `monthly` and `daily` are values
  [`study_plans.plan_type`](../database/schema.md#study_plans) accepts and no code stores, so no
  generation returns one and no read can find one; each arrives with the code that writes it. Neither
  the `/plan/today` screen nor the `/plan/month` screen is one — see
  [the notes above](#planning-endpoints).
- `superseded_plan_ids` names the plans this generation set aside. They are kept, not deleted, and
  each is still readable through PLN-003.

**Generating again supersedes rather than refusing.** The goal's existing `active` plans become
`superseded` and a new pair is written. A learner whose availability changed can generate again — but
once they have completed work, [PLN-005](#pln-005-post-apiv1study-goalsstudy_goal_idadapt) is the
better path: generation re-plans every topic, adaptation leaves out what is done.
That is deliberately unlike GOAL-001's refusal of a second active goal: a goal is what a plan is built
*from* and is expensive to re-enter, while a plan is derived and is preserved rather than destroyed.

**How the plan is built**, in full, because a learner is entitled to know and because
[ADR-020](../adr/ADR-020-initial-study-plan-generation.md) fixes each rule:

- **Which topics.** Every topic with `is_trackable`. A topic that only groups subtopics is a heading
  rather than work — the rule PRG-004 applies when it refuses a stage against one.
- **What order.** `syllabus_order`, and an unset `topic_sequencing`, follow the stored `position` of
  subjects and topics, parent before child — the order CUR-003 renders.
  `prerequisites_first` is a topological order over the `prerequisite` relationships, taking the
  earliest syllabus position among the topics ready at each step, so one defined order results rather
  than one of many valid ones. `recommended_before` and `related` do not constrain it. **The curated
  GATE CSE curriculum stores no prerequisite relationship**, so `prerequisites_first` currently yields
  syllabus order, and the plan's own reason says so rather than claiming otherwise.
- **The horizon.** `period_end` on the roadmap is the earlier of the examination window's first
  sitting day and the goal's `target_date`, whichever the goal has. It is `null` only when the goal
  aims at a schedule publishing no sitting day and carries no target date, which `generation_reason`
  then states. The examination is read on every generation rather than copied, so a corrected
  schedule reaches the next plan.
- **How long each item is.** `preferred_session_minutes`, or **60 minutes when the learner has set
  none** — chosen by the planner and named in the plan as the planner's choice, never stored against
  the goal. A preference nobody set still reads as unset on GOAL-002.
- **Which day each item falls on.** Each of the next seven days is filled with whole sessions while
  it has room for one; a day with time left but less than a full session gets a single shorter
  session only if nothing else was placed on it, so thirty minutes a day still yields a topic. No
  topic is split across days or scheduled twice.
- **A day with no availability holds no work**, whether the learner kept it free with zero minutes or
  never set it. The two remain different statements in storage; neither says they can study. A goal
  with **no saved availability at all** gets the roadmap and no week, with the reason saying so.
- **A recorded learning stage explains an item**, appearing in its `recommendation_reason`. It changes
  neither the order nor the time allowed: a stage guides the next action rather than scoring a topic
  ([FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence)).

Errors: `404` `not_found` when no such goal is stored *or it belongs to another learner*, as for
GOAL-003; `422` `validation_error` when the body names no goal, names one that is not a UUID, or
names an unknown field; `409` `conflict` when no learner exists yet to own the plan, or when more
than one learner is stored.

### PLN-002 — `GET /api/v1/study-plans`

Query parameters `study_goal_id` (a UUID, optional), `plan_type` (optional), `status` (optional),
`limit` (1–100, default 25), and `offset` (0 or greater, default 0). Returns `200` with the `data`
array and the `pagination` block, newest first.

Each item carries `id`, `learner_id`, `study_goal_id`, `plan_type`, `period_start`, `period_end`,
`status`, `generation_reason`, `item_count`, and `items`.

**`items` is empty on a listed plan.** A page of plans each carrying every item would be an unbounded
payload inside a paginated one, which the [pagination block](conventions.md#success-response-shapes)
cannot describe; `item_count` says how large each plan is, and PLN-003 returns the items of the one a
client opens.

A `study_goal_id` that matches nothing returns an empty page rather than `404`: a filter that matches
nothing is an empty result, not a missing record. An unknown `plan_type` or `status` is different and
is refused — a client asking for `status=finished` has misread the contract, and returning nothing
would let it keep doing so.

An installation where setup has not run has no learner and therefore no plans, which is an empty page.

Errors: `422` `validation_error` for a `limit`, `offset`, or `study_goal_id` outside those bounds or
shapes, or for a `plan_type` or `status` outside the documented values — `details` names
`query.plan_type` or `query.status` and never echoes the rejected value; `409` `conflict` when more
than one learner is stored.

### PLN-003 — `GET /api/v1/study-plans/{plan_id}`

`plan_id` is a UUID. Returns `200` with one plan under `data`, in the shape PLN-002 returns per item,
with `items` filled and ordered by `priority`.

Each item carries `id`, `topic`, `action_type`, `scheduled_for`, `estimated_minutes`, `priority`,
`status`, `recommendation_reason`, and `completed_at`.

- `topic` is the topic's `id`, `code`, `name`, `subject_id`, and `subject_name`, embedded so a client
  showing a plan needs no second request to name what it recommends. It is `null` only for an item
  recommending work belonging to no single topic; nothing writes one today.
- `scheduled_for` is `null` on a roadmap item — a roadmap says what order to work in, not which day —
  and set on every weekly item.
- `priority` is where the item falls in its plan, counting from 1. **An order, not a score.**
- `action_type` is `study` on everything generated today. `practice`, `revise`, and `review_mistakes`
  name work the product does not yet model.
- `status` is `planned` on everything generated. PLN-004 moves it between all four values, and
  PLN-005 also marks an overdue item `postponed` on the plan it supersedes.
- `completed_at` is when the learner marked the item completed, and `null` on everything else,
  including a skipped item.

**A superseded plan is readable, and its content and reasons read exactly as they were written.**
That is the point of superseding rather than deleting, and it is why PLN-004 refuses to write into
one — for every status, including taking a skip or a postponement back. The one thing that may move on
a superseded plan is an item's `status`, and only adaptation may move it: it marks work whose day
passed `postponed` as it sets the plan aside, which is a statement about what happened rather than a
rewriting of what was planned.

Errors: `404` `not_found` when no such plan is stored *or it belongs to another learner*; `422`
`validation_error` when the path segment is not a UUID; `409` `conflict` when more than one learner
is stored.

### PLN-004 — `PATCH /api/v1/plan-items/{plan_item_id}`

`plan_item_id` is a UUID. Request body: `status`. It is required, and an unknown field is rejected.
Returns `200` with the whole updated item under `data`, in the shape PLN-003 returns per item.

Contracted by [ADR-021](../adr/ADR-021-plan-item-completion.md) and extended by
[ADR-024](../adr/ADR-024-plan-item-skipping.md) and
[ADR-025](../adr/ADR-025-learner-postponement.md). It needed **no migration** any of the three times:
`plan_items.status` and `completed_at` have existed since `20260806_03`, and PLN-004 is the only code
that writes `completed` or `skipped` and the **second** of the two that write `postponed` — PLN-005
wrote it first.

**All four statuses are accepted: `completed`, `skipped`, `postponed`, and `planned`.** A learner may
move an item to any of them from any of them, so what a learner may *ask for* and what the column may
*hold* now coincide. This **completes [FR-004](../requirements/functional.md#fr-004-plan-adaptation)'s
first acceptance criterion**.

- **`completed`** says the item's planned work happened.
- **`skipped`** says the learner decided it will not happen.
- **`postponed`** says they decided it will not happen *yet*. It is the same value PLN-005 writes for
  work whose day passed with nothing said about it, and it means the same thing either way: the work
  is to be placed again on the plan that replaces this one.
- **`planned`** takes any of the three back.

**`skipped` and `postponed` are statements about *this item*, not about the topic.** Adaptation leaves
either alone and **plans its topic again**, which is what distinguishes both from a completed one. The
next plan therefore treats them identically; the difference is what the record says about the line.
See [PLN-005](#pln-005-post-apiv1study-goalsstudy_goal_idadapt).

**Postponing takes no date and moves nothing by itself.** No request field names a day, `scheduled_for`
is not rewritten, and no adaptation is triggered — the learner asks for that on `/plan`. The work is
placed again when they do.

**An undated roadmap item may be postponed**, as it may be completed or skipped. The endpoint knows
nothing about dated versus undated items.

**Nothing here is one-way.** Sending `planned` puts an item back, and a learner may move directly
between any two of the other three. Nothing treats a statement about work as a verdict, which is the
position [PRG-004](#prg-004-patch-apiv1progresstopicstopic_id) takes on a learning stage.

**Sending the status an item already holds is accepted and writes nothing**, so a repeated form
submission does not fail on its second attempt.

**`completed_at` is not accepted from a client.** It is the server's record of when the learner said
so, read from the same clock a plan's dates come from, so no caller can backdate work. It is set only
while an item is `completed` and cleared by a move to `skipped`, `postponed`, or `planned`. **There is
no `skipped_at` and no `postponed_at`**: nothing records when an item was skipped or postponed.
Neither carries a reason field — nothing stores one, and asking would invite a view about the answer.

**Only the named item moves.** No plan changes, no other item changes — including a roadmap item
naming the same topic as a settled weekly one, which stays `planned` because nothing links the two but
the topic. No learning stage is written: a plan item records whether planned work
happened, not that the topic is understood, which is rule 4 of the
[domain model](../domain/domain-model.md#domain-rules-and-invariants). Nothing is re-planned, and **nothing
is counted** — no completion, skip, or postponement total is reported for a day, a week, or a plan.

**Only an item on an `active` plan may be moved**, which is refused otherwise with `409` `conflict`.
A superseded plan is kept because it reads exactly as it was written, and that refusal covers every
status: there is no exception for taking a skip or a postponement back. The learner is not stranded by
it, because a skipped or postponed topic is planned again on the plan that replaced the one they
marked it on. `draft` and `archived` are constrained and unused, so today that refusal only ever means
superseded.

Errors: `404` `not_found` when no such item is stored *or its plan belongs to another learner*; `422`
`validation_error` when the path segment is not a UUID, when the body names an unknown field or omits
`status`, or when `status` is not one of the four — the `details` entry names
`body.status` with type `unknown_plan_item_status` and never echoes the rejected value; `409`
`conflict` when the item's plan has been superseded, when no learner exists yet, or when more than one
learner is stored.

### PLN-005 — `POST /api/v1/study-goals/{study_goal_id}/adapt`

`study_goal_id` is a UUID. **No request body**: everything adaptation acts on is already stored, so
no caller can adapt toward a preference the learner never set. Returns `201` with the adaptation
under `data`.

Contracted by [ADR-022](../adr/ADR-022-plan-adaptation.md). It needed **no migration**: `plan_items.status` has accepted `postponed` since
`20260806_03`, and this is the first code to write it.

`data` carries `study_goal_id`, `adapted_on`, `plans`, `superseded_plan_ids`,
`postponed_plan_item_ids`, `completed_topic_count`, and `remaining_topic_count`. The plans are the
same shape PLN-003 returns, with their items.

**The learner asks; nothing adapts on its own.** Completing an item re-plans nothing and saving a
study week re-plans nothing — there is no scheduler and no background job. That keeps PLN-004's
promise that only the named item moves.

**A topic with a completed session is not planned again**, wherever on the goal it was completed,
including on a plan long superseded. Superseding a plan does not un-complete the work done under it.
The exclusion is applied before the ordering and placement rules run, so an adapted plan is a real
plan over what remains rather than a generated one with holes in it.

**Overdue work is marked `postponed`** on the plan being set aside, and its topic is re-placed on the
new one. What makes an item overdue is decided in the domain: it is dated before today and nothing has
been said about it. An item dated *today* is not overdue, an undated roadmap item is never overdue,
and a **settled** item is never overdue — `completed` however late the work was done, `skipped`, or
`postponed`. The word describes the **item**, never the learner.

**A skipped or postponed item is left exactly as the learner left it, and its topic is planned
again.** That is the difference between those two and completing: a completed topic is finished with,
while a skipped one is only not happening and a postponed one only not happening yet. Nothing
overwrites either with `postponed` of its own, which would replace the learner's own statement with an
inference about a date, and **`postponed_plan_item_ids` names only what adaptation itself set aside**.
Both topics therefore count toward `remaining_topic_count`, not `completed_topic_count`, and a learner
who still does not want a topic marks it again on the new plan. See
[ADR-024](../adr/ADR-024-plan-item-skipping.md) and
[ADR-025](../adr/ADR-025-learner-postponement.md).

**Adaptation supersedes exactly as PLN-001 does.** The goal's active plans become `superseded`, a new
`roadmap` and — when the week has room — a new `weekly` plan are written, and nothing is deleted.
`monthly` and `daily` remain unwritten.

**The two counts describe the plan, not the learner.** They say how much of the curriculum this plan
covers and why it is shorter than the last one. Nothing is ranked, scored, or congratulated, and this
response reports no total for a day, a week, or a plan — the horizon total belongs to
[PLN-006](#pln-006-get-apiv1study-goalsstudy_goal_idplan-feasibility) alone.

A goal where every topic is completed receives a roadmap with no items and a reason saying so, rather
than an error.

Errors: `404` `not_found` when no such goal is stored *or it belongs to another learner*; `422`
`validation_error` when the path segment is not a UUID; `409` `conflict` when the goal has no active
plan to adapt, when no learner exists yet, or when more than one learner is stored.

Related entities: [study plan](../domain/entities.md#study-plan) and
[plan item](../domain/entities.md#plan-item). Related tables:
[`study_plans`](../database/schema.md#study_plans) and
[`plan_items`](../database/schema.md#plan_items).

### PLN-006 — `GET /api/v1/study-goals/{study_goal_id}/plan-feasibility`

`study_goal_id` is a UUID. Takes no request body and no query parameter: everything it reads is
already stored, so no caller can ask about a week the learner never saved. Returns `200` with the
assessment under `data`.

**It writes nothing.** No plan, no availability slot, no planning preference, and no plan item status
moves because this was asked, and nothing adapts. It is the only planning endpoint that is purely a
read, and a learner may ask as often as they like — which is what keeps the answer current as they
edit their week, where a sentence frozen into `generation_reason` would go stale.

`data` carries `study_goal_id`, `assessed_on`, `verdict`, `reason`, `unknown_reason`,
`horizon_ends_on`, `remaining_topic_count`, `session_minutes`, `session_minutes_chosen_by_planner`,
`study_days`, `available_minutes`, `required_minutes`, `shortfall_minutes`, and
`coverable_topic_count`.

- `assessed_on` is the date in the **learner's own timezone**, from `learners.timezone`. The answer
  depends on it, so it is reported rather than left implicit.
- `verdict` is `sufficient`, `insufficient`, or `unknown`.
- **`unknown` is an answer, not a failure**, and `unknown_reason` says which gap caused it:
  `no_horizon` when the goal aims at neither an examination cycle nor a target date, and
  `no_availability_saved` when no study week is stored. The two are kept apart because they ask the
  learner for different things. A week saved and deliberately **kept free is neither** — that is zero
  minutes, a real answer, so the distinction
  [ADR-018](../adr/ADR-018-weekly-availability-slots.md) keeps between a day kept free and a day never
  set survives here.
- `session_minutes_chosen_by_planner` is `true` when the learner has set no session length and
  LearnFlow used its own 60 minutes. A preference nobody set is never reported as a default.

**How the assessment is made**, in full, because a learner is entitled to know:

- **What the work needs.** One session for each topic still to be worked through.
- **Which topics remain.** Every topic on the goal's **active roadmap except those with a completed
  session anywhere on the goal** — the exclusion PLN-005 applies, so the two cannot disagree. A
  **skipped or postponed** topic still counts, because the next plan places its work again.
- **What time is available.** The minutes the saved week offers on every day from `assessed_on` to the
  horizon, **both ends included**: today can still be studied, and so can the horizon day.
- **The horizon.** The same one PLN-001 plans against — the earlier of the examination window's first
  sitting day and the goal's `target_date`. A horizon that has already passed leaves zero study days
  rather than negative ones.
- **A goal with no active plan** has nothing to assess and reports no topics remaining. A plan that
  does not exist cannot be short of time; PLN-001 is what creates one.

**Everything is reported as counts and durations.** There is deliberately **no percentage, no
completion rate, and no proportion**: `coverable_topic_count` and `remaining_topic_count` are two
counts a client states side by side, never one over the other, per
[terminology](../domain/terminology.md#plan-coverage-counts-are-not-learner-scores).
`shortfall_minutes` is zero when the week is enough and is **never negative** — a surplus is reported
by the verdict instead. Nothing here describes the learner.

Errors: `404` `not_found` when no such goal is stored *or it belongs to another learner*, as for
GOAL-003 and PLN-005; `422` `validation_error` when the path segment is not a UUID; `409` `conflict`
when no learner exists yet to own a plan, or when more than one learner is stored.

## Progress and Study-Activity Endpoints

Supports **FR-005 — Topic Progress and Learning Evidence** and **FR-011 — Progress Overview**.

| ID | Method and path | Purpose | Primary request/result | State |
| --- | --- | --- | --- | --- |
| PRG-001 | `GET /api/v1/progress/overview` | Read learner summary: progress, current plan, revisions due, and priority focus areas. | Overview-ready summary. | Not implemented |
| PRG-002 | `GET /api/v1/progress/topics` | List the learner's recorded topic progress, filterable by curriculum version. | Topic progress collection. | Implemented |
| PRG-003 | `GET /api/v1/progress/topics/{topic_id}` | Read detailed progress/evidence for one topic. | Progress summary, evidence, and next action. | Not implemented |
| PRG-004 | `PATCH /api/v1/progress/topics/{topic_id}` | Record the learner's learning stage for a topic. | Updated topic progress. | Implemented |
| ACT-001 | `POST /api/v1/study-activities` | Record actual study, practice, revision, or mistake-review activity. | Activity record; optional progress/recommendation update. | Not implemented |
| ACT-002 | `GET /api/v1/study-activities` | Read activity history with date/topic filters. | Activity collection. | Not implemented |

The API must not treat a plan-item update, a manual stage update, or one quiz result as automatic permanent mastery.

PRG-002 and PRG-004 are implemented, and their contracts are fixed by
[ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md). Neither accepts a `learner_id`: the
effective learner is resolved server-side, per the [identity assumption](#identity-assumption) above.
Both are synchronous, and both read and write through the `ManageTopicProgress` application use case.

**Material status is not yet recorded anywhere.** PRG-004's original intent line said "material
status or learning stage"; it accepts the stage alone, because
`learner_topic_progress.material_status` is not created — see
[schema.md](../database/schema.md#learner_topic_progress). The field would promise storage the
database has not got, which is the reason GOAL-004 withheld planning preferences until
[ADR-019](../adr/ADR-019-study-goal-planning-preferences.md) created the columns to hold them.

### PRG-002 — `GET /api/v1/progress/topics`

Query parameters `curriculum_version_id` (a UUID, optional), `limit` (1–100, default 25), and
`offset` (0 or greater, default 0). Returns `200` with the `data` array and the `pagination` block
described in [conventions](conventions.md#success-response-shapes), newest first.

Each item carries `id`, `learner_id`, `learning_stage`, `stage_source`, and `topic` — the topic's
`id`, `code`, `name`, `is_trackable`, `subject_id`, and `curriculum_version_id`.

**Only topics the learner has recorded something against are returned.** A topic absent from this
collection has no stored stage, which reads as *Not explored* — the neutral starting state. Listing
every topic is what CUR-003 does; a client showing both joins them by topic identifier. LearnFlow
never creates a progress record the learner did not ask for, so a fresh installation returns an empty
page rather than one row per topic.

`stage_source` is `learner` for a stage the learner set themselves. `derived` and `mixed` are
reserved for a stage produced from quiz or external-test evidence; nothing produces one yet.

An installation where setup has not run has no learner and therefore no records, which is an empty
page rather than a failure. An unknown `curriculum_version_id` returns an empty page rather than
`404`: a filter that matches nothing is an empty result, not a missing record.

`subject_id` and `learning_stage` filters, which this catalogue's original intent line also named,
are **not** accepted. They are compatible additions under
[versioning](versioning.md#compatible-changes-within-a-major-version) and arrive with the screen that
needs them. **Neither screen reading this endpoint has needed one.** The curriculum view and the
progress overview's stages-by-subject panel both want the collection in full and join it to CUR-003
by topic identifier, so a filter would narrow a read they want whole — see
[ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md), which also records why no subject name
is added to this response.

Errors: `422` `validation_error` for a `limit`, `offset`, or `curriculum_version_id` outside those
bounds or shapes; `409` `conflict` when more than one learner is stored.

### PRG-004 — `PATCH /api/v1/progress/topics/{topic_id}`

`topic_id` is a UUID. Request body: `learning_stage`, one of `not_explored`, `building_foundation`,
`developing_confidence`, `practice_ready`, or `strong_understanding`. It is required, and an unknown
field is rejected. Returns `200` with the record under `data`, in the per-item shape PRG-002 returns.

The record comes into existence on the learner's own action, as the learner profile does under
LRN-002, and is rewritten afterwards. A learner may move to any stage from any stage, **including
backwards**: a stage guides the next action rather than scoring the learner, and noticing that a
topic needs more work is worth recording. Recording the stage a topic already holds is accepted and
writes nothing, so a repeated form submission does not fail on its second attempt.

The stored values are `snake_case`; [terminology](../domain/terminology.md) holds the labels a
learner reads. The two are deliberately separate representations, so rewording a label is a text
change rather than a migration over learner rows.

**There is no way to clear a stage.** `learning_stage: null` is rejected rather than treated as a
clear — a stage always holds a value, the same rule LRN-002 applies to `timezone` and GOAL-004 to
`status`. A learner who has changed their mind records `not_explored`, which stores a record saying
they did so deliberately and stays distinguishable from a topic never touched.

A topic that only groups subtopics is refused. `topics.is_trackable` says whether progress can be
recorded directly against a topic, and a grouping heading cannot hold a stage of its own.

Errors: `404` `not_found` when no such topic is stored; `422` `validation_error` when the stage is
not one of the five, when the topic is not trackable, or when the request names an unknown field —
`details` names `body.learning_stage` or `path.topic_id` accordingly, and never echoes the rejected
value; `409` `conflict` when no learner exists yet to own the record, or when more than one learner
is stored.

### PRG-001, PRG-003, ACT-001, and ACT-002 — not implemented

Each waits on something that does not exist rather than on a decision:

- **PRG-001** reports the current plan, revisions due, and priority focus areas. All three now have
  stored facts behind them — `study_plans` and `plan_items` are read by PLN-002 and PLN-003,
  `revision_records` by REV-001, and the *priority focus area* panel is drawn from a plan item whose
  day has passed, a review REV-001 reports as due, and PLN-006's verdict. **Quiz evidence is now
  stored** — QZ-005 writes per-question outcomes to `quiz_attempt_answers` — but nothing draws a
  priority from it, and no *score* exists to draw one from. What PRG-001 still waits on is the
  **external-test and mistake evidence** its purpose also implies, which FR-010 would store and which
  does not exist.

  **The progress overview screen does not use it.** `/progress` is a *reading* of eight existing
  contracts — LRN-001, GOAL-002, PLN-002, PLN-003, PLN-006, REV-001, PRG-002, and CUR-003 — and adds
  **no endpoint, no column, no migration, and no backend change at all**, which is the shape
  [ADR-026](../adr/ADR-026-monthly-study-view.md) used for the monthly study view. It clears none of
  [ADR-023](../adr/ADR-023-daily-study-view.md)'s bar for a new endpoint, because every fact it states
  is already a field of a response. Fixing PRG-001's shape now would make it a public contract that
  the half its own purpose promises would later break, so it stays uncontracted until the evidence
  arrives. Contracted by [ADR-029](../adr/ADR-029-progress-overview.md), and extended by
  [ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md) and
  [ADR-031](../adr/ADR-031-priority-focus-panel.md), neither of which changed a contract here.

  Of [FR-011](../requirements/functional.md#fr-011-progress-overview)'s four acceptance criteria,
  **two are met and a third is partly met**. Met: viewing upcoming study tasks and revisions due, and
  viewing progress by subject and topic — the recorded stages, gathered under each topic's subject on
  `/progress` by joining PRG-002 to CUR-003 in the client, and still shown beside each topic in the
  curriculum view where they are recorded. That second one is met **for the progress LearnFlow
  stores**, which is the learning stage alone: `material_status` is not created and `study_activities`
  does not exist. **Partly met:** priority focus areas, gathered from the three stored facts above and
  explained, and **ranking nothing**, per [ADR-031](../adr/ADR-031-priority-focus-panel.md) — the
  recorded learning stage is deliberately not a signal,
  because selecting some of the five stages would rank them against each other. It is partial because
  no priority is drawn from quiz, test, or mistake evidence — quiz outcomes are now stored but
  nothing ranks or reads them, and the other two are stored nowhere. **Not met:** recent quiz history
  and external test results on this screen; QZ-006 lists attempts on `/practice` and, in full and a
  page at a time, on `/practice/history`, while `/progress` deliberately gains no panel from either,
  because summarising attempts there is the counting
  [terminology](../domain/terminology.md) refuses. This criterion asks for that history **on the
  overview**, so [ADR-034](../adr/ADR-034-checkpoint-practice-history.md) leaves it unmet rather than
  claiming it: a history a learner opens deliberately on the practice screen is not a panel that
  follows them onto an overview. **FR-011 is not met in full.**
- **PRG-003** promises a progress summary, evidence, and a next action. The only evidence stored is
  the stage itself, so today it would return exactly what PRG-002 returns per item.
- **ACT-001** and **ACT-002** need `study_activities`, which is not created.

Three of [FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence)'s six
acceptance criteria are met — marking a topic with one of the five stages, updating it at any time,
and presenting an encouraging next action. Three are not: recording that study material has been
completed, which needs `material_status`; storing quiz, test, mistake, and revision evidence
separately — **quiz and revision evidence now exist**, in `quiz_attempt_answers` and
`revision_records`, while test and mistake evidence need tables that do not; and the rule against
claiming mastery from one signal, which is respected and now exercised, because a quiz outcome
deliberately moves no learning stage.

Related entities: [learner topic progress](../domain/entities.md#learner-topic-progress) and
[topic](../domain/entities.md#topic). Related tables:
[progress and revision schema area](../database/schema.md#schema-areas).

## Revision Endpoints

Supports **FR-006 — Revision Guidance**, which these four endpoints do **not** complete. They deliver
its revision scheduling, its status updates, and its view of what is due. The **resource-and-practice
half of FR-006's second criterion is deferred**: a revision links its topic, and linking resource or
practice suggestions depends on FR-007's resources and FR-009's checkpoint quizzes. **Both now
exist**, and the half stays deferred for a different reason: linking material to a review is done
(RES-002), while suggesting a *quiz* for a topic would be recommending one, and nothing in LearnFlow
recommends. See [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md). FR-006's fourth criterion
considers three of its four inputs — completion, learning stage, and prior revision history. **Quiz
evidence is now stored** but nothing reads it: no revision interval, plan, or learning stage moves on
a quiz result.

| ID | Method and path | Purpose | Primary response | State |
| --- | --- | --- | --- | --- |
| REV-001 | `GET /api/v1/revisions` | List the learner's revisions, earliest due date first. | Revision collection. | Implemented |
| REV-002 | `GET /api/v1/revisions/{revision_id}` | Read one revision record and its topic. | Revision details. | Implemented |
| REV-003 | `PATCH /api/v1/revisions/{revision_id}` | Mark a revision completed, skipped, or postponed, or put it back to due. | Updated revision record. | Implemented |
| REV-004 | `POST /api/v1/revisions/schedule` | Schedule revisions for topics whose finished work is ready to return. | The revisions written, and what was left alone. | Implemented |

All four are implemented and contracted by [ADR-028](../adr/ADR-028-revision-workflow.md). None of
them accepts a `learner_id`: the effective learner is resolved server-side, per the
[identity assumption](#identity-assumption) above. All four are synchronous and read and write
through the `ManageRevisions` application use case.

**REV-004 is not one of the three this catalogue first held.** Something has to create a revision,
and nothing may create one automatically — completing a plan item writes no revision, because that
would move a record the learner did not name (ADR-021). So the learner asks, exactly as they ask for
a plan to be generated or adapted. ADR-028 records the addition, as ADR-022 recorded PLN-005's
departure.

**The learner asks; nothing schedules on its own.** Asking twice creates nothing the second time: a
topic with a revision already waiting, or one the learner has skipped or postponed, is left alone,
and `already_scheduled_topic_count` says how many. The endpoint takes no request body.

**A topic returns an interval after the work it follows**, and the interval comes from the learning
stage the learner recorded — 7 days with none recorded, rising to 21 at `strong_understanding`. Those
are LearnFlow's intervals, named as its own in every revision's `recommendation_reason`. A completed
review schedules the next, which is FR-006's *prior revision history*.

**A revision is not a plan item**, does not appear in any plan, and is untouched by PLN-005: a review
the learner acted on survives the supersede adaptation performs on every active plan of a goal.
**Nothing here writes a learning stage** — a revision records that a review happened, never that a
topic is understood.

**REV-003 mirrors PLN-004.** It accepts `due`, `completed`, `skipped`, and `postponed`, from
whichever the revision holds; every move is allowed and reversible. `completed_at` is read from the
server's clock and cleared by any move off `completed`. There is deliberately no `skipped_at`, no
date, and no reason field. `scheduled` is refused: the column holds it, but nothing collects the date
it would need.

Errors: `404` `not_found` when no such revision is stored *or it belongs to another learner*; `422`
`validation_error` for an unknown status, an unknown filter, a path segment that is not a UUID, or a
body carrying an unknown field; `409` `conflict` when no learner exists yet, or when more than one is
stored.

### REV-001 — `GET /api/v1/revisions`

Query parameters `status` (optional), `due_only` (boolean, default `false`), `limit` (1–100, default
25), and `offset` (0 or greater, default 0). Returns `200` with the `data` array and the `pagination`
block described in [conventions](conventions.md#success-response-shapes), **earliest due date first** —
the order a learner works through them, fixed by the backend so a page cannot be reordered after it
has been sliced.

Each item carries `id`, `topic`, `due_on`, `scheduled_for`, `status`, `trigger_type`,
`recommendation_reason`, `completed_at`, and `is_due`.

- `topic` names the topic to review, with its subject. It is `null` only when the topic is no longer
  stored, which is reported rather than hiding the learner's own record.
- `scheduled_for` is **always null**: naming a day for a review is an approved capability nothing
  writes.
- `is_due` says whether the review is owed today — its day has arrived or passed and nobody has
  settled it. Reported by the backend because what counts as due is a domain rule, so a client cannot
  disagree with it. Unlike an *overdue* plan item, a revision dated **today is due**.
- `recommendation_reason` is written when the revision is created and never rewritten, so the record
  explains itself in the terms that produced its date.

`due_only=true` returns the revisions nobody has settled. An installation where setup has not run has
no learner and therefore no revisions, which is an empty page. Errors: `422` `validation_error` for an
unknown `status`, or a `limit` or `offset` outside those bounds.

### REV-002 — `GET /api/v1/revisions/{revision_id}`

`revision_id` is a UUID. Returns `200` with one revision under `data`, in the same shape REV-001
returns per item. Errors: `404` `not_found` when no such revision is stored *or it belongs to another
learner*; `422` `validation_error` when the path segment is not a UUID.

### REV-003 — `PATCH /api/v1/revisions/{revision_id}`

Request body: `status`, one of `due`, `completed`, `skipped`, or `postponed`. An unknown field is a
`422` rather than being ignored. Returns `200` with the updated revision under `data`.

**Every move between the four is allowed**, from whichever the revision currently holds, and each is
reversible — the shape PLN-004 uses for a plan item. Sending the status a revision already holds is
accepted and changes nothing, so a repeated submission does not fail.

`completed_at` is read from the **server's clock** rather than accepted from a caller, and is cleared
by any move off `completed`. There is deliberately **no `skipped_at`, no date, and no reason field**:
asking why a learner skipped a review would invite the product to form a view about the answer.

**Only the named revision moves** — no other revision, no plan, no plan item, and **no learning
stage**. `scheduled` is refused with a `422`: the column holds it, but nothing collects the date it
would need.

### REV-004 — `POST /api/v1/revisions/schedule`

**No request body.** Everything it reads is already stored, so no caller can schedule toward an
interval the learner never set. Returns `201` with the run under `data`.

`data` carries `scheduled_on`, `created`, `already_scheduled_topic_count`, and `reason`.

- `scheduled_on` is the date in the **learner's own timezone**, from `learners.timezone`.
- `created` holds the revisions written, each in REV-001's item shape with the reason it exists.
- `already_scheduled_topic_count` says how many finished topics were left alone because they already
  have a review waiting or one the learner has settled. A description of **the run**, not a score for
  the learner.
- `reason` says what the run looked at, what it wrote, and what it left alone — including when it
  wrote nothing, which is the common case once a learner has asked twice.

Errors: `409` `conflict` when no learner exists yet to own a revision, or when more than one learner
is stored.

## Resource and Ingestion Endpoints

Supports **FR-007 — Learning Resource Organization**, which RES-001 to RES-004 begin and do not
complete, and supplies the **resource half** of
[FR-006](../requirements/functional.md#fr-006-revision-guidance)'s second criterion, which
[ADR-028](../adr/ADR-028-revision-workflow.md) deferred. The practice half is **deliberately still open**: checkpoint practice exists, but surfacing a quiz beside a review would mean recommending one for a topic, and nothing in LearnFlow recommends. See [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md).

| ID | Method and path | Purpose | Primary request/result | State |
| --- | --- | --- | --- | --- |
| RES-001 | `POST /api/v1/resources` | Register where a piece of study material is, and which topics it covers. | Resource record. | Implemented |
| RES-002 | `GET /api/v1/resources` | List the learner's material, filterable by topic, type, and status. | Resource collection. | Implemented |
| RES-003 | `GET /api/v1/resources/{resource_id}` | Read one resource and its topic links. | Resource details. | Implemented |
| RES-004 | `PATCH /api/v1/resources/{resource_id}` | Update title, resource type, source label, link, topic links, or status. | Updated resource. | Implemented |
| RES-005 | `DELETE /api/v1/resources/{resource_id}` | Request safe removal of a resource and related derived artifacts. | `204` or accepted cleanup operation. | Not implemented |
| RES-006 | `POST /api/v1/resources/{resource_id}/ingestions` | Start/retry text extraction and indexing. | `202` + ingestion reference. | Not implemented |
| RES-007 | `GET /api/v1/resources/{resource_id}/ingestions` | List ingestion attempts/statuses. | Ingestion collection. | Not implemented |
| RES-008 | `GET /api/v1/resource-ingestions/{ingestion_id}` | Read a single ingestion status/failure message. | Ingestion details. | Not implemented |
| RES-009 | `POST /api/v1/resources/{resource_id}/notes` | Keep one of the learner's own written notes against a piece of material. | Resource note. | Implemented |
| RES-010 | `GET /api/v1/resources/{resource_id}/notes` | List the notes kept against one piece of material, filterable by status. | Resource note collection. | Implemented |
| RES-011 | `GET /api/v1/resource-notes/{note_id}` | Read one note. | Resource note details. | Implemented |
| RES-012 | `PATCH /api/v1/resource-notes/{note_id}` | Correct a note's title or text, or put it aside. | Updated resource note. | Implemented |
| RES-013 | `GET /api/v1/resource-notes/search` | Find passages in the learner's own notes for one curriculum topic. | Passages with their note, material, and topic context. | Implemented |

RES-001 to RES-004 are implemented and contracted by
[ADR-032](../adr/ADR-032-learning-resource-catalogue.md). None of them accepts a `learner_id`: the
effective learner is resolved server-side, per the [identity assumption](#identity-assumption) above.
All four are synchronous and read and write through the `ManageResources` application use case.

**Resource endpoints expose safe metadata only. They must not return absolute local filesystem paths
or provider credentials.** That rule is kept by **refusing the input**: `external_reference` accepts
an `http` or `https` address and nothing else, so no local path is stored, and none can therefore be
returned. Material that is not on the web is described by `source_label`, in the learner's own words.

**A resource is metadata, never the material.** Nothing here uploads, downloads, extracts, embeds, or
indexes anything: `storage_key`, `metadata`, and `resource_ingestions` are all absent, and each
arrives with the code that maintains it, per
[ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md). RES-006 to RES-008 wait on that
same table and an extractor.

**RES-009 to RES-012 narrow that sentence on one point and leave the rest standing.** A learner may
keep their **own written notes and copied-out passages** against a piece of material, which is the
first study material LearnFlow stores rather than points at. It is text the learner **typed or pasted
themselves**: still nothing uploaded, still nothing fetched, still no location on their own machine,
still nothing extracted, chunked, embedded, or indexed into a vector store. Searching those notes arrives with [RES-013](#res-013-get-apiv1resource-notessearch) below. See
[ADR-037](../adr/ADR-037-learner-written-resource-notes.md).

**Nothing is deleted.** RES-005 is not implemented: a learner puts material aside with
`status: archived` through RES-004, which is reversible and destroys nothing — the position
[ADR-022](../adr/ADR-022-plan-adaptation.md) took for a superseded plan. RES-005 arrives with the
files and vectors its stated purpose exists to clean up.

**Nothing is recommended, ranked, or counted.** A topic's material is the material the learner linked
to it, in the order this API returns it. No resource is suggested for a topic, promoted above
another, or counted on any response or screen.

### RES-001 — `POST /api/v1/resources`

Request body: `resource_type`, `title`, `source_label` (a string or `null`), `external_reference` (a
string or `null`), and `topic_ids` (a list of UUIDs, empty by default). An unknown field is rejected.
Returns `201` with the resource under `data`.

There is deliberately **no `status`**: every resource is written `registered`, and putting one aside
is a later statement made through RES-004 — the shape PLN-004 uses for a plan item, whose status is
likewise not a creation field.

**This endpoint's original intent line also named "upload/store an eligible source file", which is
not implemented.** Nothing is uploaded: the request is metadata alone, and a file gains somewhere to
live with the storage and ingestion change. Adding it later is a compatible addition under
[versioning](versioning.md#compatible-changes-within-a-major-version), because nothing was ever
accepted for it.

- `resource_type` is one of `pdf`, `note`, `pyq`, `formula_sheet`, or `video_reference`. `image` and
  `attachment` are approved values this build does not accept: both name an uploaded file, and
  nothing uploads one.
- `title` is what the learner calls the material, and is required.
- `source_label` is where the material is, in the learner's own words — a book and chapter, a folder
  they keep, a lecture series. **This is what carries material that is not on the web.**
- `external_reference` must be a full `http` or `https` address. Any other scheme, a bare path, or an
  address naming no host is a `422`.
- **At least one of `source_label` and `external_reference` is required**, so a record can always
  lead the learner back to the material. That is the approved *at least one of `storage_key` or
  `external_reference`* constraint, read for a catalogue that stores no files.
- `topic_ids` may name **any stored topic**, including one that only groups subtopics. That is
  deliberately unlike [PRG-004](#prg-004-patch-apiv1progresstopicstopic_id), which refuses a stage on
  a grouping topic: a stage claims something about understanding a unit of work, while a textbook may
  genuinely cover a whole heading. At most 100 may be named, and a topic named twice is refused
  rather than collapsed — the rule GOAL-005 applies to a day named twice.

A resource response carries `id`, `owner_learner_id`, `resource_type`, `title`, `source_label`,
`external_reference`, `status`, and `topics` — each topic's `id`, `code`, `name`, `subject_id`, and
`subject_name`. `owner_learner_id` is `null` only for curated or shared content, which nothing writes.

Errors: `422` `validation_error` when the type is not one of the five, the title is empty, neither a
label nor a link is given, the link is not an `http` or `https` address, a topic is not stored, a
topic is named twice, more than 100 topics are named, or the request names an unknown field —
`details` names the offending field and never echoes the rejected value. `409` `conflict` when no
learner exists yet to own the resource, or when more than one learner is stored.

### RES-002 — `GET /api/v1/resources`

Query parameters `topic_id` (a UUID, optional), `resource_type` (optional), `status` (optional),
`limit` (1–100, default 25), and `offset` (0 or greater, default 0). Returns `200` with the `data`
array and the `pagination` block, **newest first** — the order every learner-owned collection uses.

`topic_id` is what answers **FR-007's fourth acceptance criterion**, finding the material associated
with a topic, without a client holding the whole collection to filter it. A resource covering a topic
appears once however many links it holds.

**`topics` is filled on a listed resource**, unlike a study plan's `items` under
[PLN-002](#pln-002-get-apiv1study-plans). A link set is bounded at 100 and naming what a resource
covers is the point of the catalogue, where a page of plans each carrying every item would be an
unbounded payload inside a paginated one.

**No status is assumed.** A caller wanting only what is in the catalogue asks for `registered`, and
one wanting what has been put aside asks for `archived`, which is how PLN-002 and REV-001 treat their
own statuses.

A `topic_id` that matches nothing returns an empty page rather than `404`: a filter that matches
nothing is an empty result, not a missing record. An unknown `resource_type` or `status` is different
and is refused — a client asking for `status=ready` has misread the contract, and returning nothing
would let it keep doing so.

There is deliberately **no `subject_id` filter**, which this catalogue's original intent line named.
It is a compatible addition under
[versioning](versioning.md#compatible-changes-within-a-major-version) and arrives with a screen that
needs one; neither screen reading this endpoint does, because both want the collection whole and join
it by topic identifier — the position [PRG-002](#prg-002-get-apiv1progresstopics) takes.

An installation where setup has not run has no learner and therefore no resources, which is an empty
page. Errors: `422` `validation_error` for a `limit`, `offset`, or `topic_id` outside those bounds or
shapes, or for a `resource_type` or `status` outside the documented values — `details` names
`query.resource_type` or `query.status`; `409` `conflict` when more than one learner is stored.

### RES-003 — `GET /api/v1/resources/{resource_id}`

`resource_id` is a UUID. Returns `200` with one resource under `data`, in the shape RES-001 returns.

Errors: `404` `not_found` when no such resource is stored *or it belongs to another learner*; `422`
`validation_error` when the path segment is not a UUID; `409` `conflict` when more than one learner
is stored.

### RES-004 — `PATCH /api/v1/resources/{resource_id}`

`resource_id` is a UUID. Request body: `title`, `resource_type`, `source_label`,
`external_reference`, `status`, and `topic_ids`. All optional; an unknown field is rejected. Returns
`200` with the updated resource.

A field the request omits is left alone; an explicit `null` clears `source_label` or
`external_reference`. `title: null`, `resource_type: null`, and `status: null` are rejected: a
resource always has all three, the rule LRN-002 applies to a timezone and GOAL-004 to a status. The
result must still name a location, so clearing the last of the two is a `422`.

**A supplied `topic_ids` replaces the whole link set**, so a topic left out of one is unlinked and an
empty list — or an explicit `null` — unlinks everything. Omitting the field leaves the links alone.
That is GOAL-005's whole-week replacement applied to a link set, and for the same reason: a form
shows every topic at once, so a topic the learner cleared has to reach the API as a clearance.

**`status` accepts `registered` and `archived` only.** `processing`, `ready`, and `failed` are
approved values this build refuses: each is an ingestion lifecycle state, and `resource_ingestions`
does not exist, so a resource could enter one and never leave it. **Archiving is reversible**, and it
destroys nothing.

Sending the values already stored is accepted and writes nothing, as it is under GOAL-004, GOAL-005,
PLN-004, PRG-004, and REV-003.

**Only the named resource moves.** No other resource, no learning stage, no plan, no plan item, and
no revision — a resource says where material is, never that a topic is understood or that work
happened.

The `/resources` screen calls this endpoint two ways, deliberately kept apart: an **edit** form
sends the five describing fields and never `status`, and an **archive** control sends `status`
alone. Correcting a typo and deciding to stop using something are different statements, so neither
control can make the other by accident.

Errors: `404` `not_found` as for RES-003; `422` `validation_error` when the update names no field to
change, names an unknown type or status, clears the last location, or breaks any rule RES-001
documents; `409` `conflict` when more than one learner is stored.

Related entities: [learning resource](../domain/entities.md#learning-resource) and
[topic](../domain/entities.md#topic). Related tables:
[resources and RAG metadata schema area](../database/schema.md#schema-areas).

### RES-009 — `POST /api/v1/resources/{resource_id}/notes`

`resource_id` is a UUID. Request body: `title` and `body`. An unknown field is rejected. Returns
`201` with the note under `data`.

**This endpoint stores text and does nothing else with it.** It is not sent to any AI, embedding, or
retrieval provider, summarised, or indexed into a vector store. One thing reads a note:
[RES-013](#res-013-get-apiv1resource-notessearch), a local full-text search the learner asks for. Nothing uploads a file, fetches an address, downloads a page, extracts text from a
document, or runs OCR to fill it.

- `title` is what the learner calls the note, so they can find it again without opening it. Required,
  at most 300 characters.
- `body` is what they wrote or pasted. Required, at most **20,000 characters**, and stored **as the
  learner wrote it**: their line breaks, blank lines, and indentation survive. Exactly two things are
  done to it — line terminators are canonicalised to `LF`, and surrounding whitespace is removed.
  The canonicalisation undoes a choice the *transport* made rather than one the learner did: the HTML
  form-data encoding algorithm normalises newlines to `CRLF`, so a form posted with JavaScript
  disabled would otherwise store the same note differently from one posted through a hydrated server
  action. It is plain text: nothing here parses it as markup, and nothing renders it as any.
- There is deliberately **no `status`**: every note is written `active`, and putting one aside is a
  later statement made through RES-012 — the shape RES-001 uses for a resource.
- There is deliberately **no `resource_id` in the body.** The path names it, so a body cannot
  disagree with the resource whose ownership was just checked.
- A note carries **no `topic_ids`**. It inherits the topics its resource covers, so correcting what a
  resource covers moves its notes with it and the two can never disagree.

**One resource holds at most 200 notes**, notes put aside included — a bound on one note is no bound
at all without a bound on their number. **That figure is never reported**: it is read to decide
whether one more note may be written, and reaches no response and no screen, because a count
beside a learner's own writing would measure the learner.

RES-010's `pagination.total` is a different number and is **not** that figure — it is the documented
pagination block every collection carries, per
[ADR-014](../adr/ADR-014-api-response-contract.md). The `/resources` screen **never reads it**, which
is the position [ADR-034](../adr/ADR-034-checkpoint-practice-history.md) fixed for QZ-006 for the
same reason.

A note response carries `id`, `resource_id`, `title`, `body`, and `status`.

Errors: `404` `not_found` when no such resource is stored *or it belongs to another learner*; `409`
`conflict` when the material is **put aside**, because archived material is read-only — the learner
brings it back through RES-004 first — or when more than one learner is stored; `422`
`validation_error` when the title or the text is empty, either is too long, the resource already
holds as many notes as it may, or the request names an unknown field. **No refusal echoes the
learner's text**, which is the [conventions](conventions.md#error-codes) rule applied where it
matters most: the rejected value is their own study material.

### RES-010 — `GET /api/v1/resources/{resource_id}/notes`

`resource_id` is a UUID. Query parameters `status` (optional), `limit`, and `offset`. Returns `200`
with a page of notes under `data`, **newest first**, and the documented pagination block.

**No status is assumed.** A caller wanting only what the learner is using asks for `active`, and one
wanting what has been put aside asks for `archived` — how RES-002, PLN-002, and REV-001 each treat
their own.

**The notes of archived material are readable.** Putting material aside stops it being written to and
takes it off the screens that show a topic's material; it destroys nothing and hides nothing a
learner goes looking for.

There is deliberately **no query parameter that searches note text**. Searching is its own endpoint:
see [RES-013](#res-013-get-apiv1resource-notessearch), which is scoped to one topic rather than to
one resource.

Errors: `404` `not_found` as for RES-009; `422` `validation_error` for a `status` outside the
documented values — `details` names `query.status`; `409` `conflict` when more than one learner is
stored.

### RES-011 — `GET /api/v1/resource-notes/{note_id}`

`note_id` is a UUID. Returns `200` with one note under `data`, in the shape RES-009 returns, and its
text **exactly as the learner stored it**.

Addressed by the note's own identifier rather than nested under its resource - the flat shape
RES-008 already sketches — so a note has one address wherever it is reached from.

Errors: `404` `not_found` when no such note is stored *or its resource belongs to another learner*.
Both are reported as missing: a caller who may not read the note may not learn that its resource
exists either. `409` `conflict` when more than one learner is stored.

### RES-012 — `PATCH /api/v1/resource-notes/{note_id}`

`note_id` is a UUID. Request body: `title`, `body`, and `status`, all optional; an unknown field is
rejected. Returns `200` with the updated note.

A field the request omits is left alone. **No field may be null**: a note always has a title, a body,
and a status, the rule LRN-002 applies to a timezone, GOAL-004 to a status, and RES-004 to a
resource's title. There is nothing to clear.

**A note is corrected in place, as often as the learner likes.** That is where a note differs from a
practice question, whose wording [ADR-035](../adr/ADR-035-practice-question-correction.md) fixes once
a quiz has asked it: a stored attempt is assembled from the live question row, so rewriting a prompt
would rewrite a result the learner already read. **Nothing derived from a note is stored** — [RES-013](#res-013-get-apiv1resource-notessearch) reads one live and keeps nothing — so no record can be
made to disagree with a correction, and no such rule is needed. A correction keeps the same record
and the same identifier.

**`status` accepts `active` and `archived` only.** Archiving **is reversible** and destroys nothing:
there is no `DELETE`, and nothing here removes a note.

A note cannot be moved to another resource - `resource_id` is not an accepted field. It belongs to
the material it was written against.

Sending the values already stored is accepted and writes nothing, as it is under GOAL-004, GOAL-005,
PLN-004, PRG-004, REV-003, and RES-004.

**Only the named note moves.** No other note, no resource, no topic link, no learning stage, no plan,
no plan item, no revision, and no quiz.

The `/resources` screen calls this endpoint two ways, deliberately kept apart, exactly as it does
RES-004: a **correction** form sends `title` and `body` and never `status`, and a **put aside**
control sends `status` alone.

Errors: `404` `not_found` as for RES-011; `409` `conflict` when the note's material is **put aside**,
or when more than one learner is stored; `422` `validation_error` when the update names no field to
change, names an unknown status, empties the title or the text, or breaks any rule RES-009
documents. **No refusal echoes the learner's text.**

Related entities: [resource note](../domain/entities.md#resource-note) and
[learning resource](../domain/entities.md#learning-resource). Related table:
[`resource_notes`](../database/schema.md#resource_notes).

### RES-013 — `GET /api/v1/resource-notes/search`

Query parameter `topic_id`, a UUID, and nothing else. Returns `200` with one search result under
`data`.

**This is retrieval, and there is no mentor.** Nothing here generates an answer, summarises,
paraphrases, or explains; what comes back is the learner's own writing with the material and topic it
came from named beside it. **No AI model, embedding service, vector database, external API, URL
fetcher, or background job is reached or configured** — the search is PostgreSQL's own full-text
search, running locally.

**It runs only when the learner asks.** Nothing triggers a search from a page render or a save.

**The topic is the query.** There is deliberately **no free-text parameter**: the chosen topic's name
supplies the search terms. A typed query is a different feature with its own question about what is
recorded, and **nothing here records anything** — there is no search history.

**Only the learner's own material is searched, and only where they said it covers this topic.** A
note is considered when it is `active`, its resource is `registered` and owned by them, and that
resource is linked to the topic. Archived material drops out, exactly as it does from the curriculum,
revision, and plan screens.

A result carries `topic_id`, `topic_name`, `subject_name`, an `outcome`, and `passages`. Each passage
carries `note_id`, `note_title`, `resource_id`, `resource_title`, `resource_type`, `topic_id`,
`topic_name`, `subject_name`, and `passage`.

**`passage` is plain text and an exact substring of the stored note** — one contiguous stretch, cut
on word boundaries. Nothing is highlighted, marked up, escaped, re-encoded, joined, or elided, so
`vector<int>`, `a < b`, and every other literal arrive exactly as the learner typed them. It is
shorter than the note when the note is long; `note_id` leads to the rest. At most 20 passages are
returned.

**`outcome` names one of four results, and tells the three empty ones apart**, because each asks the
learner to do something different:

- `found` — at least one passage matched.
- `no_linked_material` — nothing is linked to this topic yet.
- `no_active_notes` — material is linked, but carries no active note.
- `no_matching_passage` — active notes exist and none mentions the topic.

**There is no relevance figure, and no count.** Relevance decides the order passages arrive in and is
then discarded; a number beside a learner's own writing would read as a mark on it. No total says how
many notes they have written.

Errors: `404` `not_found` when the topic identifier names nothing stored; `409` `conflict` when no
learner is stored yet, or when more than one is. **No refusal echoes note text.**

Related entities: [resource note](../domain/entities.md#resource-note) and
[topic](../domain/entities.md#topic). Related table:
[`resource_notes`](../database/schema.md#resource_notes).

### FR-007 acceptance criteria

**Two of [FR-007](../requirements/functional.md#fr-007-learning-resource-organization)'s four
acceptance criteria are met in full and two are partly met.** This section is authoritative for
the count.

- *"The learner can register PDFs, notes, PYQs, and references/paths to local video resources"* —
  **partly met.** Each of those kinds can be registered and described. A **path** to a local file
  cannot: `external_reference` accepts a web address alone, because this catalogue must not return an
  absolute local filesystem path. Material that is not on the web is carried by `source_label`. The
  local-file half arrives with the storage and ingestion change that gives a file somewhere to live.
- *"A resource can be linked to one or more subjects, topics, or subtopics"* — **met for topics and
  subtopics**, which are the same table. Subject-level linking is not storable:
  [schema.md](../database/schema.md#resource_topic_links) has no subject equivalent.
- *"LearnFlow records basic resource metadata, including title, type, source location, and linked
  curriculum areas"* — **met in full.**
- *"The learner can find resources associated with a topic"* — **met in full**, by RES-002's
  `topic_id` filter, and on the `/resources`, curriculum, `/revisions`, `/plan`, and `/plan/today`
  screens. The last two were added by
  [ADR-036](../adr/ADR-036-topic-material-on-the-plan-screens.md), which changes no contract here and
  leaves this verdict and the count above unchanged: it adds surfaces rather than capability.

**RES-009 to RES-013 leave all four verdicts and the count above unchanged.** RES-013 searches
material FR-007 already covers rather than adding a way to register, link, describe, or find it; what
it advances is FR-008, below.

Keeping a learner's own written notes against a resource, and searching them, are capabilities
beside FR-007's four criteria rather than any of them: they register nothing, link no topic, record
no resource metadata, and add no way of finding a topic's *material*. What they advance is
[FR-008](../requirements/functional.md#fr-008-grounded-mentor-assistance), which is **not met** —
see [its own count below](#fr-008-acceptance-criteria). See
[ADR-037](../adr/ADR-037-learner-written-resource-notes.md) and
[ADR-038](../adr/ADR-038-local-topic-note-retrieval.md).

## Mentor Endpoints

Supports **FR-008 — Grounded Mentor Assistance**.

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| MNT-001 | `POST /api/v1/mentor/questions` | Ask a learner question with optional topic/resource context. | Mentor answer, source references, suggested next actions. |
| MNT-002 | `GET /api/v1/mentor/availability` | Report whether configured mentor/retrieval capability is ready. | Safe capability status. |

The mentor endpoint must not silently modify learner progress, learning stage, plans, or revisions.

**Neither MNT endpoint is implemented, and there is no mentor.** Nothing in LearnFlow generates an
answer, and no AI provider is configured or reached.

### FR-008 acceptance criteria

**One of [FR-008](../requirements/functional.md#fr-008-grounded-mentor-assistance)'s six acceptance
criteria is partly met and five are not met.** This section is authoritative for the count.

- *"LearnFlow retrieves relevant indexed material before generating an answer when relevant material
  exists"* — **partly met**, by [RES-013](#res-013-get-apiv1resource-notessearch): the learner's own
  notes are retrieved for a topic they choose, locally and deterministically. The half that
  *generates an answer* does not exist, and nothing is *indexed* in the vector sense — the search is
  PostgreSQL full-text over stored text. See
  [ADR-038](../adr/ADR-038-local-topic-note-retrieval.md).
- *"The learner can ask a learning question for a topic"* — **not met.** A learner chooses a topic;
  they ask no question, and nothing answers one.
- *"The mentor can explain concepts, summarize material, answer doubts, and suggest next study
  actions"* — **not met.** Nothing is generated.
- *"The mentor can indicate the resources used for a grounded answer where practical"* — **not met**,
  because there is no answer. RES-013 does name the note, material, and topic behind every passage,
  which is the source-reference shape [retrieval.md](../rag/retrieval.md) asks for.
- *"The initial local AI provider is Ollama"* — **not met.** No AI provider is configured or reached.
- *"A mentor response does not silently update learner progress"* — **not met**, having no mentor
  response; RES-013 writes nothing at all.

## Checkpoint Quiz Endpoints

Supports **FR-009 — Topic Checkpoint Practice**.

**The learner writes every question.** Nothing here is generated by a model, taken from a
previous-year paper, or shipped with the repository: `source_type` is always `curated`, and
`generated` and `verified_pyq` remain constrained and unwritten. See
[ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md).

**No response under this heading carries a score.** There is no total, no mark, no count of correct
answers, and no percentage — a result is a list of per-question outcomes. `quiz_attempts.score` and
the marks columns are not created at all. This is [terminology](../domain/terminology.md)'s rule
against a number that rates the learner, applied to an assessment.

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| QZ-001 | `POST /api/v1/checkpoint-quizzes/generate` | Assemble a checkpoint quiz for one or more topics. | Quiz record with its linked topics and the questions it asks. Rejects a request carrying no topic. |
| QZ-002 | `GET /api/v1/checkpoint-quizzes/{quiz_id}` | Read quiz instructions and learner-safe questions. | Quiz content without expected answers. |
| QZ-003 | `POST /api/v1/checkpoint-quizzes/{quiz_id}/attempts` | Start an attempt. | Attempt record. |
| QZ-004 | `PATCH /api/v1/quiz-attempts/{attempt_id}/answers/{question_id}` | Save/update one submitted answer before final submission. | Saved answer state. **Not implemented**; see below. |
| QZ-005 | `POST /api/v1/quiz-attempts/{attempt_id}/submit` | Submit an attempt's answers and mark them. | Per-question outcomes. **Takes the answers in its body**; see below. |
| QZ-006 | `GET /api/v1/quiz-attempts` | List learner quiz-attempt history. | Attempt collection. |
| QZ-007 | `GET /api/v1/quiz-attempts/{attempt_id}` | Read a completed/in-progress attempt with permitted feedback. | Attempt details. |
| QZ-008 | `POST /api/v1/practice-questions` | Write one practice question against the topics it covers. | Question record with its topics. |
| QZ-009 | `GET /api/v1/practice-questions` | List the questions the learner has written. | Question collection, filterable by topic and status. |
| QZ-010 | `PATCH /api/v1/practice-questions/{question_id}` | Correct a question, set it aside, or bring it back. | Updated question. **Correctable only until a quiz has asked it**; see below. |

QZ-008 to QZ-010 were added by [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md). The
catalogue had no endpoint for creating a question, because who writes one had never been decided.

### QZ-001 — `POST /api/v1/checkpoint-quizzes/generate`

Assembles a quiz from the learner's own `ready` questions for the topics named. **Deterministic,
with no AI provider**: the same topics over the same question bank always produce the same quiz, in
the same order — which is why the catalogued `202` for asynchronous generation is not used.

**Every ready question linked to a chosen topic is asked**, in the order the questions were written.
LearnFlow selects none and leaves none out: choosing which few to ask would be a ranking. There is no
cap, no sampling, and no shuffling, so the length of a quiz is the learner's own decision. A question
linked to two chosen topics is asked once; a **retired** question is left out.

Request: `{"topic_ids": ["…"]}`. **At least one topic is required**, which is
[ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md)'s rule. `422` for no topic, an
unknown topic, a topic named twice, or topics the learner has written no ready question for — a quiz
that asks nothing cannot be attempted, so none is stored. `409` when no learner exists.

Asking again assembles a **new** quiz rather than returning the last one. Nothing is superseded and
nothing is deleted.

### QZ-002 — `GET /api/v1/checkpoint-quizzes/{quiz_id}`

**The response has no field for an expected answer and none for an explanation**, so a quiz open in
a browser cannot be read for its answers. That is enforced by the response shape rather than by
stripping a field. `404` when no such quiz is stored or it belongs to another learner.

### QZ-003 — `POST /api/v1/checkpoint-quizzes/{quiz_id}/attempts`

**Safe to ask for twice.** An unfinished attempt at the same quiz is returned with `200 OK` rather
than a second attempt being created; a newly created attempt is `201 Created`. That is the position
REV-004 takes for a review already waiting.

Takes no request body. `started_at` comes from the server's clock. `404` when no such quiz is stored
or it belongs to another learner.

### QZ-004 — not implemented

Saving one answer before submission needs a client that keeps an attempt open across requests. A
learner submits the whole attempt in one form post instead, which works with no JavaScript. The
endpoint stays catalogued for a build that has a reason to save partial work.

### QZ-005 — `POST /api/v1/quiz-attempts/{attempt_id}/submit`

**Departs from the catalogue by taking a request body**, because QZ-004 does not exist to have saved
the answers first:

```json
{ "answers": [{ "question_id": "…", "option_key": "b" }] }
```

**A question the submission omits is recorded as unanswered** — `submitted_answer` and `is_correct`
both null — **never as wrong**. An empty `answers` list is allowed and marks every question
unanswered.

The response carries, for each question in the quiz's own order: what the learner chose, whether it
matches the expected answer, the expected answer, and the explanation the question was written with.
**It carries no score, no marks, and no count.**

`409` when the attempt has already been marked — a record of what happened is not edited afterwards,
which is the position PLN-004 takes for an item on a superseded plan; the learner starts a new
attempt instead. `422` for an answer naming a question the quiz does not ask, a question answered
twice, or an option the question does not offer. `404` when the attempt is not the learner's.

Marking writes **no learning stage, no plan, no plan item, and no revision**. A checkpoint says what
happened in one attempt; it does not claim a topic is understood.

### QZ-006 — `GET /api/v1/quiz-attempts`

Newest first, paginated with `limit` and `offset`. **Nothing is counted, totalled, or compared**: the
collection is a list of what happened, and no attempt is set against another.

A listed attempt carries the **same shape** as a read one, so it includes every question's outcome.
That is deliberate — a list that emptied a field the same schema populates elsewhere would read as
"this attempt had no questions" — and its cost is a payload that grows with the learner's own question
bank. See [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md).

**The checkpoint practice history reads it, outcomes and all.** `/practice/history` shows every
attempt a page at a time, with what became of each question, and `/practice` shows the most recent —
so the payload above is now what the screens are built from, and the *separate summary shape* ADR-033
named as its eventual fix is deliberately not taken. Paging uses the `limit` and `offset` this
endpoint has always accepted; **no query parameter is added**, and nothing about this contract
changes. `pagination.total` is **never read** by either screen: on this endpoint it is the count of
the learner's quizzes, which [terminology](../domain/terminology.md) forbids showing by name, so
whether an older page exists is decided by asking for one record more than a page holds. See
[ADR-034](../adr/ADR-034-checkpoint-practice-history.md).

### QZ-007 — `GET /api/v1/quiz-attempts/{attempt_id}`

An attempt still `in_progress` reads back **without** its expected answers and explanations, so
opening a result before submitting reveals nothing.

### QZ-008 — `POST /api/v1/practice-questions`

Records one multiple-choice question the learner has written:

```json
{
  "prompt": "How many bits are needed to address 1 KiB?",
  "options": ["8", "10", "16", "1024"],
  "correct_option_index": 1,
  "explanation": "1 KiB is 2^10 bytes, so ten bits address it.",
  "topic_ids": ["…"]
}
```

**Option keys are assigned by LearnFlow from each option's position** — the first is `a`, the second
`b` — and are never accepted from a caller, so a stored expected answer always names an option the
question offers. Between two and six options; two options with identical wording are refused, because
a learner choosing the other one would be marked wrong for the same answer.

**At least one topic is required**: a quiz is assembled by topic, so a question covering none could
never be asked. A question may cover **any** stored topic, including one that only groups subtopics —
following RES-001 rather than PRG-004.

There is no `status`, no `source_type`, and no `question_type` field: a question is written `ready`,
`curated`, and `multiple_choice`. `409` when no learner exists.

### QZ-009 — `GET /api/v1/practice-questions`

Filterable by `topic_id` and `status`, paginated with `limit` and `offset`. **No status is assumed**:
a caller wanting only what a quiz may ask asks for `ready`, and one wanting what has been set aside
asks for `retired` — how PLN-002, REV-001, and RES-002 treat their own.

**This response carries the expected answers**, because it is the author reading back what they
wrote. A quiz being taken reads QZ-002 instead.

### QZ-010 — `PATCH /api/v1/practice-questions/{question_id}`

Carries a `status`, the question's content, or both. An empty body is `422`.

**A question may be corrected only until a quiz has asked it.** A past result is assembled from the
**live** question row, and `quiz_attempt_answers` references the question by identifier, so once a
quiz asks it the wording is fixed: correcting it would change what an attempt already marked against
it says the learner answered. That is `409`, and the learner sets the question aside and writes
another instead — both stay readable. A question no quiz holds has no attempt referencing it and no
history to rewrite. Contracted by [ADR-035](../adr/ADR-035-practice-question-correction.md), which
amends [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md) on this one point.

**A question already set aside is read-only** and is `409` too: bring it back, then correct it, which
is RES-004's rule for archived material. Both refusals are read from what is **stored**, never from
the request, so a caller cannot edit an asked question by also asking to bring it back.

**The content travels as one group** — `prompt`, `options`, `correct_option_index`, and `topic_ids`
together, or none of them; a partly supplied group is `422`. An `explanation` left out of a supplied
group is **cleared**, which is the group-replacement rule GOAL-001 and GOAL-005 follow. Option keys
are **reassigned by position**, exactly as when the question was written, so a stored expected answer
always names an option the question offers. The topic links are replaced wholesale.

A correction is **the same question said better**: the identifier is kept, no second record is
written, and the order a quiz asks in does not move.

`ready` and `retired` only for `status`, in either direction. **Retiring is reversible and deletes
nothing**: a retired question is asked by no *new* quiz, and goes on being asked by every quiz
already assembled from it. `404` when the question is not the learner's.

**No field reports whether a question may still be corrected.** QZ-009 gains none, so a client offers
the correction and shows the refusal when one arrives.

### FR-009 acceptance criteria

**Three of [FR-009](../requirements/functional.md#fr-009-topic-checkpoint-practice)'s six acceptance
criteria are met in full, two are partly met, and one is unmet.** This section is authoritative for
the count.

- *"The learner can request a short topic-focused checkpoint quiz covering one or more topics; every
  quiz covers at least one topic"* — **met in full.** *Short* is the learner's own decision: the quiz
  asks every question they wrote for the topics they chose, so LearnFlow neither lengthens nor
  shortens it.
- *"The quiz can use relevant notes/PYQs as context when available"* — **unmet.** It needs retrieval,
  which does not exist; nothing here reads a resource.
- *"The learner can submit answers and receive basic feedback"* — **met in full**, over QZ-005: each
  question reads back as correct, not correct, or unanswered, with the expected answer and the
  explanation.
- *"Objective answers can be scored automatically"* — **met in full.** Every answer is marked
  deterministically by a pure domain rule. No *total* is produced, deliberately; see below.
- *"The product stores the attempt, answers, score, and identified mistakes"* — **partly met.** The
  attempt and its answers are stored. **No score is**, because
  [terminology](../domain/terminology.md) forbids a number that rates the learner and
  [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md) resolves that conflict in terminology's
  favour. **No mistake is**, because `mistake_evidence` has four discovery-source foreign keys of
  which two reference tables that do not exist; it arrives with FR-010.
- *"Quiz results inform learning-stage, practice, and revision recommendations but do not alone prove
  mastery"* — **partly met**, and deliberately from the second half. Nothing here writes a learning
  stage, reorders a plan, or schedules a revision, so no result claims mastery. Informing a
  recommendation waits on the stored evidence above.

## External Test Result Endpoints

Supports **FR-010 — External Test Result Tracking**.

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| EXT-001 | `POST /api/v1/external-test-results` | Manually record a test-series/mock result. | Test-result record. |
| EXT-002 | `GET /api/v1/external-test-results` | List learner-entered results, filterable by source, type, and date. | Result collection. |
| EXT-003 | `GET /api/v1/external-test-results/{result_id}` | Read one result with subject/topic evidence and mistakes. | Result details. |
| EXT-004 | `PATCH /api/v1/external-test-results/{result_id}` | Correct manually entered result data or add evidence. | Updated result. |
| EXT-005 | `DELETE /api/v1/external-test-results/{result_id}` | Remove a learner-entered result. | `204 No Content`. |

These are manual learner-data endpoints. The MVP does not include Testbook/Made Easy scraping, credentials, or direct provider integrations.

## Endpoint Implementation Order

Implement in an order that enables one working learner flow:

1. Operational health and curriculum reads. **Done** — OPS-001 and CUR-001 to CUR-003.
2. Learner setup and study-goal creation. **Done** — EXM-001, LRN-001, LRN-002, and GOAL-001 to
   GOAL-004, contracted by [ADR-016](../adr/ADR-016-learner-onboarding-api-contracts.md); GOAL-005,
   contracted by [ADR-018](../adr/ADR-018-weekly-availability-slots.md); and the planning preferences
   GOAL-001 and GOAL-004 accept, contracted by
   [ADR-019](../adr/ADR-019-study-goal-planning-preferences.md).
3. Progress reads/updates and basic study activities. **Partly done** — PRG-002 and PRG-004 record a
   learning stage and read it back, contracted by
   [ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md). PRG-003, ACT-001, and ACT-002 wait on
   the study-activity records described above. **PRG-001 waits on the quiz, external-test, and
   mistake evidence alone** — the plan, the revisions, and now a priority focus drawn from stored
   dates and statuses all exist without it — and the `/progress` screen that gathers them is a
   *reading* of eight existing contracts rather than a consumer of it, per
   [ADR-029](../adr/ADR-029-progress-overview.md),
   [ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md) — which made PRG-002 one of the
   eight without changing it — and [ADR-031](../adr/ADR-031-priority-focus-panel.md), which added no
   read at all.
4. Plan generation/read/update. **Done** — PLN-001, PLN-002, and PLN-003 generate a plan and read
   it back, contracted by [ADR-020](../adr/ADR-020-initial-study-plan-generation.md); PLN-004 marks
   one of its items completed, contracted by
   [ADR-021](../adr/ADR-021-plan-item-completion.md) and extended to accept `skipped` by
   [ADR-024](../adr/ADR-024-plan-item-skipping.md) and `postponed` by
   [ADR-025](../adr/ADR-025-learner-postponement.md); and PLN-005 rebuilds a plan around what
   happened, contracted by [ADR-022](../adr/ADR-022-plan-adaptation.md). **FR-004's first criterion
   is met in full**: a learner can explicitly mark an item `completed`, `skipped`, or `postponed`,
   and take any of them back. Reporting that a learner's week cannot reach their horizon — FR-004's
   third criterion — is **now built too**, over PLN-006, so **all three of FR-004's acceptance
   criteria are met**.
5. Revision reads/updates. **Done** — REV-001 to REV-004, per [ADR-028](../adr/ADR-028-revision-workflow.md).
6. Resource registration and ingestion status. **Partly done** — RES-009 to RES-012 keep the learner's own written notes against a piece of material, which is storage alone; RES-001 to RES-004 catalogue the learner's own study material and link it to topics, contracted by [ADR-032](../adr/ADR-032-learning-resource-catalogue.md), with migration `20260816_01` creating `resources` and `resource_topic_links`. RES-005 to RES-008 wait on file storage and an extractor, neither of which exists; **RES-005 also waits on a reason to delete**, since archiving through RES-004 is reversible and destroys nothing.
7. Mentor questions and grounded retrieval.
8. Checkpoint quizzes and attempts. **Partly done** — QZ-001, QZ-002, QZ-003, QZ-005, QZ-006, and QZ-007 assemble a quiz from the learner's own questions, run an attempt at it, and read the result back, and QZ-008 to QZ-010 hold the question bank they are built from, contracted by [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md), with migration `20260818_01` creating the whole assessment area. **QZ-004 waits on a client with a reason to save partial work.** Nothing is generated by a model and no question content ships with the repository, so `generated` and `verified_pyq` stay unwritten; and **no response carries a score**, which is the conflict ADR-033 resolves in terminology's favour.
9. External test result entry and analysis.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](../adr/ADR-011-sqlalchemy-persistence-implementation.md) — the per-milestone schema ordering these endpoints follow
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — what a study goal aims at, and the deferral ADR-016 discharges
- [ADR-014: Fix the public HTTP API response contract](../adr/ADR-014-api-response-contract.md) — the envelope, pagination block, and error codes every endpoint here returns
- [ADR-016: Fix the learner setup API contracts](../adr/ADR-016-learner-onboarding-api-contracts.md) — the request and response fields of EXM-001, LRN-001, LRN-002, and GOAL-001 to GOAL-004
- [ADR-017: Record manual topic progress as a learner-owned stage](../adr/ADR-017-topic-progress-api-and-schema.md) — the request and response fields of PRG-002 and PRG-004, and why the other four progress endpoints stay uncontracted
- [ADR-018: Store weekly availability as named days replaced a week at a time](../adr/ADR-018-weekly-availability-slots.md) — the request and response fields of GOAL-005, and the `availability` object every goal response carries
- [ADR-019: Store planning preferences as typed columns replaced as a group](../adr/ADR-019-study-goal-planning-preferences.md) — the `planning_preferences` group GOAL-001 and GOAL-004 accept, and the criterion it completes
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](../adr/ADR-020-initial-study-plan-generation.md) — the request and response fields of PLN-001 to PLN-003, and the rules a generated plan follows
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](../adr/ADR-021-plan-item-completion.md) — the request and response fields of PLN-004, and the reversibility every status it accepts inherits
- [ADR-022: Adapt a study plan by rebuilding it around what happened](../adr/ADR-022-plan-adaptation.md) — the request and response fields of PLN-005, the path it departs from, and the first write of `postponed`
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](../adr/ADR-023-daily-study-view.md) — the daily study view that consumes five of these contracts and adds none
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](../adr/ADR-024-plan-item-skipping.md) — the third status PLN-004 accepts, and what a skip does to a later adaptation
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](../adr/ADR-025-learner-postponement.md) — the fourth status PLN-004 accepts, and the criterion it completes
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](../adr/ADR-026-monthly-study-view.md) — the monthly study view that consumes four of these contracts and adds none
- [ADR-027: Report whether the saved week reaches the horizon, as a read-only planning rule](../adr/ADR-027-plan-feasibility.md) — the contract PLN-006 answers, and why it is the one planning endpoint that only reads
- [API conventions](conventions.md)
- [API versioning](versioning.md)
- [Functional requirements](../requirements/functional.md)
- [Domain model](../domain/domain-model.md)
- [Domain entities](../domain/entities.md) — the entities the implemented endpoints return
- [Database schema](../database/schema.md)
- [Database migrations](../database/migrations.md) — the seed that loads the rows the curriculum endpoints serve
- [Delivery milestones](../roadmap/milestones.md) — which endpoints each milestone delivers
- [ADR-028: Schedule revisions from finished work, on the learner's ask](../adr/ADR-028-revision-workflow.md) — the four revision contracts, and the one this catalogue did not hold
- [ADR-029: Show the progress overview as a reading of what is stored, counting nothing of its own](../adr/ADR-029-progress-overview.md) — the screen that gathered six of these contracts and added none, and why PRG-001 stays unimplemented
- [ADR-030: Gather the recorded learning stages by subject, listing them rather than counting them](../adr/ADR-030-learning-stages-by-subject-panel.md) — the seventh and eighth contracts that screen reads, PRG-002 and CUR-003, and why neither gains a filter or a field
- [ADR-031: Draw priority focus from facts backend rules already decided, ranking nothing](../adr/ADR-031-priority-focus-panel.md) — the panel that added no read and no contract, and what PRG-001 waits on now
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](../adr/ADR-032-learning-resource-catalogue.md) — the four resource contracts above, why the other four stay unimplemented, and what a resource may point at
- [ADR-037: Store the learner's own written notes against a learning resource](../adr/ADR-037-learner-written-resource-notes.md) — RES-009 to RES-012, and the boundary around what they store
- [ADR-038: Retrieve passages from a learner's own notes locally, when they ask](../adr/ADR-038-local-topic-note-retrieval.md) — RES-013, and why it sits in the resource family rather than the mentor one
- [ADR-034: Show the checkpoint-practice history as a paged reading of stored attempts, counting nothing](../adr/ADR-034-checkpoint-practice-history.md) — why the history reads QZ-006 unchanged, and why `pagination.total` is never read
- [ADR-035: Let a practice question be corrected until a quiz has asked it](../adr/ADR-035-practice-question-correction.md) — QZ-010's content group, and the two `409` refusals
