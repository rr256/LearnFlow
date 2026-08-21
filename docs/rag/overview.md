---
title: LearnFlow RAG Overview
status: approved
owner: architecture-and-ai
last_updated: 2026-08-20
related:
  - ../adr/ADR-037-learner-written-resource-notes.md
  - ../adr/ADR-038-local-topic-note-retrieval.md
  - ../adr/ADR-039-source-grounded-study-answers.md
  - ../00-project-context.md
  - ingestion.md
  - retrieval.md
  - embeddings.md
  - ../architecture/provider-pattern.md
  - ../adr/ADR-040-learner-uploaded-resource-files.md
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

**A learner's own written notes are not a resource type** and so are absent from the table above: they are text kept *against* a resource of any type, and they are the one thing in this document that is stored today. See below.

## Learner-Written Text: a Source With No File

Every source above is a **file** the learner already has, and the pipeline below exists to get usable
text out of one. There is a second kind of source that skips all of that: text the learner **typed or
pasted themselves**, kept against a resource as a *resource note*.

**A learner's notes are now searchable.** [ADR-038](../adr/ADR-038-local-topic-note-retrieval.md) adds RES-013: a
learner chooses a topic and sees passages from their own notes, found by **PostgreSQL full-text
search running locally**. That is retrieval without any of the pipeline below — no file, no
extraction, no chunking, no embedding, and no vector store — and it is all the retrieval there is.
An AI provider now reads what it returns, when the learner asks a question
([ADR-039](../adr/ADR-039-source-grounded-study-answers.md)), and it runs locally.

**This was the only content LearnFlow stored until uploaded PDFs arrived** ([ADR-040](../adr/ADR-040-learner-uploaded-resource-files.md)), and it is still the only content anything *reads*. It is the first study material the product holds
rather than points at — learner-written practice questions are stored too, but a question is
something the learner *made*, not material they *study from*. Files **are** now uploaded and stored, as bytes in a local volume with their
metadata in PostgreSQL. Nothing else on this page is built: **no text is extracted**, nothing is
normalised, chunked, embedded, or indexed, and no vector store exists — a stored PDF is kept and
handed back, and nothing reads inside it.
A mentor now answers a question from these notes — grounded in them alone, and never asked at all
when they support nothing.

A note is a source with no file, so four of the ingestion steps have nothing to do:

```text
Learner types or pastes text
        ↓
Stored verbatim against one resource        (no file to store, nothing to extract)
        ↓
Found by full-text search on a topic       (RES-013, local, only when asked)
        ↓
[ not chunked, not embedded, not vector-indexed — none of this exists yet ]
```

Two consequences worth stating before retrieval is built:

- **A note needs no extraction and has no extraction failure mode.** The honest-failure rules below
  exist because a scanned PDF may yield nothing; typed text always yields itself.
- **A note is not normalised.** [Ingestion](ingestion.md#step-3-normalize-content) prescribes
  normalisation before chunking, and it is deliberately not applied: rewriting what a learner typed
  would change what they wrote. Whether a note is normalised *when it is chunked* is a decision for
  the change that builds chunking.

Notes **are** the retrieval context, and the only one. They are searched locally by RES-013, and when
the learner asks a question the matching passages — and nothing else — are sent to a locally running
model by MNT-001. Nothing else is retrieved, because nothing else is stored. See
[ADR-037](../adr/ADR-037-learner-written-resource-notes.md),
[ADR-038](../adr/ADR-038-local-topic-note-retrieval.md), and
[ADR-039](../adr/ADR-039-source-grounded-study-answers.md).

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
- [ADR-037: Store the learner's own written notes against a learning resource](../adr/ADR-037-learner-written-resource-notes.md) — the file-free source this page now records, and the boundary around it
- [ADR-038: Retrieve passages from a learner's own notes locally, when they ask](../adr/ADR-038-local-topic-note-retrieval.md) — the retrieval that exists, and the pipeline it deliberately does not enter
- [RAG retrieval](retrieval.md)
- [Embeddings](embeddings.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Learning resources](../domain/entities.md)
- [Non-functional requirements](../requirements/non-functional.md)
