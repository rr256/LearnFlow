---
title: LearnFlow API Endpoint Catalog
status: approved
owner: architecture-and-api
last_updated: 2026-08-01
related:
  - ../00-project-context.md
  - conventions.md
  - ../requirements/functional.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../roadmap/milestones.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
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
returns per item. Errors: `404` `resource_not_found` when no such program is stored; `422`
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
`resource_not_found` when no such version is stored; `422` `validation_error` when the path segment
is not a UUID.

Related entities: [learning program](../domain/entities.md#learning-program),
[curriculum version](../domain/entities.md#curriculum-version),
[subject](../domain/entities.md#subject), [topic](../domain/entities.md#topic), and
[topic relationship](../domain/entities.md#topic-relationship). Related tables:
[curriculum schema area](../database/schema.md#schema-areas). The rows they return are loaded by
[the curriculum seed](../database/migrations.md#the-curriculum-seed).

## Learner Setup and Goal Endpoints

Supports **FR-002 — Initial Learner Setup**.

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| LRN-001 | `GET /api/v1/learner/profile` | Read local learner profile/preferences. | Current learner summary. |
| LRN-002 | `PATCH /api/v1/learner/profile` | Update learner display preferences/timezone. | Updated profile. |
| GOAL-001 | `POST /api/v1/study-goals` | Create a study goal for a selected program/version, aiming at an examination cycle, a target date, or both. | Goal data, including the examination window when a cycle is named. |
| GOAL-002 | `GET /api/v1/study-goals` | List the learner's goals. | Goal collection. |
| GOAL-003 | `GET /api/v1/study-goals/{goal_id}` | Read one study goal. | Goal + availability summary. |
| GOAL-004 | `PATCH /api/v1/study-goals/{goal_id}` | Update the examination cycle, target date, status, or planning preferences. | Updated goal. |
| GOAL-005 | `PUT /api/v1/study-goals/{goal_id}/availability` | Replace recurring weekly available study time. | Saved availability slots. |

A goal aims at an examination cycle, a target date, or both, and never at neither — a rule the
database enforces. A response reports an examination as a **window** spanning the published sitting
days, together with the source it came from and whether those dates are still provisional; it never
reports a single examination date the examining body has not published. None of these endpoints is
implemented; their request and response schemas are written with the client that consumes them. See
[ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md).

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

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| PRG-001 | `GET /api/v1/progress/overview` | Read learner summary: progress, current plan, revisions due, and priority focus areas. | Dashboard-ready overview. |
| PRG-002 | `GET /api/v1/progress/topics` | List topic-progress records, filterable by curriculum, subject, stage, or material status. | Topic progress collection. |
| PRG-003 | `GET /api/v1/progress/topics/{topic_id}` | Read detailed progress/evidence for one topic. | Progress summary, evidence, and next action. |
| PRG-004 | `PATCH /api/v1/progress/topics/{topic_id}` | Update learner-entered material status or learning stage. | Updated topic progress. |
| ACT-001 | `POST /api/v1/study-activities` | Record actual study, practice, revision, or mistake-review activity. | Activity record; optional progress/recommendation update. |
| ACT-002 | `GET /api/v1/study-activities` | Read activity history with date/topic filters. | Activity collection. |

The API must not treat a plan-item update, a manual stage update, or one quiz result as automatic permanent mastery.

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
2. Learner setup and study-goal creation. Gated on the client that consumes it, per
   [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md); the order below resumes once
   those schemas can be written against a real caller.
3. Progress reads/updates and basic study activities.
4. Plan generation/read/update.
5. Revision reads/updates.
6. Resource registration and ingestion status.
7. Mentor questions and grounded retrieval.
8. Checkpoint quizzes and attempts.
9. External test result entry and analysis.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — what a study goal aims at, and why the goal endpoints are deferred
- [API conventions](conventions.md)
- [API versioning](versioning.md)
- [Functional requirements](../requirements/functional.md)
- [Domain model](../domain/domain-model.md)
- [Domain entities](../domain/entities.md) — the entities the implemented endpoints return
- [Database schema](../database/schema.md)
- [Database migrations](../database/migrations.md) — the seed that loads the rows the curriculum endpoints serve
- [Delivery milestones](../roadmap/milestones.md) — which endpoints each milestone delivers
