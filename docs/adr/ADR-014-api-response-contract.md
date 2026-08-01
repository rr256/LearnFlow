---
title: "ADR-014: Fix the Public HTTP API Response Contract"
status: accepted
owner: architecture-and-api
last_updated: 2026-08-01
related:
  - ../00-project-context.md
  - ADR-001-clean-architecture.md
  - ADR-010-feature-delivery-workflow.md
  - ADR-013-examination-schedule-and-study-goal.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../domain/terminology.md
  - ../development/coding-standards.md
  - ../architecture/decisions.md
---

# ADR-014: Fix the Public HTTP API Response Contract

## Status

Accepted — 2026-08-01

## Context

[api/conventions.md](../api/conventions.md) has been approved since the documentation foundation. It
fixes three things about every `/api/v1` response: a success envelope with the result under `data`, a
collection shape adding a `pagination` block, and an error envelope with a `code`, a `message`,
optional `details`, and an optional `request_id`.

Implementing the first endpoints — the curriculum reads CUR-001 to CUR-003 — showed that the
approved document decides the *shapes* but not enough of their *contents* for a client to be written
against them:

1. **No error code exists except by example.** `conventions.md` requires `code` to be "stable and
   machine-readable" and illustrates the envelope with one value. It names no catalogue, so every
   endpoint would otherwise invent its own, and the first client would depend on strings no document
   had approved.

2. **The framework's own errors do not use the envelope.** FastAPI returns a bare `{"detail": [...]}`
   for a validation failure and plain text for an unhandled exception, and Starlette returns
   `{"detail": "Not Found"}` for a path no router claims. Left alone, a client would meet three
   different error shapes from one API, only one of them documented.

3. **`details` has no entry shape.** The envelope declares `details` as "optional structured
   validation information" and forbids leaking secrets, stack traces, or raw database errors, but
   does not say what a well-formed entry contains — and the framework's default fills it with the
   rejected input.

4. **Pagination is conditional.** `conventions.md` says collection endpoints use `limit` and `offset`
   "when needed", so the first collection had to decide whether "needed" means "large today".

A fifth question surfaced during review rather than implementation. The illustrative `404` code is
`resource_not_found`, and **resource** is a canonical term in
[terminology](../domain/terminology.md) for a learner's study material — PDFs, notes, PYQs. The
endpoint catalogue already reserves `/api/v1/resources` for exactly that under RES-001 to RES-008. A
generic code carrying the word would make one name mean two things in the same contract, and it
would be a breaking change to correct once a client depended on it.

None of these is answerable from an implementation seat: `versioning.md` classifies changing the
error-envelope shape or a stable error code as a breaking change, so each answer is a public
commitment.

## Decision

### The response envelope stays as `conventions.md` describes it, and this record makes it binding

A single record or action result is returned under `data`. A collection is returned as a `data`
array plus a `pagination` object carrying `limit`, `offset`, and `total`. Operational endpoints —
`GET /health` today — remain exempt from the `data` envelope on success, because probe tooling reads
the status field directly.

No endpoint returns a bare array, a bare scalar, or a persistence model. `data` exists so a response
can gain a sibling key — `pagination` today, a cursor or a warning block later — without changing
the shape a client already parses.

### A collection endpoint carries the `pagination` block from its first version

`limit` defaults to 25 and is bounded to 1–100; `offset` defaults to 0 and must be 0 or greater.
`total` counts every matching record, ignoring the window.

The block is present even when a collection holds one row. "When needed" is a judgement that changes
as data grows, and a client that has to discover pagination later cannot distinguish a complete list
from a truncated one in the meantime. A bound on `limit` is part of the contract rather than a
defensive detail: an unbounded `limit` is a request to materialise an entire table.

### Every failure returns the error envelope, including ones the application did not raise

The framework's default error bodies are replaced at the application level, not per router. A
validation failure, an unmatched path, an unsupported method, and an unhandled exception all return:

```json
{ "error": { "code": "...", "message": "...", "details": [] } }
```

An unmatched path is included deliberately. A client that mistypes a URL must not receive a
differently shaped body from one that requests a record that does not exist, because both are
handled by the same client-side code.

### The error-code catalogue is closed, with a named fallback

| Status | `code` |
| --- | --- |
| `404` | `not_found` |
| `405` | `method_not_allowed` |
| `422` | `validation_error` |
| `500` | `internal_error` |
| any other | `request_failed` |

A status not in the table returns `request_failed` rather than an improvised code, so no undocumented
string can reach a client. A status gains its own code in the change where an endpoint starts
returning it deliberately; that is a compatible change, because no documented code changes meaning
and a client handling the fallback keeps working.

### The `404` code is `not_found`

Not `resource_not_found`. **Resource** belongs to the learner's study material in LearnFlow's
vocabulary, and `/api/v1/resources` is reserved for it. `not_found` names the HTTP condition without
borrowing a domain term, so `resource_not_found` stays available should the resource endpoints ever
need a code of their own.

### A `details` entry is `field`, `message`, and `type`, and never the rejected input

`field` is the dotted request location — `query.limit`, `path.program_id`. `message` explains the
failure. `type` is the stable validation-rule name, so a client can branch on the rule rather than
parse prose.

The rejected value is deliberately excluded. Pydantic reports it by default, and echoing it back
returns whatever a client sent — into a response body, and into any log or error tracker that
records one. A caller already knows what it sent.

### A `500` never carries the reason, and `request_id` is omitted until it exists

An unhandled exception returns a fixed message. Its text can otherwise carry a database error, a file
path, or a connection string; the detail goes to the log instead.

`request_id` is documented as included *when available*. Nothing generates a correlation identifier
yet, so the key is absent rather than `null` — a null would tell a client the value exists and is
unknown. It is added with the mechanism that produces it.

## Consequences

### Positive

- A client can be written against a documented contract rather than against observed behaviour, which
  is what [ADR-013](ADR-013-examination-schedule-and-study-goal.md) requires before the deferred
  learner and study-goal endpoints are shaped.
- One error shape covers every failure, so client error handling is written once.
- The rejected-input rule and the fixed `500` message make the two most common accidental leaks —
  echoed payloads and raw exception text — structurally impossible rather than a review habit.
- Correcting `resource_not_found` now costs nothing. After a client existed it would be a breaking
  change under `versioning.md`.
- A bounded `limit` means no client request can ask the API to load an unbounded result set.

### Negative

- Replacing the framework's error bodies means the API no longer matches FastAPI's documented
  defaults, so a contributor expecting `{"detail": ...}` must read this record.
- A closed catalogue makes every genuinely new error condition a documentation change, not just a
  code change. That is the intended cost, but it is a cost.
- `pagination` on a one-row collection is noise until the collection grows.
- `request_failed` is a real code a client may receive while carrying almost no information. It is a
  safety net for a status nobody planned, not a category.

### Neutral

- The contract is implemented only by OPS-001 and CUR-001 to CUR-003 today. Every endpoint added
  later inherits it rather than negotiating it.
- Handlers live in the presentation layer and are registered by the composition root. No application
  or domain code learns about HTTP status codes, per
  [ADR-001](ADR-001-clean-architecture.md).

## Alternatives considered

### Return the resource directly, with no `data` envelope

Fewer keys to traverse, and the common REST shape.

**Not selected:** a collection then has nowhere to put pagination except a header or a wrapper that
only collections use, giving the API two response shapes instead of one. The envelope also leaves
room for a sibling key later without breaking a client that already parses `data`.

### Keep FastAPI's default error bodies

No handlers to write, and the shape matches the framework's own documentation and generated schema.

**Not selected:** it contradicts the approved envelope in `conventions.md`, and it gives a client
three different error shapes depending on whether the failure came from validation, routing, or an
unhandled exception.

### Leave the error codes to each endpoint

Every endpoint documents its own codes in the catalogue, with no cross-cutting table.

**Not selected:** the same condition would acquire several names — `not_found`, `missing`,
`unknown_program` — and a client would need per-endpoint handling for a case that is identical
everywhere. Endpoint-specific codes remain possible for genuinely endpoint-specific conditions; the
table covers the cross-cutting ones.

### Add pagination only when a collection is large enough to need it

Simpler responses now, and a compatible change later under `versioning.md`.

**Not selected:** until it arrives, a client cannot tell a complete collection from a truncated one,
and the decision to add it would fall to whoever first noticed a slow response rather than to a
contract.

### Keep `resource_not_found` and disambiguate in prose

The value already appears in an approved document, and a note could explain the two senses.

**Not selected:** a note does not help a developer reading a JSON body, and the collision lands
exactly where the resource endpoints will. Correcting it before a client exists is free; afterwards
it needs a major version.

## Implementation notes

- The envelope, the pagination bounds, the code table, and the `details` shape are catalogued in
  [api/conventions.md](../api/conventions.md#error-codes), which stays the document a contributor
  reads. This record holds the rationale. **Where the two ever differ, `conventions.md` is
  authoritative**: a code added after this record was accepted belongs there, and an accepted ADR is
  not rewritten to keep a copy current.
- Handlers and response schemas live in `backend/app/presentation/api/errors.py` and
  `backend/app/presentation/api/schemas/`. `register_error_handlers` is called by the composition
  root before the routers are included.
- `backend/tests/api/test_error_envelope.py` covers each documented code, the absence of the rejected
  input from `details`, and that a `500` leaks neither the exception type nor its message.
- This record fixes response contracts only. It decides nothing about request bodies, authentication,
  rate limiting, or idempotency keys, none of which any endpoint uses yet.
- The deferred learner and study-goal endpoints — LRN-001, LRN-002, and GOAL-001 to GOAL-005 — remain
  deferred by [ADR-013](ADR-013-examination-schedule-and-study-goal.md). This record shapes how they
  will respond, not whether they exist.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-001: Adopt Clean Architecture](ADR-001-clean-architecture.md) — why HTTP mapping stays in the presentation layer
- [ADR-010: Deliver features through pull requests with automated gates](ADR-010-feature-delivery-workflow.md) — the gate at which a public contract decision is raised
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — the endpoints this contract will shape once their client exists
- [API conventions](../api/conventions.md) — the catalogue this record decides
- [API endpoint catalog](../api/endpoints.md) — the per-endpoint error codes
- [API versioning](../api/versioning.md) — what makes a change to this contract breaking
- [Terminology](../domain/terminology.md) — the meaning of *resource* that `not_found` avoids
- [Coding standards](../development/coding-standards.md) — the boundary rules the handlers follow
- [Architecture decision register](../architecture/decisions.md) — DEC-027
