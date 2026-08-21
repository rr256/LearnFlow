---
title: LearnFlow RAG Ingestion
status: approved
owner: architecture-and-ai
last_updated: 2026-08-20
related:
  - ../adr/ADR-037-learner-written-resource-notes.md
  - ../adr/ADR-038-local-topic-note-retrieval.md
  - ../00-project-context.md
  - overview.md
  - embeddings.md
  - ../architecture/provider-pattern.md
  - ../database/schema.md
  - ../adr/ADR-040-learner-uploaded-resource-files.md
---

# LearnFlow RAG Ingestion

## Purpose

Define how eligible learner-owned resources become searchable knowledge while preserving source files, ownership, traceability, and honest failure states.

## Ingestion Scope

The MVP supports text extraction and indexing for eligible text-based study resources such as PDF notes, PYQ PDFs, short notes, and formula sheets.

Video transcription, unrestricted website ingestion, and fully automated OCR for scanned PDFs are not MVP requirements.

**One step of this document is implemented, and no more.** A learner's uploaded PDFs **are stored** —
bytes in a local volume, metadata in `resource_files` — which is *Step 1*, register and validate
([ADR-040](../adr/ADR-040-learner-uploaded-resource-files.md)). **No text is extracted**, nothing is
normalised, chunked, embedded, or indexed, `resource_ingestions` does not exist, and **no ingestion
record is created**: a stored file enters no lifecycle. The lifecycle below is the approved target
for **file-based** sources.

### Learner-written text enters no lifecycle

There is one source that is stored today and does **not** pass through any of it: text the learner
**typed or pasted themselves**, kept against a resource as a *resource note*
([ADR-037](../adr/ADR-037-learner-written-resource-notes.md)).

Every step below assumes a file. A note has none, so the first four have nothing to do — there is no
storage reference to validate, no original to keep, nothing to extract, and no extraction that could
fail. It is stored **verbatim** and, deliberately, is **not normalised**: normalisation exists to
improve retrieval from extracted text, and rewriting what a learner typed would change what they
wrote.

A note is therefore **not ingested, not chunked, and not embedded**, and it creates no ingestion
record. Whether it is normalised at the point it is chunked is left to the change that builds
chunking. This section records where such a source would enter, not that it has.

**One narrow exception, on the word *indexed*.** A note's text **does** have a local index: a
PostgreSQL full-text (GIN) index over every note's title and body, added for RES-013 so a learner
can ask for passages on a topic they choose. Only **active** notes on registered material are ever
searched, but that is a filter the query applies, not a condition of the index ([ADR-038](../adr/ADR-038-local-topic-note-retrieval.md)). That is an ordinary database
index over text already in the table — it is **not** the vector indexing this document means. To be
explicit about what that index is and is not:

- **Not embedded**, and no embedding provider exists.
- **Not stored in a vector database**, and no ChromaDB service exists.
- **Not chunked**; the note is indexed whole.
- **Not sent anywhere.** It is read on the learner's own machine, by one query, only when they ask.
- **Nothing derived is persisted** — no chunk, no vector, no cached extract, no search history.

Everything else in this document is unchanged: a note still enters no ingestion lifecycle, and
`resource_ingestions` still does not exist.

## Ingestion Lifecycle

```text
Register resource
       ↓
Validate ownership, type, size, and storage reference
       ↓
Store original file / resource metadata
       ↓
Create ingestion record: queued
       ↓
Extract text and source-location metadata
       ↓
Normalize and validate extracted content
       ↓
Split into retrievable chunks
       ↓
Create embeddings
       ↓
Index chunks with source metadata
       ↓
Mark ingestion completed or failed
```

Ingestion is asynchronous when it may take longer than an ordinary API request. The learner can see `queued`, `processing`, `completed`, or `failed` status.

## Step 1 — Register and Validate Resource

Before extraction, LearnFlow must:

- Confirm the resource belongs to or is accessible by the effective learner.
- Record resource type, title, source label, storage reference, and topic links.
- Validate configured file-type and file-size limits.
- Store the original source file through the configured storage provider before treating it as indexed knowledge.
- Reject unsupported or unsafe inputs with a clear user-facing error.

The application must not treat an absolute local filesystem path as a frontend-facing resource identifier.

## Step 2 — Extract Text

For a supported text-based PDF, the extraction provider should produce:

- Extracted text.
- Page/section location information when available.
- Basic document metadata when available.
- Extraction warnings or failure details.

If a PDF is scanned/image-only and no usable text can be extracted, the resource remains registered but its ingestion is marked failed or unsupported. LearnFlow must not pretend that it indexed the document.

## Step 3 — Normalize Content

Normalize extracted content before chunking while preserving source traceability.

Typical normalization includes:

- Removing repeated whitespace and obvious extraction noise.
- Preserving meaningful headings, page boundaries, lists, and formula context where possible.
- Removing empty or unusable sections.
- Maintaining page/section references for later citations.

Do not aggressively rewrite the learner's source material during ingestion. Normalization must improve retrieval, not alter meaning.

## Step 4 — Chunk Content

Split usable text into chunks that are small enough for retrieval and large enough to preserve concept context.

### Chunking rules

- Prefer semantic boundaries such as headings, paragraphs, and page sections over arbitrary character cuts.
- Use controlled overlap only when necessary to avoid losing context at boundaries.
- Keep the chunking policy configurable and versioned.
- Preserve a stable sequence number and page/section reference for every chunk.
- Avoid indexing empty, duplicate, or extraction-garbage chunks.

Exact chunk size and overlap values are implementation configuration, to be evaluated with real GATE CSE notes before being finalized.

## Step 5 — Create Embeddings and Index

For each accepted chunk:

1. Request an embedding from the configured embedding provider.
2. Store/index the vector through the retrieval provider.
3. Include enough metadata to filter and cite the result later.

Required retrieval metadata includes, where applicable:

```text
resource_id
learner_id or ownership scope
resource_type
resource title/source label
curriculum version
subject/topic IDs
page/section reference
chunk sequence
document/content fingerprint
extraction version
embedding model/version
```

The vector index is derived data. The resource file and PostgreSQL metadata remain the source of truth.

## Duplicate and Re-Ingestion Handling

- Compute/store a content fingerprint when practical.
- Detect when the same resource content has already been indexed with the same extraction and embedding configuration.
- Avoid duplicate vector entries from repeated ingestion requests.
- Re-ingest when the resource changes, extraction improves, chunking policy changes, or the embedding model changes.
- Keep a history of ingestion attempts so failures and rebuilds are understandable.

## Failure and Retry Behavior

| Failure type | Required behavior |
| --- | --- |
| Unsupported file | Keep resource metadata; mark ingestion failed/unsupported with a clear explanation. |
| Text extraction failure | Keep original resource; mark failed and allow retry after correction/provider change. |
| Embedding/provider failure | Do not mark indexed; record safe error details and allow retry. |
| Vector-index failure | Do not claim resource is searchable; preserve original file and ingestion record. |
| Partial indexing failure | Mark attempt failed or incomplete according to implementation policy; clean/reconcile partial derived vectors before retry. |

Retries must not silently produce duplicate chunks or leave an apparently successful resource in a partially indexed state.

## Resource Deletion and Reindexing

- Deleting a resource requires coordinated removal of derived vectors/chunks and associated storage content according to the resource lifecycle policy.
- Deleting derived vectors does not delete the original resource unless the learner explicitly removes the resource.
- Changing embedding models or vector providers requires planned re-indexing; it must not affect learner progress, plans, or assessments.

## Privacy and Access Rules

- Index only resources the learner explicitly registered or uploaded.
- Store ownership scope in both structured metadata and retrieval filters.
- Retrieval must filter by the effective learner once multi-user support exists.
- Do not send full original documents to the AI provider as a shortcut; retrieve only selected chunks.
- Do not index secrets, configuration files, or arbitrary computer files outside configured LearnFlow resource storage.

## MVP Limitations

- No guarantee of perfect PDF extraction.
- No automatic video transcription/indexing.
- No automatic acceptance of scanned PDFs as searchable content without a supported OCR path.
- No external test-platform scraping or import.
- No claim that indexing a resource makes every mentor answer correct; retrieval quality is evaluated separately.

## Verification Checklist

Before marking an ingestion implementation ready:

- [ ] A supported GATE CSE PDF can be registered and indexed.
- [ ] Indexed chunks retain resource and page/section traceability.
- [ ] The learner can see processing/completed/failed status.
- [ ] A failed ingestion preserves the original resource and gives a useful retry path.
- [ ] Repeated ingestion does not create duplicate searchable content.
- [ ] Deleting/re-indexing a resource handles derived vectors safely.
- [ ] Retrieval can filter by topic and resource ownership.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-002: Use provider interfaces for external capabilities](../adr/ADR-002-provider-pattern.md) — why extraction, embedding, and storage stay replaceable
- [ADR-004: Use Ollama as the initial local AI provider](../adr/ADR-004-ollama-local-ai-provider.md) — the embedding implementation this pipeline calls
- [RAG overview](overview.md)
- [ADR-037: Store the learner's own written notes against a learning resource](../adr/ADR-037-learner-written-resource-notes.md) — the file-free source that enters none of this lifecycle
- [ADR-038: Retrieve passages from a learner's own notes locally, when they ask](../adr/ADR-038-local-topic-note-retrieval.md) — the full-text index an active note has, and why it is not vector indexing
- [Embeddings](embeddings.md)
- [RAG retrieval](retrieval.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Database schema](../database/schema.md)
- [Non-functional requirements](../requirements/non-functional.md)
