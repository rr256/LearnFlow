---
title: "ADR-015: Build the Frontend on Next.js and Reach the API from the Server"
status: accepted
owner: architecture-and-development
last_updated: 2026-08-05
related:
  - ../00-project-context.md
  - ADR-001-clean-architecture.md
  - ADR-005-docker-compose-local-development.md
  - ADR-009-configuration-naming-and-validation.md
  - ADR-013-examination-schedule-and-study-goal.md
  - ADR-014-api-response-contract.md
  - ADR-016-learner-onboarding-api-contracts.md
  - ../architecture/overview.md
  - ../development/tech-stack.md
  - ../development/folder-structure.md
  - ../development/coding-standards.md
  - ../deployment/docker.md
  - ../deployment/environments.md
  - ../deployment/ci-cd.md
  - ../api/conventions.md
  - ../requirements/non-functional.md
  - ../architecture/decisions.md
---

# ADR-015: Build the Frontend on Next.js and Reach the API from the Server

## Status

Accepted — 2026-08-03

Resolves DEC-008, which had been approved since the documentation foundation with its ADR recorded
as pending.

## Implementation status — 2026-08-05

*The decision below is unchanged, and in particular the CORS position it takes still holds.*

**The frontend now writes.** A learner setup screen at `/setup` creates and updates the learner
profile and the study goal, per [ADR-016](ADR-016-learner-onboarding-api-contracts.md). It inherits
this record rather than renegotiating it, which is what the Neutral bullet below says every later
screen does: the form posts to a Next.js **server action**, so the API call is still made by the
Next.js server, the browser still issues no request to the backend, and `API_CORS_ALLOWED_ORIGINS`
stays planned rather than implemented. This was verified against the production standalone server —
no API address appears in the served HTML or in any client script.

Three statements are overtaken, and as elsewhere the accepted text is left as written:

- Under [Neutral](#neutral), "Only the curriculum reads have a client today" — the learner setup
  endpoints have one too.
- Under [Implementation notes](#implementation-notes), "the learner and study-goal endpoints remain
  deferred by ADR-013" describes the state at acceptance. ADR-016 discharges that deferral for all
  but GOAL-005.
- The record says it "decides nothing about … learner-owned screens". One now exists, decided by
  ADR-016 rather than here.

**One consequence of the framework choice was found the same way this record's loading-boundary trap
was — by running the built server, not by reading the code.** A `"use server"` module may export only
async functions; exporting a constant from one throws on the first request that reaches it, and
neither `tsc --noEmit` nor `next build` reports it.
[folder-structure.md](../development/folder-structure.md#frontendfeatures) records the rule, and a
test now enforces it.

## Context

[DEC-008](../architecture/decisions.md) read "Next.js with TypeScript is the initial web frontend
technology — Approved — ADR pending" from the writing of the architecture register until this record.
The register's own rule is that a pending ADR is created "before or alongside implementation of the
affected area". Building the frontend fired that trigger.

The technology itself was the settled part. What implementing it exposed was that three further
questions had no recorded answer anywhere, and each is expensive to reverse once a client exists.
Each is stated below as it stood before this record; the documents quoted have since been updated.

1. **How the frontend reaches the API.** [ADR-009](ADR-009-configuration-naming-and-validation.md)
   separated `API_HOST`/`API_PORT` — the address the backend binds to — from `API_BASE_URL`, and
   deferred the second, saying only that "the client-facing URL becomes frontend configuration when a
   frontend exists". It did not say *which process* holds that configuration, and the answer decides
   whether the value is a server-side setting or a browser-visible one.

2. **Whether the backend needs CORS.** [environments.md](../deployment/environments.md) listed
   `API_CORS_ALLOWED_ORIGINS` as a planned core-runtime setting "for when CORS middleware is
   introduced", without saying what introduces it. A browser that calls the API cross-origin
   requires an allow-list; a browser that never calls it does not. This is security-relevant
   behaviour, so it cannot be settled by whichever page happened to be written first.

3. **Styling, testing, and linting.** [tech-stack.md](../development/tech-stack.md) named frontend
   testing as "TypeScript/React test tooling — exact framework selected with frontend scaffold", and
   said nothing about styling or linting. Each is a dependency, and the project's rule is that a
   dependency is justified against an approved requirement rather than adopted because it is common.

The MVP context constrains all three. LearnFlow is local-first and single-learner
([NFR-001](../requirements/non-functional.md#nfr-001-local-first-privacy)), there is no
authentication, and the only implemented endpoints are the curriculum reads CUR-001 to CUR-003, which
return curated reference data and write nothing.

## Decision

### Next.js with React and TypeScript is the frontend foundation

The App Router, with TypeScript `strict` enabled. This confirms DEC-008 rather than revisiting it;
what follows is what DEC-008 left open.

The frontend consumes the public HTTP contract and nothing else. It holds no business rule: planning,
progress calculation, and curriculum rules stay in the backend, and ordering is one of them — the
frontend renders subjects and topics in the order the API returns them rather than sorting.

### Learner-facing pages reach the API from the Next.js server

The curriculum views are React Server Components. The Next.js server calls the API and sends rendered
HTML; the browser receives no API address and issues no request to the backend.

`API_BASE_URL` is therefore **server-side frontend configuration**. It carries no `NEXT_PUBLIC_`
prefix, which is what would place a value in a client bundle, and it is catalogued in
[environments.md](../deployment/environments.md), which remains the authoritative variable list under
ADR-009.

This settles the question ADR-009 deferred: the client-facing base URL belongs to the frontend
process, not the backend, and not the browser.

### No browser-to-backend call, and therefore no CORS middleware, in this scope

Because no browser calls the API, there is no cross-origin request to permit. The backend gains no
CORS middleware, and `API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented — consistent
with ADR-009's rule that a variable is added in the change that introduces the code reading it.

**This is scoped, not permanent.** A future feature that genuinely needs the browser to call the API
directly — an interactive control that must not re-render the page, say — introduces the middleware,
the allow-list variable, and a review of what an allowed origin may reach, in that same change. What
this record forbids is acquiring a CORS allow-list *incidentally*, as a side effect of a page that
did not need one.

Nothing here weakens the boundary in [tech-stack.md](../development/tech-stack.md): the frontend
still reaches no database, file store, vector store, or provider, and holds no provider credential.

### CSS Modules, Vitest with React Testing Library, and ESLint with `eslint-config-next`

These are implementation choices, recorded so the next contributor extends them rather than
re-deciding:

| Concern | Choice | Why |
| --- | --- | --- |
| Styling | CSS Modules | Built into Next.js. Component-scoped styles beside their component, with no styling dependency and no build configuration. |
| Testing | Vitest + React Testing Library | Vitest reuses the bundler pipeline Next.js already implies, so tests need no second transform configuration. Testing Library queries by role and accessible name, so a test fails when markup stops being reachable. |
| Linting | ESLint with `eslint-config-next` | Ships with the framework and carries the `jsx-a11y` accessibility rules, so markup is linted for accessibility rather than only reviewed for it. |
| Package manager | npm, lockfile committed | Already present with Node. `npm ci` fails when the lockfile and `package.json` disagree, which `npm install` would silently reconcile. |

Accessibility *conformance* remains a future quality target in
[non-functional requirements](../requirements/non-functional.md#future-quality-considerations). The
linting choice above is what keeps it reachable; it is not a claim to have met it.

## Consequences

### Positive

- The browser holds no API address and makes no backend request, so the API's exposure surface is
  unchanged by the arrival of a client. There is no allow-list to get wrong, and no
  infrastructure endpoint in a client bundle — which is what
  [environments.md](../deployment/environments.md#configuration-principles) requires.
- A page renders with data already present, so a learner does not watch an empty shell fetch its
  contents.
- The container image needs no API at build time, because every curriculum route renders per request.
- `API_BASE_URL` has one meaning and one reader, ending the ambiguity ADR-009 recorded.
- Adding CORS later remains cheap and becomes a deliberate, reviewable decision rather than an
  inherited default.

### Negative

- Every interaction that needs fresh data is a server round trip until something is deliberately made
  client-side. For a curriculum that changes when a seed runs, that is the right trade; for a future
  interactive control it may not be, and that feature will have to make the case.
- The frontend is now a server process with its own configuration and its own container, not a static
  bundle. It cannot be served from a plain file host.
- Testing a server component means testing the functions it composes rather than mounting a route, so
  the component tests cover rendering and the API client separately rather than end to end.
- A loading boundary must be placed below any call that decides the response status. A `Suspense`
  boundary — or a `loading.tsx`, which also covers every nested route — commits a `200` before the
  suspended work runs, so a boundary above a lookup that raises "not found" turns a `404` into a
  `200`. This was found by testing the built server, not by reading the code.

### Neutral

- Only the curriculum reads have a client today. Every later screen inherits this decision rather
  than renegotiating it.
- The response contract the client parses is fixed by
  [ADR-014](ADR-014-api-response-contract.md); this record decides who calls the API, not what it
  returns.
- The client raises two failure codes of its own — for an unreachable API and for a success body that
  does not match the documented envelope. Neither travels over HTTP, so neither widens the closed
  wire catalogue ADR-014 fixed.

## Alternatives considered

### Fetch from the browser and add CORS middleware to the backend

The conventional single-page-application shape: client components call the API directly, and the
backend gains CORS middleware plus `API_CORS_ALLOWED_ORIGINS`.

**Not selected:** it buys nothing this scope needs and costs security-relevant surface. A read-only
curriculum view has no interaction that a server render cannot serve, so the allow-list would exist
solely because of how the page was written. It would also make the API address browser-visible,
requiring a `NEXT_PUBLIC_` variable, and would fix an origin policy before there is any authenticated
or learner-owned endpoint whose exposure could be reasoned about.

### Proxy browser calls through a Next.js rewrite

The browser calls a same-origin path that Next.js rewrites to the backend. No CORS needed.

**Not selected:** it re-exposes the whole backend surface through the frontend origin — including
endpoints added later, which nobody would revisit this rewrite to reconsider — and adds a network hop
for no gain over rendering on the server.

### A framework-free React single-page application

Drop Next.js and serve a static React bundle.

**Not selected:** it contradicts DEC-008 without new evidence, and it forces the browser-fetch
alternative above, since a static bundle has no server to call from.

### Add a styling framework now

Tailwind CSS or similar alongside the foundation.

**Not selected:** one read-only view does not need it, and it is a durable decision no requirement
supports yet. CSS Modules impose no obstacle to adopting one later; the reverse is less true.

### Ship the foundation without a test runner

Rely on lint, type checking, and the production build.

**Not selected:** [coding standards](../development/coding-standards.md#testing-standards) require
tests for changed behaviour, and [CI/CD strategy](../deployment/ci-cd.md) names component tests as
part of the frontend check set. A learner-facing view with no test would be an exception argued from
convenience.

## Implementation notes

- Structure, file naming, and the boundary-placement rule are described in
  [folder structure](../development/folder-structure.md#frontend-structure) and
  [coding standards](../development/coding-standards.md#typescript-and-frontend-standards). Those
  documents are what a contributor reads; this record holds the rationale and is not rewritten as the
  frontend grows.
- `API_BASE_URL` is catalogued in
  [environments.md](../deployment/environments.md#frontend), which stays authoritative for every
  configuration variable.
- The Compose service, the image decisions, and the fixed `API_BASE_URL` inside the container are in
  [Docker strategy](../deployment/docker.md#the-frontend-service).
- The CI job and its commands are in [CI/CD strategy](../deployment/ci-cd.md#the-frontend-job).
- This record decides the client's foundation and how it reaches the API. It decides nothing about
  authentication, learner-owned screens, or which endpoints exist — the learner and study-goal
  endpoints remain deferred by [ADR-013](ADR-013-examination-schedule-and-study-goal.md), whose
  deferral condition this frontend now affects; see the implementation-status note there.
- Recorded as DEC-008 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-001: Adopt Clean Architecture](ADR-001-clean-architecture.md) — why the frontend holds no business rule
- [ADR-005: Use Docker Compose for local development](ADR-005-docker-compose-local-development.md) — the topology the `frontend` service joins
- [ADR-009: Name and validate configuration variables explicitly](ADR-009-configuration-naming-and-validation.md) — the `API_BASE_URL` deferral this record settles
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — the endpoint deferral this frontend's existence affects
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the contract this client parses
- [ADR-016: Fix the learner setup API contracts](ADR-016-learner-onboarding-api-contracts.md) — the first learner-owned screen, which inherits this record's call topology for its writes
- [Architecture overview](../architecture/overview.md) — the web application component this record gives a call topology
- [Technology stack](../development/tech-stack.md)
- [Repository and folder structure](../development/folder-structure.md)
- [Coding standards](../development/coding-standards.md)
- [Docker strategy](../deployment/docker.md)
- [Environments and configuration](../deployment/environments.md)
- [CI/CD strategy](../deployment/ci-cd.md)
- [API conventions](../api/conventions.md)
- [Non-functional requirements](../requirements/non-functional.md) — the local-first and accessibility positions this record relies on
- [Architecture decision register](../architecture/decisions.md) — DEC-008
