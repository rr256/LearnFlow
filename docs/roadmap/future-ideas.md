---
title: LearnFlow Deferred Ideas
status: approved
owner: product-and-architecture
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - roadmap.md
  - milestones.md
  - ../requirements/mvp.md
---

# LearnFlow Deferred Ideas

## Purpose

Preserve useful LearnFlow ideas without treating them as current commitments. An item in this document is not approved for implementation until it enters a roadmap milestone with requirements, design review, and any required ADRs.

## How to Use This Backlog

For every new idea, record:

- The learner problem it solves.
- Why it is not part of the current milestone.
- Existing design room that supports it, if any.
- The evidence or trigger needed to revisit it.

Do not start implementation from this document alone.

## Deferred Product Capabilities

| Idea | Why it is valuable | Why deferred | Revisit when |
| --- | --- | --- | --- |
| Multiple learner accounts | Lets friends use the platform with separate progress/resources. | MVP focuses on one local learner and avoids authentication complexity. | A second real learner needs independent data. |
| Secure login and roles | Enables shared/hosted usage and future administrator/curator roles. | Requires security, identity, privacy, and deployment decisions. | Multi-user requirement is approved. |
| Cloud synchronization | Lets learners access data across machines. | Requires storage, privacy, cost, backup, and account decisions. | Local workflow is useful and multi-device need is proven. |
| Azure Blob Storage | Managed file storage for a hosted product. | Local filesystem is sufficient for MVP. | Cloud/shared deployment is approved. |
| Optional cloud AI providers | Higher-quality reasoning for learners who choose it. | Ollama supports local-first and lower recurring cost initially. | Local model quality/capacity is insufficient for a validated use case. |
| Other GATE branches | Expands LearnFlow beyond GATE CSE. | First validate complete GATE CSE workflow and curated curriculum process. | GATE CSE is stable and another branch has verified curriculum/resources. |
| Syllabus-PDF setup wizard | Lets a learner create a draft program from a syllabus. | Extraction can be inaccurate; GATE CSE should be curated first. | Review/edit/approval workflow is designed and tested. |
| University/certification/interview programs | Broadens LearnFlow to general structured learning. | Requires validated domain/content patterns beyond GATE. | Generic curriculum model is proven with more than one real program. |
| Video transcription and indexing | Makes video lectures searchable. | Adds cost, processing, storage, and quality complexity. | PDF/RAG workflow is stable and video search is a real learner pain point. |
| OCR for scanned PDFs | Makes image-only notes searchable. | Extraction quality and local compute need validation. | Learners commonly use scanned notes and PDF extraction is insufficient. |
| Advanced mock analytics | Deeper time/question-pattern analytics and error trends. | MVP first needs reliable manual entry and basic evidence model. | Enough quiz/mock history exists to validate useful analysis. |
| Flashcards/spaced repetition UI | Supports quick review and retention. | Revision workflow must first prove useful. | Learner needs are clear after regular revision use. |
| Notifications/reminders | Helps learners act on plans and revisions. | Needs careful non-intrusive UX and local/hosted delivery choices. | Core plan/revision workflow is stable. |
| Mobile application | Convenient study access. | Web MVP and API contracts need validation first. | Real learners prefer mobile use and web workflows are stable. |
| Friend collaboration | Shared goals, accountability, or study groups. | Requires multi-user privacy, consent, and social-product design. | Individual workflow is proven and users request collaboration. |
| Community content sharing | Sharing curated notes/resources. | Requires copyright, moderation, ownership, and permissions model. | Clear legal/product policy and multi-user foundation exist. |
| Plugin ecosystem | Allows external education tools/content integrations. | Premature before core internal extension points are stable. | Provider/API architecture is mature and third-party use case is real. |

## Deferred Architecture and Operations Ideas

| Idea | Why deferred | Revisit when |
| --- | --- | --- |
| LangGraph or another agent framework | Custom orchestrator is simpler for current focused workflows. | Workflows need checkpoints, complex branching, long-running state, or human approval. |
| Redis/Celery/background queue | Simple application-managed asynchronous work is enough initially. | Ingestion/retry volume needs durable queues or workers. |
| Kubernetes | Docker Compose is sufficient for local development. | Hosted operations require scale/orchestration beyond managed services or Compose. |
| Managed vector database | ChromaDB is suitable for local RAG. | Scale, filtering, cloud hosting, or operational needs justify migration. |
| Public CI/CD deployment | Local-first MVP does not need hosted delivery. | Staging/production environment, security, backups, and release process are approved. |
| Advanced observability platform | Basic safe logs/health checks come first. | Hosted/multi-user operation needs centralized metrics/traces/alerts. |

## Explicitly Rejected for the MVP

These are not merely delayed; they conflict with the MVP direction unless the product vision changes:

- Scraping or logging into Testbook, Made Easy, or other test-series platforms.
- Requesting learners’ external-platform credentials.
- Presenting AI estimates as guaranteed ranks, marks, or exam outcomes.
- Treating one quiz score as proof of permanent mastery.
- Letting an autonomous AI silently change critical learner data.
- Turning LearnFlow into a generic social-media or unrestricted chatbot product.

## Idea Review Template

When promoting an idea from this backlog, create an entry with:

```text
Problem:
Evidence:
Target user:
Expected learning benefit:
Scope impact:
Privacy/cost/security impact:
Architecture/documents affected:
ADR required?:
Suggested milestone:
```

## Related Documents

- [Project context](../00-project-context.md)
- [Roadmap](roadmap.md)
- [Delivery milestones](milestones.md)
- [MVP scope](../requirements/mvp.md)
- [Architecture decision register](../architecture/decisions.md)
