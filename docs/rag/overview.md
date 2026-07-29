---
title: LearnFlow RAG Overview
status: approved
owner: architecture-and-ai
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ingestion.md
  - retrieval.md
  - embeddings.md
  - ../architecture/provider-pattern.md
---

# LearnFlow RAG Overview

## Purpose

Define how LearnFlow uses Retrieval-Augmented Generation (RAG) to answer learner questions using relevant, learner-owned study materials.

RAG gives the mentor useful context at request time. It is not model training, and it is not a replacement for structured learner progress, curriculum, or plan data.

## Core Principle

```text
Original resource + structured metadata
        ↓
Extracted, searchable representations
        ↓
Relevant retrieval for a learner question
        ↓
Selected context sent to the AI provider
        ↓
Grounded answer with source references where practical
```

The model does not permanently “remember” a learner's PDFs. LearnFlow retrieves relevant content for each request.

## What RAG Is Used For

- Explaining a concept from the learner's notes.
- Answering doubts using relevant PDFs, short notes, and PYQs.
- Creating a topic-focused summary or revision guide.
- Generating grounded practice questions when appropriate.
- Suggesting relevant resources/pages for a topic.

## What RAG Is Not Used For

- Storing learner progress, plans, revisions, or test scores.
- Deciding deterministic planning/scheduling rules.
- Proving that a learner understands a topic.
- Replacing original PDF/source files.
- Giving the model unrestricted access to the learner's computer or all files.

## Initial Supported Resource Direction

| Resource type | MVP treatment |
| --- | --- |
| Text-based PDF notes | Store, extract text, index when extraction succeeds. |
| PYQ PDFs | Store, extract/index when suitable; retain source labeling. |
| Short notes/formula sheets | Store and index when suitable. |
| Scanned/image-only PDFs | Register resource; extraction/OCR support is evaluated separately and failure must be visible. |
| Local video resources | Store a reference/path and topic links; video transcription/indexing is not an MVP requirement. |
| Screenshots/PDFs of test results | Store as private reference; not automatically used as trusted topic evidence without learner confirmation. |

## Data Boundaries

```text
PostgreSQL
  Resource metadata, learner ownership, topic links, ingestion status

File Storage
  Original PDFs and other source files

Vector Search
  Derived chunks, embeddings, source references, searchable metadata

AI Provider
  Receives only the selected question and limited relevant context for a request
```

Vectors and chunks are derived artifacts. They can be rebuilt from eligible source files and metadata when an embedding model or vector provider changes.

## End-to-End Flow

### 1. Resource registration

The learner registers/uploads a resource and links it to one or more GATE CSE topics.

### 2. Ingestion

The ingestion workflow validates the resource, extracts usable text, normalizes it, splits it into chunks, creates embeddings, and indexes the chunks with source metadata.

### 3. Retrieval

When a learner asks a question, LearnFlow uses topic context, resource ownership, and query relevance to retrieve a small set of useful source excerpts.

### 4. Mentor generation

The mentor service sends the question, selected excerpts, applicable learner context, and output instructions to the configured AI provider.

### 5. Response and citations

LearnFlow returns the answer along with resource/source references where practical. The learner should be able to understand whether an answer is grounded in their material.

## Retrieval Context Rules

- Retrieve only resources the effective learner is allowed to use.
- Use curriculum/topic metadata as a filter or relevance signal when available.
- Send only a limited, relevant context set to the AI provider.
- Preserve resource/page/chunk references needed to explain answer sources.
- Do not claim that an answer is source-grounded when retrieval failed or no relevant source was found.
- If RAG is unavailable, the mentor may provide a clearly labeled general AI response only when product policy permits; it must not pretend to have read the learner's notes.

## Grounding and Citation Policy

Where the mentor uses retrieved material, the response should identify supporting resources in a learner-friendly way, for example:

```text
Based on: Operating Systems Notes, “Deadlocks” section
Related practice: PYQ collection, Deadlock questions
```

Citation display should not expose internal vector IDs, raw storage paths, or implementation-specific metadata.

## Privacy and Safety

- Index only learner-authorized resources.
- Keep source resources local by default in the MVP.
- Do not expose one learner's resources to another learner when multi-user support is introduced.
- Do not use learner resources to train a model as part of the product workflow.
- Keep provider endpoints and credentials out of retrieved content and AI prompts.
- Preserve original source attribution for PYQs and other verified material.

## Initial Technology Direction

- **File storage:** local storage provider.
- **Embeddings:** Ollama through an embedding-provider adapter, with the embedding model selected through configuration.
- **Vector search:** ChromaDB through a retrieval-provider adapter.
- **Generation:** Ollama through an AI-provider adapter.

These are replaceable infrastructure choices. Application use cases depend on the relevant provider interfaces, not vendor libraries.

## RAG Quality Expectations

RAG quality is measured by whether retrieved sources are relevant, grounded answers are traceable, and failure states are honest. The system must not silently hallucinate a resource citation or present irrelevant text as supporting evidence.

Detailed chunking, embedding, retrieval-ranking, and evaluation rules belong in the related documents.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-004: Use Ollama as the initial local AI provider](../adr/ADR-004-ollama-local-ai-provider.md) — the generation and embedding choice behind this pipeline
- [ADR-002: Use provider interfaces for external capabilities](../adr/ADR-002-provider-pattern.md) — why retrieval and embeddings stay replaceable
- [RAG ingestion](ingestion.md)
- [RAG retrieval](retrieval.md)
- [Embeddings](embeddings.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Learning resources](../domain/entities.md)
- [Non-functional requirements](../requirements/non-functional.md)
