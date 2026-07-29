---
title: LearnFlow Architecture Overview
status: approved
owner: architecture
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - clean-architecture.md
  - provider-pattern.md
  - dependency-rules.md
  - ../development/tech-stack.md
---

# LearnFlow Architecture Overview

## Purpose

Describe LearnFlow's major components, their responsibilities, and the boundaries through which they communicate.

This document establishes the system shape. Detailed layer rules, provider interfaces, database schema, API contracts, and deployment configuration are specified in related documents.

## Architectural Goals

- Provide a useful local-first AI mentor for GATE CSE learners.
- Keep learning business rules independent from specific AI, storage, vector-search, and cloud technologies.
- Support a dynamic curriculum and future learning programs without frontend topic hardcoding.
- Preserve learner privacy and control over study materials and progress.
- Allow future cloud and multi-user evolution without building those features prematurely.
- Keep deterministic planning and progress logic usable even when an AI provider is unavailable.

## System Context

```text
Learner
   │
   ▼
Web Application (Next.js + TypeScript)
   │  HTTPS/REST
   ▼
Backend API (FastAPI)
   │
   ├── Learning Application Services
   │     ├── Curriculum and resource management
   │     ├── Planning and revision scheduling
   │     ├── Progress and assessment analysis
   │     └── Mentor / RAG coordination
   │
   ├── PostgreSQL
   │     └── Structured learner, curriculum, plan, progress, and assessment data
   │
   ├── Local File Storage
   │     └── Learner PDFs, attachments, and local resource references
   │
   ├── Vector Search Provider (initially ChromaDB)
   │     └── Searchable knowledge representations of resources
   │
   └── AI Provider (initially host-machine Ollama)
         └── Explanations, grounded answers, and practice generation
```

## Major Components

### Web Application

The web application is the learner-facing interface.

**Responsibilities:**

- Display curriculum, study plan, progress, revisions, resources, mentor interactions, and assessment history.
- Collect learner input, including study availability, progress updates, quiz answers, and external test performance.
- Present supportive guidance and clear next actions.
- Render data returned by the backend; it must not hardcode GATE CSE subjects or topics.

**Does not own:** learning business rules, provider-specific logic, database access, or direct calls to Ollama/ChromaDB.

### Backend API

The FastAPI backend is the application boundary between the UI and core services.

**Responsibilities:**

- Authenticate/identify requests when identity support is introduced.
- Validate requests and return stable API responses.
- Invoke application use cases.
- Coordinate storage, persistence, retrieval, and AI providers through interfaces.
- Translate expected domain/application errors into user-safe API errors.

**Does not own:** frontend presentation concerns or direct business-rule duplication.

### Learning Application Services

Application services coordinate domain rules to achieve a learner-facing outcome.

Core service areas include:

- **Curriculum service:** exposes the curated GATE CSE program and future program data.
- **Resource service:** registers resources and links them to subjects/topics.
- **Planning service:** creates and adapts roadmap, weekly, and daily plans.
- **Progress service:** records evidence and derives supportive next actions.
- **Revision service:** identifies and tracks revision work.
- **Assessment service:** manages checkpoint quizzes, attempts, mistakes, and external test-performance entries.
- **Mentor service:** retrieves relevant knowledge and asks the configured AI provider for an explanation or practice content.

Services use domain concepts and application interfaces; they must not depend directly on specific infrastructure libraries.

### Domain Layer

The domain layer contains the stable learning concepts and rules documented in `docs/domain/`.

**Examples:** learning programs, topics, study goals, plans, topic progress, revisions, quizzes, mistakes, and external test results.

The domain layer must not import FastAPI, ORM, ChromaDB, Ollama, Docker, or frontend code.

### Persistence: PostgreSQL

PostgreSQL stores structured, transactional information.

**Examples:** curriculum hierarchy, learner profile, plans, plan items, progress evidence, quiz attempts, revisions, external test results, and resource metadata.

It does not store the primary PDF/video file content or vector embeddings as the main source of truth.

### File Storage

File storage holds learner-owned PDFs, attachments, and other source files. The initial implementation is local storage.

Application code accesses it through a storage-provider interface so a later adapter can use Azure Blob Storage or another system.

### RAG and Vector Search

The retrieval system turns eligible learning resources into searchable knowledge.

**Initial direction:** ChromaDB as the vector-search implementation and a local embedding model compatible with the local AI workflow.

The rest of the application communicates through retrieval/embedding interfaces, not directly through ChromaDB-specific calls.

### AI Provider

The AI provider supplies language reasoning and generation.

**Initial direction:** Ollama running on the learner's machine.

**Appropriate responsibilities:** grounded explanations, concept summaries, doubt resolution, practice-question generation, and natural-language guidance.

**Not appropriate responsibilities:** authoritative storage of progress, deterministic scheduling rules, direct database writes, or unreviewed changes to learner records.

## Core Flows

### Planning Flow

```text
Learner updates goal, availability, or progress
   ↓
Planning service reads curriculum, progress, revisions, and constraints
   ↓
Deterministic planning rules create or update recommendations
   ↓
Plan and plan items are stored in PostgreSQL
   ↓
Web application displays the updated timeline
```

An AI provider may improve wording or explanations, but the core plan must not require AI availability.

### Grounded Mentor Flow

```text
Learner asks a topic question
   ↓
Mentor service identifies relevant topic and learner context
   ↓
Retrieval service searches eligible learning resources
   ↓
Relevant source excerpts + question are sent to the AI provider
   ↓
Mentor response and source references are returned to the learner
```

The AI provider does not receive an entire document collection or unrestricted access to the learner's machine.

### Progress and Assessment Flow

```text
Learner completes study work, a checkpoint quiz, or enters a test result
   ↓
Progress/assessment service validates and stores evidence
   ↓
Topic progress, mistakes, and revision needs are evaluated
   ↓
Planning service can use the new evidence in later recommendations
   ↓
Web application shows a supportive stage and next action
```

### Resource Ingestion Flow

```text
Learner registers or uploads a resource
   ↓
Resource metadata and curriculum links are stored
   ↓
File is stored through the storage provider
   ↓
Eligible text is extracted, chunked, embedded, and indexed
   ↓
Index status is shown to the learner
```

## Initial Local Deployment Shape

Docker Compose is the local environment coordinator.

```text
Docker Compose
 ├── Web application container
 ├── Backend API container
 ├── PostgreSQL container
 └── ChromaDB container

Host machine
 └── Ollama service and downloaded local models
```

The backend must receive the Ollama endpoint through configuration. Containerized Ollama is a future option, not an MVP requirement.

## Future Evolution Boundaries

- New learning programs are curriculum data; they do not require a separate frontend or backend codebase.
- Cloud AI providers, cloud storage, alternative vector databases, and embedding models are added as adapters behind existing interfaces.
- Multi-user support adds identity and authorization around learner-owned records.
- Agent frameworks may replace only the orchestration layer if future workflows become complex; specialized learning responsibilities remain modular.
- Public cloud hosting is separate from the local-first MVP deployment.

## Explicit Architectural Constraints

- Frontend code must not hardcode curriculum topics or business rules.
- Business logic must not call Ollama, ChromaDB, storage SDKs, or ORM APIs directly.
- AI responses must not silently mutate learner progress or plans.
- Learner progress and resources must remain separate from model memory.
- External test-series data is entered by the learner; the MVP does not scrape or integrate with third-party test platforms.

## Related Documents

- [Project context](../00-project-context.md)
- [Clean Architecture](clean-architecture.md)
- [Provider pattern](provider-pattern.md)
- [Dependency rules](dependency-rules.md)
- [Technology stack](../development/tech-stack.md)
- [Domain model](../domain/domain-model.md)
- [RAG overview](../rag/overview.md)
