---
title: "ADR-008: Model Assessment Topics and Mistake Evidence Sources Explicitly"
status: accepted
owner: product-and-architecture
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../database/schema.md
---

# ADR-008: Model Assessment Topics and Mistake Evidence Sources Explicitly

## Status

Accepted — 2026-07-29

## Context

Three related modelling questions were left ambiguous across the domain, entity, and schema documents, and the documents had drifted apart as a result.

1. **Where mistakes come from.** The domain documents described a mistake as something discovered through a quiz, a revision, or an external test result, and the entity catalog also allowed a study activity. The schema permitted only two sources and required at least one of them, so a mistake noticed during revision or ordinary study could not be stored.
2. **How many topics a checkpoint quiz covers.** The domain model stated one topic per quiz; the entity catalog stated one or more. The schema persisted no direct quiz-to-topic link at all, reachable only indirectly through question topic links, so neither reading was enforceable.
3. **What counts as topic performance evidence.** The entity catalog described topic performance evidence as coming from "an external test result or assessment", which invited checkpoint-quiz outcomes into a structure the schema binds to an external test result.

These are durable data-model decisions. Getting them wrong is costly to reverse once migrations and learner data exist, and they affect the domain layer, the schema, the assessment API, and progress interpretation.

## Decision

### Mistake evidence has exactly one discovery source

A mistake record is discovered through exactly one of four sources:

```text
quiz-attempt answer
external test result
revision record
study activity
```

The schema models these as four nullable foreign keys with a database constraint requiring exactly one to be present. LearnFlow does not use a generic polymorphic source field such as `source_type` + `source_id`.

Named nullable foreign keys keep real referential integrity on every source, keep the source readable in queries, and let the database enforce the rule. A polymorphic pair would surrender foreign-key enforcement and push the rule into application code.

### A checkpoint quiz covers one or more topics

A checkpoint quiz links to topics through a `checkpoint_quiz_topics` join table carrying `checkpoint_quiz_id`, `topic_id`, and a unique constraint on the pair.

The application requires at least one linked topic; a quiz with no topic is invalid. This is an application rule because the database cannot express "at least one row in a child table" with a simple constraint.

The interface may begin by creating single-topic quizzes. The data model must not encode that interim choice, because multi-topic checkpoints across related topics are an expected extension and retrofitting the join table later would require migrating existing quizzes.

### Topic performance evidence belongs only to an external test result

Topic performance evidence records topic-level detail that a learner transcribed from an external test report. It always belongs to exactly one external test result and one topic.

Checkpoint quiz outcomes are not topic performance evidence. A quiz influences learner topic progress through its quiz attempt, its answers, and the topic links on the questions answered. That path already carries topic-level detail, so a second representation would create two sources of truth for the same signal with different provenance and reliability.

## Consequences

### Positive

- Mistakes arising from revision or ordinary study can be recorded, which the previous schema prevented.
- Every mistake has exactly one traceable, referentially enforced origin.
- Multi-topic checkpoint quizzes need no schema migration later.
- Quiz-derived and externally entered evidence keep distinct provenance, preserving the evidence-based progress rule in DEC-015.
- The domain, entity, and schema documents state one consistent model.

### Negative

- `mistake_evidence` carries four mostly-null columns, and each new source type adds another column and updates the constraint.
- The "at least one topic" rule lives in application code and needs test coverage rather than a database guarantee.
- Reading a mistake's source requires checking four columns instead of one pair.

### Mitigations

- Keep the source set closed and deliberate; adding a fifth source is an explicit decision, not an incidental change.
- Cover the exactly-one-source constraint and the at-least-one-topic rule with tests at the repository and application boundaries.
- Expose a single resolved source in application DTOs so callers do not branch across four columns.

## Alternatives Considered

### Polymorphic source columns on mistake evidence

Store `source_type` and `source_id` and resolve the target in application code.

**Rejected:** loses foreign-key integrity for every source, allows dangling references, makes joins awkward, and moves a rule the database can enforce into application code. Explicitly ruled out by this decision.

### Keep the two-source constraint and narrow the domain documents

Restrict mistakes to quiz answers and external test results, and remove revision and study activity from the domain documents.

**Rejected:** mistakes noticed during revision or study are ordinary and valuable learning signals. Narrowing the model to match an incomplete schema would remove product behaviour to preserve an implementation detail.

### A single `topic_id` column on `checkpoint_quizzes`

Model one topic per quiz and revisit if multi-topic quizzes are needed.

**Rejected:** conflicts with the entity catalog and the product agents document, and a later change would require migrating quizzes and their attempts. The join table costs little now.

### Let checkpoint quizzes also produce topic performance evidence

Reuse the topic performance evidence structure for quiz outcomes.

**Rejected:** creates two representations of topic-level performance with different provenance and reliability, and would require the external-test foreign key to become nullable, weakening a currently strict relationship.

## Implementation Notes

- Follow `docs/database/schema.md` for `mistake_evidence` and `checkpoint_quiz_topics`.
- Implement the exactly-one-source rule as a database check constraint, not only in application validation.
- Enforce at least one quiz topic in the application use case that creates or selects a quiz, and reject a quiz creation request carrying no topic.
- Do not add a `topic_id` column to `checkpoint_quizzes`; the join table is the only quiz-to-topic link.
- When interpreting progress, read quiz evidence through quiz attempts and question topic links; do not write quiz outcomes into `external_test_topic_performance`.
- Index `checkpoint_quiz_topics(topic_id, checkpoint_quiz_id)` for topic-scoped quiz lookups.

## Related Documents

- [Project context](../00-project-context.md)
- [Domain model](../domain/domain-model.md)
- [Domain entities](../domain/entities.md)
- [Database schema](../database/schema.md)
- [Functional requirements](../requirements/functional.md)
- [API endpoints](../api/endpoints.md)
- [ADR-003: Use PostgreSQL for structured persistence](ADR-003-postgresql-persistence.md)
- [Architecture decision register](../architecture/decisions.md)
