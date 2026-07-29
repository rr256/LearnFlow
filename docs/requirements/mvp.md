---
title: LearnFlow MVP Scope
status: approved
owner: product-and-architecture
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - functional.md
  - ../vision/vision.md
  - ../roadmap/milestones.md
---

# LearnFlow MVP Scope

## Purpose

Define the smallest useful LearnFlow release: a personal AI learning mentor that can guide GATE CSE preparation through planning, progress tracking, resource-grounded help, and revision.

The MVP must be useful for daily study. It must also preserve clear extension points for future users, providers, storage systems, and learning programs without implementing those features prematurely.

## MVP User and Learning Program

- **Initial user:** one learner using LearnFlow locally.
- **Initial learning program:** GATE Computer Science.
- **Initial AI runtime:** local Ollama.
- **Initial resources:** learner-owned digital PDFs, notes, PYQs, and references to local video resources.

## Build Now

### Learner profile and goal

- Capture the learner's target examination date or target completion date.
- Capture available study time and basic study preferences.
- Support a GATE CSE learning program with subjects and topics.

### Planning and timeline

- Create a long-term study roadmap toward the target date.
- Produce monthly, weekly, and daily study recommendations.
- Reschedule unfinished work when the learner misses planned study tasks or changes availability.
- Show the learner what to study next and why it is recommended.

### Progress and revision

- Mark topics as not started, in progress, or completed.
- Record topic confidence, study activity, and basic mistakes or learning notes.
- Show progress by subject and across the learning program.
- Schedule and display topics due for revision.
- Identify basic priority focus areas from completion state, confidence, and assessment outcomes.

### Learning resources and grounded AI help

- Register and organize local PDFs, notes, PYQs, and video references by subject and topic.
- Ingest supported text-based documents into a local knowledge base.
- Retrieve relevant material before answering a learner question whenever applicable.
- Use Ollama to explain concepts, answer doubts, summarize relevant material, and generate practice questions.
- Present the source resource information used for a grounded answer where practical.

### Practice and feedback

- Generate topic-focused practice questions.
- Record answers and basic correctness/feedback.
- Manually record results from tests taken outside LearnFlow, including subject-wise and topic-wise detail when the learner's report provides it.
- Use outcomes to update progress signals and future revision recommendations.

### Foundation and local operation

- Run the application locally with a reproducible Docker-based development setup.
- Store structured learner data in PostgreSQL.
- Keep uploaded/local resource files separate from structured database data.
- Keep external integrations behind clear interfaces where replacement is expected.

## Postpone, but Prepare For

The following are future features. They are intentionally not part of the MVP, but the MVP design must not prevent them.

| Future capability | Design room created in the MVP |
| --- | --- |
| Multiple learner accounts | Associate learner-owned data with a `learner_id` from the start, even while only one local learner exists. |
| Authentication and roles | Keep identity and authorization boundaries separate from learning business rules. |
| Cloud storage, including Azure Blob Storage | Access files through a storage-provider interface; start with a local storage adapter. |
| Cloud AI providers | Access language models through an AI-provider interface; start with an Ollama adapter. |
| Alternative vector databases and embedding models | Hide vector search and embeddings behind provider/service interfaces. |
| Advanced mock-test analytics | Store attempts, answers, scores, mistakes, timing, and topic links in reusable data structures. |
| Mobile or desktop clients | Keep learning business logic in the backend and expose stable API contracts. |
| More learning programs | Model generic learning programs, subjects, topics, resources, and assessments rather than hard-coding GATE-specific concepts into the platform core. |
| Complex agent orchestration or an agent framework | Keep mentor, planner, quiz, revision, and progress responsibilities modular; begin with a predictable custom orchestrator. |
| Public cloud deployment | Use containers and environment-based configuration now; postpone public hosting, managed cloud services, and scaling infrastructure. |
| Friend collaboration or community features | Keep user data ownership clear; defer social and sharing workflows. |

## Explicitly Not in the MVP

- Public multi-user registration and login flows.
- Social feeds, chat communities, rankings, or public profiles.
- Mobile applications.
- Public cloud hosting, billing, subscriptions, or payment processing.
- Advanced prediction claims, such as guaranteed ranks or exam outcomes.
- Autonomous agents that make important learning changes without learner visibility or control.
- Broad support for every exam or course before the GATE CSE workflow is useful and stable.

## MVP Completion Criteria

The MVP is complete when one learner can:

1. Set a GATE CSE goal, target date, and available study time.
2. See a realistic roadmap and monthly, weekly, and daily study guidance.
3. Track topic completion, confidence, and revision needs.
4. Add and search relevant local study material.
5. Ask the mentor a question and receive a grounded, useful response from Ollama.
6. Practise topic-focused questions and retain basic feedback.
7. Manually record an external test result and see it inform recommendations.
8. Continue using the system locally through a reproducible setup.

## Change Control

Any proposed feature that is not listed in **Build Now** must be placed in the roadmap or deferred-ideas document before it is implemented. A future feature can enter the MVP only when its value, cost, and effect on the current milestone have been reviewed.

## Related Documents

- [Project context](../00-project-context.md)
- [Product vision](../vision/vision.md)
- [Functional requirements](functional.md)
- [Technology stack](../development/tech-stack.md)
- [Roadmap](../roadmap/roadmap.md)
- [Deferred ideas](../roadmap/future-ideas.md)
