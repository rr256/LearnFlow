---
title: LearnFlow Non-Functional Requirements
status: approved
owner: product-and-architecture
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - functional.md
  - ../architecture/overview.md
  - ../development/coding-standards.md
---

# LearnFlow Non-Functional Requirements

## Purpose

Define the quality, safety, privacy, and operational expectations for LearnFlow. These requirements apply across all features, including planning, progress tracking, RAG, assessments, and AI mentor responses.

## Scope

The MVP is a local-first, single-learner GATE CSE mentor. Requirements for public hosting, multi-user accounts, and cloud services are future-ready constraints, not current delivery commitments.

## NFR-001 — Local-First Privacy

**Priority:** MVP

Learner-owned study data must remain local by default.

### Requirements

- Local PDFs, notes, progress, quiz attempts, and manually entered test performance must not be uploaded to third parties by default.
- The MVP must not collect or request credentials for Testbook, Made Easy, or other external test-series platforms.
- If a future cloud AI or storage provider is enabled, the application must make the provider and data-sharing implications clear before use.
- Attached test-result screenshots and PDFs are private learner resources, not public content.

## NFR-002 — Data Integrity and Recovery

**Priority:** MVP

Learner progress is valuable and must not be silently lost or corrupted.

### Requirements

- Progress updates, quiz attempts, plans, revisions, and test-performance entries must be stored consistently.
- Failed operations must show a clear error and must not appear successful when data was not saved.
- The system must keep enough timestamps and history to explain when important learner data changed.
- The local deployment must have a documented backup and restore approach before regular daily use is recommended.

## NFR-003 — Responsiveness and Feedback

**Priority:** MVP

Normal learner interactions should feel responsive and long-running work must remain visible.

### Requirements

- Viewing the dashboard, curriculum, progress, and current plan should not require waiting for an AI response.
- Document ingestion, indexing, large uploads, and AI generation must show an understandable in-progress, completed, or failed state.
- The learner must be able to understand what operation is running and what to do when it fails.
- Performance targets will be measured and refined after the first local end-to-end workflow is implemented.

## NFR-004 — Usability and Supportive Language

**Priority:** MVP

LearnFlow must help learners act without using discouraging or judgmental language.

### Requirements

- Present progress through constructive stages such as `Building foundation`, `Developing confidence`, `Practice-ready`, and `Strong understanding`.
- Pair a lower-performance signal with a practical next action, not a negative label.
- Make the current recommended task, overdue work, and revision due items easy to find.
- Do not hide important trade-offs when a learner's available time is insufficient for the target timeline.
- The learner can correct manual entries and revise personal learning-stage assessments.

## NFR-005 — AI Transparency and Learning Safety

**Priority:** MVP

AI guidance must be useful without being presented as unquestionable truth or a substitute for learning.

### Requirements

- Where an answer uses local resources, show or identify the supporting resource when practical.
- Distinguish AI-generated practice content from verified external questions such as PYQs.
- Do not represent one quiz score, one AI response, or one manually selected stage as proof of permanent mastery.
- AI suggestions must not silently alter learner progress, plans, or records without learner confirmation or recorded evidence.
- The product must not promise ranks, marks, selection, or examination outcomes.

## NFR-006 — Security Baseline

**Priority:** MVP

The local MVP must use sensible safeguards appropriate to learner data and local files.

### Requirements

- Validate file type, size, and handling before accepting uploaded resources.
- Do not store secrets, API keys, or passwords in source code or committed configuration files.
- Use environment-based configuration for infrastructure connections and provider credentials.
- Restrict file operations to configured application storage locations.
- Design future user data ownership and authorization boundaries even though public authentication is not part of the MVP.

## NFR-007 — Maintainability and Replaceability

**Priority:** MVP

LearnFlow must remain understandable and adaptable as its product scope grows.

### Requirements

- Business logic must not depend directly on a specific AI model, vector database, file-storage system, or cloud provider.
- External systems that are expected to change must be accessed through clear interfaces/adapters.
- Modules must have focused responsibilities and avoid unrelated cross-layer dependencies.
- Significant, durable decisions must be recorded in Architecture Decision Records (ADRs).
- Documentation must be updated when a change alters an approved behavior, interface, or architecture decision.

## NFR-008 — Testability and Verification

**Priority:** MVP

Important learning rules must be verifiable without depending on a live AI model or an external service.

### Requirements

- Planning, revision, progress, and evidence-evaluation rules must be testable with deterministic test data.
- Provider interfaces must support mock or fake implementations for automated tests.
- Critical data changes must have automated tests once their implementation begins.
- AI/RAG output quality must be evaluated separately from deterministic business-rule correctness.

## NFR-009 — Local Portability and Reproducibility

**Priority:** MVP

The project must be practical for the learner and future contributors to run on another local machine.

### Requirements

- The local runtime must be reproducible through documented Docker-based setup.
- Application configuration must be separated from source code.
- A new developer should be able to identify required software, environment variables, persistent data locations, and startup steps from project documentation.
- Ollama model availability may remain a host-machine prerequisite, but the application must clearly report when the configured model is unavailable.

## NFR-010 — Observability and Diagnostics

**Priority:** MVP

When the product fails, the learner and developer need enough information to recover without exposing sensitive content unnecessarily.

### Requirements

- Log application errors, integration failures, and major background operations with timestamps and correlation information where practical.
- Do not log full private note content, secrets, or unnecessary learner data.
- Provide understandable user-facing errors for failed uploads, failed indexing, unavailable models, and unsaved changes.
- Capture enough diagnostic information to investigate failures in planning, retrieval, and AI-provider calls.

## Future Quality Considerations

The following require formal targets when LearnFlow expands beyond a local single-user MVP:

- Multi-user data isolation and authorization.
- Accessibility conformance.
- Public-service availability and disaster recovery.
- Cloud-provider cost controls.
- Scalability and concurrent processing.
- Audit trails and deletion/export controls.

## Related Documents

- [Project context](../00-project-context.md)
- [Functional requirements](functional.md)
- [Product vision](../vision/vision.md)
- [Architecture overview](../architecture/overview.md)
- [Coding standards](../development/coding-standards.md)
- [Docker strategy](../deployment/docker.md)
