---
title: LearnFlow Documentation
status: approved
owner: project-governance
last_updated: 2026-07-29
audience: contributors-and-ai-assistants
related:
  - 00-project-context.md
  - development/documentation-standards.md
  - architecture/decisions.md
---

# LearnFlow Documentation

This directory is the authoritative documentation for LearnFlow. Start with [00-project-context.md](00-project-context.md) before proposing or implementing any change.

## Documentation map

- [Project context](00-project-context.md) — mandatory onboarding and master index
- [Vision](vision/vision.md) — product purpose and boundaries
- [Requirements](requirements/) — MVP and quality requirements
- [Architecture](architecture/) — system structure and dependency rules
- [Domain](domain/) — learning concepts and terminology
- [Database](database/) — persistence design and migrations
- [API](api/) — HTTP conventions and endpoint contracts
- [RAG](rag/) — knowledge ingestion and retrieval
- [AI](ai/) — product agents and engineering AI workflow
- [Development](development/) — stack, repository, code, Git, and docs practices
- [Deployment](deployment/) — containers and environments
- [Roadmap](roadmap/) — milestones and deferred ideas
- [Architecture Decision Records](adr/) — approved decisions and their rationale

## Status language

Normal documents and ADRs use separate status vocabularies:

- **Normal documents**: `draft`, `proposed`, `approved`, `superseded`, `template`.
- **ADRs**: `proposed`, `accepted`, `superseded`, `rejected`.

[Documentation standards](development/documentation-standards.md) defines what each status means and is the authoritative source.

## Documentation workflow

1. Read `00-project-context.md` and the related documents for the task.
2. Discuss or propose a change before changing architecture, public APIs, data models, or dependencies.
3. Update the affected document in the same change as implementation.
4. Create an ADR for a significant, durable architectural decision.
5. Keep documents concise, factual, and aligned with the current approved direction.

## Related Documents

- [Project context](00-project-context.md)
- [Documentation standards](development/documentation-standards.md)
