---
title: LearnFlow Database Overview
status: approved
owner: architecture-and-data
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - schema.md
  - migrations.md
  - ../domain/domain-model.md
  - ../architecture/provider-pattern.md
---

# LearnFlow Database Overview

## Purpose

Define the responsibility and boundaries of structured persistence in LearnFlow before individual tables and columns are designed.

## Decision Summary

PostgreSQL is the initial relational database for LearnFlow. It stores structured, transactional product data through application repository interfaces.

PostgreSQL is not the primary store for original PDF/video files or vector embeddings. Those have separate responsibilities.

## Data Ownership Boundaries

```text
PostgreSQL
├── Learner identity and preferences
├── Learning programs and curated curriculum structure
├── Study goals, availability, plans, and plan items
├── Learner topic progress and learning evidence
├── Revision records
├── Quiz definitions, attempts, answers, scores, and mistakes
├── Manually entered external test results and topic evidence
├── Resource metadata and curriculum links
└── References to stored files and retrieval/indexing status

File Storage
├── Original PDFs and attachments
├── Optional test-result screenshots/PDFs
└── Other learner-owned source files

Vector Search / ChromaDB
├── Derived text chunks
├── Embeddings
└── Search metadata required for grounded retrieval
```

## Why the Separation Matters

- Original files remain available even if an index is rebuilt or an embedding model changes.
- Learner progress and plans remain durable even if the AI, vector database, or retrieval system is unavailable.
- Vector records remain derived artifacts rather than an accidental source of truth.
- Structured relationships, validation, ownership, and transaction consistency are handled by a relational database.

## Core Data Areas

### Curriculum Data

Stores the generic learning-program hierarchy:

```text
Learning Program
→ Curriculum Version
→ Subject
→ Topic / Subtopic
→ Topic Relationships
```

The initial curated data is GATE CSE. The model must support future learning programs without requiring new core table designs.

### Learner Data

Stores learner-owned goals, availability, preferences, plans, progress, study activities, assessment evidence, revision history, and resource ownership.

Although the MVP has one local learner, learner-owned records must be associated with a learner identity from the beginning. This avoids a future migration that would otherwise touch every data area.

### Planning and Progress Data

Stores study goals, study plans, plan items, topic progress, learning-stage evidence, and revision records.

Progress remains evidence-based. Do not collapse manual completion, learning stage, quiz score, external test results, and revision history into one irreversible database field.

### Assessment Data

Stores checkpoint quizzes, questions, learner attempts, answer-level results, scores, timing, and mistake evidence.

Stores manually entered external test results separately from internal quizzes, while allowing both to contribute evidence to the same topic progress.

### Resource Metadata

Stores resource titles, types, learner ownership, storage references, subject/topic links, indexing status, and lifecycle metadata.

The database stores a safe logical reference to a file; it does not treat an absolute local path as a frontend-facing identifier.

## Data Integrity Principles

- Use database constraints for relationships that must always be valid.
- Enforce learner ownership at every learner-owned relationship.
- Preserve timestamps and relevant history for important changes, such as plans, progress evidence, quiz attempts, and external test results.
- Use transactions for operations that must succeed or fail together.
- Do not mark progress, plans, or attempts as saved until persistence succeeds.
- Keep manually entered and AI-generated information distinguishable from verified source data.
- Never infer topic-level performance from a total test score alone.

## Deletion and Retention Principles

Detailed deletion policy will be defined with the schema, but the following direction applies:

- A learner should be able to correct or remove their own manual entries.
- Deleting a source resource must consider linked metadata, indexes, and learner-visible history.
- Derived vectors/chunks may be safely rebuilt or removed when their source resource lifecycle allows it.
- Historical assessment and progress evidence should not be silently discarded when a current plan changes.

## Repository Boundary

Application services access structured persistence through meaningful repository interfaces, not generic database commands.

Examples:

```text
CurriculumRepository
StudyGoalRepository
StudyPlanRepository
TopicProgressRepository
ResourceRepository
AssessmentRepository
ExternalTestResultRepository
RevisionRepository
```

Concrete PostgreSQL/SQLAlchemy implementations belong in infrastructure. Domain and application logic must not import ORM models or database sessions.

## Backup and Restore Direction

The local MVP must document how to back up and restore:

- PostgreSQL structured data.
- Learner-owned source files.
- Configuration needed to reconnect services.

The vector index may be backed up, but it must also be rebuildable from stored resources and metadata.

## Not Defined Here

This document intentionally does not decide:

- Table names, fields, SQL types, primary-key format, or index definitions.
- Exact ORM model structure.
- Soft-delete versus archive behavior for every entity.
- Migration-tool commands.
- Query optimization details.

Those decisions belong in `schema.md`, `migrations.md`, and implementation-specific ADRs.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-003: Use PostgreSQL for structured persistence](../adr/ADR-003-postgresql-persistence.md) — the decision this document implements
- [Domain model](../domain/domain-model.md)
- [Domain entities](../domain/entities.md)
- [Database schema](schema.md)
- [Database migrations](migrations.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Non-functional requirements](../requirements/non-functional.md)
