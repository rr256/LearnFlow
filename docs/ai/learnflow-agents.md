---
title: LearnFlow Product Agents
status: approved
owner: architecture-and-ai
last_updated: 2026-08-01
related:
  - ../00-project-context.md
  - ../architecture/overview.md
  - ../architecture/clean-architecture.md
  - ../domain/terminology.md
  - ../rag/overview.md
  - engineering-ai.md
---

# LearnFlow Product Agents

## Purpose

Define the specialized learning responsibilities inside LearnFlow.

“Agent” in LearnFlow means a focused application capability with a clear responsibility, controlled inputs, permitted tools, and predictable outputs. It does **not** mean an autonomous process that can freely access databases, files, or external services.

This document covers **product agents** only. The engineering assistant subagents defined under `.claude/agents/`, such as the documentation reviewer, are a separate and unrelated sense of the word; see [engineering AI workflow](engineering-ai.md#review-agent).

## Design Decision

The MVP uses a simple custom application orchestrator/router, implemented as normal backend code. It coordinates focused services. An agent framework is not required initially.

```text
Learner request or system event
        ↓
Application orchestrator
        ↓
Focused learning service(s)
        ↓
Repositories / retrieval / AI provider through application ports
        ↓
Structured result, recommendation, or learner-confirmed update
```

If future workflows need durable checkpoints, complex branching, long-running coordination, or human approval steps, the orchestration layer can be evaluated independently without rewriting the learning responsibilities.

## Shared Rules

Every product agent/service must:

- Have one primary responsibility.
- Use application ports rather than direct vendor SDKs or database sessions.
- Receive only the learner/resource context needed for its task.
- Return structured outputs that the application can validate.
- Preserve learner control over consequential changes.
- Keep deterministic business rules outside LLM generation when practical.

No product agent/service may:

- Silently overwrite learner progress, learning stage, plan, or assessment data.
- Access arbitrary local files outside registered/authorized resources.
- Treat an LLM response as durable memory.
- Make unsupported claims about mastery, ranks, marks, or exam outcomes.

## Planner Service

### Responsibility

Create and adapt the learner's roadmap, monthly, weekly, and daily plan.

### Inputs

- Active study goal and its horizon — an examination window, a target date, or both.
- Availability slots and planning preferences.
- Curriculum structure and topic relationships.
- Topic progress, revision records, pending plan items, and assessment evidence.

### Outputs

- Study plans and plan items.
- A transparent rationale for important recommendations or trade-offs.
- Warnings when available time is insufficient for the target scope.

### Implementation direction

Core scheduling and prioritization are deterministic application rules. An AI provider may help phrase explanations, but the plan must remain usable when Ollama is unavailable.

## Mentor Service

### Responsibility

Explain concepts, answer doubts, summarize relevant material, and guide the learner to appropriate next actions.

### Inputs

- Learner question.
- Optional topic and resource context.
- Relevant learner progress context when it improves the answer.
- Retrieved authorized source excerpts.

### Outputs

- Grounded explanation or clearly labeled general response.
- Source references when retrieval succeeded.
- Optional suggested next action, without silently changing plans/progress.

### Permitted capabilities

- Retrieval provider.
- AI provider.
- Read-only curriculum/resource/progress access through application services.

## Progress Coach Service

### Responsibility

Interpret learner evidence into an understandable progress summary and supportive next action.

### Inputs

- Material-completion state.
- Learner-selected learning stage.
- Study activities.
- Quiz attempts, external test results, mistakes, and revision history.

### Outputs

- Topic progress summary.
- Priority focus areas.
- Recommended next action, such as study concepts, practice, revision, or mistake review.

### Implementation direction

The evidence interpretation rules are deterministic and auditable. The learner-visible stage remains supportive:

```text
Not explored
Building foundation
Developing confidence
Practice-ready
Strong understanding
```

One quiz or score must not create a permanent mastery claim.

## Revision Service

### Responsibility

Identify, schedule, and track topic revisions.

### Inputs

- Topic completion and learning-stage evidence.
- Quiz/test mistakes and confidence signals.
- Prior revision records.
- Study availability and active plan.

### Outputs

- Due/scheduled revision records.
- Revision-related plan items.
- Targeted resource or practice recommendations when available.

### Implementation direction

Use explicit, configurable revision rules. AI can help create a revision summary but does not decide or silently complete revisions.

## Quiz Service

### Responsibility

Create/manage checkpoint quizzes, evaluate attempts, and return useful feedback.

### Inputs

- Selected topic(s).
- Desired question count/difficulty where supported.
- Verified question/PYQ availability.
- Relevant retrieved notes when AI-generated questions are needed.

### Outputs

- Checkpoint quiz with source type clearly identified.
- Quiz attempt result, scores, answer feedback, and mistake evidence.
- Inputs to progress/revision recommendations.

### Implementation direction

- Prefer verified PYQs or curated questions when available.
- Label generated questions as AI-generated.
- Score objective questions deterministically where possible.
- Treat subjective evaluation as guidance requiring careful presentation.

## External Test Analysis Service

### Responsibility

Use learner-entered external test-series results as evidence within the wider mentoring system.

### Inputs

- Manually entered score, accuracy, time, counts, subject/topic performance, and mistake reasons.
- Optional private attachment/resource reference.

### Outputs

- Stored external-test result and linked topic performance evidence.
- Priority focus/revision recommendations based on available evidence.
- Clear distinction between actual entered data and any derived recommendation.

### Boundary

The MVP does not scrape, log into, or directly integrate with Testbook, Made Easy, or other external platforms.

## Resource and Knowledge Service

### Responsibility

Register learning resources, connect them to curriculum topics, and coordinate ingestion/retrieval status.

### Inputs

- Learner resource metadata, file/reference, and topic links.

### Outputs

- Resource record.
- Ingestion status.
- Searchable resource context for Mentor/Quiz services when indexing succeeds.

### Boundary

This service handles resource lifecycle and RAG coordination; it does not decide learner plans or progress stages.

## Orchestrator / Router

### Responsibility

Route a learner request or system event to the minimal focused service(s) required.

### Examples

| Event/request | Primary service(s) |
| --- | --- |
| “What should I study today?” | Planner, Revision, Progress Coach |
| “Explain deadlocks using my notes.” | Mentor, Resource/Knowledge, Retrieval |
| “Create five questions on deadlocks.” | Quiz, Resource/Knowledge, Mentor/AI provider |
| Quiz submitted | Quiz, Progress Coach, Revision |
| External mock result entered | External Test Analysis, Progress Coach, Revision, Planner on next replan |
| Resource uploaded | Resource/Knowledge, Ingestion |

### Boundary

The orchestrator selects a workflow; it does not become a second place for business rules. Each focused service owns its own rules.

## Learner Control and Approval

| Action | Learner confirmation needed? |
| --- | --- |
| Mark material completed / set learning stage | Yes; explicit learner action. |
| Create/accept plan recommendations | Learner can view and adjust; application records plan state transparently. |
| Save quiz attempt | Yes; learner submits the attempt. |
| Save external test result | Yes; learner enters/confirms data. |
| Mark revision complete | Yes; explicit learner action. |
| Mentor explanation/resource suggestion | No durable state change by default. |

## Future Evolution

Potential future needs include long-running workflow checkpoints, multi-agent handoffs, approval queues, and richer analytics. If those needs become real, replace or extend the orchestration layer only after documenting the concrete problem an agent framework solves.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-006: Start with a custom product-agent orchestrator](../adr/ADR-006-custom-agent-orchestration.md) — the decision this document implements, including the re-evaluation triggers for adopting a framework
- [Architecture overview](../architecture/overview.md)
- [Clean Architecture](../architecture/clean-architecture.md)
- [Domain terminology](../domain/terminology.md) — the canonical vocabulary for stages, evidence, and focus areas used here
- [RAG overview](../rag/overview.md)
- [Functional requirements](../requirements/functional.md)
- [Engineering AI workflow](engineering-ai.md) — the engineering assistant subagents, a separate sense of “agent” from the product agents defined here
