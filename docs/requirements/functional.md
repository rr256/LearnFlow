---
title: LearnFlow Functional Requirements
status: approved
owner: product-and-architecture
last_updated: 2026-08-05
related:
  - ../00-project-context.md
  - mvp.md
  - ../vision/vision.md
  - ../domain/domain-model.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
---

# LearnFlow Functional Requirements

## Purpose

Define the learner-facing behavior of the first LearnFlow release. These requirements describe what the product must do; technical implementation choices belong in architecture and domain documents.

## Scope and Prioritization

- **MVP:** required for the first useful local GATE CSE mentor.
- **Future-ready:** not necessarily exposed in the first UI, but the implementation must not block it.
- **Out of scope:** explicitly not implemented in the MVP.

## FR-001 — Curated GATE CSE Learning Program

**Priority:** MVP

LearnFlow must provide one verified GATE CSE learning program containing its subjects, topics, and subtopics.

### Acceptance criteria

- The learner can browse the GATE CSE curriculum as a structured hierarchy.
- The application loads curriculum data from the backend/database; subjects and topics are not hardcoded in the frontend.
- Each topic has a stable identifier that can be linked to resources, progress, quizzes, revisions, and test results.
- The curriculum is the first supported program, not a permanent platform restriction.

### Future-ready boundary

The data model must support additional learning programs, including other GATE branches, without changing the core frontend or learning business rules. Syllabus-PDF extraction and learner-created programs are not MVP features.

## FR-002 — Initial Learner Setup

**Priority:** MVP

LearnFlow must allow a learner to create a study baseline before planning begins, and must show that
baseline back to them afterwards.

### Acceptance criteria

- The learner can set a target examination schedule or completion date.
- The learner can set available study time and basic planning preferences.
- The learner can confirm GATE CSE as the active learning program.
- The learner can review the setup they saved — their profile, their active learning program, and
  their study goal with the published dates of the examination it aims at — without re-entering it.
- The learner can start with no previous progress and still receive an initial plan.

A learner who cannot see what was stored cannot tell a saved setup from a lost one, and every date
shown back to them carries its source and whether it is still provisional, per
[ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md).

## FR-003 — Study Timeline and Plan

**Priority:** MVP

LearnFlow must transform the learner's goal, available time, curriculum, and progress into an actionable study timeline.

### Acceptance criteria

- The learner can view a long-term roadmap toward the target date.
- The learner can view monthly, weekly, and daily recommendations.
- Each planned item identifies the related topic and recommended action, such as study, practise, or revise.
- The learner can view why an item is recommended when practical.

## FR-004 — Plan Adaptation

**Priority:** MVP

LearnFlow must help the learner recover from missed work rather than requiring a completely manual re-plan.

### Acceptance criteria

- The learner can mark a planned task as completed, skipped, or postponed.
- When work is missed or availability changes, the learner can request an updated plan.
- The updated plan preserves target-date awareness and highlights meaningful trade-offs when time is insufficient.

## FR-005 — Topic Progress and Learning Evidence

**Priority:** MVP

LearnFlow must track progress as multiple signals, not as a single claim of mastery.

### Acceptance criteria

- The learner can mark a topic as `Not explored`, `Building foundation`, `Developing confidence`, `Practice-ready`, or `Strong understanding`.
- The learner can record that study material for a topic has been completed.
- The learner can update their current learning stage at any time.
- The product stores study activity, confidence/stage, quiz outcomes, test outcomes, mistakes, and revision history as separate evidence.
- The product does not claim permanent mastery from one quiz or one manual update.
- The interface presents an encouraging next action instead of negative or demotivating labels.

## FR-006 — Revision Guidance

**Priority:** MVP

LearnFlow must identify topics that should be revisited and guide the learner through revision.

### Acceptance criteria

- The learner can see topics due for revision.
- A revision recommendation links to a topic and, where available, relevant resource or practice suggestions.
- Completing or skipping a revision is recorded.
- Revision recommendations can consider completion, learning stage, quiz/test evidence, and prior revision history.

## FR-007 — Learning Resource Organization

**Priority:** MVP

LearnFlow must help a learner organize their owned study material against the GATE CSE curriculum.

### Acceptance criteria

- The learner can register PDFs, notes, PYQs, and references/paths to local video resources.
- A resource can be linked to one or more subjects, topics, or subtopics.
- LearnFlow records basic resource metadata, including title, type, source location, and linked curriculum areas.
- The learner can find resources associated with a topic.

## FR-008 — Grounded Mentor Assistance

**Priority:** MVP

LearnFlow must provide mentor assistance using the learner's relevant resources when available.

### Acceptance criteria

- The learner can ask a learning question for a topic.
- LearnFlow retrieves relevant indexed material before generating an answer when relevant material exists.
- The mentor can explain concepts, summarize material, answer doubts, and suggest next study actions.
- The mentor can indicate the resources used for a grounded answer where practical.
- The initial local AI provider is Ollama.
- A mentor response does not silently update learner progress; learner confirmation or explicit assessment evidence is required.

## FR-009 — Topic Checkpoint Practice

**Priority:** MVP

LearnFlow must allow a learner to test their understanding after studying a topic.

### Acceptance criteria

- The learner can request a short topic-focused checkpoint quiz covering one or more topics; every quiz covers at least one topic.
- The quiz can use relevant notes/PYQs as context when available.
- The learner can submit answers and receive basic feedback.
- Objective answers can be scored automatically.
- The product stores the attempt, answers, score, and identified mistakes.
- Quiz results inform learning-stage, practice, and revision recommendations but do not alone prove mastery.

## FR-010 — External Test Result Tracking

**Priority:** MVP

LearnFlow must allow learners to bring their own results from external test-series providers into their personal mentor profile.

### Acceptance criteria

- The learner can manually record a test source/name, test type, date, score, total marks, accuracy, and time taken when available.
- The learner can record correct, incorrect, and unattempted question counts when available.
- The learner can add subject-wise and topic-wise performance when their test report provides it.
- The learner can record mistake reasons such as concept gap, calculation error, careless error, or time-management issue.
- The learner may attach a screenshot or PDF as a private reference for the entered result.
- LearnFlow uses entered evidence to update recommendations and identify priority focus areas.
- LearnFlow does not scrape, sign in to, or directly integrate with Testbook, Made Easy, or other test-series websites in the MVP.

## FR-011 — Progress Overview

**Priority:** MVP

LearnFlow must give the learner a clear, non-judgmental overview of their study state.

### Acceptance criteria

- The learner can view progress by subject and topic.
- The learner can view upcoming study tasks and revisions due.
- The learner can view priority focus areas based on the available evidence.
- The learner can view recent quiz history and manually entered external test results.

## Out of Scope for This Document's MVP

- Public sign-up, login, friend accounts, and social sharing.
- Direct external test-series integrations, scraping, or credential collection.
- Automatic syllabus extraction from arbitrary PDFs.
- Automatic inference of topic-level knowledge from a total score without topic-level evidence.
- Public cloud deployment, mobile clients, payment systems, and community features.

## Traceability

Each implementation task, API contract, data-model change, and test should link back to one or more requirement IDs in this document.

## Related Documents

- [Product vision](../vision/vision.md)
- [MVP scope](mvp.md)
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — what a target examination schedule is, and why FR-002 does not ask for a single date
- [Domain model](../domain/domain-model.md)
- [API endpoints](../api/endpoints.md)
- [Roadmap](../roadmap/roadmap.md)
