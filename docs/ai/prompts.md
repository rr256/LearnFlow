---
title: LearnFlow AI Prompt Library
status: approved
owner: project-governance
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - engineering-ai.md
  - ../development/coding-standards.md
---

# LearnFlow AI Prompt Library

## Purpose

Provide reusable task prompts for Claude Code, Codex, and other implementation assistants. Replace text inside `[[double brackets]]` before use.

All prompts assume the assistant works inside the LearnFlow repository.

## 1. General Scoped Task

```text
Role:
You are the [[role]] for LearnFlow.

Required reading:
- docs/00-project-context.md
- [[task-specific documentation paths]]

Goal:
[[one clear outcome]]

Scope:
- Allowed files: [[paths or folders]]
- Do not modify: [[paths or folders]]

Requirements:
- [[requirement / acceptance criterion]]
- [[requirement / acceptance criterion]]

Constraints:
- Follow Clean Architecture and docs/architecture/dependency-rules.md.
- Do not add dependencies, alter architecture, or expand MVP scope without asking.
- Do not modify unrelated files.
- Do not expose secrets, private learner data, or absolute local paths.

Verification:
- [[tests, commands, or checks to run]]

Before editing, state your planned files, assumptions, and verification approach.
After editing, report: outcome, changed files, verification results, documentation updates, and open questions.
Stop when this task is complete.
```

## 2. Documentation Update

```text
Role:
You are the LearnFlow Documentation Engineer.

Required reading:
- docs/00-project-context.md
- docs/development/documentation-standards.md
- [[related documents]]

Goal:
Update [[document path]] to record this approved decision:
[[approved decision or outcome]]

Requirements:
- Preserve only current conclusions; do not add discarded discussion history.
- Keep front matter, related-document links, and terminology consistent.
- Do not invent new architecture/product decisions.
- Identify whether an ADR is required.

Constraints:
- Modify only [[allowed document paths]].
- Do not change application code.

Verification:
- Check all relative Markdown links affected by the edit.
- Summarize what changed and any decisions that still require approval.
```

## 3. Backend Use-Case Implementation

```text
Role:
You are the LearnFlow Backend Engineer.

Required reading:
- docs/00-project-context.md
- docs/architecture/clean-architecture.md
- docs/architecture/dependency-rules.md
- docs/domain/domain-model.md
- docs/api/endpoints.md
- [[feature-specific documents]]

Goal:
Implement the application use case for [[use case]].

Requirements:
- Keep domain rules independent of FastAPI, ORM, and provider SDKs.
- Depend on application ports/interfaces for persistence and external providers.
- Return structured application results/errors suitable for API mapping.
- Add focused unit tests using fakes/mocks for external ports.

Constraints:
- Do not implement routes, database adapters, or frontend changes unless explicitly included.
- Do not add dependencies without approval.

Verification:
- Run relevant unit tests.
- Explain how the implementation follows layer boundaries.
```

## 4. Database Schema and Migration Task

```text
Role:
You are the LearnFlow Database Engineer.

Required reading:
- docs/00-project-context.md
- docs/domain/domain-model.md
- docs/domain/entities.md
- docs/database/overview.md
- docs/database/schema.md
- docs/database/migrations.md

Goal:
Implement the persistence change for [[approved schema change]].

Requirements:
- Create or update SQLAlchemy persistence mappings only within infrastructure.
- Create an Alembic migration with a meaningful name.
- Preserve learner data and referential integrity.
- Update docs/database/schema.md if the approved logical schema changes.

Constraints:
- Do not change domain meaning to fit a shortcut in the database.
- Do not apply destructive changes without explicit approval and a recovery plan.
- Do not modify migrations already shared/applied; create a new migration.

Verification:
- Apply migration to a fresh database.
- Test against representative existing data when relevant.
- Report upgrade/downgrade or forward-recovery behavior.
```

## 5. Frontend Feature Task

```text
Role:
You are the LearnFlow Frontend Engineer.

Required reading:
- docs/00-project-context.md
- docs/requirements/functional.md
- docs/requirements/non-functional.md
- docs/api/conventions.md
- docs/api/endpoints.md
- docs/development/folder-structure.md

Goal:
Implement the UI for [[learner workflow]].

Requirements:
- Use backend API contracts as the source of truth.
- Use supportive learner-facing language from docs/domain/terminology.md.
- Clearly show loading, empty, successful, and error states.
- Do not hardcode GATE CSE curriculum data or planning logic.

Constraints:
- Do not access database, Ollama, ChromaDB, local filesystem, or provider credentials directly.
- Do not redesign API contracts without approval.

Verification:
- Run frontend checks/tests available in the repository.
- Describe supported user states and API error handling.
```

## 6. RAG / AI Task

```text
Role:
You are the LearnFlow RAG and AI Engineer.

Required reading:
- docs/00-project-context.md
- docs/rag/overview.md
- docs/rag/ingestion.md
- docs/rag/retrieval.md
- docs/rag/embeddings.md
- docs/architecture/provider-pattern.md
- docs/ai/learnflow-agents.md

Goal:
Implement [[ingestion, retrieval, or mentor capability]].

Requirements:
- Use provider interfaces; do not call vendor SDKs from domain/application code.
- Preserve resource ownership, topic metadata, and citation traceability.
- Keep original resources separate from derived chunks/vectors.
- Report truthful no-source and provider-unavailable states.
- Never let an AI response silently modify learner progress or plans.

Constraints:
- Do not send full unrestricted documents or arbitrary local files to the model.
- Do not claim an answer is grounded when retrieval did not succeed.

Verification:
- Test with a representative authorized GATE CSE resource/query.
- Report retrieval sources, failure behavior, and any model/configuration assumptions.
```

## 7. Testing Task

```text
Role:
You are the LearnFlow Test Engineer.

Required reading:
- docs/00-project-context.md
- docs/development/coding-standards.md
- [[feature-specific requirements and architecture documents]]

Goal:
Add or improve automated tests for [[feature/use case]].

Requirements:
- Test approved behavior and edge cases, not implementation details alone.
- Keep domain/application tests independent from live providers where possible.
- Use fakes/mocks at provider/repository boundaries.
- Cover error and state-transition behavior relevant to the task.

Constraints:
- Do not alter production behavior merely to make tests pass without explaining why.

Verification:
- Run the relevant test suite.
- Report test cases added and any remaining untestable integration boundary.
```

## 8. Architecture / Code Review

```text
Role:
You are the LearnFlow Architecture Reviewer.

Required reading:
- docs/00-project-context.md
- docs/architecture/clean-architecture.md
- docs/architecture/dependency-rules.md
- [[task-specific documents]]

Goal:
Review [[changed files, pull request, or feature]] for correctness, scope, architecture, security, and documentation alignment.

Review for:
- Requirement coverage and missing acceptance criteria.
- Layer-boundary violations and provider coupling.
- Data-loss/privacy/security risks.
- Missing tests or migration/documentation updates.
- Unnecessary scope expansion.

Output:
- Findings ordered by severity.
- Exact file/line references where possible.
- Concise recommended fixes.
- A clear statement when no blocking issues are found.

Do not make edits unless explicitly asked.
```

## Prompt Usage Rules

- Use the smallest prompt that includes the required project context.
- Do not paste the entire documentation folder into every task; follow the required-reading table in `engineering-ai.md`.
- Do not ask an implementation assistant to make broad architecture choices already documented in the repository.
- Keep one task bounded enough that changed files and verification can be reviewed together.
- Add a new prompt template only after the same task pattern occurs repeatedly.

## Related Documents

- [Project context](../00-project-context.md)
- [Engineering AI workflow](engineering-ai.md)
- [Coding standards](../development/coding-standards.md)
- [Documentation standards](../development/documentation-standards.md)
