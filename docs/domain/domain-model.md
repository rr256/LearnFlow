---
title: LearnFlow Domain Model
status: approved
owner: product-and-architecture
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - entities.md
  - terminology.md
  - ../requirements/functional.md
  - ../database/schema.md
---

# LearnFlow Domain Model

## Purpose

Define the core learning concepts and relationships used by LearnFlow before designing database tables, APIs, or frontend screens.

The model is intentionally generic. GATE CSE is the first curated learning program, but the platform core must also support future learning programs without becoming GATE-specific.

## Domain Overview

```text
Learning Program
  └── Subject
       └── Topic / Subtopic
            ├── Learning Resource
            ├── Learner Topic Progress
            ├── Revision Record
            ├── Checkpoint Quiz and Quiz Attempts
            └── External Test Performance Evidence

Learner
  ├── Study Goal and Availability
  ├── Study Plan
  │    └── Plan Items
  ├── Topic Progress
  ├── Quiz Attempts
  ├── External Test Performance
  └── Revision Records
```

## Core Concepts

### Learner

A person using LearnFlow to pursue a learning goal.

The MVP has one local learner, but all learner-owned progress, plans, resources, assessments, and preferences must be associated with a learner identity from the beginning. This preserves a future path to multiple accounts without changing the core model.

### Learning Program

A structured curriculum or learning journey, such as GATE CSE.

A learning program has a versioned curriculum structure and can contain subjects, topics, subtopics, suggested priorities, and program-level metadata. The first supported program is a verified GATE CSE curriculum.

### Subject

A major curriculum area within a learning program, such as Operating Systems, DBMS, or Algorithms.

### Topic and Subtopic

A teachable and trackable curriculum unit. A topic may contain nested subtopics when the syllabus needs finer granularity.

Topics are the shared anchor for planning, resources, quizzes, revision, learner progress, and test-performance evidence. Each topic must have a stable identifier.

### Learning Resource

A learner-owned or curated reference used for study. Examples include PDF notes, PYQs, short notes, formula sheets, and references to local video resources.

A resource can be linked to one or more subjects, topics, or subtopics. Resource content is distinct from the curriculum structure and from learner progress.

### Study Goal

The learner's target outcome and timeline, including a target examination/completion date and planned study availability.

The goal provides the constraint used to create and adapt study plans.

### Study Plan

A time-bounded plan that translates the learner's goal, availability, curriculum, progress, and revision needs into recommended work.

Plans may exist at roadmap, monthly, weekly, and daily levels. A plan contains ordered plan items.

### Plan Item

A single recommended action in a study plan, such as studying a topic, practising questions, revising a topic, or reviewing mistakes.

A plan item links to a learner, a planned time period, an action type, and usually a topic. Its completion state is separate from the learner's long-term topic progress.

### Learner Topic Progress

The learner-specific record of engagement and understanding for one topic.

Topic progress is evidence-based rather than a single permanent mastery score. It brings together:

- Material-completion state.
- Current learner-visible learning stage.
- Study activity.
- Checkpoint-quiz outcomes.
- External test-performance evidence.
- Mistakes and learning notes.
- Revision history.

The learner-visible stages are:

```text
Not explored
Building foundation
Developing confidence
Practice-ready
Strong understanding
```

These stages guide the next action. They must not be presented as a permanent or guaranteed claim of mastery.

### Revision Record

A record that a topic was recommended for revision, scheduled, completed, skipped, or postponed.

Revision records preserve the history needed to make future revision recommendations. They can be linked to a plan item, resource, quiz, or mistake-review activity.

### Checkpoint Quiz

A topic-focused practice set used to gather learning evidence after study or revision. Questions may be generated with grounded context or drawn from verified sources when available.

### Quiz Attempt

The learner's response to a checkpoint quiz. It records answers, score, feedback, mistakes, and topic links. Quiz attempts influence recommendations but do not independently prove mastery.

### External Test Performance

A learner-entered record of an assessment completed on an external test-series platform or elsewhere.

It may include the source/name, type, date, marks, accuracy, time, correct/incorrect/unattempted counts, subject/topic results, mistake reasons, and an optional private screenshot or PDF reference.

LearnFlow does not require access to an external test-series platform. It uses the learner's manually entered evidence in the context of their own study plan.

### Mistake Evidence

A reusable record of an error or learning gap discovered through a quiz, revision, or external test result. Initial mistake categories include concept gap, calculation error, careless error, and time-management issue.

Mistake evidence may be attached to a topic and used to recommend focused study, practice, or revision.

## Key Relationships

```text
Learning Program 1 ── * Subject
Subject 1 ── * Topic
Topic 1 ── * Subtopic (optional hierarchy)

Learner 1 ── * Study Goal
Learner 1 ── * Study Plan
Study Plan 1 ── * Plan Item

Learner 1 ── * Learner Topic Progress
Topic 1 ── * Learner Topic Progress

Topic * ── * Learning Resource
Topic 1 ── * Revision Record
Topic 1 ── * Checkpoint Quiz
Checkpoint Quiz 1 ── * Quiz Attempt
Learner 1 ── * Quiz Attempt

Learner 1 ── * External Test Performance
External Test Performance * ── * Topic Performance Evidence
```

## Domain Rules and Invariants

1. A learner's progress belongs to both one learner and one topic.
2. A topic belongs to one learning-program curriculum hierarchy, even when resources link to it from multiple places.
3. Curriculum structure, learning resources, and learner progress are separate concerns.
4. A plan item records whether planned work happened; it does not automatically mean the topic is mastered or completed.
5. AI-generated content or advice must not silently change learner progress, learning stage, or assessment evidence.
6. Topic-level performance can be updated only from evidence that is actually linked to that topic. A total test score alone cannot reliably create topic-level conclusions.
7. External test performance is learner-entered private data; LearnFlow does not rely on provider integration or scraping.
8. The GATE CSE curriculum is curated and verified. Future AI-extracted syllabus structures must remain draft until reviewed and approved by a learner or authorized curator.
9. A learning stage should lead to a supportive next action, not a negative label or irreversible judgement.

## Future-Ready Boundaries

- Additional learning programs are new curriculum data, not a separate application codebase.
- Syllabus-PDF extraction can propose a draft learning program later; it is not an MVP feature.
- Multi-user support adds authentication and authorization around existing learner-owned records.
- Additional AI, storage, embedding, and vector providers must not change the core domain concepts.
- Advanced mock analytics can build on quiz attempts, external test performance, mistake evidence, and topic links.

## Not Defined Here

This document intentionally does not define database fields, table names, API endpoints, frontend components, scheduling algorithms, or provider implementation details. Those belong in the database, API, architecture, and development documents.

## Related Documents

- [Project context](../00-project-context.md)
- [Functional requirements](../requirements/functional.md)
- [Domain entities](entities.md)
- [Terminology](terminology.md)
- [Database schema](../database/schema.md)
- [Architecture overview](../architecture/overview.md)
