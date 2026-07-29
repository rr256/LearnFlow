---
title: LearnFlow Database Schema
status: approved
owner: architecture-and-data
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - overview.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - migrations.md
---

# LearnFlow Database Schema

## Purpose

Define the initial logical PostgreSQL schema for LearnFlow. This is the baseline for SQLAlchemy models and Alembic migrations, not executable SQL.

## Conventions

- Primary keys use `uuid`.
- Timestamps use timezone-aware UTC `timestamptz`.
- Tables that represent durable records include `created_at` and `updated_at` unless noted otherwise.
- Enumerated values may be implemented with PostgreSQL enums or validated text fields; the API/domain vocabulary remains authoritative.
- Foreign keys use database constraints. Complex cross-row rules may be validated in application logic where a simple constraint is insufficient.
- `jsonb` is reserved for flexible provider/resource payloads, not core relational concepts.
- Single-user MVP records still include `learner_id` where the data is learner-owned.

## Schema Areas

```text
Curriculum
  learning_programs → curriculum_versions → subjects → topics

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
| `timezone` | text | IANA timezone; default configured local timezone. |
| `created_at` | timestamptz | Creation timestamp. |
| `updated_at` | timestamptz | Last update timestamp. |

### `learning_programs`

Stores reusable programs such as GATE CSE.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Program identifier. |
| `code` | text unique | Stable code, e.g. `gate-cse`. |
| `name` | text | Display name. |
| `description` | text nullable | Program description. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

### `curriculum_versions`

Stores a versioned curriculum for a learning program.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Version identifier. |
| `learning_program_id` | uuid FK | References `learning_programs.id`. |
| `version_label` | text | Human-readable version. |
| `status` | text | `draft`, `active`, or `retired`. |
| `source_reference` | text nullable | Official or curator reference. |
| `published_at` | timestamptz nullable | When the version became active. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(learning_program_id, version_label)`; at most one active version per program should be enforced by a partial unique index or application workflow.

### `subjects`

Stores major areas within a curriculum version.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Subject identifier. |
| `curriculum_version_id` | uuid FK | References `curriculum_versions.id`. |
| `code` | text | Stable subject code within the version. |
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
| `code` | text nullable | Stable optional code within subject. |
| `name` | text | Display name. |
| `description` | text nullable | Optional scope/definition. |
| `position` | integer | Display/recommended order. |
| `is_trackable` | boolean | Whether learner progress can be recorded directly. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(subject_id, parent_topic_id, name)`; parent/child subject consistency is validated in application logic or a database trigger.

### `topic_relationships`

Stores prerequisite and sequencing relationships.

| Column | Type | Notes |
| --- | --- | --- |
| `source_topic_id` | uuid FK | References `topics.id`. |
| `target_topic_id` | uuid FK | References `topics.id`. |
| `relationship_type` | text | `prerequisite`, `recommended_before`, or `related`. |
| `created_at` | timestamptz | Creation timestamp. |

**Primary key:** `(source_topic_id, target_topic_id, relationship_type)`.

**Constraints:** source and target must differ.

### `study_goals`

Stores a learner's goal and planning target.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Goal identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `learning_program_id` | uuid FK | References `learning_programs.id`. |
| `curriculum_version_id` | uuid FK | References `curriculum_versions.id`. |
| `target_date` | date | Target exam/completion date. |
| `status` | text | `active`, `paused`, `completed`, or `archived`. |
| `planning_preferences` | jsonb nullable | Non-core preferences, versioned carefully. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

### `availability_slots`

Stores recurring available study time for a study goal.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Slot identifier. |
| `study_goal_id` | uuid FK | References `study_goals.id`. |
| `day_of_week` | smallint | 0–6 according to documented convention. |
| `available_minutes` | integer | Non-negative study time. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(study_goal_id, day_of_week)`; `available_minutes >= 0`.

### `study_plans`

Stores a generated or learner-adjusted plan.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Plan identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `study_goal_id` | uuid FK | References `study_goals.id`. |
| `plan_type` | text | `roadmap`, `monthly`, `weekly`, or `daily`. |
| `period_start` | date nullable | Start of covered period. |
| `period_end` | date nullable | End of covered period. |
| `status` | text | `draft`, `active`, `superseded`, or `archived`. |
| `generation_reason` | text nullable | Why it was created/replanned. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

### `plan_items`

Stores one actionable recommendation within a plan.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Plan item identifier. |
| `study_plan_id` | uuid FK | References `study_plans.id`. |
| `topic_id` | uuid FK nullable | References `topics.id`. |
| `action_type` | text | `study`, `practice`, `revise`, or `review_mistakes`. |
| `scheduled_for` | date nullable | Recommended date. |
| `estimated_minutes` | integer nullable | Expected effort. |
| `priority` | integer | Relative plan priority. |
| `status` | text | `planned`, `completed`, `skipped`, or `postponed`. |
| `recommendation_reason` | text nullable | Learner-facing rationale. |
| `completed_at` | timestamptz nullable | Completion timestamp. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** `estimated_minutes > 0` when present.

### `learner_topic_progress`

Stores the current learner-specific progress summary for a topic.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Progress identifier. |
| `learner_id` | uuid FK | References `learners.id`. |
| `topic_id` | uuid FK | References `topics.id`. |
| `material_status` | text | `not_started`, `in_progress`, or `completed`. |
| `learning_stage` | text | Approved learner-visible stage. |
| `stage_source` | text | `learner`, `derived`, or `mixed`. |
| `last_studied_at` | timestamptz nullable | Most recent study evidence. |
| `material_completed_at` | timestamptz nullable | When material was marked completed. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** unique `(learner_id, topic_id)`.

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
| `trigger_type` | text | Why revision was created, e.g. completion, low evidence, spaced schedule. |
| `completed_at` | timestamptz nullable | Completion timestamp. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

### `resources`

Stores resource metadata, not the primary file binary.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | Resource identifier. |
| `owner_learner_id` | uuid FK nullable | References `learners.id`; null for curated/shared future content. |
| `resource_type` | text | `pdf`, `note`, `pyq`, `formula_sheet`, `video_reference`, `image`, or `attachment`. |
| `title` | text | Learner-facing title. |
| `source_label` | text nullable | Optional source attribution. |
| `storage_key` | text nullable | Opaque storage-provider reference. |
| `external_reference` | text nullable | Local video/reference metadata, not a provider credential. |
| `metadata` | jsonb nullable | File-specific metadata. |
| `status` | text | `registered`, `processing`, `ready`, `failed`, or `archived`. |
| `created_at`, `updated_at` | timestamptz | Audit timestamps. |

**Constraints:** require at least one of `storage_key` or `external_reference`.

### `resource_topic_links`

Links a resource to curriculum topics.

| Column | Type | Notes |
| --- | --- | --- |
| `resource_id` | uuid FK | References `resources.id`. |
| `topic_id` | uuid FK | References `topics.id`. |
| `relationship_type` | text | `primary`, `supporting`, `practice`, or `revision`. |
| `created_at` | timestamptz | Creation timestamp. |

**Primary key:** `(resource_id, topic_id, relationship_type)`.

### `resource_ingestions`

Tracks extraction and indexing of eligible resources.

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

Create indexes in addition to primary/unique keys for likely MVP access patterns:

- `topics(subject_id, parent_topic_id, position)`
- `learner_topic_progress(learner_id, topic_id)` unique
- `study_plans(learner_id, study_goal_id, status, period_start)`
- `plan_items(study_plan_id, scheduled_for, status)`
- `revision_records(learner_id, due_on, status)`
- `study_activities(learner_id, topic_id, created_at desc)`
- `resource_topic_links(topic_id, resource_id)`
- `resources(owner_learner_id, status)`
- `resource_ingestions(resource_id, status)`
- `checkpoint_quiz_topics(topic_id, checkpoint_quiz_id)`
- `quiz_attempts(learner_id, checkpoint_quiz_id, created_at desc)`
- `external_test_results(learner_id, taken_on desc)`
- `external_test_topic_performance(topic_id, external_test_result_id)`
- `mistake_evidence(learner_id, topic_id, resolved_at)`

## Referential-Integrity and Lifecycle Notes

- Curriculum records are reference data and should not be casually deleted once learner records reference them.
- Deleting a learner-owned resource requires coordinated cleanup of file storage and derived vector records; do not rely only on cascading database deletion.
- Plans may be superseded rather than deleted so the learner's plan history remains explainable.
- Quiz attempts and external test results are historical evidence and should normally be retained even when a current plan changes.
- Indexing metadata is not the source of truth for a resource and can be recreated from the original resource file and metadata.

## Implementation Review Required

Before the first migration, review this schema against:

- The final GATE CSE curriculum seed structure.
- The planned SQLAlchemy mapping strategy.
- The first API contracts.
- The actual revision-scheduling rules.
- Database constraints supported by the selected PostgreSQL/Alembic versions.

Any material change must update this document and be implemented through an Alembic migration.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-003: Use PostgreSQL for structured persistence](../adr/ADR-003-postgresql-persistence.md) — the decision this schema implements
- [ADR-008: Model assessment topics and mistake evidence sources explicitly](../adr/ADR-008-assessment-and-mistake-evidence-model.md) — the quiz-topic, mistake-source, and evidence-boundary rules
- [Database overview](overview.md)
- [Database migrations](migrations.md)
- [Domain model](../domain/domain-model.md)
- [Functional requirements](../requirements/functional.md)
- [API endpoints](../api/endpoints.md)
