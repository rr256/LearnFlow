---
title: LearnFlow Domain Model
status: approved
owner: product-and-architecture
last_updated: 2026-08-22
related:
  - ../00-project-context.md
  - entities.md
  - terminology.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
  - ../adr/ADR-037-learner-written-resource-notes.md
  - ../adr/ADR-039-source-grounded-study-answers.md
  - ../adr/ADR-038-local-topic-note-retrieval.md
  - ../adr/ADR-017-topic-progress-api-and-schema.md
  - ../adr/ADR-018-weekly-availability-slots.md
  - ../adr/ADR-019-study-goal-planning-preferences.md
  - ../adr/ADR-020-initial-study-plan-generation.md
  - ../adr/ADR-021-plan-item-completion.md
  - ../adr/ADR-022-plan-adaptation.md
  - ../adr/ADR-024-plan-item-skipping.md
  - ../adr/ADR-025-learner-postponement.md
  - ../adr/ADR-026-monthly-study-view.md
  - ../adr/ADR-027-plan-feasibility.md
  - ../adr/ADR-028-revision-workflow.md
  - ../requirements/functional.md
  - ../database/schema.md
  - ../adr/ADR-032-learning-resource-catalogue.md
  - ../adr/ADR-033-checkpoint-practice-workflow.md
  - ../adr/ADR-035-practice-question-correction.md
  - ../adr/ADR-040-learner-uploaded-resource-files.md
  - ../adr/ADR-041-removing-a-stored-file-or-note.md
  - ../adr/ADR-042-removing-a-whole-resource.md
---

# LearnFlow Domain Model

## Purpose

Define the core learning concepts and relationships used by LearnFlow before designing database tables, APIs, or frontend screens.

The model is intentionally generic. GATE CSE is the first curated learning program, but the platform core must also support future learning programs without becoming GATE-specific.

## Domain Overview

```text
Learning Program
  ├── Examination Schedule
  │    └── Examination Period
  └── Subject
       └── Topic / Subtopic
            ├── Learning Resource
            │    └── Resource Note
            ├── Learner Topic Progress
            ├── Revision Record
            ├── Checkpoint Quiz and Quiz Attempts
            └── Topic Performance Evidence

Learner
  ├── Study Goal and Availability
  ├── Study Plan
  │    └── Plan Items
  ├── Topic Progress
  ├── Quiz Attempts
  ├── External Test Result
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

Topics are the shared anchor for planning, resources, quizzes, revision, learner progress, and topic performance evidence. Each topic must have a stable identifier.

### Learning Resource

A learner-owned or curated reference used for study. Examples include PDF notes, PYQs, short notes, formula sheets, and references to local video resources.

A resource can be linked to one or more subjects, topics, or subtopics. Resource content is distinct from the curriculum structure and from learner progress.

**Only topic and subtopic links are stored today** — the two are the same record — and a resource records **where the material is** rather than the material itself. Subject-level linking stays a model target with no table behind it. The one exception is a **resource note**, defined below. See [entities](entities.md#learning-resource) and [ADR-032](../adr/ADR-032-learning-resource-catalogue.md).

### Resource Note

Text the learner typed or pasted themselves, kept against one learning resource: their own notes on a piece of study material, or a passage they transcribed from it.

It belongs to exactly one resource and **inherits the topics that resource covers**, carrying none of its own, so correcting what a resource covers moves its notes with it and the two can never disagree.

This was the **first place the model holds study material rather than a pointer to it** — an uploaded PDF, kept as a *stored file* since [ADR-040](../adr/ADR-040-learner-uploaded-resource-files.md), is the second. For a note the boundary is narrow: the learner types or pastes, and nothing uploads it, fetches an address, extracts text from a document, chunks, embeds, or indexes it into a vector store. Two things read it, both locally and both only when the learner asks: the *topic note search*, a PostgreSQL full-text search, and a locally running AI model, which MNT-001 gives the passages that search selected and never a whole note. Neither stores anything derived from a note. Chunks, embeddings, and vector records remain [non-entities](entities.md#important-non-entities) — derived data belonging in a vector index, rebuildable from the note. A note is corrected in place, and no status change deletes it; it **may be removed permanently** by RES-019, a separate deliberate request and one of only three destructive capabilities in the product, beside RES-018 and RES-005 — the last of which removes a resource's notes along with the material they belong to. *Put aside* stays the reversible answer, and because nothing derived from a note is stored, removing one leaves nothing orphaned — the same fact that keeps it correctable in place. See [entities](entities.md#resource-note), [ADR-037](../adr/ADR-037-learner-written-resource-notes.md), [ADR-038](../adr/ADR-038-local-topic-note-retrieval.md), [ADR-039](../adr/ADR-039-source-grounded-study-answers.md), and [ADR-041](../adr/ADR-041-removing-a-stored-file-or-note.md).

### Examination Schedule

The dated calendar an examining body publishes for one cycle of a learning program, such as GATE 2027.

It is reference data, not learner data: it describes the world, carries a named source and the date that source was read, and every learner aiming at that cycle reads the same dates. A schedule is `provisional` while its source says the dates are liable to change, and `confirmed` only once the examining body confirms them.

### Examination Period

One dated span within a schedule: registration, late registration, the examination itself, or the results announcement. A period that occupies a single day starts and ends on the same day.

The examination is always modelled as one or more periods, never as a single date. An examining body commonly publishes a range of sitting days and announces the specific paper's day much later, so a single stored date would be a guess. The **examination window** — the first published sitting day to the last — is derived from the examination periods, excluding the deadlines that bracket them.

### Study Goal

The learner's target outcome and timeline, including what they are working toward and planned study availability.

A goal aims at a published examination cycle, at a target completion date, or at both — never at neither, because a plan needs a horizon. A goal that names an examination cycle *refers* to its schedule rather than copying its dates, so a correction the examining body publishes reaches the goal without rewriting it.

The goal provides the constraint used to create and adapt study plans. It also owns the learner's
planning preferences and their weekly availability, both described below.

### Availability Slot

How much study time one day of the week holds, for one study goal.

A goal has at most seven — one per day — and the set of them is the learner's **weekly availability**. It is saved a week at a time: the days named become the week, and a day left out is removed.

A day is identified by name rather than by an index, so no numbering convention exists to be read wrongly. A slot records a quantity of minutes, not a sitting between two clock times; nothing in the model has a time of day. Zero minutes is a day deliberately kept free, which is a different statement from a day with no slot at all.

Availability is a planning input and nothing more. Nothing ranks one day above another. Totalling a week and judging whether it is enough belong to the planner, which is where the trade-offs can be shown: since [ADR-027](../adr/ADR-027-plan-feasibility.md) a domain rule does exactly that, reporting whether the saved week covers the work left before the goal's horizon. Nothing else adds a week up.

### Planning Preference

A choice the learner has made about *how* a study plan should be built, for one study goal.

Where availability says how much time a week holds, a planning preference says what a plan should do with it: how long one block of study should run, and which order the plan should work through the curriculum in.

A preference the learner has not set is **unset**, not a default. Nothing invents one on their behalf, so a preference they chose stays distinguishable from one the product would have guessed — the same distinction an explicit *Not explored* draws against a topic with no record, and a day kept free draws against a day never set. A plan meeting an unset preference chooses for itself, visibly.

Preferences belong to the goal rather than to the learner, as availability does: a learner who archives one goal and starts another may want to study differently. Like availability, a preference is a planning input and nothing more — nothing ranks two preferences, scores one, or judges a choice. See [ADR-019](../adr/ADR-019-study-goal-planning-preferences.md).

### Study Plan

A time-bounded plan that translates the learner's goal, availability, curriculum, progress, and revision needs into recommended work.

Plans may exist at roadmap, monthly, weekly, and daily levels. A plan contains ordered plan items.

A plan is **derived**, which is what distinguishes it from everything else a learner owns: the goal,
the week, the preferences, and the stages are all statements a learner made, and a plan is what
LearnFlow makes of them. That has two consequences. Generating again replaces rather than conflicts —
the plan it supersedes is kept as history, not defended as the learner's answer — and a plan must be
able to say what it was derived from, because a learner cannot check a conclusion whose reasoning is
hidden.

A plan is generated by deterministic rules, not by an AI provider. The same inputs produce the same
plan, so it can be replayed and explained rather than merely trusted; an AI provider may later phrase
an explanation, but the plan must remain usable without one.

Roadmap and weekly plans are generated today; monthly and daily plans remain part of the model. See
[ADR-020](../adr/ADR-020-initial-study-plan-generation.md).

A learner can nonetheless **read** their plan at a daily and a monthly level, because both screens
select from the two plans that are generated rather than generating a third. A *daily study view*
([ADR-023](../adr/ADR-023-daily-study-view.md)) filters the weekly plan to one date, and a *monthly
study view* ([ADR-026](../adr/ADR-026-monthly-study-view.md)) groups it and the roadmap to one
calendar month. Neither is a plan: no `monthly` or `daily` record is written, and what each of those
plan types would *contain* is still undecided.

### Plan Item

A single recommended action in a study plan, such as studying a topic, practising questions, revising a topic, or reviewing mistakes.

A plan item links to a learner, a planned time period, an action type, and usually a topic. Its completion state is separate from the learner's long-term topic progress.

An item carries its own **reason**: why this work, here, in the terms that were true when the plan was
generated. It is a statement about the plan's reasoning rather than about the learner, and it is not
rewritten afterwards, so a superseded plan still explains itself.

An item's position in its plan is an **order, not a ranking**. Nothing scores a topic, and a topic
later in a plan is not one the learner is worse at.

### Learner Topic Progress

The learner-specific record of engagement and understanding for one topic.

Topic progress is evidence-based rather than a single permanent mastery score. It brings together:

- Material-completion state.
- Current learner-visible learning stage.
- Study activity.
- Checkpoint-quiz outcomes.
- Topic performance evidence from external test results.
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

The labels above are what a learner reads. [Terminology](terminology.md) is authoritative for them and for the `snake_case` form each is stored and sent as; do not restate the stored values here. A stage a learner sets themselves is distinguished from one derived from evidence, which is what makes rule 5 below enforceable. See [ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md).

### Revision Record

A record that a topic was recommended for revision, scheduled, completed, skipped, or postponed.

Revision records preserve the history needed to make future revision recommendations. They can be linked to a plan item, resource, quiz, or mistake-review activity.

A revision is created **only when the learner asks**, from a topic they have completed planned
work on, and comes back an interval later that the learning stage they recorded decides. It is **not**
a plan item and never becomes one: adaptation supersedes every active plan of a goal, and a review the
learner has acted on must survive that. Completing a review records that **the review happened** and
writes no learning stage, which is the same principle rule 4 states for a plan item. See
[ADR-028](../adr/ADR-028-revision-workflow.md).

### Checkpoint Quiz

A topic-focused practice set used to gather learning evidence after study or revision. Questions may be generated with grounded context or drawn from verified sources when available.

A checkpoint quiz covers one or more topics and must cover at least one. The interface may begin with single-topic quizzes, but the model supports a checkpoint spanning several related topics.

**As built, the learner writes every question and the quiz asks all of them.** A quiz is assembled deterministically, with no AI provider, from the learner's own `ready` questions for the topics they chose, in the order those questions were written: LearnFlow selects none and leaves none out, because choosing which few to ask is a ranking. Generated and verified-source questions remain in the model and wait on the capabilities that would produce them. See [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md).

### Quiz Attempt

The learner's response to a checkpoint quiz. It records answers, feedback, and topic links. Quiz attempts influence recommendations but do not independently prove mastery.

**As built, an attempt records no score and no mistakes.** A result states what became of each question — correct, not correct, or *unanswered* — with the expected answer and the explanation, and states no total, mark, or percentage: a figure like "3 of 5" measures the learner rather than the work, which [terminology](terminology.md) forbids. An **unanswered question is not a wrong one**, which is why the three outcomes are kept apart rather than collapsed. Mistake evidence waits on the external-evidence tables two of its four discovery sources reference. See [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md).

**A question is never edited once a quiz has asked it**, only retired and rewritten: an answer references its question by identifier, so rewriting a prompt would silently rewrite a result the learner has already read. A question no quiz holds has no answer referencing it and no history to rewrite, so it may be corrected in place — the same record, with its content replaced as a whole. A question already retired is read-only until it is brought back. See [ADR-035](../adr/ADR-035-practice-question-correction.md), which amends [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md) on this point.

A quiz attempt informs learner topic progress through its answers and the topic links on the questions answered. Quiz outcomes are not topic performance evidence, which records only what a learner transcribed from an external test report.

### External Test Result

A learner-entered record of an assessment completed on an external test-series platform or elsewhere.

It may include the source/name, type, date, marks, accuracy, time, correct/incorrect/unattempted counts, subject/topic results, mistake reasons, and an optional private screenshot or PDF reference.

LearnFlow does not require access to an external test-series platform. It uses the learner's manually entered evidence in the context of their own study plan.

### Mistake Evidence

A reusable record of an error or learning gap. Initial mistake categories include concept gap, calculation error, careless error, and time-management issue.

Every mistake has exactly one discovery source — a quiz-attempt answer, an external test result, a revision record, or a study activity. Recording exactly one source keeps the origin of each mistake traceable and prevents the same error being counted twice from different directions.

Mistake evidence may be attached to a topic and used to recommend focused study, practice, or revision.

## Key Relationships

```text
Learning Program 1 ── * Subject
Subject 1 ── * Topic
Topic 1 ── * Subtopic (optional hierarchy)

Learning Program 1 ── * Examination Schedule (one per cycle)
Examination Schedule 1 ── * Examination Period
Study Goal * ── 0..1 Examination Schedule

Learner 1 ── * Study Goal
Learner 1 ── * Study Plan
Study Plan 1 ── * Plan Item

Learner 1 ── * Learner Topic Progress
Topic 1 ── * Learner Topic Progress

Topic * ── * Learning Resource
Learning Resource 1 ── * Resource Note
Topic 1 ── * Revision Record
Checkpoint Quiz * ── * Topic (at least one topic per quiz)
Checkpoint Quiz 1 ── * Quiz Attempt
Learner 1 ── * Quiz Attempt

Learner 1 ── * External Test Result
External Test Result 1 ── * Topic Performance Evidence
Topic 1 ── * Topic Performance Evidence
```

## Domain Rules and Invariants

1. A learner's progress belongs to both one learner and one topic.
2. A topic belongs to one learning-program curriculum hierarchy, even when resources link to it from multiple places.
3. Curriculum structure, learning resources, and learner progress are separate concerns.
4. A plan item records whether planned work happened; it does not automatically mean the topic is mastered or completed.
5. AI-generated content or advice must not silently change learner progress, learning stage, or assessment evidence.
6. Topic-level performance can be updated only from evidence that is actually linked to that topic. A total test score alone cannot reliably create topic-level conclusions.
7. Topic performance evidence comes only from an external test result. Checkpoint quiz outcomes reach topic progress through quiz attempts and question topic links, not through topic performance evidence.
8. A mistake record has exactly one discovery source: a quiz-attempt answer, an external test result, a revision record, or a study activity.
9. A checkpoint quiz covers at least one topic.
10. An external test result is learner-entered private data; LearnFlow does not rely on provider integration or scraping.
11. The GATE CSE curriculum is curated and verified. Future AI-extracted syllabus structures must remain draft until reviewed and approved by a learner or authorized curator.
12. A learning stage should lead to a supportive next action, not a negative label or irreversible judgement.
13. A study goal aims at an examination cycle, a target date, or both. A goal aiming at neither has no horizon to plan against.
14. An examination period is a span of days. LearnFlow never records a single examination date that the examining body has not published, and never presents a provisional date without saying it may change.

## Future-Ready Boundaries

- Additional learning programs are new curriculum data, not a separate application codebase.
- Syllabus-PDF extraction can propose a draft learning program later; it is not an MVP feature.
- Multi-user support adds authentication and authorization around existing learner-owned records.
- Additional AI, storage, embedding, and vector providers must not change the core domain concepts.
- Advanced mock analytics can build on quiz attempts, external test results, mistake evidence, and topic links.

## Not Defined Here

This document intentionally does not define database fields, table names, API endpoints, frontend components, scheduling algorithms, or provider implementation details. Those belong in the database, API, architecture, and development documents.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-008: Model assessment topics and mistake evidence sources explicitly](../adr/ADR-008-assessment-and-mistake-evidence-model.md) — quiz-topic cardinality, mistake sources, and evidence boundaries
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — the examination schedule concept and what a study goal aims at
- [ADR-017: Record manual topic progress as a learner-owned stage](../adr/ADR-017-topic-progress-api-and-schema.md) — which part of learner topic progress is persisted today, and how a learner-set stage is told from a derived one
- [ADR-018: Store weekly availability as named days replaced a week at a time](../adr/ADR-018-weekly-availability-slots.md) — the availability slot concept, and why nothing totals a week
- [ADR-019: Store planning preferences as typed columns replaced as a group](../adr/ADR-019-study-goal-planning-preferences.md) — the planning preference concept, and why an unset preference is not a default
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](../adr/ADR-020-initial-study-plan-generation.md) — what a generated plan contains today, and why it is deterministic and self-explaining
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](../adr/ADR-021-plan-item-completion.md) — the first code to write a plan item's status, and why it writes no learning stage with it
- [ADR-022: Adapt a study plan by rebuilding it around what happened](../adr/ADR-022-plan-adaptation.md) — the adaptation that rebuilds a plan around completed and missed work, without writing a learning stage
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](../adr/ADR-023-daily-study-view.md) — the daily reading of the weekly plan, which is not the `daily` plan level above
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](../adr/ADR-026-monthly-study-view.md) — the monthly reading, which is not the `monthly` plan level above
- [ADR-027: Report whether the saved week reaches the horizon, as a read-only planning rule](../adr/ADR-027-plan-feasibility.md) — the one place a week is totalled, and the judgement this section defers to the planner
- [Functional requirements](../requirements/functional.md)
- [Domain entities](entities.md)
- [Terminology](terminology.md)
- [Database schema](../database/schema.md)
- [Architecture overview](../architecture/overview.md)
- [ADR-028: Schedule revisions from finished work, on the learner's ask](../adr/ADR-028-revision-workflow.md) — the revision record, and why completing a review writes no learning stage
