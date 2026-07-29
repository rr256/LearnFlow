---
title: "ADR-007: Use Repository Documentation and ADRs as Shared Project Memory"
status: accepted
owner: project-governance
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ../development/documentation-standards.md
  - ../ai/engineering-ai.md
  - ../architecture/decisions.md
---

# ADR-007: Use Repository Documentation and ADRs as Shared Project Memory

## Status

Accepted — 2026-07-29

## Context

LearnFlow is being designed and implemented over time with assistance from multiple AI tools and potentially future contributors. Individual chat histories are long, temporary, tool-specific, and may not preserve all active context.

Without a shared written source of truth, different assistants can make inconsistent assumptions about product scope, architecture, data model, provider choices, and deferred features.

## Decision

Treat the repository `docs/` folder as the authoritative project handbook.

Require every contributor or AI assistant to begin with `docs/00-project-context.md` and then read task-specific documentation.

Use focused documents for detailed topics and Architecture Decision Records (ADRs) for significant, durable decisions. Record current conclusions only; do not preserve abandoned discussion paths as active guidance.

## Consequences

### Positive

- Project knowledge survives chat/tool/session changes.
- Claude Code, Codex, ChatGPT, and future contributors can work from the same documented context.
- Decisions have rationale, alternatives, and consequences instead of relying on memory.
- Documentation structure prevents one huge, hard-to-navigate context file.
- Architecture drift is easier to detect in review.

### Negative

- Documentation requires ongoing maintenance.
- Contributors must read relevant documents before editing.
- Small changes may require documentation updates in addition to code/tests.

### Mitigations

- Keep `00-project-context.md` concise and link to focused documents.
- Use standard front matter, statuses, and related-document links.
- Update only documents affected by a change; avoid unnecessary duplicate writing.
- Use ADRs only for consequential decisions, not every implementation detail.
- Include documentation checks in review/CI once tooling exists.

## Alternatives Considered

### Rely on One Long Chat Conversation

Use a continuing chat as the project’s main memory.

**Rejected:** context can be lost, tools do not share it, and conversations are difficult to audit/version with code.

### One Giant Project Specification File

Put all project information in a single very large Markdown document.

**Rejected:** hard for humans and AI assistants to navigate; changes create duplication and stale sections.

### Code as the Only Documentation

Expect source code and tests to explain all decisions.

**Rejected:** code cannot reliably communicate product rationale, rejected alternatives, deferred scope, or intended boundaries.

### External Wiki as the Sole Source of Truth

Maintain decisions outside the repository.

**Rejected:** creates synchronization problems and makes implementation assistants less likely to load the current context automatically.

## Implementation Notes

- Follow `docs/development/documentation-standards.md`.
- `docs/00-project-context.md` is mandatory reading for meaningful tasks.
- `docs/architecture/decisions.md` indexes current approved/deferred decisions.
- `docs/adr/` holds accepted/superseded ADRs using the shared template.
- Code changes that alter approved behavior update affected documents in the same reviewable change.
- AI assistants must not mark a decision approved without project-owner direction.

## Related Documents

- [Project context](../00-project-context.md)
- [Documentation standards](../development/documentation-standards.md)
- [Engineering AI workflow](../ai/engineering-ai.md)
- [Architecture decision register](../architecture/decisions.md)
- [ADR directory](README.md)
