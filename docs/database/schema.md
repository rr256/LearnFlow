---
title: LearnFlow Database Schema
status: approved
owner: architecture-and-data
last_updated: 2026-08-18
related:
  - ../adr/ADR-028-revision-workflow.md
  - ../adr/ADR-032-learning-resource-catalogue.md
  - ../adr/ADR-033-checkpoint-practice-workflow.md
  - ../adr/ADR-035-practice-question-correction.md
  - ../00-project-context.md
  - overview.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - migrations.md
  - ../adr/ADR-011-sqlalchemy-persistence-implementation.md
  - ../adr/ADR-012-curriculum-seed-and-reconciliation.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
  - ../adr/ADR-016-learner-onboarding-api-contracts.md
  - ../adr/ADR-017-topic-progress-api-and-schema.md
  - ../adr/ADR-018-weekly-availability-slots.md
  - ../adr/ADR-019-study-goal-planning-preferences.md
  - ../adr/ADR-020-initial-study-plan-generation.md
  - ../adr/ADR-021-plan-item-completion.md
  - ../adr/ADR-022-plan-adaptation.md
  - ../adr/ADR-024-plan-item-skipping.md
  - ../adr/ADR-025-learner-postponement.md
  - ../roadmap/milestones.md
  - ../api/endpoints.md
---

# LearnFlow Database Schema

## Purpose

Define the initial logical PostgreSQL schema for LearnFlow. This is the baseline for SQLAlchemy models and Alembic migrations, not executable SQL.

## Implementation Status

Every table below is approved. Tables are created one schema area per migration, in the milestone
that introduces the code reading them, per [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md).

The areas are those in [Schema Areas](#schema-areas) below; the milestones are defined in
[delivery milestones](../roadmap/milestones.md). Two areas span more than one milestone, so their
tables arrive in more than one migration.

| Schema area | State |
| --- | --- |
| Curriculum | Implemented — migrations `20260731_01_create_curriculum_tables` and `20260731_02_add_topic_code_unique_constraint`, populated by the idempotent seed described in [migrations](migrations.md#the-curriculum-seed). |
| Examination schedule | Implemented — migration `20260801_01_create_examination_schedule_and_learner_goal_tables`, populated by the idempotent seed described in [migrations](migrations.md#the-examination-schedule-seed). |
| Learner planning | Implemented — `learners` and `study_goals` arrive in migration `20260801_01`, `availability_slots` in `20260806_01`, whose `day_of_week` is stored as a day *name* rather than the `smallint` documented [below](#availability_slots), `study_goals`' planning preferences in `20260806_02`, as two typed columns rather than the `planning_preferences jsonb` documented [below](#study_goals), and `study_plans` and `plan_items` in `20260806_03`, whose controlled columns are `varchar(32)` guarded by a `CHECK` rather than the `text` documented [below](#study_plans). |
| Progress and revision | Partly implemented — `learner_topic_progress` arrives in migration `20260805_01`, with three of its documented columns deliberately not created; see [below](#learner_topic_progress). `revision_records` arrives in `20260813_01` with the revision code that reads it, per [ADR-028](../adr/ADR-028-revision-workflow.md). `study_activities` still arrives with the code that records study work. |
| Resources and RAG metadata | Partly implemented — `resources` and `resource_topic_links` arrive in migration `20260816_01` with the catalogue code that reads them (RES-001 to RES-004), per [ADR-032](../adr/ADR-032-learning-resource-catalogue.md); two columns of `resources` are deliberately not created, and `resource_ingestions` arrives with the extractor and vector index it tracks. See [below](#resources). |
| Assessment | Implemented — all seven tables arrive in migration `20260818_01` with the checkpoint-practice code that reads them (QZ-001 to QZ-010), per [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md). Seven columns are deliberately not created and one is added beyond this document; see [the area review](#assessment-area-review-2026-08-18). |
| External evidence | Not implemented — arrives with FR-010, in the second half of Milestone 5. `mistake_evidence` waits with it: two of its four discovery sources reference tables in this area. |

A pending area's columns are an approved target, not a committed shape. One of the three details this
document recorded as undecided **remains so** — numeric precision for score and marks columns. It was
*not* settled by the assessment migration, because that change creates none of those columns:
[ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md) reports per-question outcomes and no total,
so nothing would have read the answer. It is decided by the change that first stores a mark. The other
two are settled:

- The **default learner timezone** was decided when `learners` was created: it comes from
  `APP_DEFAULT_TIMEZONE`, which defaults to `Asia/Kolkata`. See
  [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md) and the
  [configuration catalogue](../deployment/environments.md#application).
- The **`day_of_week` numbering convention** was **retired rather than chosen** when
  `availability_slots` was created. The column holds a `snake_case` day *name*, so no numbering exists
  to document or to mis-map. See [ADR-018](../adr/ADR-018-weekly-availability-slots.md) and
  [`availability_slots`](#availability_slots) below.

SQLAlchemy models for implemented tables live in `backend/app/infrastructure/persistence/`.

## Conventions

- Primary keys use `uuid`, generated by the application rather than by a database default, so an entity carries its identity before it is written.
- Timestamps use timezone-aware UTC `timestamptz`.
- Tables that represent durable records include `created_at` and `updated_at` unless noted otherwise. Both default to `now()`; `updated_at` is refreshed by the ORM on update, not by a database trigger.
- Short controlled identifiers — codes, labels, and enumerated values — use a bounded `varchar`; free-form learner-facing prose such as `name` and `description` uses `text`. The bound is a typo guard, not a storage optimisation: PostgreSQL stores both identically. A value that outgrows its bound is a migration, so pending schema areas record `text` until their first migration fixes a width.
- Enumerated values are implemented as validated text fields with a `CHECK` constraint rather than PostgreSQL enums, so adding a value stays an ordinary constraint change. The API/domain vocabulary remains authoritative. See [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md).
- Constraints and indexes are named by a convention on the SQLAlchemy metadata, so a migration can drop by name what an earlier migration created.
- Foreign keys use database constraints. Complex cross-row rules may be validated in application logic where a simple constraint is insufficient.
- PostgreSQL 15 or later is required: the `topics` uniqueness constraint depends on `NULLS NOT DISTINCT`. Local development and CI both run PostgreSQL 18.
- `jsonb` is reserved for flexible provider/resource payloads, not core relational concepts.
- Single-user MVP records still include `learner_id` where the data is learner-owned.

## Schema Areas

```text
Curriculum
  learning_programs → curriculum_versions → subjects → topics → topic_relationships

Examination schedule
  learning_programs → examination_schedules → examination_periods

Learner planning
  learners → study_goals → availability_slots / study_plans → plan_items

Progress and revision
  learners + topics → learner_topic_progress → revision_records / study_activities

Resources and RAG metadata
  resources ↔ resource_topic_links → resource_ingestions

Assessment
  checkpoint_quizzes ↔ checkpoint_quiz_topics → topics
  checkpoint_quizzes ↔ questions → quiz_attempts → quiz_attempt_answers

External evidence
  external_test_results → subject/topic performance → mistake_evidence
```

## Tables

### `learners`

Stores a learner identity and local preferences.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Learner identifier. |
| `display_name` | text nullable | Optional learner-facing name. |
| `timezone` | varchar(64) | IANA timezone name. Supplied by the composition root from `APP_DEFAULT_TIMEZONE`, which defaults to `Asia/Kolkata`; validated there as a real zone. No database default — a timestamp read in the wrong zone is wrong by a day at the boundary, which is where a study plan's dates land. |
| `created_at` | timestamptz | Creation timestamp. |
| `updated_at` | timestamptz | Last update timestamp. |

### `learning_programs`

Stores reusable programs such as GATE CSE.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Program identifier. |
| `code` | varchar(64) unique | Stable code, e.g. `gate-cse`. |
| `name` | text | Display name. |
| `description` | text nullable | Program description. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

### `curriculum_versions`

Stores a versioned curriculum for a learning program.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Version identifier. |
| `learning_program_id` | uuid FK | References `learning_programs.id`. |
| `version_label` | varchar(64) | Human-readable version. |
| `status` | varchar(32) | `draft`, `active`, or `retired`. |
| `source_reference` | text nullable | Official or curator reference. |
| `published_at` | timestamptz nullable | When the version became active. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(learning_program_id, version_label)`; at most one active version per program, enforced by a partial unique index on `learning_program_id WHERE status = 'active'`. Any number of `draft` and `retired` versions may accompany the active one. `status` is constrained to the three documented values.

### `subjects`

Stores major areas within a curriculum version.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Subject identifier. |
| `curriculum_version_id` | uuid FK | References `curriculum_versions.id`. |
| `code` | varchar(64) | Stable subject code within the version. |
| `name` | text | Display name. |
| `description` | text nullable | Optional description. |
| `position` | integer | Display/recommended order. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(curriculum_version_id, code)` and `(curriculum_version_id, position)`.

### `topics`

Stores topics and optional nested subtopics.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Stable topic identifier. |
| `subject_id` | uuid FK | References `subjects.id`. |
| `parent_topic_id` | uuid FK nullable | Self-reference for subtopics. |
| `code` | varchar(64) nullable | Stable optional code within subject. |
| `name` | text | Display name. |
| `description` | text nullable | Optional scope/definition. |
| `position` | integer | Display/recommended order. |
| `is_trackable` | boolean | Whether learner progress can be recorded directly. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(subject_id, parent_topic_id, name)`, declared `NULLS NOT DISTINCT` so it also covers root topics — every root topic has a NULL parent, and PostgreSQL would otherwise treat each NULL as distinct and skip the check entirely. Also unique `(subject_id, code)`, so a topic code identifies one topic anywhere in the subject's tree, not merely among siblings. `is_trackable` is `NOT NULL` with no database default; the seed or use case creating a topic states it. Parent/child subject consistency is validated in application logic or a database trigger.

The two uniqueness rules treat NULL oppositely, deliberately:

| Constraint | NULL handling | Why |
| --- | --- | --- |
| `uq_topics_subject_id_parent_topic_id_name` | `NULLS NOT DISTINCT` | A root topic's parent is NULL. Under the default, every root topic would escape the rule. |
| `uq_topics_subject_id_code` | Default `NULLS DISTINCT` | `code` is optional, and a curriculum that numbers nothing leaves every code NULL. Under `NULLS NOT DISTINCT` a subject could hold only one such topic. |

The code constraint is what lets the curriculum seed match a topic on its code and rename the topic
underneath it; see [ADR-012](../adr/ADR-012-curriculum-seed-and-reconciliation.md). It arrived in
migration `20260731_02`, after `20260731_01` created the table.

### `topic_relationships`

Stores prerequisite and sequencing relationships.

| Column | Type | Notes |
| --- | --- | --- |
| `source_topic_id` | uuid FK | References `topics.id`. |
| `target_topic_id` | uuid FK | References `topics.id`. |
| `relationship_type` | varchar(32) | `prerequisite`, `recommended_before`, or `related`. |
| `created_at` | timestamptz | Creation timestamp. |

**Primary key:** `(source_topic_id, target_topic_id, relationship_type)`.

**Constraints:** source and target must differ, enforced by a `CHECK`. `relationship_type` is constrained to the three documented values.

### `examination_schedules`

Stores the calendar an examining body publishes for one cycle of a learning program, such as GATE
2027. Reference data, not learner data: every learner aiming at the cycle reads the same dates.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Schedule identifier. |
| `learning_program_id` | uuid FK | References `learning_programs.id`. |
| `cycle_label` | varchar(64) | Stable cycle label within the program, e.g. `2027`. |
| `name` | text | Display name, e.g. `GATE 2027`. |
| `organising_body` | text nullable | Body publishing the schedule, e.g. `IIT Madras`. |
| `source_reference` | text | Official source URL. |
| `source_checked_on` | date | When the source was read and transcribed. |
| `schedule_status` | varchar(32) | `provisional` or `confirmed`. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(learning_program_id, cycle_label)`; `schedule_status` is constrained to the
two documented values.

`source_reference` is `NOT NULL`, unlike `curriculum_versions.source_reference`. A schedule exists
only because a source published it, and a stored date with no traceable origin cannot be checked when
the examining body revises it.

`schedule_status` is where "liable to change" survives into the database. A schedule stays
`provisional` while its source says the dates may still move, and becomes `confirmed` only when the
examining body confirms them.

### `examination_periods`

Stores one dated period of a schedule. A period whose start and end are the same day is a single-day
event, which is how a results announcement is stored.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Period identifier. |
| `examination_schedule_id` | uuid FK | References `examination_schedules.id`. |
| `period_type` | varchar(32) | `registration`, `late_registration`, `examination`, or `results`. |
| `starts_on` | date | First day of the period. |
| `ends_on` | date | Last day of the period; equals `starts_on` for a single-day event. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(examination_schedule_id, period_type, starts_on)`, named
`uq_examination_periods_schedule_id_period_type_starts_on`; `ends_on >= starts_on`; `period_type` is
constrained to the four documented values.

A cycle holds several periods of one type — GATE 2027 is sat over three separate weekends — so the
type alone does not identify a period, but a type and a start date do. That pair is the seed's
natural key.

The examination is never stored as a single date. An examining body publishes a range of sitting days
and announces the specific paper's day much later, so one date column could hold only a guess. The
three GATE 2027 weekends are three `examination` periods rather than one 6–21 February range: eleven
days in that range hold no examination. The examination window a plan is built against is derived —
first sitting day to last — from the `examination` periods alone, in the application, not stored.
See [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md).

This table carries the only two constraint names in the schema that do not read exactly as the
naming convention would spell them. The convention would generate 68-character identifiers from this
table name plus the full `examination_schedule_id` column, past PostgreSQL's 63-character limit,
where a silently truncated name is one a downgrade cannot drop. Both abbreviate that one segment to
`schedule_id`.

### `study_goals`

Stores a learner's goal and planning target.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Goal identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `learning_program_id` | uuid FK | References `learning_programs.id`. |
| `curriculum_version_id` | uuid FK | References `curriculum_versions.id`. |
| `examination_schedule_id` | uuid FK nullable | References `examination_schedules.id`. A reference, not a copy of the dates. |
| `target_date` | date nullable | Target completion date, for a learner following no published examination. |
| `status` | varchar(32) | `active`, `paused`, `completed`, or `archived`. |
| `preferred_session_minutes` | integer nullable | How long one study block should be, 15 to 480. A duration, not a time of day. NULL when the learner has set no preference. |
| `topic_sequencing` | varchar(32) nullable | `syllabus_order` or `prerequisites_first`. NULL when the learner has set no preference. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** at least one of `target_date` and `examination_schedule_id` is non-null, enforced by
`ck_study_goals_aims_at_a_date_or_an_examination`; `status` is constrained to the four documented
values; `preferred_session_minutes` is NULL or between 15 and 480; `topic_sequencing` is NULL or one of
the two documented values.

`target_date` was first documented here as a plain non-null date. It is nullable because a learner
preparing for a published examination aims at a *window* whose specific paper day the examining body
has not announced; storing one date would record a guess as the learner's deadline. Both columns are
nullable so neither has to be invented, and the `CHECK` refuses a goal that aims at neither.

The learner's **planning preferences** are the two typed columns above, not the single
`planning_preferences` (`jsonb nullable`) this document first approved.
[ADR-019](../adr/ADR-019-study-goal-planning-preferences.md) records why, and it is the same kind of
departure from a documented target that [`availability_slots`](#availability_slots) made:

- **`jsonb` cannot be constrained.** No `CHECK` reaches a key inside a JSON document, so
  `topic_sequencing` — a controlled value — would be guarded by application code alone, and a
  misspelled key would store successfully and read back as absent. That is the silent mis-mapping
  ADR-018 removed from `day_of_week`. The [Conventions](#conventions) above also reserve `jsonb` for
  flexible provider and resource payloads rather than core relational concepts, so following the
  original target would have contradicted this document's own rules.
- **Both columns are nullable with no database default**, which is what keeps a preference the learner
  never set distinguishable from one the product guessed for them. It is the distinction
  [`learner_topic_progress`](#learner_topic_progress) draws between an explicit `not_explored` and no
  record, and [`availability_slots`](#availability_slots) draws between zero minutes and no row. A
  planner meeting NULL chooses its own default visibly.
- **A third preference is a migration**, deliberately, where a `jsonb` column would have taken it as
  data. An additive nullable column is the change [migrations](migrations.md#additive-changes-first)
  prefers, and a preference worth planning against is worth naming properly.

`preferred_session_minutes` is a **duration**, the same kind of value as
`availability_slots.available_minutes`. It does not reopen the decision recorded under
[`availability_slots`](#availability_slots) not to store a clock time; nothing here records when in a
day a session falls.

Both columns are now read by the plan PLN-001 generates: a session length decides how long an item
runs, and a topic order decides the sequence. They were created before that planner existed because
[FR-002](../requirements/functional.md#fr-002-initial-learner-setup) asks what a learner can *set*, and
[endpoints](../api/endpoints.md#fr-002-acceptance-criteria) carries that criterion's status.
`learner_topic_progress.stage_source` is now the one column in this schema that nothing reads.

### `availability_slots`

Stores recurring available study time for a study goal.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Slot identifier. |
| `study_goal_id` | uuid FK | References `study_goals.id`. |
| `day_of_week` | varchar(16) | `monday` to `sunday`. |
| `available_minutes` | integer | Study time that day, 0 to 1440. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(study_goal_id, day_of_week)`; `day_of_week` is constrained to the seven day
names; `available_minutes >= 0 AND available_minutes <= 1440`.

`day_of_week` was first documented here as a `smallint` holding "0–6 according to documented
convention", with the convention itself recorded as an open project-owner decision. It is
`varchar(16)` holding the day's name because that **retires the decision rather than answering it**:
Python's `date.weekday()` makes Monday zero while JavaScript's `Date.getDay()` and PostgreSQL's
`EXTRACT(DOW)` make Sunday zero, and a client that assumes the wrong one misfiles a whole week with no
error anywhere. A stored name has nothing to mis-map, and it matches every other controlled value in
this schema, which are validated text guarded by a `CHECK` rather than numbers or PostgreSQL enums.
See [ADR-018](../adr/ADR-018-weekly-availability-slots.md).

Nothing stores the week's order. Monday-first is presentation, so the application sorts against a
fixed list rather than an `ORDER BY`.

`available_minutes` gains an upper bound this document did not originally specify: a day holds 1440
minutes, so a larger value is always a mistake. **Zero is accepted and meaningful** — it records a day
the learner deliberately keeps free, which stays distinguishable from a day they have not set, whose
row does not exist. That distinction is why the lower bound is `>= 0` rather than `> 0`, and it is the
same one [`learner_topic_progress`](#learner_topic_progress) draws between an explicit `not_explored`
and no record at all.

A slot holds no clock time. `starts_at`/`ends_at` columns would fix which timezone a wall-clock time is
read in before any planner exists to have an opinion, and nothing consumes a time of day; adding them
later is an additive migration.

### `study_plans`

Stores a generated or learner-adjusted plan.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Plan identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `study_goal_id` | uuid FK | References `study_goals.id`. |
| `plan_type` | varchar(32) | `roadmap`, `monthly`, `weekly`, or `daily`. |
| `period_start` | date nullable | Start of covered period. |
| `period_end` | date nullable | End of covered period. |
| `status` | varchar(32) | `draft`, `active`, `superseded`, or `archived`. |
| `generation_reason` | text nullable | Why it was created/replanned. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** `plan_type` and `status` are each constrained to their documented values.

`plan_type` and `status` are `varchar(32)` guarded by a `CHECK`, not the bare `text` this document
first approved. It is the departure [`availability_slots`](#availability_slots) and
[`study_goals`](#study_goals) each made, for the reason the [Conventions](#conventions) above give:
every controlled value in this schema is validated text, and one guarded by application code alone is
stored and trusted the first time a caller gets it wrong. See
[ADR-020](../adr/ADR-020-initial-study-plan-generation.md).

Both period columns are nullable as approved. A roadmap's `period_end` is the goal's horizon — the
earlier of the examination window's first sitting day and the target date — and is NULL only when the
goal aims at a schedule publishing no sitting day and carries no target date beside it, which
`generation_reason` then states.

`generation_reason` is written when the plan is generated and never rewritten, so a plan set aside
months ago still explains itself in the terms that produced it. That is what makes a superseded plan
worth keeping.

`learner_id` sits beside `study_goal_id` although the goal already names the learner, as this document
first approved: the required index leads on `learner_id`, so a learner's plans are reachable without
joining through their goals.

Generation and adaptation both write `active` and move what they replace to `superseded`, which is the lifecycle rule
[below](#referential-integrity-and-lifecycle-notes). `draft` and `archived` are constrained and
unused: nothing proposes a plan before adopting it, and nothing files one away by hand.

### `plan_items`

Stores one actionable recommendation within a plan.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Plan item identifier. |
| `study_plan_id` | uuid FK | References `study_plans.id`. |
| `topic_id` | uuid FK nullable | References `topics.id`. |
| `action_type` | varchar(32) | `study`, `practice`, `revise`, or `review_mistakes`. |
| `scheduled_for` | date nullable | Recommended date. |
| `estimated_minutes` | integer nullable | Expected effort. |
| `priority` | integer | Position within the plan, counting from 1. |
| `status` | varchar(32) | `planned`, `completed`, `skipped`, or `postponed`. |
| `recommendation_reason` | text nullable | Learner-facing rationale. |
| `completed_at` | timestamptz nullable | Completion timestamp. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** `estimated_minutes > 0` when present; `action_type` and `status` are each
constrained to their documented values.

`action_type` and `status` are `varchar(32)` guarded by a `CHECK` for the same reason `plan_type` is.

`scheduled_for` is NULL on a roadmap item and set on a dated one: a roadmap says what order to work
in, not which day to do it on.

`priority` is the item's position within its plan, counting from 1. It is an **order, not a score** —
nothing ranks one topic above another by anything except where the planning rules placed it.

Every item is *generated* with `action_type = 'study'` and `status = 'planned'`. The other three
actions name work the product does not yet model — practice needs checkpoint quizzes, mistake review needs `mistake_evidence` — so nothing writes one.

**`status` and `completed_at` are now written**, by PLN-004, which moves an item between all four
values and is contracted by [ADR-021](../adr/ADR-021-plan-item-completion.md),
[ADR-024](../adr/ADR-024-plan-item-skipping.md), and
[ADR-025](../adr/ADR-025-learner-postponement.md). It needed no migration any of the three times: both
columns were created by `20260806_03` ahead of the code that writes them, which is the argument
[ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md) made for `stage_source` — an item without
a state is not a plan item, and adding the column once learners held plans would have meant
backfilling rows whose state nobody recorded.

`completed_at` holds the instant the learner marked the item completed and is NULL for every other
status, including an item put back to `planned` and one moved on to `skipped` or `postponed`. It is
written from the server's clock rather than from a request, so no caller can backdate work. **There is
deliberately no `skipped_at` and no `postponed_at`**: `status` carries the whole of what each is,
nothing reads a date for either, and a second timestamp would need its own invariant against `status`
kept in step in every write path.

**`postponed` has two writers.** PLN-005 writes it when adaptation supersedes a plan, for an item
whose day has passed with nothing said about it, and re-places the topic on the plan that replaces it —
which is the answer to what postponing moves work *to*. PLN-004 writes it when the **learner** says the
work is not happening yet, on an active plan and on any day, which completes FR-004's first acceptance
criterion. The value means the same thing either way, and neither needed a migration: the `CHECK` has
accepted it since this table was created. See [ADR-022](../adr/ADR-022-plan-adaptation.md) and
[ADR-025](../adr/ADR-025-learner-postponement.md).

**`skipped` is now written too**, by PLN-004, which makes it the last of the four values the `CHECK`
has carried unwritten since this table was created. It is a statement about **this item** — the
learner has decided the work will not happen — and not about the topic: adaptation leaves a skipped
item alone and **plans its topic again**, where a completed topic is excluded from every plan that
follows. That difference is what keeps a skip reversible in practice, because a skip on a superseded
plan can no longer be edited. See [ADR-024](../adr/ADR-024-plan-item-skipping.md) and
[the skipping review below](#plan_items-skipping-review-2026-08-10); the
[adaptation review](#plan_items-adaptation-review-2026-08-09) before it covers `postponed`.

A completed item is a record that planned work happened, a skipped one that the learner decided it
would not, and a postponed one that they decided it would not yet. None is a claim about whether the
topic is understood — rule 4 of the
[domain model](../domain/domain-model.md#domain-rules-and-invariants) — so none writes anything to
`learner_topic_progress`, and moving a weekly item leaves a roadmap item naming the same topic
`planned`. Only a plan whose `status` is `active` may have an item moved, whatever status is asked
for — see [PLN-004](../api/endpoints.md#pln-004-patch-apiv1plan-itemsplan_item_id) for the rule and its
error.

`topic_id` is nullable as approved, so a later item recommending work belonging to no single topic
has somewhere to live. Nothing writes one today.

### `learner_topic_progress`

Stores the current learner-specific progress summary for a topic.

| Column | Type | Notes | State |
| --- | --- | --- | --- |
| `id` | uuid PK | Progress identifier. | Implemented |
| `learner_id` | uuid FK | References `learners.id`. | Implemented |
| `topic_id` | uuid FK | References `topics.id`. | Implemented |
| `material_status` | text | `not_started`, `in_progress`, or `completed`. | **Not created** |
| `learning_stage` | varchar(32) | Approved learner-visible stage, in the stored form below. | Implemented |
| `stage_source` | varchar(16) | `learner`, `derived`, or `mixed`. | Implemented |
| `last_studied_at` | timestamptz nullable | Most recent study evidence. | **Not created** |
| `material_completed_at` | timestamptz nullable | When material was marked completed. | **Not created** |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. | Implemented |

**Constraints:** unique `(learner_id, topic_id)`, named
`uq_learner_topic_progress_learner_id_topic_id`, which is also the required index below;
`learning_stage` and `stage_source` are each constrained to their documented values.

Migration `20260805_01` creates this table with five of its eight documented columns. The three
marked above remain an approved target and arrive with the code that maintains them, per
[ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) and
[ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md): `material_status` and
`material_completed_at` belong to material completion, which nothing records yet, and
`last_studied_at` can only be filled from a study activity, and `study_activities` does not exist.
Each is a nullable addition to an existing table, which is the additive change
[migrations](migrations.md#additive-changes-first) prefers.

`stage_source` is deliberately **not** deferred with them, though every row written today says
`learner` and nothing derives a stage. It is what distinguishes a stage the learner chose from one
produced by evidence, which is the boundary
[FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence) draws; adding the
column after evidence starts proposing stages would mean backfilling rows whose origin is no longer
recoverable. It is `NOT NULL` with no database default, so no row can acquire a source nobody chose.

`learning_stage` stores the `snake_case` form of the five learner-visible stages —
`not_explored`, `building_foundation`, `developing_confidence`, `practice_ready`, and
`strong_understanding` — matching every other controlled value in this schema.
[Terminology](../domain/terminology.md) holds the labels a learner reads; the two are separate
representations so rewording a label stays a text change rather than a migration over learner rows.

**A topic with no row here has no recorded stage**, which the interface shows as *Not explored*. The
row is created by the learner's own action, so a fresh installation holds none rather than one per
trackable topic. Setting `not_explored` explicitly stores a row, and is how a learner records that
they reset a topic deliberately.

Whether a topic may hold progress at all is `topics.is_trackable`, and it is enforced in the
application rather than here: a topic that only groups subtopics cannot hold a stage, and a database
check would have to reach across a foreign key to find out.

### `study_activities`

Stores actual learner work.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Activity identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `topic_id` | uuid FK nullable | References `topics.id`. |
| `plan_item_id` | uuid FK nullable | References `plan_items.id`. |
| `activity_type` | text | `study`, `practice`, `revision`, or `review_mistakes`. |
| `started_at` | timestamptz nullable | Optional start. |
| `ended_at` | timestamptz nullable | Optional end. |
| `duration_minutes` | integer nullable | Recorded effort. |
| `notes` | text nullable | Private learner note. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** `duration_minutes >= 0` when present.

### `revision_records`

Stores recommended and completed revisions.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Revision identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `topic_id` | uuid FK | References `topics.id`. |
| `plan_item_id` | uuid FK nullable | References `plan_items.id`. |
| `due_on` | date | Date revision becomes due. |
| `scheduled_for` | date nullable | Planned completion date. |
| `status` | text | `due`, `scheduled`, `completed`, `skipped`, or `postponed`. |
| `trigger_type` | varchar(32) | Why revision was created. `completed_plan_item` or `completed_revision`. |
| `recommendation_reason` | text nullable | The sentence the revision gives for itself. |
| `completed_at` | timestamptz nullable | Completion timestamp. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Implemented** by migration `20260813_01`, with the code that reads it (REV-001 to REV-004), per
[ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md). Three points where the created
table differs from the row above, all recorded by
[ADR-028](../adr/ADR-028-revision-workflow.md):

- **`status` and `trigger_type` are `varchar(32)` guarded by a `CHECK`** rather than bare `text`,
  which is this document's own *Conventions* rule and the departure `day_of_week`,
  `topic_sequencing`, and the study-plan columns each made.
- **`recommendation_reason` is a column this table did not list.** A revision's due date is computed
  from the learning stage recorded *at the moment it was created*, so a reason recomputed later from
  a stage the learner has since changed would contradict the date stored beside it. Freezing the
  sentence keeps the record self-explaining — the guarantee `plan_items.recommendation_reason` and
  `study_plans.generation_reason` carry, and the reason ADR-020 gave for them.
- **`trigger_type` permits only the two values something writes.** Low evidence needs quiz and
  external-test records, which do not exist; a third value arrives with the evidence that justifies
  it.

`scheduled` and `scheduled_for` are created and **unwritten**: naming a day for a review is a second
capability, and the `CHECK` carries the value so it arrives as a use-case change rather than a
migration. A revision is **not** a plan item and never becomes one — `plan_items.action_type =
'revise'` stays unwritten — because adaptation supersedes every active plan of a goal and a review the
learner has acted on must survive that.

### `resources`

Stores resource metadata, not the primary file binary.

| Column | Type | Notes | State |
| --- | --- | --- | --- |
| `id` | uuid PK | Resource identifier. | Implemented |
| `owner_learner_id` | uuid FK nullable | References `learners.id`; null for curated/shared future content. | Implemented |
| `resource_type` | varchar(32) | `pdf`, `note`, `pyq`, `formula_sheet`, or `video_reference` today; `image` and `attachment` name uploaded files and are not permitted yet. | Implemented |
| `title` | text | Learner-facing title. | Implemented |
| `source_label` | text nullable | Where the material is, in the learner's own words. | Implemented |
| `storage_key` | text nullable | Opaque storage-provider reference. | **Not created** |
| `external_reference` | text nullable | An `http` or `https` address. Never a local path; see below. | Implemented |
| `metadata` | jsonb nullable | File-specific metadata. | **Not created** |
| `status` | varchar(32) | `registered` or `archived` today; `processing`, `ready`, and `failed` are ingestion states and are not permitted yet. | Implemented |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. | Implemented |

**Constraints:** at least one of `source_label` and `external_reference` is non-null, enforced by
`ck_resources_names_a_location`; `resource_type` and `status` are each constrained to the values
permitted above. **Index:** `resources(owner_learner_id, status)`, as
[Required Indexes](#required-indexes) lists.

Migration `20260816_01` creates every documented column except `storage_key` and `metadata`, with
the code that reads the rest, per [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) and
[ADR-032](../adr/ADR-032-learning-resource-catalogue.md). Four points where the created table differs
from the rows above:

- **`storage_key` and `metadata` are not created.** Both describe a stored file, and nothing uploads
  one: this catalogue records **where material is**, not the material. Creating either now would fix
  a storage provider before one exists, which is the trap ADR-011 avoids and the reason
  [`learner_topic_progress`](#learner_topic_progress) was created without three of its columns. Each
  arrives with the ingestion change.
- **The approved "at least one of `storage_key` or `external_reference`" constraint is expressed over
  `source_label` or `external_reference`.** The invariant is the same — a resource must say where its
  material is — read for a catalogue that stores no files.
- **`external_reference` holds a web address alone.** The application refuses any other scheme, so no
  absolute local filesystem path is stored, which is what keeps
  [endpoints.md](../api/endpoints.md#resource-and-ingestion-endpoints)'s rule that no resource
  endpoint returns one true by construction rather than by filtering. Material that is not on the web
  is described by `source_label`.
- **`resource_type` and `status` are `varchar(32)` guarded by a `CHECK`** rather than the bare `text`
  above, which is this document's own *Conventions* rule and the departure `day_of_week`,
  `topic_sequencing`, the study-plan columns, and the revision columns each made. Each permits only
  the values something writes: the two absent types name uploaded files, and the three absent
  statuses are ingestion lifecycle states a resource could enter and never leave.

`owner_learner_id` is nullable as approved, so curated or shared content has somewhere to live later.
**Nothing writes an ownerless row today**: the application requires an owner on every write, because
a resource belonging to nobody would be invisible to every learner-scoped read.

**Nothing deletes a resource.** A learner puts material aside by moving `status` to `archived`, which
is reversible, so the coordinated cleanup of file storage and vector records that
[the lifecycle notes](#referential-integrity-and-lifecycle-notes) require has nothing to coordinate
yet. See [ADR-032](../adr/ADR-032-learning-resource-catalogue.md).

### `resource_topic_links`

Links a resource to curriculum topics.

| Column | Type | Notes |
| --- | --- | --- |
| `resource_id` | uuid FK | References `resources.id`. |
| `topic_id` | uuid FK | References `topics.id`. |
| `relationship_type` | varchar(32) | `primary`, `supporting`, `practice`, or `revision`. Only `primary` is written. |
| `created_at` | timestamptz | Creation timestamp. |

**Primary key:** `(resource_id, topic_id, relationship_type)`.

**Constraints:** `relationship_type` is constrained to the four documented values. **Index:**
`resource_topic_links(topic_id, resource_id)`, as [Required Indexes](#required-indexes) lists.

Implemented by migration `20260816_01`. It carries `created_at` alone, as
[`topic_relationships`](#topic_relationships) does: a link is write-once reference data, and changing
its role means a different link. A learner editing what a resource covers replaces the whole set.

**All four roles are permitted although only `primary` is written**, which is the opposite of the
choice `resources.status` makes and deliberately so: choosing between these needs no storage that
does not exist, so offering them later is a use-case change rather than a migration — the argument
[ADR-020](../adr/ADR-020-initial-study-plan-generation.md) made for `plan_items.status`. A learner
links material to a topic and is not asked to grade how central it is.

**A link may name any stored topic, including one that only groups subtopics.** That is deliberately
unlike [`learner_topic_progress`](#learner_topic_progress), which the application restricts to a
trackable topic: a stage claims something about understanding a unit of work, while a textbook may
genuinely cover a whole heading.

**There is no subject equivalent.** A resource is linked to topics and subtopics, which are the same
table; [FR-007](../requirements/functional.md#fr-007-learning-resource-organization)'s "one or more
subjects, topics, or subtopics" is therefore met for two of the three, and a subject-level link is a
table no requirement has yet constrained.

### `resource_ingestions`

Tracks extraction and indexing of eligible resources.

**Not implemented.** It arrives with the extractor and the vector index that give it something to track, which is why `resources.status` permits neither `processing`, `ready`, nor `failed` today. See [ADR-032](../adr/ADR-032-learning-resource-catalogue.md).

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Ingestion identifier. |
| `resource_id` | uuid FK | References `resources.id`. |
| `status` | text | `queued`, `processing`, `completed`, or `failed`. |
| `extractor_name` | text nullable | Extraction implementation identifier. |
| `embedding_model` | text nullable | Model/version used for indexed vectors. |
| `started_at`, `completed_at` | timestamptz nullable | Lifecycle timestamps. |
| `error_message` | text nullable | Safe diagnostic message. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

### `checkpoint_quizzes`

**Migration `20260818_01` creates every table in this area, and every documented column except**
`questions.difficulty`, `quiz_questions.max_marks`, `quiz_attempt_answers.awarded_marks`,
`quiz_attempt_answers.feedback`, `quiz_attempts.score`, `quiz_attempts.max_score`, and
`quiz_attempts.duration_seconds` — seven columns nothing maintains. It **adds**
`questions.author_learner_id`, which this document does not list. The tables below are the approved
target; [the area review](#assessment-area-review-2026-08-18) records what was built and why it
differs, per [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md).

Stores a topic-focused practice set.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Quiz identifier. |
| `learner_id` | uuid FK nullable | References `learners.id`; nullable for reusable future quizzes. |
| `title` | text | Learner-facing title. |
| `source_type` | text | `generated`, `verified_pyq`, or `curated`. |
| `status` | text | `draft`, `ready`, `archived`. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

### `checkpoint_quiz_topics`

Links a checkpoint quiz to the topics it covers. A quiz covers one or more topics.

| Column | Type | Notes |
| --- | --- | --- |
| `checkpoint_quiz_id` | uuid FK | References `checkpoint_quizzes.id`. |
| `topic_id` | uuid FK | References `topics.id`. |
| `created_at` | timestamptz | Creation timestamp. |

**Primary key:** `(checkpoint_quiz_id, topic_id)`.

**Constraints:** unique `(checkpoint_quiz_id, topic_id)`.

The application requires at least one linked topic per quiz. A simple database constraint cannot express "at least one row in a child table", so that rule is enforced in the application use case that creates or selects a quiz. Do not add a `topic_id` column to `checkpoint_quizzes`; this table is the only quiz-to-topic link. See [ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md).

### `questions`

Stores reusable assessment items.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Question identifier. |
| `question_type` | text | `multiple_choice`, `multiple_select`, `numeric`, or `short_answer`. |
| `source_type` | text | `generated`, `verified_pyq`, or `curated`. |
| `prompt` | text | Question content. |
| `options` | jsonb nullable | Structured options when applicable. |
| `expected_answer` | jsonb nullable | Answer representation. |
| `explanation` | text nullable | Explanation/solution. |
| `difficulty` | text nullable | Optional controlled value. |
| `status` | text | `draft`, `ready`, `retired`. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

### `question_topic_links`

Links questions to topics.

| Column | Type | Notes |
| --- | --- | --- |
| `question_id` | uuid FK | References `questions.id`. |
| `topic_id` | uuid FK | References `topics.id`. |
| `created_at` | timestamptz | Creation timestamp. |

**Primary key:** `(question_id, topic_id)`.

### `quiz_questions`

Orders questions within a checkpoint quiz.

| Column | Type | Notes |
| --- | --- | --- |
| `checkpoint_quiz_id` | uuid FK | References `checkpoint_quizzes.id`. |
| `question_id` | uuid FK | References `questions.id`. |
| `position` | integer | Display order. |
| `max_marks` | numeric | Available marks. |

**Primary key:** `(checkpoint_quiz_id, question_id)`.

**Constraints:** unique `(checkpoint_quiz_id, position)`; `max_marks > 0`.

### `quiz_attempts`

Stores one learner attempt at a checkpoint quiz.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Attempt identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `checkpoint_quiz_id` | uuid FK | References `checkpoint_quizzes.id`. |
| `status` | text | `in_progress`, `submitted`, `evaluated`, or `abandoned`. |
| `started_at`, `submitted_at`, `evaluated_at` | timestamptz nullable | Attempt lifecycle. |
| `score` | numeric nullable | Calculated score snapshot. |
| `max_score` | numeric nullable | Maximum score snapshot. |
| `duration_seconds` | integer nullable | Attempt duration. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

### `quiz_attempt_answers`

Stores answer-level results.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Answer identifier. |
| `quiz_attempt_id` | uuid FK | References `quiz_attempts.id`. |
| `question_id` | uuid FK | References `questions.id`. |
| `submitted_answer` | jsonb nullable | Learner answer. |
| `is_correct` | boolean nullable | Null when not automatically evaluable. |
| `awarded_marks` | numeric nullable | Scored marks. |
| `feedback` | text nullable | Learner feedback. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(quiz_attempt_id, question_id)`.

### `external_test_results`

Stores learner-entered performance from a test taken outside LearnFlow.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Test-result identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `source_label` | text nullable | E.g. a provider name, entered manually. |
| `test_name` | text | Learner-entered test name. |
| `test_type` | text | `topic`, `subject`, or `full_mock`. |
| `taken_on` | date | Test date. |
| `score`, `max_score` | numeric nullable | Overall score. |
| `accuracy_percent` | numeric nullable | 0–100 when available. |
| `duration_seconds` | integer nullable | Time used. |
| `correct_count`, `incorrect_count`, `unattempted_count` | integer nullable | Counts when available. |
| `attachment_resource_id` | uuid FK nullable | References `resources.id` for a private reference attachment. |
| `notes` | text nullable | Learner-entered observations. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** counts are non-negative; `accuracy_percent` is between 0 and 100 when present.

### `external_test_subject_performance`

Stores optional subject-level performance from an external test.

| Column | Type | Notes |
| --- | --- | --- |
| `external_test_result_id` | uuid FK | References `external_test_results.id`. |
| `subject_id` | uuid FK | References `subjects.id`. |
| `score`, `max_score` | numeric nullable | Subject result when available. |
| `correct_count`, `incorrect_count`, `unattempted_count` | integer nullable | Optional counts. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Primary key:** `(external_test_result_id, subject_id)`.

### `external_test_topic_performance`

Stores optional topic-level performance when the learner's test report provides it. This table is the only home for topic performance evidence; checkpoint quiz outcomes are never written here. See [ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md).

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Topic-performance identifier. |
| `external_test_result_id` | uuid FK | References `external_test_results.id`. |
| `topic_id` | uuid FK | References `topics.id`. |
| `score`, `max_score` | numeric nullable | Topic result when available. |
| `correct_count`, `incorrect_count`, `unattempted_count` | integer nullable | Optional counts. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(external_test_result_id, topic_id)`.

### `mistake_evidence`

Stores a learner error or learning gap linked to usable evidence.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Mistake identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `topic_id` | uuid FK nullable | References `topics.id`. |
| `quiz_attempt_answer_id` | uuid FK nullable | Discovery source: references `quiz_attempt_answers.id`. |
| `external_test_result_id` | uuid FK nullable | Discovery source: references `external_test_results.id`. |
| `revision_record_id` | uuid FK nullable | Discovery source: references `revision_records.id`. |
| `study_activity_id` | uuid FK nullable | Discovery source: references `study_activities.id`. |
| `mistake_category` | text | `concept_gap`, `calculation_error`, `careless_error`, or `time_management`. |
| `notes` | text nullable | Learner/system note. |
| `resolved_at` | timestamptz nullable | Optional resolution timestamp. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** exactly one discovery source must be present — precisely one of `quiz_attempt_answer_id`, `external_test_result_id`, `revision_record_id`, or `study_activity_id` is non-null. Topic may be null only when the source has no available topic mapping.

Use named nullable foreign keys rather than a generic polymorphic `source_type`/`source_id` pair, so every source keeps real referential integrity and the exactly-one rule stays enforceable in the database. See [ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md).

## Required Indexes

Create indexes in addition to primary/unique keys for likely MVP access patterns. Each is created by
the migration that creates its table; the entries marked below are implemented today.

- `topics(subject_id, parent_topic_id, position)` — implemented
- `examination_periods(examination_schedule_id, starts_on)` — implemented
- `learner_topic_progress(learner_id, topic_id)` unique — implemented, as the unique constraint named above
- `study_plans(learner_id, study_goal_id, status, period_start)` — implemented
- `plan_items(study_plan_id, scheduled_for, status)` — implemented
- `revision_records(learner_id, due_on, status)` — implemented
- `study_activities(learner_id, topic_id, created_at desc)`
- `resource_topic_links(topic_id, resource_id)` — implemented
- `resources(owner_learner_id, status)` — implemented
- `resource_ingestions(resource_id, status)`
- `checkpoint_quiz_topics(topic_id, checkpoint_quiz_id)` — implemented
- `quiz_attempts(learner_id, checkpoint_quiz_id, created_at desc)` — implemented
- `questions(author_learner_id, status)` — implemented; not listed when this document was written, and added by [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md) for the access pattern that assembles a quiz
- `question_topic_links(topic_id, question_id)` — implemented; added for the same reason, and how a quiz finds the questions covering a topic
- `external_test_results(learner_id, taken_on desc)`
- `external_test_topic_performance(topic_id, external_test_result_id)`
- `mistake_evidence(learner_id, topic_id, resolved_at)`

`learners` and `study_goals` need no index beyond their keys yet. A single-learner installation holds
one learner and a handful of goals, so every access is a sequential scan of a few rows. Add one with
the code whose access pattern justifies it.

## Referential-Integrity and Lifecycle Notes

- Curriculum records are reference data and should not be casually deleted once learner records reference them.
- Deleting a learner-owned resource requires coordinated cleanup of file storage and derived vector records; do not rely only on cascading database deletion.
- Plans may be superseded rather than deleted so the learner's plan history remains explainable.
- Quiz attempts and external test results are historical evidence and should normally be retained even when a current plan changes.
- Indexing metadata is not the source of truth for a resource and can be recreated from the original resource file and metadata.

## Implementation Review Required

Review a schema area against the following before the migration that creates it:

- The final GATE CSE curriculum seed structure.
- The planned SQLAlchemy mapping strategy.
- The first API contracts.
- The actual revision-scheduling rules.
- Database constraints supported by the selected PostgreSQL/Alembic versions.

Some inputs will not exist when an area is first migrated, because the schema grows alongside the
code that reads it. Review against every input that exists, record the remainder as pending in the
area's subsection below, and complete each pending review when its input arrives. An area is fully
reviewed only once no input is left pending.

Any material change must update this document and be implemented through an Alembic migration.

### Curriculum area — initial review approved 2026-07-31

This is an **approved initial review of the curriculum schema**, not a fully discharged review of
every input listed above. It approves the curriculum tables as created by migration
`20260731_01_create_curriculum_tables` and amended by `20260731_02_add_topic_code_unique_constraint`.

Covered by this review:

- The planned SQLAlchemy mapping strategy.
- Database constraints supported by the selected PostgreSQL and Alembic versions.

Together these produced the conventions and constraint decisions recorded above and in
[ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md).

**Remaining review inputs:**

| Review input | State |
| --- | --- |
| The final GATE CSE curriculum seed structure | **Reviewed 2026-07-31** — the curriculum fits the tables; one constraint was added by migration `20260731_02`. See below. |
| The first API contracts | **Reviewed 2026-08-01** — CUR-001 to CUR-003 are implemented and their schemas need no change to the tables. See below. |
| The actual revision-scheduling rules | Not applicable to this area. |

No input is left pending, so **the curriculum area is fully reviewed**. Either review could have
found that the approved shape needed to change — a subject code longer than `varchar(64)`, say, or
an ordering rule the `position` uniqueness forbids. Such a finding is a follow-up migration, never an
edit to an applied one.

#### Seed-structure review outcome

The curated curriculum — 11 subjects and 65 topics and subtopics, loaded by
`backend/scripts/seed_curriculum.py` — fits the applied tables, with one constraint added. What the
review settled:

- `subjects.code` holds the longest code in use, `computer-organization-and-architecture`, at 38
  characters, comfortably inside `varchar(64)`.
- `topics.code` stays null throughout. The official syllabus names topics rather than numbering them,
  so the seed matches a topic on `(subject_id, parent_topic_id, name)` — the uniqueness rule this
  table already declared. `code` remains available for a curriculum that needs renames to survive.
  The review found that the seed could match on a code that no constraint enforced, so
  `uq_topics_subject_id_code` was added in migration `20260731_02`. It is the one change this review
  produced.
- `topics.name` is `text`, which the syllabus needs: the longest topic name is 139 characters,
  because several official entries are a clause rather than a label.
- Two levels are enough for this syllabus; the self-referencing `parent_topic_id` is not exercised
  beyond depth two.
- `is_trackable` is set by the seed, as this document requires. A topic that groups subtopics is not
  directly trackable; a leaf is.
- `subjects.position` uniqueness holds, but only because the seed works around it: the constraint is
  checked per statement rather than deferred, so re-ordering needs the existing rows moved aside
  first. No schema change was needed.
  [Re-ordering subjects](migrations.md#re-ordering-subjects) describes the step.
- `curriculum_versions.published_at` is set when a version is seeded as active and is never
  overwritten afterwards, so a repeat run reports no change.

One follow-up migration resulted — `20260731_02`, adding `uq_topics_subject_id_code` — created as a
new revision rather than an edit to the applied one, as this document requires. The rules the review
settled are recorded durably in
[ADR-012](../adr/ADR-012-curriculum-seed-and-reconciliation.md).

#### API-contract review outcome

The curriculum read endpoints CUR-001 to CUR-003, defined in [endpoints](../api/endpoints.md), are
implemented and read these tables. **No schema change resulted.** What the review settled:

- Every column an endpoint returns already exists. The API adds no field the tables cannot supply,
  and asks for none they do not hold.
- `topics.parent_topic_id` carries the whole hierarchy the tree endpoint returns. The API nests
  subtopics in the application layer rather than storing a rendered tree, so a curriculum of any
  depth needs no column.
- `subjects.position` and `topics.position` are what the API orders by. The `index
  topics(subject_id, parent_topic_id, position)` this area already creates serves that read.
- The partial unique index on one active version per program is what lets a program report exactly
  one `active_curriculum_version`; without it the API would have to pick between rivals.
- No new index was needed. A page of learning programs orders by `code`, which is already unique,
  and a single-learner installation holds one program.
- `curriculum_versions.source_reference` stays nullable. The API returns it as a nullable field
  rather than requiring one, unlike `examination_schedules.source_reference`.

### Examination schedule area — initial review approved 2026-07-31

This is an **approved initial review of the examination schedule tables** as created by migration
`20260801_01`. It is not a fully discharged review of every input listed above.

Covered by this review:

- The final GATE 2027 schedule seed structure — `backend/scripts/gate_cse_examination_schedule.json`,
  six periods across four types, fits the tables with no change.
- The planned SQLAlchemy mapping strategy.
- Database constraints supported by the selected PostgreSQL and Alembic versions.

What the review settled:

- One `examination_schedules` row per program and cycle. `cycle_label` holds `2027`, far inside
  `varchar(64)`.
- The examination is periods, not a date. Three `examination` periods hold the GATE 2027 weekends;
  `results` is a single-day period, so the range check is `>=` rather than `>`.
- `(examination_schedule_id, period_type, starts_on)` is the natural key, because a cycle holds three
  periods of the same type. It is enforced, as ADR-012 requires of every key a seed matches on.
- Two constraint names had to be shortened by hand against PostgreSQL's 63-character limit, as
  recorded under [`examination_periods`](#examination_periods) above. This is the first place in the
  schema where the naming convention could not be applied verbatim; a unit test now fails any future
  name that overruns.
- `late_registration` is stored as a period beginning the day after regular registration closes,
  which is the seed file's one inference; its `$comment` block and
  [migrations](migrations.md#source-of-the-bundled-gate-2027-schedule) record why.

**Remaining review inputs:**

| Review input | State |
| --- | --- |
| The first API contracts | **Reviewed 2026-08-05** — EXM-001 is implemented and its schema needs no change to the tables. See below. |
| The actual revision-scheduling rules | Not applicable to this area. |

No input is left pending, so **the examination schedule area is fully reviewed**.

#### API-contract review outcome

EXM-001, defined in [endpoints](../api/endpoints.md#exm-001-get-apiv1examination-schedules), reads
these tables. **No schema change resulted.** What the review settled:

- Every column the endpoint returns already exists, and it asks for none the tables do not hold.
- The examination window stays derived rather than stored, as
  [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md) decided. The endpoint computes it
  from the `examination` periods on each read, so a re-seeded correction reaches every reader at once.
- `source_reference`, `source_checked_on`, `organising_body`, and `schedule_status` are all returned,
  so a client can state where a date came from and whether it is settled. `source_reference` being
  `NOT NULL` is what lets the response promise a source rather than a nullable one.
- The `examination_periods(examination_schedule_id, starts_on)` index this area already creates serves
  the periods read, which fetches every period of a page of schedules in one query.
- No new index was needed. A single-learner installation holds one program and a handful of cycles.

### Learner planning area — partial review approved 2026-07-31

This review covers only `learners` and `study_goals`, the two tables migration `20260801_01` creates.
`availability_slots` has since been created and reviewed
[separately below](#availability_slots-review-approved-2026-08-06), and `study_plans` and `plan_items`
[below that](#study_plans-and-plan_items-review-2026-08-06).

What the review settled:

- `learners.timezone` is `varchar(64)` and has no database default. The default value comes from
  `APP_DEFAULT_TIMEZONE`, closing one of the three open items ADR-011 recorded.
- `study_goals.target_date` becomes nullable, gaining `examination_schedule_id` and a `CHECK`
  requiring at least one of the two. The rationale is in
  [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md).
- A goal references a schedule rather than copying its dates, so a corrected schedule reaches every
  goal without a learner-data migration.
- `planning_preferences` is deliberately not created.
- No index beyond the keys, as recorded above.

**Remaining review inputs:**

| Review input | State |
| --- | --- |
| The first API contracts | **Reviewed 2026-08-05** — LRN-001, LRN-002, and GOAL-001 to GOAL-004 are implemented and their schemas need no change to `learners` or `study_goals`. See below. |
| The actual revision-scheduling rules | **Discharged** — [ADR-028](../adr/ADR-028-revision-workflow.md) supplies them, and decides that a revision is not a plan item at all. |
| The `day_of_week` numbering convention | **Retired 2026-08-06** — `availability_slots` stores the day's name, so there is no numbering. See [its own review](#availability_slots-review-approved-2026-08-06) below. |

One input remains pending. Every table in the area now exists and has been reviewed — `learners`,
`study_goals`, and `availability_slots` above, `study_goals`' planning preferences
[below](#planning-preferences-review-2026-08-06), and `study_plans` and `plan_items`
[below](#study_plans-and-plan_items-review-2026-08-06) — so the area is **fully reviewed except for
the revision-scheduling input**, which constrains what a revision plan item looks like and arrives
with `revision_records` in Milestone 3.

#### API-contract review outcome

The learner and study-goal endpoints, defined in
[endpoints](../api/endpoints.md#learner-setup-and-goal-endpoints) and contracted by
[ADR-016](../adr/ADR-016-learner-onboarding-api-contracts.md), read and write these two tables.
**No schema change resulted.** What the review settled:

- Every column an endpoint returns already exists. `learners.display_name` being nullable is what
  lets LRN-002 remove a name; `learners.timezone` being `NOT NULL` with no database default is what
  makes the composition root supply `APP_DEFAULT_TIMEZONE` on creation rather than the database
  inventing one.
- `display_name` stays unbounded `text`. The API bounds it at 200 characters as a typo guard, which
  is a contract constraint rather than a storage one; a longer name is a `422`, not a truncated row.
- Both nullable goal columns and `ck_study_goals_aims_at_a_date_or_an_examination` hold exactly the
  rule the endpoints enforce. The application refuses a goal aiming at nothing *before* the database
  sees it, so the constraint stays a backstop rather than the error path — failing it there would
  surface as an unexplained `500` instead of a `422` naming the fields.
- `study_goals.curriculum_version_id` records the version a goal was created against and is never
  rewritten by an update, so a retired version still reads back as the goal's own. GOAL-001 binds a
  new goal to the program's active version instead of accepting one from a client.
  *(`planning_preferences` was withheld at the time of this review; see
  [its own review](#planning-preferences-review-2026-08-06) below.)*
- The "one active goal per program" rule GOAL-001 enforces is **not** a database constraint. A partial
  unique index on `(learner_id, learning_program_id) WHERE status = 'active'` would express it, and
  was deliberately not added: the rule belongs to the create path only, no other writer exists —
  `scripts.set_study_goal` updates its own active goal by design — and the index would make that
  command's upsert fail where it currently succeeds. Recorded as intentional future work in
  [deferred ideas](../roadmap/future-ideas.md#deferred-architecture-and-operations-ideas), with the
  triggers that would justify adding it.
- No index beyond the keys was needed, as recorded above. A single-learner installation holds one
  learner and a handful of goals, so every access is a sequential scan of a few rows.
- `planning_preferences` stays uncreated, and GOAL-004 accordingly does not accept it.

#### `availability_slots` review — approved 2026-08-06

This review covers the third learner-planning table, created by migration `20260806_01` and read and
written by GOAL-005, whose contract is fixed by
[ADR-018](../adr/ADR-018-weekly-availability-slots.md). **One documented column type changed**, and
the table is otherwise created as approved. What the review settled:

- `day_of_week` is `varchar(16)` holding a day name, not the documented `smallint`. This retires the
  open numbering convention rather than answering it; the rationale is under
  [`availability_slots`](#availability_slots) above.
- `available_minutes` gains an upper bound of 1440 beside the approved `>= 0`. Zero is accepted
  deliberately and means a day the learner keeps free.
- The unique `(study_goal_id, day_of_week)` key is created as approved. It is what makes saving a week
  rewrite the days it names rather than appending beside them, and it is what lets GOAL-005 address a
  day rather than a row.
- **No further index was needed.** The unique constraint creates one whose leading column serves the
  only read there is — every slot belonging to one goal — and
  [Required Indexes](#required-indexes) lists none for this table.
- The row hangs off `study_goals` rather than `learners`, as approved: a learner who archives one goal
  and starts another is describing a different week.
- No column stores a clock time and none stores the week's order. Both were considered and left out;
  see ADR-018.

#### Planning preferences review — 2026-08-06

This review covers the two columns migration `20260806_02` adds to `study_goals`, read and written by
GOAL-001 and GOAL-004, whose contract is fixed by
[ADR-019](../adr/ADR-019-study-goal-planning-preferences.md). **One documented column was replaced by
two of different types**, and the reasoning is recorded under [`study_goals`](#study_goals) above. What
the review settled:

- `planning_preferences jsonb` is **not created**. `preferred_session_minutes integer` and
  `topic_sequencing varchar(32)` are created in its place, each guarded by a `CHECK`, because no `CHECK`
  can reach a key inside `jsonb` and `topic_sequencing` is a controlled value. This follows the
  validated-text convention ADR-011 chose, as `day_of_week` did.
- Both are **nullable with no database default**, so a preference nobody set never reads as one somebody
  chose. `NOT NULL` with defaults was considered and rejected: it would satisfy FR-002's "the learner
  can set" with values the learner never set.
- The bounds are `15` to `480` on a session length. Below a quarter of an hour a plan item is scheduling
  overhead rather than study; eight hours is a full working day, and a day is already bounded by its
  availability.
- **No index was added.** Nothing filters or orders goals by a preference — a preference is read as part
  of the goal that owns it, already addressed by its primary key — and
  [Required Indexes](#required-indexes) lists none for this table.
- **No separate table.** A fourth learner-planning table for two nullable scalars would add a join to
  every goal read and a new "no row versus a row of nulls" distinction, where the columns already
  express the only distinction that matters. `availability_slots` earns its table by holding up to seven
  keyed rows; a preference group holds one of each.
- The columns sit on `study_goals` rather than on `learners`, matching availability: a learner who
  archives one goal and starts another may want to study differently.
- A revision share, a practice share, a pre-examination revision buffer, and an evidence-ranked topic
  order were all considered and left out; ADR-019 records each with the work it waits on.
- The constraint-name length limit was checked, as the examination-schedule precedent requires: the
  longest, `ck_study_goals_preferred_session_minutes_within_bounds`, is 54 characters, inside
  PostgreSQL's 63-character limit. The unit test guarding that limit covers this table.

**Review inputs:** the first API contracts — GOAL-001 and GOAL-004 — were reviewed here, and the
revision-scheduling rules remain **pending** for `study_plans` and `plan_items`, as recorded above.
`study_goals` itself is now **fully reviewed**.

#### `study_plans` and `plan_items` review — 2026-08-06

This review covers the last two learner-planning tables, created by migration `20260806_03` and read
and written by PLN-001 to PLN-003, whose contract is fixed by
[ADR-020](../adr/ADR-020-initial-study-plan-generation.md). **Three documented column types changed**,
and every other column is created as approved. What the review settled:

- `plan_type`, `study_plans.status`, `plan_items.action_type`, and `plan_items.status` are
  `varchar(32)` guarded by a `CHECK` rather than the bare `text` the tables above first described.
  This follows the [Conventions](#conventions) in this document and the validated-text rule ADR-011
  chose, as `day_of_week` and `topic_sequencing` did.
- **Both required indexes are created**, exactly as [Required Indexes](#required-indexes) lists them.
  `ix_study_plans_learner_id_study_goal_id_status_period_start` also serves the read generation makes
  before it writes — every `active` plan of the goal being replanned — so no further index was needed.
- `estimated_minutes > 0` is created as approved, written with an explicit NULL branch because the
  column is nullable.
- **No unique constraint was added.** A goal may hold several active plans deliberately — a roadmap
  and a week are generated together — and a plan may hold two items naming the same topic, which is
  what makes the week the first stretch of the roadmap rather than separate work. A key forbidding
  either would have made the chosen plan shape unstorable.
- `plan_items.status` and `completed_at` are created although nothing writes anything but `planned`.
  They are the exception to ADR-011's ordering rule that ADR-017 established for `stage_source`: a
  state added after learners hold plans could only be backfilled by guessing. **Both are now written**
  by PLN-004, which arrived on 2026-08-08 needing no migration —
  see [the review note below](#plan_items-status-review-2026-08-08).
- Items are read one plan at a time and counted a page at a time, so no index on `topic_id` was
  needed; nothing yet asks which plans mention a topic.
- The constraint-name length limit was checked, as the examination-schedule precedent requires: the
  longest, `ix_study_plans_learner_id_study_goal_id_status_period_start`, is 58 characters, inside
  PostgreSQL's 63-character limit. The unit test guarding that limit covers both tables.
- **The revision-scheduling review input is now discharged.** It was pending here because these
  tables were created for planning rather than for revision. `revision_records` now exists
  (`20260813_01`), and [ADR-028](../adr/ADR-028-revision-workflow.md) settles what a revision
  plan item looks like by deciding there is not one: a revision is its own record, and
  `plan_items.action_type = 'revise'` stays unwritten permanently, because adaptation supersedes
  every active plan of a goal and a review the learner has acted on must survive that.

**Review inputs:** the first API contracts — PLN-001 to PLN-003 — were reviewed here. The
revision-scheduling rules are supplied by [ADR-028](../adr/ADR-028-revision-workflow.md), which leaves no input outstanding for this area.

#### `plan_items` status review — 2026-08-08

This review covers the first code to write `plan_items.status` and `completed_at`, contracted by
[ADR-021](../adr/ADR-021-plan-item-completion.md). **No schema change resulted, and no migration was
written**: both columns, the `status` `CHECK`, and
`ix_plan_items_study_plan_id_scheduled_for_status` were all created by `20260806_03`. What the
review settled:

- **The columns created ahead of their code were the right shape.** The `CHECK` already accepted
  `completed`, and `completed_at` was already nullable and timezone-aware, so the endpoint stored what
  the review above anticipated without altering anything. That discharges the risk ADR-011's ordering
  rule exists to catch, in the one place ADR-017's exception was applied to this area.
- **The application accepts fewer statuses than the column holds.** `skipped` and `postponed` pass the
  `CHECK` and are refused by PLN-004. The constraint stays as approved: it describes what a plan item
  may *be*, and which of those a learner may currently *ask for* is a contract rule, not a column one.
  *(Overtaken. `skipped` became askable with [ADR-024](../adr/ADR-024-plan-item-skipping.md) and
  `postponed` with [ADR-025](../adr/ADR-025-learner-postponement.md); the endpoint and the `CHECK` now
  admit the same four values. The reasoning stands — the two remain separate rules that happen to
  agree.)*
- **`completed_at` is application-maintained, not defaulted.** No column default and no trigger sets
  it; the use case writes the clock's instant when an item becomes `completed` and NULL when it does
  not. A database default would have made an item completed the moment a row was touched.
- **No index was added.** Nothing yet asks which items a learner has completed — the plan screen reads
  one plan at a time, and the existing index already leads with `study_plan_id`.
- **No `CHECK` ties `status` to `completed_at`.** The pairing is enforced in the application and
  asserted by the study-plan fake. A two-column constraint was considered and not added: nothing else
  in this schema constrains one column by another, and the pair is written by exactly one caller.

**Review inputs:** the API contract PLN-004 was reviewed here. The revision-scheduling rules remain
**pending** and are still the last input outstanding for this area.

#### `plan_items` adaptation review — 2026-08-09

This review covers the first code to write `plan_items.status = 'postponed'`, contracted by
[ADR-022](../adr/ADR-022-plan-adaptation.md). **No schema change resulted, and no migration was
written**: the `CHECK` created by `20260806_03` already accepted the value. What the review settled:

- **The status is written on the plan being superseded, not on the new one.** A superseded plan's
  items therefore end in one of three states — `completed`, `postponed`, or `planned` and never due —
  so the history distinguishes work the learner missed from work that was never reached. The plan's
  `generation_reason` and its items' `recommendation_reason` are still never rewritten.
- **`completed_at` is cleared when an item is postponed**, because a postponed item is by definition
  not completed. The application rule pairing the two columns holds in both directions.
- **No index was added.** Adaptation reads a goal's completed topics once per request, through
  `study_plans.study_goal_id`, which
  `ix_study_plans_learner_id_study_goal_id_status_period_start` already leads on; and it reads one
  plan's items at a time through `ix_plan_items_study_plan_id_scheduled_for_status`.
- **No constraint ties an item's status to its plan's.** A `postponed` item on an `active` plan is
  unreachable through the API but not forbidden by the database, which matches how every other
  controlled value in this schema is guarded: the column says what a value may be, the application
  says who may set it.
- **Adaptation writes no `learner_topic_progress`**, so rule 4 of the domain model holds across the
  whole planning surface rather than only in PLN-004.

**Review inputs:** the API contract PLN-005 was reviewed here. The revision-scheduling rules remain
**pending**.

#### `plan_items` skipping review — 2026-08-10

This review covers the first code to write `plan_items.status = 'skipped'`, contracted by
[ADR-024](../adr/ADR-024-plan-item-skipping.md). **No schema change resulted, and no migration was
written**: the `CHECK` created by `20260806_03` already accepted the value, which was the last of its
four to be written. What the review settled:

- **No `skipped_at` column.** A skip is a standing state of an item rather than an event a learner
  needs dated, nothing reads such a date, and a second timestamp would need its own invariant against
  `status` maintained in every write path. `completed_at` stays the only status timestamp, and it
  stays NULL for a skipped item. Adding `skipped_at` later remains an additive change.
- **No column records *why* an item was skipped**, and none is planned. Storing a reason would
  invite the product to form a view about it, which
  [FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence) refuses.
- **`completed_at` is cleared when an item is skipped**, exactly as it is when one is postponed or put
  back to `planned`. The application rule pairing the two columns holds in all directions.
- **A skipped topic is not excluded from the plans that follow**, unlike a completed one. Adaptation
  reads `plan_items.status = 'completed'` alone through `list_completed_topic_ids`; that query is
  unchanged, and no new read was added.
- **No index was added.** Skipping writes one row by primary key and reads nothing new. The overdue
  scan adaptation performs is unchanged in shape — it reads one plan's items through
  `ix_plan_items_study_plan_id_scheduled_for_status` and now excludes two statuses rather than one,
  in application code rather than in SQL.
- **No constraint ties an item's status to its plan's**, as above. A skipped item on a superseded plan
  is reachable only because adaptation superseded the plan after the learner skipped it, and the
  database is not what stops it being edited — PLN-004 is.
- **An earlier dated note is now half overtaken.** The 2026-08-08 completion review recorded that
  "`skipped` and `postponed` pass the `CHECK` and are refused by PLN-004"; that is true of
  `postponed` alone. The `CHECK` is still deliberately wider than the endpoint, by one value rather
  than two. The same sentence appears in
  [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md), where it is dated history.
  *(Now fully overtaken — see the postponement review below.)*

**Review inputs:** the API contract PLN-004 was re-reviewed here, and the domain rule
`select_overdue` with it. The revision-scheduling rules are supplied by [ADR-028](../adr/ADR-028-revision-workflow.md).

#### `plan_items` postponement review — 2026-08-11

This review covers the second writer of `plan_items.status = 'postponed'`, contracted by
[ADR-025](../adr/ADR-025-learner-postponement.md). **No schema change resulted, and no migration was
written**: the `CHECK` created by `20260806_03` already accepted the value, and PLN-005 has written it
since [ADR-022](../adr/ADR-022-plan-adaptation.md). What the review settled:

- **The `CHECK` and the endpoint now admit the same four values**, which closes the gap the two
  reviews above tracked. They stay separate rules for the reason recorded there — one describes what a
  plan item may *be*, the other what a learner may *ask for* — and a fifth value added to the column
  would arrive unwritable until somebody decided it should be askable.
- **No `postponed_at` column**, for the reasons the skipping review gave for `skipped_at`: nothing
  reads such a date, and a second timestamp would need its own invariant against `status` maintained
  in every write path. `completed_at` stays the only status timestamp and stays NULL for a postponed
  item, whichever writer set the status. Adding `postponed_at` later remains an additive change.
- **No column records *why* an item was postponed**, and none is planned — the skipping review's
  reasoning, unchanged.
- **No column distinguishes who wrote `postponed`.** A learner's postponement and adaptation's are the
  same stored value, and the only surviving trace of the difference is `postponed_plan_item_ids` in
  the adaptation response. That is recorded as a consequence in ADR-025 rather than solved with a
  `status_source` column, which would be the shape ADR-017 gave `stage_source` and is not yet needed
  by anything.
- **A postponed topic is not excluded from the plans that follow**, as a skipped one is not.
  Adaptation still reads `plan_items.status = 'completed'` alone through `list_completed_topic_ids`;
  that query is unchanged, and no new read was added.
- **No index was added.** Postponing writes one row by primary key and reads nothing new. The overdue
  scan is unchanged in shape and now excludes three statuses rather than two, in application code
  rather than in SQL.
- **No constraint ties an item's status to its plan's**, as above. PLN-004 is still what refuses a
  write to a superseded plan, for every status without exception.

**Review inputs:** the API contract PLN-004 was re-reviewed here, and the application set
`SETTLED_STATUSES` with it. The revision-scheduling rules are supplied by [ADR-028](../adr/ADR-028-revision-workflow.md).

### Progress and revision area — partial review approved 2026-08-05

This review covers only `learner_topic_progress`, the one table migration `20260805_01` creates, and
only the five of its eight columns that migration creates. `study_activities` and `revision_records`
are unreviewed and unimplemented.

Covered by this review:

- The first API contracts — PRG-002 and PRG-004, fixed by
  [ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md).
- The planned SQLAlchemy mapping strategy.
- Database constraints supported by the selected PostgreSQL and Alembic versions.

**No schema change resulted beyond the table this migration creates.** What the review settled:

- The five learning stages are stored as `snake_case` text guarded by a `CHECK`, in `varchar(32)`.
  The longest, `strong_understanding`, is 20 characters. This follows the controlled-value convention
  ADR-011 chose rather than a PostgreSQL enum, so adding a sixth stage stays an ordinary constraint
  change.
- `stage_source` is `varchar(16)` — `derived`, the longest of the three, is 7 — and is created now
  rather than deferred, for the reason recorded under the table above. It is the one column in this
  area whose later absence could not be repaired by a backfill.
- Three columns are deliberately not created. Each is a nullable additive change when its writer
  arrives, so nothing here forecloses them.
- `(learner_id, topic_id)` uniqueness is what makes PRG-004 rewrite one row rather than append a
  second, and it is the required index this document already listed. No further index was needed: a
  single-learner installation holds at most one record per topic, and the curated GATE CSE curriculum
  has 65 topics and subtopics.
- PRG-002's `curriculum_version_id` filter reaches through `subjects` to `topics`; no column was
  added to `learner_topic_progress` to shorten that path. Denormalising the version onto a
  learner-owned row would let it drift from the topic it describes.
- "A grouping topic holds no stage" is **not** a database constraint. `topics.is_trackable` lives on
  another table, so expressing it would need a trigger or a redundant copy of the flag; the use case
  refuses it before the database sees it, and a `422` naming the topic is a better answer than an
  integrity error.
- The examination-schedule precedent on identifier length was checked: the longest name here,
  `uq_learner_topic_progress_learner_id_topic_id`, is 45 characters, comfortably inside PostgreSQL's
  63-character limit. The unit test guarding that limit covers this table too.

**Remaining review inputs:**

| Review input | State |
| --- | --- |
| The final GATE CSE curriculum seed structure | **Reviewed 2026-08-05** — progress references `topics.id`, which the seed already creates and never deletes, so a re-seeded curriculum cannot orphan a learner's record. |
| The actual revision-scheduling rules | **Discharged** — supplied by [ADR-028](../adr/ADR-028-revision-workflow.md). |

One input remains pending, and it belongs to a table this review does not cover, so the area stays
**partly reviewed** for `learner_topic_progress` and unreviewed for the two tables that do not exist
yet.

### Resources and RAG metadata area — partial review 2026-08-16

This review covers only `resources` and `resource_topic_links`, the two tables migration
`20260816_01` creates, and only the eight of `resources`' ten documented columns that migration
creates. `resource_ingestions` is unreviewed and unimplemented. The decision it rests on is
[ADR-032](../adr/ADR-032-learning-resource-catalogue.md).

Covered by this review:

- The first API contracts — RES-001 to RES-004, fixed by ADR-032.
- The planned SQLAlchemy mapping strategy.
- Database constraints supported by the selected PostgreSQL and Alembic versions.
- The final GATE CSE curriculum seed structure, since a link references `topics.id`.

**No schema change resulted beyond the two tables this migration creates.** What the review settled:

- `resource_type` and `status` are `snake_case` text guarded by a `CHECK`, in `varchar(32)`. The
  longest values in use, `video_reference` and `registered`, are 15 and 10 characters. This follows
  the controlled-value convention ADR-011 chose rather than a PostgreSQL enum, so permitting `image`,
  `attachment`, or an ingestion state later stays an ordinary constraint change.
- **Two values are carried and five are not**, and the line between them is the one this document
  already draws for `plan_items.status` and `revision_records.trigger_type`. A value a later
  *use-case* change alone could write is carried: all four of
  `resource_topic_links.relationship_type`. A value that needs storage which does not exist is left
  out: `image` and `attachment` need a file, and `processing`, `ready`, and `failed` need
  `resource_ingestions`.
- `ck_resources_names_a_location` expresses the approved *at least one of `storage_key` or
  `external_reference`* invariant over the two columns this catalogue has. Both are `text` and
  nullable, so the check is the only thing that makes a resource say where its material is.
- "A link must be an `http` or `https` address" is **not** a database constraint. A `CHECK` over a
  scheme could be written, but the rule is about what the product accepts rather than what the
  column can hold, and a `422` naming the field is a better answer than an integrity error — the
  position this document takes on `topics.is_trackable`.
- Two columns are deliberately not created. Each is a nullable additive change when its writer
  arrives, so nothing here forecloses them.
- `resource_topic_links` is keyed on `(resource_id, topic_id, relationship_type)` as approved, which
  is what lets one resource cover many topics and one topic be covered by many resources. It carries
  `created_at` alone, as `topic_relationships` does.
- Neither foreign key cascades. Curriculum rows are reference data this document forbids deleting
  casually, and nothing deletes a resource at all, so a cascade would describe a deletion path that
  does not exist.
- Both required indexes were created with their tables. `resources(owner_learner_id, status)` serves
  the catalogue's own reads, and `resource_topic_links(topic_id, resource_id)` serves the topic
  filter the curriculum and revision screens depend on.
- The identifier-length precedent was checked: the longest name here,
  `ix_resource_topic_links_topic_id_resource_id`, is 44 characters, comfortably inside PostgreSQL's
  63-character limit. The unit test guarding that limit covers both tables.
- **No seed accompanies these tables.** Study material is the learner's own, so there is no natural
  key to reconcile and no reference data to load; the reconciliation rules
  [ADR-012](../adr/ADR-012-curriculum-seed-and-reconciliation.md) fixes do not apply here.

**Remaining review inputs:**

| Review input | State |
| --- | --- |
| The actual revision-scheduling rules | Not applicable to this area. A revision names a topic, never a resource. |
| Numeric precision for score and marks columns | Not applicable to this area. |

One table of this area does not exist yet, so it stays **partly reviewed** for the two created and
unreviewed for `resource_ingestions`.

### Assessment area — review 2026-08-18

This is a review of the assessment tables as created by migration
`20260818_01_create_assessment_tables`, which creates the area **whole** — all seven tables — with
the checkpoint-practice code that reads them (QZ-001 to QZ-010), per
[ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) and
[ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md). The area arrives whole rather than
partially because a quiz that cannot be attempted and an attempt that cannot be marked are not a
smaller feature but a broken one.

Reviewed against the inputs that exist: the final GATE CSE curriculum seed structure, the SQLAlchemy
mapping strategy, the first API contracts (QZ-001 to QZ-010), and the constraint support of
PostgreSQL 18 with Alembic. **One input stays pending**: the actual mistake-evidence rules, which
belong to `mistake_evidence` in the *External evidence* area and cannot be reviewed until the tables
its discovery sources reference exist.

[ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md) is implemented unchanged:
`checkpoint_quiz_topics` is the only quiz-to-topic link, `checkpoint_quizzes` has no `topic_id`, the
"at least one topic" rule is enforced in the use case because no simple constraint can express it,
and no quiz outcome is written to `external_test_topic_performance`.

#### Columns deliberately not created

Each is absent because nothing maintains it, which is the rule ADR-011 states and the reason
`learner_topic_progress` and `resources` each arrived short of their documented shape.

- **`questions.difficulty`.** An "optional controlled value" with no controlled vocabulary decided
  anywhere in this repository, and a difficulty would rank one question above another, which nothing
  in LearnFlow does.
- **`quiz_questions.max_marks`**, **`quiz_attempt_answers.awarded_marks`**, **`quiz_attempts.score`**,
  and **`quiz_attempts.max_score`.** These are a mark scheme, and this build has none: a result
  states per-question outcomes and no total at all. See ADR-033, which resolves the conflict between
  this document and [terminology](../domain/terminology.md) in terminology's favour. Their absence is
  also why the numeric-precision question above **stays open**.
- **`quiz_attempts.duration_seconds`.** Nothing times an attempt, and `started_at` and `submitted_at`
  already bound one, so storing the span between them would be a second source of truth.
- **`quiz_attempt_answers.feedback`.** It would freeze the explanation an answer was marked with. It
  is unnecessary because **a question a quiz has asked is never edited** — from then on it is only
  retired and rewritten — so the explanation on the question cannot drift away from an attempt
  marked against it. A question no quiz has asked may be corrected, and has no attempt to drift
  from ([ADR-035](../adr/ADR-035-practice-question-correction.md)). This is where the
  assessment area differs from `revision_records`, which needed `recommendation_reason` precisely
  because its inputs can move.

#### One column created beyond this document

- **`questions.author_learner_id`**, `uuid` FK to `learners.id`, **nullable**, indexed with `status`.
  Every question is written by the learner, and this document's own *Conventions* require a learner
  identifier on learner-owned records. It mirrors `resources.owner_learner_id` exactly, including its
  nullability, so the shared or curated bank this table was originally designed for still has
  somewhere to live. **Nothing writes an ownerless question today**: the use case requires an author
  on every write.

#### Controlled values

Every controlled column is `varchar(32)` guarded by a `CHECK` rather than the bare `text` above,
following this document's *Conventions* and ADR-011's validated-text rule, as every migration since
`20260806_01` has done.

Each `CHECK` carries **all** of its documented values, although the application writes a subset —
`multiple_choice` of the four question types, `curated` of the three source types, `ready` and
`retired` of the three question statuses, `ready` of the three quiz statuses, and `in_progress` and
`evaluated` of the four attempt statuses. None of the unwritten values needs storage that is missing,
so offering one later is a use-case change rather than a migration, which is the argument ADR-020
made for `plan_items.status` and ADR-032 for `relationship_type`.

#### `jsonb` payloads

`questions.options`, `questions.expected_answer`, and `quiz_attempt_answers.submitted_answer` are
`jsonb`, exactly as approved above. Their shape is fixed by the application and read and written in
one module: `options` holds `[{"key": "a", "text": "…"}, …]`, and both answer columns hold
`{"option_key": "a"}`. Keys are assigned by position by the domain rule and never accepted from a
caller, so a stored `expected_answer` always names an option the question offers.

`quiz_attempt_answers.is_correct` is nullable and stays so **deliberately**: null is a question the
learner left alone. An unanswered question is not a wrong one, and writing `false` there would state
something about the learner that they did not.

#### Constraints and indexes

`quiz_questions` keeps the approved unique `(checkpoint_quiz_id, position)`. The approved
`max_marks > 0` guards a column this migration does not create; what survives of it is
`position >= 1`, on the column that carries its role. `quiz_attempt_answers` keeps the approved
unique `(quiz_attempt_id, question_id)`.

Both indexes this document lists for the area are created. Two more are created that it does not
list, for access patterns the checkpoint-practice code has: `questions(author_learner_id, status)`
and `question_topic_links(topic_id, question_id)`. Both are recorded under *Required Indexes* above.

Curriculum foreign keys are **not** cascades, as elsewhere: curriculum rows are reference data that
learner records reference, and this document forbids deleting one casually.


## Related Documents

- [Project context](../00-project-context.md)
- [ADR-003: Use PostgreSQL for structured persistence](../adr/ADR-003-postgresql-persistence.md) — the decision this schema implements
- [ADR-008: Model assessment topics and mistake evidence sources explicitly](../adr/ADR-008-assessment-and-mistake-evidence-model.md) — the quiz-topic, mistake-source, and evidence-boundary rules
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](../adr/ADR-011-sqlalchemy-persistence-implementation.md) — the migration ordering and the constraint choices this document records
- [ADR-012: Load curriculum as reconciled reference data from a versioned file](../adr/ADR-012-curriculum-seed-and-reconciliation.md) — why `uq_topics_subject_id_code` exists and how the curriculum tables are populated
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — why the examination is periods rather than a date, and why `study_goals.target_date` is nullable
- [ADR-016: Fix the learner setup API contracts](../adr/ADR-016-learner-onboarding-api-contracts.md) — the endpoint contracts the two API reviews above were taken against
- [ADR-017: Record manual topic progress as a learner-owned stage](../adr/ADR-017-topic-progress-api-and-schema.md) — why `learner_topic_progress` is created without three of its documented columns, and why `stage_source` is not one of them
- [ADR-018: Store weekly availability as named days replaced a week at a time](../adr/ADR-018-weekly-availability-slots.md) — why `availability_slots.day_of_week` holds a day name rather than the documented `smallint`
- [ADR-019: Store planning preferences as typed columns replaced as a group](../adr/ADR-019-study-goal-planning-preferences.md) — why `study_goals` holds two typed preference columns rather than the documented `planning_preferences jsonb`
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](../adr/ADR-020-initial-study-plan-generation.md) — why the plan tables' controlled columns are `varchar(32)` guarded by a `CHECK` rather than the documented `text`, and the code that reads them
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](../adr/ADR-021-plan-item-completion.md) — the first code to write `plan_items.status` and `completed_at`, and why it needed no migration
- [ADR-022: Adapt a study plan by rebuilding it around what happened](../adr/ADR-022-plan-adaptation.md) — the first code to write `postponed`, and why it needed no migration either
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](../adr/ADR-024-plan-item-skipping.md) — the first code to write `skipped`, the last unwritten value of the `status` `CHECK`, and why no `skipped_at` column exists
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](../adr/ADR-025-learner-postponement.md) — the second writer of `postponed`, and why no `postponed_at` column and no status-source column exist
- [Database overview](overview.md)
- [Database migrations](migrations.md)
- [Delivery milestones](../roadmap/milestones.md) — when each pending schema area is migrated
- [Domain model](../domain/domain-model.md)
- [Functional requirements](../requirements/functional.md)
- [API endpoints](../api/endpoints.md)
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](../adr/ADR-032-learning-resource-catalogue.md) — the two resource tables above, the two columns they leave uncreated, and why a link is a web address
- [ADR-028: Schedule revisions from finished work, on the learner's ask](../adr/ADR-028-revision-workflow.md) — `revision_records`, its two departures from the table above, and the revision-scheduling rules this document held pending
