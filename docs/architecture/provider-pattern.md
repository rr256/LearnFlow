---
title: LearnFlow Provider Pattern
status: approved
owner: architecture
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - overview.md
  - clean-architecture.md
  - ../rag/overview.md
  - ../development/tech-stack.md
---

# LearnFlow Provider Pattern

## Purpose

Define how LearnFlow accesses replaceable external capabilities without letting specific vendor libraries enter learning business logic.

The provider pattern lets the MVP use local, low-cost tools while preserving a controlled path to cloud or alternative implementations later.

## Core Principle

Application use cases depend on capability-focused interfaces (ports), not vendor SDKs.

```text
Application use case
       ↓
Capability interface / port
       ↓
Configured infrastructure adapter
       ↓
Specific provider technology
```

For example:

```text
Mentor service
       ↓
AIProvider interface
       ↓
OllamaProvider adapter today
OpenAIProvider / GeminiProvider / ClaudeProvider later
```

## Provider Categories

| Capability | Application-facing responsibility | Initial implementation | Future examples |
| --- | --- | --- | --- |
| AI generation | Generate explanations, grounded answers, practice content, and structured outputs. | Ollama on the host machine | OpenAI, Azure OpenAI, Gemini, Claude |
| Embeddings | Convert eligible text into vectors for retrieval. | Local embedding model through an adapter | Cloud embedding services, alternate local models |
| Retrieval/vector search | Index, filter, and search resource representations. | ChromaDB | Qdrant, Pinecone, Azure AI Search |
| File storage | Save, open, delete, and locate learner-owned source files. | Local filesystem storage | Azure Blob Storage, Amazon S3 |
| Structured persistence | Store curriculum, progress, plans, assessments, and metadata. | PostgreSQL through repositories | Another relational database only if justified |
| Resource extraction | Extract usable text/metadata from supported resource formats. | Local extraction implementation | Alternate extraction services when justified |

## Initial Provider Configuration

The initial MVP deployment is local-first:

```text
AI provider:             Ollama
Embedding provider:      local model adapter
Vector search provider:  ChromaDB
File storage provider:   local filesystem
Structured persistence:  PostgreSQL
```

Provider selection must be configuration-driven. Provider names, endpoints, model names, collection names, and credentials must not be hardcoded into domain logic or frontend code.

## Application Ports

The following interfaces are expected at the application boundary. Exact method names and DTOs are implementation details, but the responsibilities are stable.

### AI Provider

**Responsibilities:**

- Accept a structured generation request containing instructions, relevant context, and output expectations.
- Return generated content and safe metadata such as provider/model identifier and generation status.
- Report availability or a clear failure state.

**Must not:**

- Write directly to the database.
- Read arbitrary learner files.
- Decide how progress, plans, or revision schedules are changed.

### Embedding Provider

**Responsibilities:**

- Convert approved text inputs into vector representations.
- Identify the model/version used so indexes can be managed safely.

**Must not:**

- Own document storage or curriculum metadata.
- Make retrieval decisions.

### Retrieval Provider

**Responsibilities:**

- Add, update, and remove searchable resource representations.
- Search for relevant representations using a query vector and supported filters.
- Return source references, relevance data, and metadata needed for citations.

**Must not:**

- Generate answers.
- Become the authoritative record of learner progress or resource ownership.

### Storage Provider

**Responsibilities:**

- Store source files and private attachments.
- Open/retrieve files for authorized application processes.
- Delete files when a valid lifecycle rule requires it.
- Report file existence and safe storage references.

**Must not:**

- Decide resource-topic links or learner permissions.
- Expose filesystem paths directly to the frontend as a security shortcut.

### Resource Extraction Provider

**Responsibilities:**

- Extract text and basic metadata from supported resource formats.
- Report extraction failures in a structured form.

**Must not:**

- Decide whether a resource is relevant to a learner question.
- Directly store vectors or call an AI provider without an application use case coordinating it.

## Persistence Is Handled Through Repositories

PostgreSQL is accessed through repositories that implement application persistence ports, such as curriculum, progress, plan, resource-metadata, and assessment repositories.

LearnFlow should not create a broad generic `DatabaseProvider` abstraction. Repositories are more useful because they expose meaningful domain operations rather than generic database commands.

```text
Planning service
       ↓
StudyPlanRepository interface
       ↓
PostgreSQL/SQLAlchemy repository adapter
```

## Provider Selection and Composition

The composition root is responsible for:

1. Reading validated environment/configuration values.
2. Constructing the selected provider adapters.
3. Verifying critical provider connectivity during startup or health checks where appropriate.
4. Injecting provider interfaces into application services.

Application services receive an interface, never a provider name or raw configuration value.

## Failure Behavior

| Provider unavailable | Required behavior |
| --- | --- |
| AI provider | Preserve non-AI product functions; show that mentor generation is temporarily unavailable. |
| Vector/retrieval provider | Do not invent a grounded answer; explain that relevant resource search is unavailable. |
| Storage provider | Prevent unsafe upload/read operations and show a clear error. |
| Embedding provider | Mark ingestion/indexing as failed or pending; retain the original resource and metadata. |
| PostgreSQL/repository | Do not report progress, plans, or attempts as saved until persistence succeeds. |

## Migration and Compatibility Rules

### Changing AI Providers

Changing AI providers must not alter learner progress, resource ownership, curriculum, plans, or assessment records. It changes only the generation adapter and configuration.

### Changing Storage Providers

Storage migration must preserve logical resource records and update storage references through an explicit migration process. Domain/application code should continue using the storage-provider interface.

### Changing Embedding Models or Vector Providers

Embeddings are model-dependent. A new embedding model or incompatible vector provider may require re-embedding and re-indexing resource content. Source files and resource metadata remain the authoritative inputs for rebuilding an index.

### Changing Relational Databases

Repository interfaces limit coupling, but database migrations and SQL-specific features still require deliberate planning. A relational-database change is not assumed to be free.

## Provider-Specific Data Boundaries

- Learner progress, plans, curriculum, and assessment records belong in structured persistence, not in an LLM or vector database.
- Original resources belong in storage, not only in a vector index.
- Vectors and chunks are derived search artifacts and can be rebuilt from eligible source resources.
- Generated AI text may be stored as a learner-visible artifact when useful, but it is not a replacement for source material or progress evidence.

## Anti-Patterns

- Calling `ollama.chat()` directly from a FastAPI route or domain entity.
- Calling ChromaDB directly from a mentor/planner use case.
- Storing an absolute local filesystem path as a frontend-facing URL.
- Letting a provider adapter decide learner progress or plan changes.
- Passing an entire document collection to an AI provider instead of retrieving relevant content.
- Adding interfaces for technologies that have no realistic replacement or testing need.

## Related Documents

- [Project context](../00-project-context.md)
- [Architecture overview](overview.md)
- [Clean Architecture](clean-architecture.md)
- [RAG overview](../rag/overview.md)
- [Technology stack](../development/tech-stack.md)
- [Docker strategy](../deployment/docker.md)
