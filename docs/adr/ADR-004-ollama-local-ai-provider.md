---
title: "ADR-004: Use Ollama as the Initial Local AI Provider"
status: accepted
owner: architecture-and-ai
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ../architecture/provider-pattern.md
  - ../rag/overview.md
  - ../development/tech-stack.md
---

# ADR-004: Use Ollama as the Initial Local AI Provider

## Status

Accepted — 2026-07-29

## Context

LearnFlow is initially a personal, local-first GATE CSE mentor. The learner already has Ollama installed and wants to control recurring AI costs while keeping notes, progress, and personal study data local by default.

The product needs an AI capability for grounded explanations, doubt resolution, summaries, and supported practice generation. It must not depend on the AI model for durable memory, progress storage, or deterministic planning rules.

## Decision

Use Ollama running on the learner's host machine as the initial implementation for two separate capabilities:

- **Generation** — the initial `AIProvider` implementation.
- **Embeddings** — the initial `EmbeddingProvider` implementation, using an Ollama-served embedding model.

These remain two distinct application ports with independent contracts, even though one runtime serves both today. A later change may replace either one without the other.

Access Ollama only through those adapters and configuration. The backend connects through a configured endpoint; it does not embed Ollama calls in routes, domain code, or planner logic.

The generation model and the embedding model are configured separately and are not required to be the same model.

## Consequences

### Positive

- No per-request cloud API cost for the initial personal workflow.
- Learner-owned notes and prompts remain local by default.
- Works without dependence on cloud account/API setup after local model installation.
- Allows extensive experimentation with mentor/RAG features.
- Aligns with the existing installed local environment.

### Negative

- Response quality, speed, and model availability depend on the learner's hardware and selected model.
- Local models may be weaker than leading cloud models for complex reasoning.
- Downloaded model files are large and remain a host-machine prerequisite.
- Docker containers need configured access to host Ollama.

### Mitigations

- Keep the AI provider replaceable through the provider pattern.
- Keep core planning/progress/revision logic deterministic and usable without Ollama.
- Show clear model/provider unavailable states.
- Allow future cloud providers only as explicit optional adapters with transparent privacy/cost configuration.
- Evaluate models on representative GATE CSE questions and notes before setting defaults.

## Alternatives Considered

### Cloud AI Provider First

Use an OpenAI, Gemini, Claude, or similar API as the required default.

**Rejected:** introduces recurring usage costs, requires credentials/internet, and conflicts with the local-first privacy/cost objective for the MVP.

### Build a Local Model Runtime Directly

Manage model downloads, inference server, and runtime internals directly in LearnFlow.

**Rejected:** unnecessary operational complexity when Ollama already provides a local runtime interface.

### No AI in the MVP

Build only plans, progress, and resource tracking.

**Rejected:** the personal mentor experience and grounded note-based assistance are central to LearnFlow’s value, though they remain modular and do not control durable state.

## Implementation Notes

- Configure `AI_PROVIDER`, Ollama endpoint, chat model, and embedding model through environment variables.
- Keep the embedding configuration independent of the generation configuration so either can change alone. Changing the embedding model can require re-indexing; changing the generation model does not.
- Do not send entire resource collections or arbitrary local files to Ollama; use controlled retrieval context.
- AI responses do not silently update progress, plans, revisions, or assessments.
- Distinguish grounded answers from general AI answers when retrieval is unavailable.
- Containerized Ollama is deferred; Docker Compose initially connects to host Ollama through configuration.

## Related Documents

- [Project context](../00-project-context.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [RAG overview](../rag/overview.md)
- [Technology stack](../development/tech-stack.md)
- [Docker strategy](../deployment/docker.md)
- [Architecture decision register](../architecture/decisions.md)
