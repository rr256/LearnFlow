---
title: LearnFlow API Conventions
status: approved
owner: architecture-and-api
last_updated: 2026-08-05
related:
  - ../00-project-context.md
  - endpoints.md
  - versioning.md
  - ../adr/ADR-014-api-response-contract.md
  - ../adr/ADR-016-learner-onboarding-api-contracts.md
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

### Operational Endpoints Are Unversioned

Operational endpoints sit outside `/api/v1` by design:

```text
GET /health
```

They report process readiness for local environment checks, container health probes, and future deployment tooling. That tooling must not have to track the application API version, so these paths stay stable across API major versions.

Operational endpoints return no learner data, no curriculum content, and no provider configuration or secrets. Any endpoint that returns learner-facing data is an application endpoint and belongs under `/api/v1`, regardless of how simple it is.

Operational endpoints are also exempt from the `data` response envelope described below. They return a flat object, because container health probes and monitoring tools read the status field directly and should not have to traverse an envelope:

```json
{ "status": "ok" }
```

This exemption applies only to operational endpoints. Every endpoint under `/api/v1` uses the envelope.

## Resource Naming

- Use plural, lowercase, kebab-case resource names: `/study-plans`, `/resources`, `/quiz-attempts`. Separate words with hyphens; do not use underscores or camelCase in a path segment.
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

Application endpoints under `/api/v1` return the resource or action result directly under a `data` property. Operational endpoints are exempt, as described above.

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

All expected API errors use a consistent envelope. This is the whole of it — a client can rely on
these three keys and no others:

```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found.",
    "details": []
  }
}
```

### Error Rules

- `code` is stable and machine-readable.
- `message` is safe and understandable for a learner/developer.
- `details` is optional structured validation information; never expose secrets, stack traces, provider credentials, or raw database errors.
- A correlation identifier is **not** part of the envelope. See [Correlation identifiers](#correlation-identifiers) below.

### Error Codes

`code` is part of the public contract, so each value is stable and documented before a client can depend on it. The catalogue and the rules around it are decided in [ADR-014](../adr/ADR-014-api-response-contract.md). These are the codes the API emits today:

| Status | `code` | Meaning |
| --- | --- | --- |
| `404` | `not_found` | The addressed record does not exist, or the path matches no endpoint. |
| `405` | `method_not_allowed` | The path exists but does not support the method used. |
| `409` | `conflict` | The request conflicts with what is already stored. |
| `422` | `validation_error` | Request validation failed. `details` names each offending field. |
| `500` | `internal_error` | An unexpected server failure. No internal detail is returned. |
| any other | `request_failed` | Fallback for a status no endpoint yet returns deliberately. Give a status its own code here when an endpoint starts using it. |

`conflict` was added with the learner and study-goal endpoints, the first to return `409`
deliberately. Three conditions produce it today, and each is a request that cannot be satisfied
because of what is or is not already stored, rather than a malformed one:

- An active study goal already exists for the learning program (GOAL-001).
- No learner exists yet, so there is nobody to own a goal (GOAL-001).
- More than one learner is stored, so the local learner is undefined (every learner-owned endpoint).

Adding the code was a compatible change under the rule below, because `409` previously fell back to
`request_failed`.

The `404` code is `not_found`, not `resource_not_found`. **Resource** is a canonical LearnFlow term for a learner's study material, and `/api/v1/resources` is reserved for it under RES-001 to RES-008; a generic code carrying that word would make one name mean two things. See [terminology](../domain/terminology.md) and [ADR-014](../adr/ADR-014-api-response-contract.md).

Changing the code an existing status returns is a breaking change under [versioning](versioning.md#breaking-changes). Giving a status its own code where it previously fell back to `request_failed` is compatible, in the same sense as a new optional response field — no documented code changes meaning, and a client handling the fallback keeps working.

`details` entries carry `field`, `message`, and `type`. `field` is the dotted request location, such as `query.limit` or `path.program_id`; `type` is the stable validation-rule name. The rejected value itself is never echoed back.

Every error under `/api/v1` uses this envelope, and so does a `404` for a path no endpoint claims — a client that mistypes a URL must not receive a differently shaped body from one that requests a missing record. Operational endpoints are exempt from the `data` envelope on success, as described above, but their failures use this error envelope too.

### Correlation Identifiers

The error envelope carries no correlation identifier, and the example above shows every key an error
response contains today.

Nothing in the backend generates one. A `request_id` key was previously illustrated as "optional",
which left it ambiguous whether a client should look for it; it never appeared in a response, because
there was no value to put in it. Documenting a field the application does not emit is worse than
documenting nothing — a client writes a branch that never runs, and a diagnostic workflow is built
around an identifier that does not exist.

A correlation identifier is added to this envelope **only in the change that makes the application
actually emit one**, together with whatever generates and propagates it. Until then it is absent
rather than `null`, because a `null` would tell a client the field exists and its value is unknown.
Adding it later is a compatible change under [versioning](versioning.md#compatible-changes-within-a-major-version):
a client that ignores unknown optional response fields is unaffected.

### Typical Status Codes

| Status | Use |
| --- | --- |
| `400` | Invalid request state or malformed action not covered by validation. |
| `401` | Authentication required when authentication is introduced. |
| `403` | Authenticated identity lacks access to a learner-owned resource. |
| `404` | Record does not exist or is not visible to the caller. |
| `405` | Path exists but does not support the method used. |
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

Collection endpoints use a consistent query style:

```text
?limit=25&offset=0
?status=active
?topic_id={uuid}
?sort=-created_at
```

- `limit` and `offset` are the MVP pagination convention. A collection endpoint accepts both and returns the [`pagination` block](#success-response-shapes) **from its first version**, whatever the collection currently holds — a client cannot otherwise tell a complete collection from a truncated one, and "when it grows large enough" is a judgement that changes as the data does. Decided in [ADR-014](../adr/ADR-014-api-response-contract.md).
- `limit` defaults to 25 and is bounded to 1–100. The bound is part of the contract, not a defensive detail: an unbounded `limit` is a request to materialise an entire table.
- `offset` defaults to 0 and must be 0 or greater.
- `pagination.total` counts every matching record, ignoring the window.
- A `limit` or `offset` outside those bounds is a `422` `validation_error`.
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
- [ADR-014: Fix the public HTTP API response contract](../adr/ADR-014-api-response-contract.md) — the durable rationale for the envelope, the pagination block, and the error-code catalogue
- [ADR-016: Fix the learner setup API contracts](../adr/ADR-016-learner-onboarding-api-contracts.md) — the change that added `conflict` to the catalogue above
- [API endpoints](endpoints.md)
- [API versioning](versioning.md)
- [Clean Architecture](../architecture/clean-architecture.md)
- [Domain terminology](../domain/terminology.md)
- [Functional requirements](../requirements/functional.md)
