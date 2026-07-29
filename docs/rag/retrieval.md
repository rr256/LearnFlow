---
title: LearnFlow RAG Retrieval
status: approved
owner: architecture-and-ai
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - overview.md
  - ingestion.md
  - embeddings.md
  - ../ai/learnflow-agents.md
---

# LearnFlow RAG Retrieval

## Purpose

Define how LearnFlow finds relevant, authorized learning-resource excerpts for mentor answers, practice generation, and resource recommendations.

## Retrieval Contract

A retrieval request provides:

```text
effective learner identity
question or retrieval query
optional learning program / curriculum version
optional subject/topic context
optional resource-type preference
requested result count and context budget
```

A retrieval result returns:

```text
selected source excerpts
resource and page/section references
topic/resource metadata needed for display
relevance information for application use
retrieval status and safe diagnostics
```

The retrieval provider does not generate an answer or modify learner progress.

## Retrieval Flow

```text
Learner question or learning task
        ↓
Resolve effective learner and optional topic context
        ↓
Validate accessible/ready resources
        ↓
Embed search query through embedding provider
        ↓
Vector search with ownership and metadata filters
        ↓
Rank/select a small relevant context set
        ↓
Return excerpts + citations to mentor/application service
        ↓
AI provider generates answer only from selected context where grounding is required
```

## Mandatory Filters

Every retrieval request must apply the filters that are known at the time of the request:

- Effective learner ownership/access scope.
- Resource status: only successfully indexed, accessible resources.
- Active curriculum version when curriculum context is supplied.
- Subject/topic links when the learner asks about a known topic.
- Resource type when the use case requires it, such as preferring PYQs for practice.

The system must not retrieve arbitrary learner files or data outside configured LearnFlow resources.

## Ranking and Selection

Initial ranking is based on semantic relevance from the vector search provider, with metadata filters applied first.

Application-level selection may also consider:

- Exact topic/subject match.
- Resource type, for example notes versus PYQs.
- Learner-selected or curator-selected primary resources.
- Source quality/verification state where available.
- Duplicate/near-duplicate chunk reduction.
- A configurable relevance threshold.

Do not add complex reranking models in the MVP unless real retrieval evaluation shows they are needed.

## Context-Budget Rules

- Send a limited number of high-quality excerpts, not an entire document collection.
- Preserve enough surrounding context for a chunk to remain understandable.
- Prefer diversity across relevant sections/resources over repeated near-identical chunks.
- Keep citations aligned with the exact excerpts selected.
- Limit total context according to the configured AI model and use case.

Context limits are configuration, not domain rules. They may vary between explanation, summary, and quiz-generation tasks.

## Grounded Mentor Behavior

When relevant sources are successfully retrieved:

- The mentor prompt identifies the supplied sources as the grounding context.
- The resulting answer should distinguish source-based explanations from any general guidance.
- The response includes learner-friendly resource/page/section references where practical.

When no relevant source is found:

- Do not fabricate citations or say that the learner's notes were used.
- The product may offer a clearly labeled general AI explanation if that behavior is enabled.
- The product should suggest linking/uploading relevant resources when appropriate.

When retrieval itself is unavailable:

- Report that resource-based search is unavailable.
- Do not silently downgrade to an ungrounded answer while claiming to use notes.

## Source and Citation Rules

A returned source reference should contain enough information to be useful:

```text
Resource title
Resource type/source label
Page, section, or location when available
Linked topic when relevant
```

Do not expose:

- Raw vector IDs.
- Absolute filesystem paths.
- Provider-specific collection names.
- Internal ranking/debug values to ordinary learners.

## Retrieval by Use Case

| Use case | Preferred retrieval behavior |
| --- | --- |
| Explain a concept | Retrieve relevant notes/short notes linked to the topic. |
| Answer a doubt | Retrieve topic-filtered notes, then broaden only if needed. |
| Generate checkpoint practice | Prefer verified PYQs/curated questions when available; otherwise use relevant notes as generation context and label output as AI-generated. |
| Recommend what to study | Use structured plan/progress data first; retrieve resources only to recommend material. |
| Revision guidance | Use structured revision/progress data first; retrieve short notes, formula sheets, mistakes, or PYQs for targeted practice. |

## Privacy and Multi-User Readiness

- Retrieval filtering must carry learner ownership/access scope from the beginning.
- A future multi-user system must never retrieve one learner's private resource for another learner.
- Curated/shared resources, if introduced, require explicit sharing scope rather than null/implicit access assumptions.

## Retrieval Evaluation

Before relying on retrieval for daily mentor use, evaluate it with representative GATE CSE questions:

- Are the top results about the intended topic?
- Do citations point to the material actually used?
- Are irrelevant chunks or duplicate chunks common?
- Does topic filtering improve answer relevance?
- Does the system correctly report when notes do not contain an answer?

Keep an evaluation set of learner-authorized or synthetic queries; do not depend only on anecdotal testing.

## Failure Modes

| Situation | Required behavior |
| --- | --- |
| No indexed resources | Explain that resource search is unavailable and guide the learner to add/index resources. |
| No relevant matches | Do not pretend to find a source; offer general help only if clearly labeled. |
| Vector provider unavailable | Return safe dependency-unavailable status; preserve non-RAG features. |
| Incomplete source metadata | Avoid misleading page/section citations; show only reliable reference details. |
| Unsupported/failed resource ingestion | Keep it out of retrieval until ingestion succeeds. |

## Related Documents

- [RAG overview](overview.md)
- [RAG ingestion](ingestion.md)
- [Embeddings](embeddings.md)
- [LearnFlow product agents](../ai/learnflow-agents.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Functional requirements](../requirements/functional.md)
