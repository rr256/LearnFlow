---
title: ADR-006: Start with a Custom Product-Agent Orchestrator
status: accepted
owner: architecture-and-ai
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ../ai/learnflow-agents.md
  - ../architecture/clean-architecture.md
  - ../roadmap/future-ideas.md
---

# ADR-006: Start with a Custom Product-Agent Orchestrator

## Status

Accepted — 2026-07-29

## Context

LearnFlow needs several focused learning capabilities: planning, mentoring, progress interpretation, revision scheduling, quizzes, external-test analysis, and resource/RAG coordination.

These responsibilities need coordination, but the MVP workflows are known, bounded, and primarily deterministic. Introducing a large agent framework before the product has complex long-running workflows would add another abstraction to learn, test, configure, and debug.

## Decision

Implement product-agent coordination as a custom application orchestrator/router using normal backend code.

The orchestrator routes a learner request or system event to the minimal focused service(s) needed. Each service has a single responsibility and uses application ports for persistence, retrieval, and AI generation.

No agent framework such as LangGraph or CrewAI is required in the MVP.

## Consequences

### Positive

- Workflows remain easy to understand, debug, and test.
- The product does not become dependent on framework-specific state or abstractions.
- Deterministic planning/progress rules remain explicit.
- Focused services can later become graph nodes/tasks if an agent framework is justified.
- AI use is limited to tasks where generation/reasoning adds value.

### Negative

- The project owns routing, workflow state, retries, and coordination behavior.
- If workflows become highly dynamic, custom orchestration may need refactoring.
- Some advanced framework features, such as checkpoints or durable workflow state, are not available by default.

### Mitigations

- Keep the orchestrator thin; do not let it become a second home for business rules.
- Keep Mentor, Planner, Quiz, Revision, Progress, and Resource services independent.
- Use documented application DTOs and explicit service inputs/outputs.
- Re-evaluate only when a concrete workflow requirement appears.

## Alternatives Considered

### LangGraph From the Start

Use a graph-based agent framework for all learning workflows.

**Rejected for MVP:** potentially useful later for checkpoints/complex branching, but the initial known workflows do not justify its learning curve and framework coupling.

### CrewAI / Autonomous Agent Team

Model planner, teacher, quiz, and reviewer as autonomous AI agents that collaborate.

**Rejected:** LearnFlow needs predictable product workflows and controlled learner data, not unconstrained agent negotiation.

### One General Chatbot

Route every request to one LLM prompt with broad tool access.

**Rejected:** would mix planning, progress, retrieval, and assessment responsibilities, reduce reliability, and make behavior difficult to test.

## Re-Evaluation Triggers

Evaluate a workflow framework only if one or more of the following become real product needs:

- Durable long-running workflows that pause/resume.
- Complex dynamic branching among many focused services.
- Human approval checkpoints inside multi-step workflows.
- Robust retry/recovery for multi-step operations beyond ordinary background jobs.
- Workflow visualization/observability that normal application code no longer provides clearly.

Any adoption requires a new ADR and migration plan for existing orchestration behavior.

## Implementation Notes

- Follow `docs/ai/learnflow-agents.md`.
- Keep agent/service responsibilities in application layer use cases.
- The orchestrator does not call vendor SDKs directly.
- AI responses are advisory; they do not silently mutate learner progress, plans, revisions, or assessments.
- Product agents and engineering AI assistants are separate concepts with separate documentation.

## Related Documents

- [Project context](../00-project-context.md)
- [LearnFlow product agents](../ai/learnflow-agents.md)
- [Clean Architecture](../architecture/clean-architecture.md)
- [Deferred ideas](../roadmap/future-ideas.md)
- [Architecture decision register](../architecture/decisions.md)
