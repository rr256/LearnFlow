---
title: LearnFlow API Endpoint Catalog
status: approved
owner: architecture-and-api
last_updated: 2026-08-06
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
planning inputs beside availability, and nothing consumes one yet.

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
week into an hours figure is planning work, and PLN-001 is what should do it with the trade-offs
visible.

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

**Four of [FR-002](../requirements/functional.md#fr-002-initial-learner-setup)'s five acceptance
criteria are met in full, and one not at all.** This section is authoritative for the count; documents
that cite it link here rather than repeating it.

Met in full: setting a target examination schedule or completion date; setting available study time and
basic planning preferences; confirming the active learning program; and reviewing the saved setup
without re-entering it, which the home screen reads back over LRN-001, GOAL-002, and EXM-001.

- *"The learner can set available study time and basic planning preferences"* — **met in full**, having
  been partly met since GOAL-005 arrived. Available study time is set through GOAL-005; planning
  preferences are set through GOAL-001 and GOAL-004, contracted by
  [ADR-019](../adr/ADR-019-study-goal-planning-preferences.md), which creates the two columns
  [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md) had held back. Both are read back on
  the setup screen and on the home screen.

  **Nothing consumes either yet.** No plan is generated, no week is totalled, and no preference is
  ranked or scored. The criterion is about what a learner can *set*, which they now can; what reads it
  arrives with [Milestone 3](../roadmap/milestones.md#milestone-3-planning-and-revision).
- *"The learner can start with no previous progress and still receive an initial plan"* — **unmet.**
  No plan is generated at all. PLN-001 arrives with
  [Milestone 3](../roadmap/milestones.md#milestone-3-planning-and-revision).

## Planning Endpoints

Supports **FR-003 — Study Timeline and Plan** and **FR-004 — Plan Adaptation**.

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| PLN-001 | `POST /api/v1/study-plans/generate` | Generate or replan roadmap/monthly/weekly/daily recommendations for a goal. | Created plan; reason for generation/replan. |
| PLN-002 | `GET /api/v1/study-plans` | List plans, filterable by goal, type, status, and period. | Plan collection. |
| PLN-003 | `GET /api/v1/study-plans/{plan_id}` | Read one plan and its ordered items. | Plan + plan items. |
| PLN-004 | `PATCH /api/v1/plan-items/{plan_item_id}` | Mark a planned item completed, skipped, or postponed. | Updated plan item. |
| PLN-005 | `POST /api/v1/study-plans/{plan_id}/adapt` | Request an updated plan after missed work or changed availability. | New/superseding plan or accepted operation. |

## Progress and Study-Activity Endpoints

Supports **FR-005 — Topic Progress and Learning Evidence** and **FR-011 — Progress Overview**.

| ID | Method and path | Purpose | Primary request/result | State |
| --- | --- | --- | --- | --- |
| PRG-001 | `GET /api/v1/progress/overview` | Read learner summary: progress, current plan, revisions due, and priority focus areas. | Dashboard-ready overview. | Not implemented |
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
needs them.

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

- **PRG-001** reports the current plan, revisions due, and priority focus areas. `study_plans`,
  `plan_items`, and `revision_records` all arrive with
  [Milestone 3](../roadmap/milestones.md#milestone-3-planning-and-revision).
- **PRG-003** promises a progress summary, evidence, and a next action. The only evidence stored is
  the stage itself, so today it would return exactly what PRG-002 returns per item.
- **ACT-001** and **ACT-002** need `study_activities`, which is not created.

Three of [FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence)'s six
acceptance criteria are met — marking a topic with one of the five stages, updating it at any time,
and presenting an encouraging next action. Three are not: recording that study material has been
completed, which needs `material_status`; storing quiz, test, mistake, and revision evidence
separately, which needs those tables; and the rule against claiming mastery from one signal, which is
respected but not yet exercised, because only one kind of signal exists.

Related entities: [learner topic progress](../domain/entities.md#learner-topic-progress) and
[topic](../domain/entities.md#topic). Related tables:
[progress and revision schema area](../database/schema.md#schema-areas).

## Revision Endpoints

Supports **FR-006 — Revision Guidance**.

| ID | Method and path | Purpose | Primary response |
| --- | --- | --- | --- |
| REV-001 | `GET /api/v1/revisions` | List due/scheduled/completed revision records. | Revision collection. |
| REV-002 | `GET /api/v1/revisions/{revision_id}` | Read one revision record and linked topic context. | Revision details. |
| REV-003 | `PATCH /api/v1/revisions/{revision_id}` | Mark a revision completed, skipped, scheduled, or postponed. | Updated revision record. |

## Resource and Ingestion Endpoints

Supports **FR-007 — Learning Resource Organization**.

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| RES-001 | `POST /api/v1/resources` | Register resource metadata and upload/store an eligible source file or reference. | Resource record. |
| RES-002 | `GET /api/v1/resources` | List learner-accessible resources, filterable by type, topic, subject, or status. | Resource collection. |
| RES-003 | `GET /api/v1/resources/{resource_id}` | Read resource metadata, topic links, and ingestion status. | Resource details. |
| RES-004 | `PATCH /api/v1/resources/{resource_id}` | Update title, source label, metadata, or topic links. | Updated resource. |
| RES-005 | `DELETE /api/v1/resources/{resource_id}` | Request safe removal of a resource and related derived artifacts. | `204` or accepted cleanup operation. |
| RES-006 | `POST /api/v1/resources/{resource_id}/ingestions` | Start/retry text extraction and indexing. | `202` + ingestion reference. |
| RES-007 | `GET /api/v1/resources/{resource_id}/ingestions` | List ingestion attempts/statuses. | Ingestion collection. |
| RES-008 | `GET /api/v1/resource-ingestions/{ingestion_id}` | Read a single ingestion status/failure message. | Ingestion details. |

Resource endpoints expose safe metadata only. They must not return absolute local filesystem paths or provider credentials.

## Mentor Endpoints

Supports **FR-008 — Grounded Mentor Assistance**.

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| MNT-001 | `POST /api/v1/mentor/questions` | Ask a learner question with optional topic/resource context. | Mentor answer, source references, suggested next actions. |
| MNT-002 | `GET /api/v1/mentor/availability` | Report whether configured mentor/retrieval capability is ready. | Safe capability status. |

The mentor endpoint must not silently modify learner progress, learning stage, plans, or revisions.

## Checkpoint Quiz Endpoints

Supports **FR-009 — Topic Checkpoint Practice**.

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| QZ-001 | `POST /api/v1/checkpoint-quizzes/generate` | Generate/select a checkpoint quiz for one or more topics. | Quiz record with its linked topics; may return `202` if generation is asynchronous. Reject a request carrying no topic. |
| QZ-002 | `GET /api/v1/checkpoint-quizzes/{quiz_id}` | Read quiz instructions and learner-safe questions. | Quiz content without expected answers. |
| QZ-003 | `POST /api/v1/checkpoint-quizzes/{quiz_id}/attempts` | Start an attempt. | Attempt record. |
| QZ-004 | `PATCH /api/v1/quiz-attempts/{attempt_id}/answers/{question_id}` | Save/update one submitted answer before final submission. | Saved answer state. |
| QZ-005 | `POST /api/v1/quiz-attempts/{attempt_id}/submit` | Submit and evaluate an attempt. | Score, feedback, mistakes, and updated recommendations. |
| QZ-006 | `GET /api/v1/quiz-attempts` | List learner quiz-attempt history. | Attempt collection. |
| QZ-007 | `GET /api/v1/quiz-attempts/{attempt_id}` | Read a completed/in-progress attempt with permitted feedback. | Attempt details. |

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
   [ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md). PRG-001, PRG-003, ACT-001, and
   ACT-002 wait on the plan, revision, and study-activity records described above.
4. Plan generation/read/update.
5. Revision reads/updates.
6. Resource registration and ingestion status.
7. Mentor questions and grounded retrieval.
8. Checkpoint quizzes and attempts.
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
- [API conventions](conventions.md)
- [API versioning](versioning.md)
- [Functional requirements](../requirements/functional.md)
- [Domain model](../domain/domain-model.md)
- [Domain entities](../domain/entities.md) — the entities the implemented endpoints return
- [Database schema](../database/schema.md)
- [Database migrations](../database/migrations.md) — the seed that loads the rows the curriculum endpoints serve
- [Delivery milestones](../roadmap/milestones.md) — which endpoints each milestone delivers
