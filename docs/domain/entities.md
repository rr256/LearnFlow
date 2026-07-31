---
title: LearnFlow Domain Entities
status: approved
owner: product-and-architecture
last_updated: 2026-08-01
related:
  - ../00-project-context.md
  - domain-model.md
  - terminology.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
  - ../database/schema.md
---

# LearnFlow Domain Entities

## Purpose

Catalog the meaningful product concepts used by LearnFlow. This document describes responsibilities and relationships, not database tables, API payloads, or implementation classes.

## Entity Catalog

### Learner

Represents a person pursuing one or more learning goals in LearnFlow.

**Responsible for:** owning personal preferences, goals, plans, progress, resources, assessment attempts, and externally entered test results.

**Key relationships:** has study goals, study plans, topic-progress records, study activities, quiz attempts, revision records, and external test results.

### Learning Program

Represents a structured learning journey, such as GATE CSE.

**Responsible for:** identifying the curriculum and grouping its subjects, topics, and program-level metadata.

**Key relationships:** has one or more curriculum versions and subjects.

### Curriculum Version

Represents a versioned definition of a learning program's syllabus.

**Responsible for:** preserving which curriculum structure was active when a learner planned and tracked study.

**Key relationships:** belongs to a learning program; contains subjects and topics through the curriculum hierarchy.

### Subject

Represents a major curriculum area, such as Operating Systems, DBMS, or Algorithms.

**Responsible for:** grouping related topics within a curriculum version.

**Key relationships:** belongs to a curriculum version; contains topics.

### Topic

Represents a teachable and trackable unit in a subject.

**Responsible for:** acting as the common anchor for planning, resources, progress, revision, questions, mistakes, and performance evidence.

**Key relationships:** belongs to a subject; may contain subtopics; may have topic relationships; links to resources, progress records, plan items, questions, and performance evidence.

### Topic Relationship

Represents a meaningful relationship between two topics, such as prerequisite, recommended-before, or related-topic.

**Responsible for:** helping the planner preserve sensible study order without hardcoding it in the frontend or planner logic.

**Key relationships:** connects one topic to another topic within a curriculum version.

### Learning Resource

Represents a learner-owned or curated study reference, such as a PDF, notes, PYQs, short notes, formula sheets, or a reference to a local video.

**Responsible for:** describing the resource, its source location, resource type, and curriculum links.

**Key relationships:** may link to multiple subjects, topics, or subtopics; may later be ingested into the knowledge base.

### Examination Schedule

Represents the dated calendar an examining body publishes for one cycle of a learning program, such as GATE 2027.

**Responsible for:** identifying the cycle, naming the body that published it and the source it was read from, recording when that source was read, and stating whether its dates are provisional or confirmed.

**Key relationships:** belongs to a learning program; contains examination periods; referenced by the study goals aiming at it.

It is reference data, like curriculum. It is curated from a named source rather than entered by a learner, and it is shared: two learners aiming at the same cycle read one schedule, not a copy each.

### Examination Period

Represents one dated span within an examination schedule.

**Responsible for:** recording the kind of period — registration, late registration, the examination, or the results announcement — and the days it covers.

**Key relationships:** belongs to exactly one examination schedule.

A cycle may hold several periods of the same kind: an examination sat over three weekends is three examination periods, not one range spanning the gaps. A single-day event starts and ends on the same day. The examination window a plan is built against is derived from the examination periods alone.

### Study Goal

Represents a learning target and planning constraints.

**Responsible for:** recording what the learner is working toward — a published examination cycle, a target completion date, or both — together with the active learning program and curriculum version, availability, and planning preferences.

**Key relationships:** belongs to a learner; may reference an examination schedule; drives study-plan generation.

A goal referencing an examination schedule holds a reference, not a copy of its dates, so a schedule the examining body revises reaches every goal at once. A goal aiming at neither an examination nor a target date is invalid.

### Study Plan

Represents a time-bounded set of recommendations toward a study goal.

**Responsible for:** organizing roadmap, monthly, weekly, or daily planned work and preserving plan state/history.

**Key relationships:** belongs to a learner and study goal; contains plan items.

### Plan Item

Represents one recommended action in a study plan.

**Responsible for:** recording the planned work, target time period, action type, status, and associated topic where applicable.

**Key relationships:** belongs to a study plan; usually links to a topic and may result in a study activity or revision record.

### Study Activity

Represents actual learner work performed at a particular time.

**Responsible for:** recording what was studied, practised, or revised, and optionally how much time was spent.

**Key relationships:** belongs to a learner; may link to a topic, plan item, resource, quiz attempt, or revision record.

### Learner Topic Progress

Represents the learner-specific evidence and current state for one topic.

**Responsible for:** combining material completion, current learning stage, study history, assessment evidence, mistakes, and revisions into a usable picture of progress.

**Key relationships:** belongs to one learner and one topic; is informed by activities, quiz attempts, topic performance evidence, mistakes, and revisions.

### Revision Record

Represents a revision recommendation and its outcome.

**Responsible for:** recording when a topic became due, was scheduled, was completed, skipped, or postponed.

**Key relationships:** belongs to a learner and topic; may link to a plan item, study activity, or assessment.

### Checkpoint Quiz

Represents a topic-focused practice set created or selected for learning evidence.

**Responsible for:** grouping questions and defining the purpose/context of a checkpoint assessment.

**Key relationships:** links to one or more topics and must link to at least one; contains assessment items; has learner quiz attempts.

### Question / Assessment Item

Represents one answerable item in a checkpoint quiz or a verified practice source.

**Responsible for:** storing the prompt, answer format, possible options where applicable, expected answer, explanation, source type, difficulty, and topic links.

**Key relationships:** belongs to a checkpoint quiz or reusable question bank; may link to multiple topics; receives learner answers through quiz attempts.

### Quiz Attempt

Represents one learner's attempt at a checkpoint quiz.

**Responsible for:** recording submitted answers, scoring, feedback, timing, and mistakes discovered during the attempt.

**Key relationships:** belongs to a learner and checkpoint quiz; contains answer-level results; informs topic progress and revision recommendations.

### Mistake Evidence

Represents a reusable record of a learning error or gap.

**Responsible for:** recording the mistake category, topic relevance, its single discovery source, and any follow-up action.

**Key relationships:** belongs to a learner; may link to a topic; has exactly one discovery source — a quiz-attempt answer, an external test result, a revision record, or a study activity.

### External Test Result

Represents a learner-entered outcome from a test completed outside LearnFlow, such as a Testbook, Made Easy, or other mock test.

**Responsible for:** recording provider/source label, test type, date, overall marks, accuracy, time, question counts, attached private reference, and learner-entered observations.

**Key relationships:** belongs to a learner; may have subject-level and topic-level performance evidence; may produce mistake evidence and updated recommendations.

### Topic Performance Evidence

Represents performance evidence for a particular topic from an external test result.

**Responsible for:** recording topic-level correct/incorrect/unattempted counts, marks, and mistake information when it is actually available.

**Key relationships:** belongs to exactly one external test result and one topic; informs learner topic progress.

Checkpoint quiz outcomes are not topic performance evidence. A quiz reaches topic progress through its quiz attempt and the topic links on the questions answered.

## Learner-Visible Learning Stages

These are domain values used to communicate progress constructively. They are not permanent mastery claims.

```text
Not explored
Building foundation
Developing confidence
Practice-ready
Strong understanding
```

Each stage should be paired with a useful next action, such as study concepts, practise questions, revise errors, or maintain through scheduled revision.

## Important Non-Entities

The following are important, but are not domain entities in this document:

- **PDF chunks, embeddings, and vector records:** RAG/infrastructure implementation details.
- **AI provider, storage provider, and vector provider:** architecture interfaces/adapters.
- **Dashboard priority focus:** a calculated learner-facing view derived from evidence, not necessarily stored as its own entity.
- **Authentication credentials and roles:** future identity/security concerns; not part of the local single-learner MVP domain behavior.

## Relationship Summary

```text
Learner
 ├── Study Goal ── Examination Schedule (optional)
 ├── Study Goal ── Study Plan ── Plan Item
 ├── Study Activity
 ├── Learner Topic Progress ── Topic
 ├── Revision Record ── Topic
 ├── Quiz Attempt ── Checkpoint Quiz ── Question
 └── External Test Result ── Topic Performance Evidence ── Topic

Checkpoint Quiz ── Topic (one or more)

Learning Program ── Curriculum Version ── Subject ── Topic
Learning Program ── Examination Schedule ── Examination Period
Topic ── Topic Relationship ── Topic
Topic ── Learning Resource
```

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-008: Model assessment topics and mistake evidence sources explicitly](../adr/ADR-008-assessment-and-mistake-evidence-model.md) — quiz-topic cardinality, mistake sources, and evidence boundaries
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — the examination schedule and period entities
- [Domain model](domain-model.md)
- [Terminology](terminology.md)
- [Database schema](../database/schema.md)
- [Functional requirements](../requirements/functional.md)
