---
title: LearnFlow API Conventions
status: approved
owner: architecture-and-api
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - endpoints.md
  - versioning.md
  - ../architecture/clean-architecture.md
---

# LearnFlow API Conventions

## Purpose

Define consistent HTTP API behavior before individual endpoints are implemented.

The API is the boundary between the LearnFlow frontend and backend. It exposes learner-facing capabilities, not database tables, ORM models, provider SDKs, or internal architecture details.

## Base Path and Version

All public application endpoints use:

```text
/api/v1/
```

Examples:

```text
GET  /api/v1/curriculum/programs
GET  /api/v1/progress/topics
POST /api/v1/mentor/questions
```

Detailed compatibility and deprecation policy belongs in `versioning.md`.

## Resource Naming

- Use plural, lowercase, hyphen-free resource names: `/study-plans`, `/resources`, `/quiz-attempts`.
- Use nouns for resources and explicit action names only where a workflow is a command rather than CRUD.
- Use nested paths only when the child has meaning only under its parent.

Examples:

```text
GET  /study-plans/{plan_id}/items
POST /study-plans/generate
POST /mentor/questions
POST /resources/{resource_id}/ingestions
POST /quiz-attempts/{attempt_id}/submit
```

Avoid endpoint names based on implementation details, such as `/ollama-chat`, `/chromadb-search`, or `/database-progress`.

## HTTP Methods and Status Codes

| Operation | Method | Typical success response |
| --- | --- | --- |
| Read a collection or resource | `GET` | `200 OK` |
| Create a resource | `POST` | `201 Created` |
| Replace a full resource | `PUT` | `200 OK` |
| Update part of a resource | `PATCH` | `200 OK` |
| Delete a resource | `DELETE` | `204 No Content` |
| Start an action/command | `POST` | `200 OK`, `201 Created`, or `202 Accepted` |
| Long-running work accepted | `POST` | `202 Accepted` with status/reference information |

Use `202 Accepted` for resource ingestion, indexing, or other operations that are accepted but not completed in the request-response cycle.

## JSON Naming and Data Formats

- JSON fields use `snake_case`.
- IDs are UUID strings.
- Date-only values use ISO 8601 `YYYY-MM-DD`.
- Timestamps use ISO 8601 UTC timestamps with timezone information.
- Durations use explicit fields such as `duration_minutes` or `duration_seconds`; do not use ambiguous numeric fields.
- Percentages use explicit names such as `accuracy_percent` and values from 0 to 100.
- Enumerated fields use the canonical values defined in `docs/domain/terminology.md` and related documents.

## Success Response Shapes

Return the resource or action result directly under a `data` property.

```json
{
  "data": {
    "id": "uuid",
    "status": "active"
  }
}
```

For collections:

```json
{
  "data": [
    { "id": "uuid" }
  ],
  "pagination": {
    "limit": 25,
    "offset": 0,
    "total": 1
  }
}
```

Do not return raw ORM/persistence models. API schemas are explicit contracts.

## Error Response Shape

All expected API errors use a consistent envelope:

```json
{
  "error": {
    "code": "resource_not_found",
    "message": "The requested resource was not found.",
    "details": [],
    "request_id": "optional-correlation-id"
  }
}
```

### Error Rules

- `code` is stable and machine-readable.
- `message` is safe and understandable for a learner/developer.
- `details` is optional structured validation information; never expose secrets, stack traces, provider credentials, or raw database errors.
- `request_id` is included when available to support diagnostics.

### Typical Status Codes

| Status | Use |
| --- | --- |
| `400` | Invalid request state or malformed action not covered by validation. |
| `401` | Authentication required when authentication is introduced. |
| `403` | Authenticated identity lacks access to a learner-owned resource. |
| `404` | Resource does not exist or is not visible to the caller. |
| `409` | State conflict, such as invalid concurrent update. |
| `422` | Request validation failed. |
| `429` | Rate limit reached, if rate limiting is introduced. |
| `500` | Unexpected server failure; return no internal implementation detail. |
| `503` | Required dependency, such as an AI provider, is unavailable. |

## Validation Rules

- Validate request shape and basic field constraints at the API boundary.
- Validate business rules in application/domain use cases, not only in API schemas.
- Return field-specific validation details where safe and helpful.
- Reject unknown or unsupported enum values rather than silently coercing them.
- Do not trust client-supplied learner ownership, provider configuration, derived scores, or internal status values.

## Learner Ownership and Authentication Boundary

The local MVP has one learner and does not expose public registration/login flows. However:

- Learner-owned APIs must be designed around an effective learner identity.
- The backend determines that identity from configured local context now and authenticated context later.
- Clients must not freely choose another `learner_id` to read or modify data.
- Future authentication/authorization must be added at the API boundary without changing domain rules.

## Filtering, Sorting, and Pagination

Collection endpoints use a consistent query style when needed:

```text
?limit=25&offset=0
?status=active
?topic_id={uuid}
?sort=-created_at
```

- `limit` and `offset` are the MVP pagination convention.
- Sort prefix `-` indicates descending order.
- Endpoint documentation defines supported filters and sorts; unsupported query parameters should be rejected or ignored consistently.

## Action Endpoints

Use an action endpoint when the request represents a command or workflow rather than simple resource creation.

Examples:

- Generate/adapt a study plan.
- Ask the mentor a question.
- Start resource ingestion.
- Submit a quiz attempt.
- Mark a revision completed.

Action requests must return an explicit result, accepted operation, or a clear error. They must not hide long-running work or silently update unrelated learner records.

## Long-Running Operations

Resource extraction/indexing and some AI operations may take longer than ordinary API requests.

- Return `202 Accepted` when work continues asynchronously.
- Return a stable operation/resource identifier or ingestion status reference.
- Expose status through a documented read endpoint.
- Clearly distinguish `queued`, `processing`, `completed`, and `failed` states.
- Preserve failure information in a safe, user-understandable form.

## AI and Resource Safety

- The API does not expose raw Ollama, ChromaDB, filesystem, or database endpoints to the frontend.
- Mentor requests use application-controlled topic/progress/resource context.
- AI responses are advisory and must not silently mutate progress, learning stage, plan items, or revisions.
- Resource endpoints expose safe metadata and controlled download/view behavior; they do not expose absolute local filesystem paths.

## Idempotency and Retries

For the MVP, ordinary creation actions are not assumed idempotent unless endpoint documentation says otherwise. Clients should avoid automatic duplicate submission.

For later multi-user/cloud use, support an `Idempotency-Key` header for actions where duplicate creation would be harmful, especially assessment submission and external-test recording.

## API Documentation Requirements

Each endpoint entry in `endpoints.md` must define:

- Purpose and requirement IDs served.
- Method and path.
- Identity/authorization expectation.
- Request schema and validation.
- Success response and status code.
- Expected error codes.
- Whether it is synchronous or asynchronous.
- Related domain entities and use cases.

## Related Documents

- [Project context](../00-project-context.md)
- [API endpoints](endpoints.md)
- [API versioning](versioning.md)
- [Clean Architecture](../architecture/clean-architecture.md)
- [Domain terminology](../domain/terminology.md)
- [Functional requirements](../requirements/functional.md)
