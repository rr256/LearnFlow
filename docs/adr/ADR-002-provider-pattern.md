---
title: "ADR-002: Use Provider Interfaces for External Capabilities"
status: accepted
owner: architecture
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ../architecture/provider-pattern.md
  - ../architecture/clean-architecture.md
---

# ADR-002: Use Provider Interfaces for External Capabilities

## Status

Accepted — 2026-07-29

## Context

LearnFlow begins with local technology choices: Ollama for AI generation and for embeddings, ChromaDB for vector search, and local filesystem storage. The product is intended to evolve to optional cloud AI, Azure Blob Storage, alternate vector databases, and different embedding models when real needs justify them.

Direct calls to vendor SDKs from mentor, planner, resource, or progress logic would make these changes expensive and hard to test. At the same time, creating generic abstractions for every utility would over-engineer the MVP.

## Decision

Use application-facing provider interfaces/ports for external capabilities that are both important to the product and realistically expected to vary:

```text
AIProvider
EmbeddingProvider
RetrievalProvider
StorageProvider
ResourceExtractionProvider
```

Concrete adapters implement these ports in infrastructure:

```text
OllamaProvider
OllamaEmbeddingProvider
ChromaRetrievalProvider
LocalStorageProvider
LocalPdfExtractionProvider
```

`AIProvider` and `EmbeddingProvider` stay separate ports even though Ollama initially implements both. The two capabilities have different contracts, different failure behavior, and different replacement pressure.

Provider selection is configuration-driven and wired only in the composition root.

Structured persistence uses domain-focused repository interfaces rather than a broad generic `DatabaseProvider`.

## Consequences

### Positive

- Local-first MVP choices remain compatible with future cloud/provider changes.
- Application and domain tests can use fake providers.
- Provider-specific SDK types and errors stay at infrastructure boundaries.
- AI, storage, embedding, and retrieval behavior can be independently evaluated.
- Learner progress, source resources, and derived vector data retain clear ownership boundaries.

### Negative

- Adapters and DTO mapping add early implementation work.
- Each provider capability needs a clear contract and error behavior.
- Some provider features may not map perfectly across future implementations.

### Mitigations

- Keep interfaces small and capability-focused.
- Add a port only where replacement/testing value is real.
- Document compatibility/re-indexing implications for embeddings and vector providers.
- Keep provider-specific advanced features out of application contracts unless they become a deliberate product requirement.

## Alternatives Considered

### Direct Vendor SDK Calls

Call Ollama, ChromaDB, or local filesystem APIs directly from application services/routes.

**Rejected:** couples product logic to infrastructure, makes testing difficult, and prevents controlled replacement.

### One Generic Provider Interface

Use a universal `Provider` abstraction for all external systems.

**Rejected:** too vague to express distinct contracts for generation, storage, retrieval, and embeddings.

### Build Cloud Providers First

Start with OpenAI/Azure/cloud storage/vector services.

**Rejected:** conflicts with the local-first cost/privacy objective and does not help the initial personal-study MVP.

## Implementation Notes

- Follow `docs/architecture/provider-pattern.md`.
- Do not import vendor SDKs in domain/application code.
- Do not expose provider names, credentials, raw storage paths, or vendor response objects through public APIs.
- Treat original resource files, structured learner data, and vectors as separate data categories.
- Changing embedding configuration may require re-indexing; changing an AI provider must not alter learner progress or plan data.

## Related Documents

- [Project context](../00-project-context.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Clean Architecture](../architecture/clean-architecture.md)
- [RAG overview](../rag/overview.md)
- [Technology stack](../development/tech-stack.md)
- [Architecture decision register](../architecture/decisions.md)
