---
title: LearnFlow Coding Standards
status: approved
owner: architecture-and-development
last_updated: 2026-08-03
related:
  - ../00-project-context.md
  - folder-structure.md
  - ../architecture/dependency-rules.md
  - ../domain/terminology.md
  - git-workflow.md
  - documentation-standards.md
  - ../deployment/ci-cd.md
  - ../adr/ADR-010-feature-delivery-workflow.md
---

# LearnFlow Coding Standards

## Purpose

Define code-quality expectations for LearnFlow contributors and AI assistants. These standards prioritize clarity, correctness, testability, and maintainable architecture over cleverness.

## General Principles

- Prefer simple, explicit code over hidden behavior or premature abstraction.
- Keep each module focused on one responsibility.
- Name concepts using the canonical domain terminology in `docs/domain/terminology.md`.
- Write code that makes failure states visible and recoverable.
- Do not duplicate business rules across frontend, API, application, and provider adapters.
- Keep external technology details at infrastructure boundaries.
- Update tests and affected documentation with behavior changes.

## Python Standards

### Naming

- Files/modules: `snake_case.py`.
- Functions, variables, and parameters: `snake_case`.
- Classes, exceptions, DTOs, and protocols: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Use domain names clearly: `StudyPlan`, `TopicProgress`, `ExternalTestResult`; avoid vague names such as `data`, `manager`, or `helper` when a precise name exists.

### Typing

- Type all public functions, methods, and class attributes.
- Use explicit input/output DTOs at application boundaries.
- Prefer `Protocol`/interfaces for application ports over concrete infrastructure types.
- Avoid `Any` except at a tightly contained untyped boundary; convert/validate it immediately.
- Prefer immutable value objects/data structures when they represent a completed fact or command.

### Functions and Classes

- Keep functions small enough that their purpose is evident from the name and signature.
- One class/module should have one clear reason to change.
- Constructors should not perform network, database, filesystem, or AI-provider I/O.
- Pass dependencies explicitly through constructors or composition-root wiring.
- Avoid global mutable state and hidden singleton clients.

### Exceptions and Results

- Domain code raises domain-specific exceptions for invalid business states.
- Application code translates expected provider/repository failures into application-safe errors.
- Presentation code maps expected errors to documented API responses.
- Do not catch broad exceptions and silently continue.
- Never return a success response when persistence or a required operation failed.

### Python Formatting and Linting

Ruff is the selected formatter and linter. It covers formatting, linting, and import sorting in one
tool, so no separate Black, isort, or flake8 configuration is used. Configuration lives in
`backend/pyproject.toml`.

```bash
cd backend
python -m ruff check .           # lint
python -m ruff format .          # format
python -m ruff format --check .  # verify formatting without writing
```

- Both checks must pass before a change is committed, as part of the [local quality checks](#local-quality-checks).
- Do not manually reformat unrelated code in a feature change.
- Keep imports ordered and remove unused imports; Ruff enforces both.
- Prefer standard-library features before adding a utility dependency.

## Local Quality Checks

This is the canonical local check set for LearnFlow. Run all of it before committing a change. Other documents refer to this section rather than restating the commands.

```bash
cd backend
python -m pytest -W error                                              # tests; warnings fail the run
python -m ruff check .                                                 # backend lint
python -m ruff format --check .                                        # backend formatting
cd ../frontend
npm ci                                                                 # install the committed lockfile
npm run lint                                                           # frontend lint
npm run typecheck                                                      # frontend types
npm test                                                               # frontend tests
npm run build                                                          # frontend production build
cd ..
python -m ruff check --config backend/pyproject.toml scripts/          # repository scripts lint
python -m ruff format --check --config backend/pyproject.toml scripts/ # repository scripts formatting
python scripts/validate_docs.py                                        # documentation front matter and links
```

- Every command must pass. Do not suppress a check, weaken an assertion, or skip a test to make one pass.
- `-W error` treats warnings as errors, so a deprecation surfaces in the change that introduced it rather than later.
- Ruff configuration lives in `backend/pyproject.toml`. `scripts/` sits outside `backend/`, so its invocations name that configuration explicitly; both trees are held to the same rules.
- `npm ci` installs exactly what `frontend/package-lock.json` records and fails when it disagrees with `package.json`, where `npm install` would quietly reconcile the two. Run it after pulling a change that touches frontend dependencies; otherwise the four checks below it are enough.
- `npm run build` is a check, not just a packaging step: it fails on a type error Next.js reports that `tsc` alone does not, and on a route that cannot render. Every curriculum route is dynamic, so it reaches no API and needs no running backend.
- The documentation validator enforces the mechanical rules in [documentation standards](documentation-standards.md) and runs from the repository root.

This set covers the checks that need nothing beyond Python, Node.js, and the pinned development dependencies. Container commands require a Docker installation and are documented in [Docker strategy](../deployment/docker.md) instead.

CI runs every check in this set on each pull request, with one difference: the workflow runs `python -m pytest` while this local set adds `-W error`, so the local run is the stricter of the two.

CI additionally runs two things this set does not: it validates the Compose topology and builds the backend and frontend images, and it runs the database migration tests against an ephemeral PostgreSQL service. Those migration tests are part of the suite above but skip unless `TEST_DATABASE_URL` names a reachable disposable database, so a plain local run does not exercise them. See [CI/CD strategy](../deployment/ci-cd.md).

## TypeScript and Frontend Standards

### Type Safety

- Use TypeScript strict mode.
- Do not use `any` as a shortcut around API contracts or UI state.
- Define types from public API contracts, not database/ORM shapes. Keep the wire field names as the contract spells them — `snake_case`, per [API conventions](../api/conventions.md#json-naming-and-data-formats) — rather than renaming them into a shape the API does not return.
- Validate untrusted API data at the frontend boundary where needed. `frontend/lib/api-client.ts` checks every response against the documented envelope before a view sees it, because a view that trusts an unchecked body renders `undefined` instead of reporting a failure. A failure the API reported keeps the API's own [error code](../api/conventions.md#error-codes); a failure only the client can see — unreachable, or a malformed success body — gets a client-side code, which is never sent over HTTP and so does not widen the wire catalogue.

### Naming

- React components, types, and interfaces: `PascalCase`.
- Variables, functions, hooks, and props: `camelCase`. This governs identifiers the frontend owns, not the wire fields above.
- Component files are `PascalCase.tsx` beside their `PascalCase.module.css`; route files use the names Next.js reserves — `page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`, `not-found.tsx`. Other modules are `kebab-case.ts`.
- Use learner-facing domain terms consistently: `topicProgress`, `studyPlan`, `revisionRecord`.

### UI Responsibilities

- Keep planning, progress calculation, and curriculum rules in the backend. Ordering is a curriculum rule: subjects and topics arrive in syllabus order, and the frontend renders that order rather than sorting.
- Render backend-provided curriculum data; do not hardcode GATE CSE topics in UI code.
- Handle loading, empty, success, and error states for every asynchronous learner workflow. Handle an expected API failure in the page rather than leaving it to the route error boundary: a production build replaces a server-side error message with a generic one, so the boundary cannot explain what happened.
- Place a loading boundary *below* any call that can decide the response status. A `Suspense` boundary — or a `loading.tsx`, which also covers every nested route — commits a `200` before the suspended work runs, so a boundary above a lookup that calls `notFound()` turns a `404` into a `200`.
- Use supportive language from `docs/domain/terminology.md`.
- Make user-initiated changes explicit; do not silently update learner-visible state from AI text.

### Accessibility

Accessibility *conformance* is a future quality target in [non-functional requirements](../requirements/non-functional.md#future-quality-considerations), and nothing here claims it. These are the baseline habits that keep conformance reachable rather than a later rewrite:

- Use semantic elements for structure — headings in order, lists for lists, `nav` for navigation — so the page is navigable without sight.
- Never remove a focus indicator, and keep the first focusable element a skip link to the main content.
- Do not carry meaning in colour alone; put it in the text as well.
- Give every asynchronous state a text equivalent: a loading message with `role="status"`, and an error panel with `role="alert"`.
- Prefer Testing Library queries by role and accessible name, so a component test fails when the markup stops being reachable.

## API and Boundary Standards

- Follow `docs/api/conventions.md` for public HTTP contracts.
- API routes/controllers remain thin: validate, map, call a use case, map output/error.
- Do not expose ORM models, database errors, local storage paths, provider configuration, or secrets through API responses.
- Convert models explicitly at domain/application/API/persistence boundaries.
- Use provider interfaces in application code; concrete SDK clients belong only in infrastructure adapters.

## Database and Migration Standards

- Follow `docs/database/migrations.md` for every schema change.
- Use repository interfaces for business persistence needs.
- Do not write ad-hoc SQL or use ORM sessions directly in routes/use cases.
- Add database constraints for durable invariants where practical.
- Preserve learner data; destructive changes need explicit approval and a recovery plan.

## RAG and AI Standards

- Treat original resources, extracted chunks, vectors, and AI-generated text as different data types with different ownership/lifecycles.
- Do not send unrestricted files or an entire resource collection to the AI provider.
- Preserve resource/page/section metadata needed for honest citations.
- Label AI-generated questions separately from verified PYQs or curated questions.
- Do not let AI-generated text directly mutate progress, plans, revisions, or assessment records.

## Testing Standards

- Add or update tests for changed behavior and important edge cases.
- Domain tests are fast and deterministic; they do not require live databases, containers, or models.
- Application tests use fakes/mocks for ports.
- Infrastructure tests verify concrete adapter behavior.
- API tests verify request validation, response contracts, and error behavior.
- Test names describe behavior, e.g. `test_plan_marks_overdue_revision_as_priority`.
- Keep test fixtures readable and domain-focused; avoid opaque giant fixtures.

## Logging and Diagnostics

- Log errors and important operations with useful context and timestamps.
- Include safe correlation/request IDs where practical.
- Never log secrets, full private note content, provider credentials, or unnecessary learner data.
- Log provider failures at the adapter/application boundary with safe diagnostics.
- User-facing errors should explain the next possible action without exposing stack traces.

## Comments and Documentation in Code

- Write code that is understandable without comments where possible.
- Use comments to explain non-obvious reasoning, constraints, or trade-offs—not to repeat the code.
- Link unusual implementation decisions to an ADR or documentation section when helpful.
- Keep docstrings focused on public contracts, important side effects, and invariants.

## Dependencies

Before adding a dependency:

1. Identify the approved requirement it serves.
2. Check whether the standard library or existing stack already solves the need.
3. Consider license, maintenance, local portability, privacy, and security impact.
4. Document a major dependency decision and create an ADR when durable.
5. Add it through the project's dependency-management workflow and lock/version it appropriately.

## Prohibited Shortcuts

- Direct provider SDK calls in domain/application code.
- Direct database access in API routes.
- Hardcoded learner-specific paths, IDs, secrets, or curriculum content.
- Catch-all exception handling that hides errors.
- Copying business logic into frontend components.
- Committing `.env`, virtual environments, node modules, learner files, database volumes, or vector indexes.
- Large unrelated refactors inside a focused feature task.

## Related Documents

- [Project context](../00-project-context.md)
- [Domain terminology](../domain/terminology.md) — the canonical vocabulary this document requires
- [Folder structure](folder-structure.md)
- [Dependency rules](../architecture/dependency-rules.md)
- [API conventions](../api/conventions.md) — the wire field names the frontend types keep
- [Non-functional requirements](../requirements/non-functional.md) — where accessibility conformance sits as a future target
- [Database migrations](../database/migrations.md)
- [Git workflow](git-workflow.md)
- [CI/CD strategy](../deployment/ci-cd.md) — the pipeline that enforces the checks defined here
- [Documentation standards](documentation-standards.md) — the rules the documentation validator checks
- [ADR-010: Deliver features through pull requests with automated gates](../adr/ADR-010-feature-delivery-workflow.md)
