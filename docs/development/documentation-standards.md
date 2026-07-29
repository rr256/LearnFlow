---
title: LearnFlow Documentation Standards
status: approved
owner: project-governance
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ../adr/ADR-000-template.md
  - git-workflow.md
  - ../ai/engineering-ai.md
---

# LearnFlow Documentation Standards

## Purpose

Keep LearnFlow documentation accurate, concise, navigable, and useful to both people and AI assistants.

Documentation is part of the project’s source of truth. It records current approved direction; it is not a transcript of every conversation or discarded idea.

## Documentation Principles

- Record conclusions, not chat history.
- Keep one authoritative home for each kind of information.
- Link to related detailed documents instead of duplicating large explanations.
- Update documentation in the same change as implementation when behavior or architecture changes.
- Use current, precise language; avoid speculative claims presented as decisions.
- Make documents easy for an AI assistant to load selectively by using focused scope and clear links.

## Entry Points

| Document | Role |
| --- | --- |
| `docs/README.md` | Documentation home and navigation. |
| `docs/00-project-context.md` | Mandatory onboarding and master index for every AI/contributor. |
| `docs/architecture/decisions.md` | Concise register of approved and deferred decisions. |
| `docs/adr/` | Durable rationale for consequential decisions. |

Do not turn `00-project-context.md` into a giant duplicate handbook. It summarizes current state and directs readers to focused documents.

## Required Front Matter

Every maintained Markdown document under `docs/` starts with YAML front matter:

```yaml
---
title: Clear Document Title
status: draft
owner: area-or-role
last_updated: YYYY-MM-DD
related:
  - relative/path/to/related-document.md
---
```

### Field Rules

- `title`: human-readable, specific document title.
- `status`: one of the approved statuses below.
- `owner`: responsibility area/role, not necessarily a person's name.
- `last_updated`: date of the latest meaningful content change.
- `related`: relative Markdown paths to the most useful related documents.
- Optional fields such as `audience` or `read_before` are allowed when they improve navigation.

## Document Statuses

LearnFlow uses two separate status vocabularies. Ordinary documents under `docs/` use the normal-document statuses. Files under `docs/adr/` use the ADR statuses, because an ADR records a decision rather than describing current direction.

### Normal Document Statuses

Applies to every maintained document except ADRs.

| Status | Meaning |
| --- | --- |
| `draft` | Initial placeholder or work in progress; not a final decision. |
| `proposed` | Specific direction ready for review but not approved. |
| `approved` | Current authoritative direction until changed or superseded. |
| `superseded` | Retained for history; do not implement from it. Link to replacement. |
| `template` | Reusable starting format, not project-specific guidance. |

### ADR Statuses

Applies to files under `docs/adr/`.

| Status | Meaning |
| --- | --- |
| `proposed` | Decision drafted and ready for review; not yet agreed. |
| `accepted` | Agreed decision; implement in line with it until it is superseded. |
| `superseded` | Replaced by a later ADR. Retained for history; link to the replacement. |
| `rejected` | Considered and deliberately not adopted. Retained so the reasoning is not revisited blindly. |

`ADR-000-template.md` is the one file under `docs/adr/` that uses the normal-document status `template`, because it is a reusable format rather than a decision.

Do not use `draft` or `approved` on an ADR, and do not use `accepted` or `rejected` on a normal document.

Only mark a document or decision `approved`/`accepted` after the project owner confirms the direction.

## Document Structure

Use this general shape when applicable:

```markdown
--- front matter ---

# Title

## Purpose

## Scope

## Current approved direction / requirements

## Constraints, trade-offs, or non-goals

## Related Documents
```

Not every document needs every heading, but every document must state its purpose and link to related context.

## Writing Rules

- Prefer short sections, tables, diagrams, and examples over long unstructured prose.
- Use canonical terms from `docs/domain/terminology.md`.
- State what is currently true; move future ideas to `docs/roadmap/future-ideas.md`.
- State uncertainty explicitly instead of hiding it behind vague wording.
- Do not include secrets, personal file paths, learner content, credentials, or private test results.
- Do not use provider-specific implementation details in high-level product/domain documents unless they are relevant to the decision.
- Preserve privacy language: an external test result is learner-entered; the MVP has no scraping/integration with test-series providers.

## Linking Rules

- Use relative Markdown links inside `docs/`.
- Link to the most specific relevant document, not only the documentation home.
- Update links when moving/renaming a document.
- Include a `## Related Documents` section at the end of maintained design documents.
- Do not duplicate a full explanation merely to avoid a link.

## Documentation Update Triggers

Update documentation when a change alters:

| Change | Required documentation update |
| --- | --- |
| Product/MVP behavior | Vision, functional/non-functional requirements, roadmap as applicable. |
| Domain concept or terminology | Domain model, entities, terminology, database schema if persisted. |
| API contract | Endpoint catalog, API conventions/versioning, tests. |
| Database schema | Schema document, migration document, Alembic migration. |
| Provider/infrastructure choice | Architecture overview, provider pattern, tech stack, ADR when consequential. |
| RAG ingestion/retrieval behavior | Relevant RAG documents and tests. |
| Deployment/configuration | Deployment docs, tech stack, `.env.example` where applicable. |
| AI workflow/governance | Engineering AI workflow or prompt library. |

## ADR Policy

Create an Architecture Decision Record when a decision is:

- Costly or difficult to reverse.
- Likely to affect multiple modules or future contributors.
- About architecture style, persistence, security, provider strategy, public API, deployment, or durable workflow.
- Important enough that a future contributor will ask “why did we choose this?”

Do not create ADRs for small file names, routine refactors, temporary experiments, or ordinary implementation details.

### ADR Requirements

- Use `docs/adr/ADR-NNN-short-title.md`.
- Start from `ADR-000-template.md`.
- Include status, context, decision, consequences, alternatives, and implementation notes.
- Never rewrite an accepted ADR as if history changed; mark it superseded and link to the replacement ADR when needed.
- Add each accepted ADR to `docs/architecture/decisions.md`.

## AI-Assisted Documentation Workflow

When using Claude Code, Codex, or another assistant:

1. Read `00-project-context.md` and task-specific documents.
2. Ask the assistant to update only the allowed document paths.
3. Require it to preserve front matter and related links.
4. Review that it captured approved conclusions only.
5. Check for duplicated/conflicting guidance.
6. Commit documentation changes in a focused, reviewable change.

An AI assistant must not mark a decision as approved or create an ADR for an unapproved choice without project-owner direction.

## Documentation Review Checklist

Before committing a meaningful documentation change:

- [ ] Purpose and scope are clear.
- [ ] Front matter/status/last-updated date are correct.
- [ ] Links resolve and related documents are relevant.
- [ ] Canonical terminology is used.
- [ ] Current conclusions are recorded without obsolete discussion history.
- [ ] No private data, secrets, or machine-specific paths are included.
- [ ] Required ADR/schema/API/roadmap updates were considered.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-007: Use repository documentation and ADRs as shared project memory](../adr/ADR-007-documentation-and-adr-policy.md) — the decision these standards implement
- [Architecture decision register](../architecture/decisions.md)
- [ADR template](../adr/ADR-000-template.md)
- [Git workflow](git-workflow.md)
- [Engineering AI workflow](../ai/engineering-ai.md)
