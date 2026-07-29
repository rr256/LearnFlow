---
title: LearnFlow Documentation
status: draft
audience: contributors-and-ai-assistants
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

- **Draft**: under discussion; do not treat as a final decision.
- **Proposed**: ready for review, but not yet approved.
- **Approved**: authoritative until replaced by a newer ADR or document revision.
- **Superseded**: retained for history; do not implement from it.

## Documentation workflow

1. Read `00-project-context.md` and the related documents for the task.
2. Discuss or propose a change before changing architecture, public APIs, data models, or dependencies.
3. Update the affected document in the same change as implementation.
4. Create an ADR for a significant, durable architectural decision.
5. Keep documents concise, factual, and aligned with the current approved direction.

## Related documents

- [Project context](00-project-context.md)
- [Documentation standards](development/documentation-standards.md)
