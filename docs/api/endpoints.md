---
title: LearnFlow API Endpoint Catalog
status: approved
owner: architecture-and-api
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - conventions.md
  - ../requirements/functional.md
  - ../domain/domain-model.md
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
| OPS-001 | `GET /health` | Report API readiness for local environment checks. | Operational endpoint; intentionally outside `/api/v1` so health probes stay stable across API major versions. Does not expose learner data or provider secrets. |

## Curriculum Endpoints

Supports **FR-001 — Curated GATE CSE Learning Program**.

| ID | Method and path | Purpose | Primary response |
| --- | --- | --- | --- |
| CUR-001 | `GET /api/v1/curriculum/programs` | List available learning programs. | Programs, including GATE CSE. |
| CUR-002 | `GET /api/v1/curriculum/programs/{program_id}` | Read program metadata and active curriculum-version reference. | Program details. |
| CUR-003 | `GET /api/v1/curriculum/versions/{curriculum_version_id}/tree` | Read subjects, topics, subtopics, and supported relationships. | Data-driven curriculum hierarchy. |

The frontend must use these endpoints rather than embedding GATE CSE topic data in code.

## Learner Setup and Goal Endpoints

Supports **FR-002 — Initial Learner Setup**.

| ID | Method and path | Purpose | Primary request/result |
| --- | --- | --- | --- |
| LRN-001 | `GET /api/v1/learner/profile` | Read local learner profile/preferences. | Current learner summary. |
| LRN-002 | `PATCH /api/v1/learner/profile` | Update learner display preferences/timezone. | Updated profile. |
| GOAL-001 | `POST /api/v1/study-goals` | Create a study goal for a selected program/version and target date. | Goal data. |
| GOAL-002 | `GET /api/v1/study-goals` | List the learner's goals. | Goal collection. |
| GOAL-003 | `GET /api/v1/study-goals/{goal_id}` | Read one study goal. | Goal + availability summary. |
| GOAL-004 | `PATCH /api/v1/study-goals/{goal_id}` | Update target date, status, or planning preferences. | Updated goal. |
| GOAL-005 | `PUT /api/v1/study-goals/{goal_id}/availability` | Replace recurring weekly available study time. | Saved availability slots. |

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

1. Operational health and curriculum reads.
2. Learner setup and study-goal creation.
3. Progress reads/updates and basic study activities.
4. Plan generation/read/update.
5. Revision reads/updates.
6. Resource registration and ingestion status.
7. Mentor questions and grounded retrieval.
8. Checkpoint quizzes and attempts.
9. External test result entry and analysis.

## Related Documents

- [Project context](../00-project-context.md)
- [API conventions](conventions.md)
- [API versioning](versioning.md)
- [Functional requirements](../requirements/functional.md)
- [Domain model](../domain/domain-model.md)
- [Database schema](../database/schema.md)
