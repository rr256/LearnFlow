---
title: LearnFlow Domain Entities
status: approved
owner: product-and-architecture
last_updated: 2026-08-10
related:
  - ../00-project-context.md
  - domain-model.md
  - terminology.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
  - ../adr/ADR-017-topic-progress-api-and-schema.md
  - ../adr/ADR-018-weekly-availability-slots.md
  - ../adr/ADR-019-study-goal-planning-preferences.md
  - ../adr/ADR-020-initial-study-plan-generation.md
  - ../adr/ADR-021-plan-item-completion.md
  - ../adr/ADR-022-plan-adaptation.md
  - ../adr/ADR-024-plan-item-skipping.md
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

**Key relationships:** belongs to a learner; may reference an examination schedule; owns availability slots and the learner's planning preferences; drives study-plan generation.

A goal referencing an examination schedule holds a reference, not a copy of its dates, so a schedule the examining body revises reaches every goal at once. A goal aiming at neither an examination nor a target date is invalid.

The planning preferences are the goal's own attributes rather than a separate entity: a session length and a topic order, either of which may be unset. Both belong to the goal for the reason availability does — a learner who archives one goal and starts another may want to study differently.

### Availability Slot

Represents the study time available on one day of the week.

**Responsible for:** recording how many minutes the learner can give to study on that day.

**Key relationships:** belongs to exactly one study goal. A goal holds at most seven — one per day.

Availability belongs to the goal rather than to the learner: a learner who archives one goal and starts another is describing a different week. A slot is a quantity of time, not a sitting between two clock times, so nothing here records a time of day.

A day is identified by its name, never by an index, so no numbering convention exists to be read wrongly. Week order is presentation and is not stored.

A slot of zero minutes is a day the learner deliberately keeps free. A day with no slot is one they have not set — the same distinction learner topic progress draws between an explicit *Not explored* and a topic with no record.

Availability is a planning input. Nothing totals it, compares one week with another, or judges whether a week is enough; a study plan is where that reasoning belongs.

### Planning Preference

Represents a choice about how a study plan should be built. Not a separate entity: the preferences are attributes of the study goal that owns them.

**Responsible for:** recording how long one block of study should run, and which order a plan should work through the curriculum in.

**Key relationships:** belongs to exactly one study goal, beside its availability.

A preference the learner has not set is unset, and nothing supplies a default in its place — so a choice they made stays distinguishable from one the product would have guessed. A plan meeting an unset preference chooses for itself.

A session length is a quantity of minutes, not a time of day, for the same reason an availability slot is.

Like availability, a preference is a planning input. Nothing ranks two of them, scores one, or judges a choice.

### Study Plan

Represents a time-bounded set of recommendations toward a study goal.

**Responsible for:** organizing roadmap, monthly, weekly, or daily planned work and preserving plan state/history.

**Key relationships:** belongs to a learner and study goal; contains plan items.

A plan is derived from what the learner set up rather than entered by them, so a newer plan
*supersedes* an older one rather than conflicting with it, and the older one is kept: plan history is
what makes a change of direction explainable. A plan also records why it looks the way it does, in the
terms that were true when it was generated.

A roadmap and a weekly plan are generated today; monthly and daily plans remain part of the model. See
[ADR-020](../adr/ADR-020-initial-study-plan-generation.md).

### Plan Item

Represents one recommended action in a study plan.

**Responsible for:** recording the planned work, target time period, action type, status, and associated topic where applicable, together with the reason it is recommended.

**Key relationships:** belongs to a study plan; usually links to a topic and may result in a study activity or revision record.

An item's status records what became of the work it names: `planned` while it stands, `completed`
when the learner says the work happened, `skipped` when they say it will not, and `postponed` when
adaptation finds its day has passed with the work unsettled and re-places the topic on the plan that
replaces it. All four are written. The learner writes the first three, in any direction, and only
adaptation writes the fourth; the status set and its rules live in
[endpoints.md](../api/endpoints.md#pln-004-patch-apiv1plan-itemsplan_item_id) rather than here.
Skipping settles the **item**, not the topic — a skipped item's topic is planned again, where a
completed one's is not. An item's position within its plan is an order, not a ranking: nothing scores a topic, and a topic
later in a plan is not one the learner is worse at. Its reason is a statement about the plan's
reasoning rather than about the learner, and it is not rewritten, so a superseded plan still explains
itself.

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

The labels above are what a learner reads. [Terminology](terminology.md) is authoritative for them and for the `snake_case` form each is stored and sent as; do not restate the stored values here. A learner may move to any stage from any stage, including backwards — the order is a progression, not a ranking. See [ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md).

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
- [ADR-017: Record manual topic progress as a learner-owned stage](../adr/ADR-017-topic-progress-api-and-schema.md) — which part of the learner topic progress entity is persisted today
- [ADR-018: Store weekly availability as named days replaced a week at a time](../adr/ADR-018-weekly-availability-slots.md) — the availability slot entity, and why it holds minutes rather than clock times
- [ADR-019: Store planning preferences as typed columns replaced as a group](../adr/ADR-019-study-goal-planning-preferences.md) — the planning preferences the study goal owns, and why they are attributes rather than an entity
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](../adr/ADR-020-initial-study-plan-generation.md) — the study plan and plan item entities as they are persisted today
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](../adr/ADR-021-plan-item-completion.md) — the plan item whose completion state a learner now sets, reversibly
- [ADR-022: Adapt a study plan by rebuilding it around what happened](../adr/ADR-022-plan-adaptation.md) — the plan a learner has rebuilt around what happened, and the `postponed` state an item can reach
- [Domain model](domain-model.md)
- [Terminology](terminology.md)
- [Database schema](../database/schema.md)
- [Functional requirements](../requirements/functional.md)
