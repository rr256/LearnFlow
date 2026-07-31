---
title: "ADR-012: Load Curriculum as Reconciled Reference Data from a Versioned File"
status: accepted
owner: architecture-and-data
last_updated: 2026-07-31
related:
  - ../00-project-context.md
  - ADR-003-postgresql-persistence.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../domain/domain-model.md
  - ../requirements/functional.md
  - ../architecture/decisions.md
---

# ADR-012: Load Curriculum as Reconciled Reference Data from a Versioned File

## Status

Accepted — 2026-07-31

## Context

[DEC-003](../architecture/decisions.md) established that curriculum is data-driven rather than
hardcoded, and [DEC-004](../architecture/decisions.md) that the first curriculum is a verified GATE
CSE syllabus. Both were approved directions marked *ADR pending*, and both are now implemented, so
the decisions they imply need a durable record.

[ADR-011](ADR-011-sqlalchemy-persistence-implementation.md) created the curriculum tables but
deliberately left them empty; [database/migrations.md](../database/migrations.md) had already ruled
that migrations should not become a content-loading mechanism, and required "explicit, idempotent
seed/import tooling" without saying what idempotent means in practice.

Four questions could not be avoided once that tooling was written, and none had an approved answer:

1. **What identifies a record across runs**, given that the source file carries no database
   identifiers and learner progress will reference the identifiers it produces.
2. **What a re-run does to a record that changed** in the source — leave it, update it, or replace it.
3. **What happens to a record the source no longer lists**, once learner data may point at it.
4. **Where the curriculum content lives**, and how its provenance stays checkable.

The seed is not an ordinary use case. It writes reference data outside any learner-facing workflow,
it is run by hand and by CI, and its output is the anchor for planning, resources, progress,
revision, assessment, and mistake evidence. A quiet mistake here corrupts everything downstream.

## Decision

### Curriculum content is a versioned data file, not code

The curated curriculum lives in a JSON file — `backend/scripts/gate_cse_curriculum.json` for GATE CSE
— that names its learning program, its curriculum version, and its official source. Loading a
different learning program, or a later syllabus, is a new file rather than a code change. This is
what makes DEC-003 true at the persistence layer rather than only at the frontend boundary.

The file records its provenance in a `$comment` block: the official source URLs, and the
transcription rules used to turn prose into subjects and topics. `curriculum_versions.source_reference`
carries the same reference into the database, so a stored curriculum can be traced to the document it
came from without consulting the repository.

### Records are matched on natural keys, and each is a database constraint

| Record | Natural key | Constraint |
| --- | --- | --- |
| Learning program | `code` | `uq_learning_programs_code` |
| Curriculum version | `(learning_program_id, version_label)` | `uq_curriculum_versions_learning_program_id_version_label` |
| Subject | `(curriculum_version_id, code)` | `uq_subjects_curriculum_version_id_code` |
| Topic | `(subject_id, code)` when the topic carries a code | `uq_topics_subject_id_code` |
| Topic | `(subject_id, parent_topic_id, name)` otherwise | `uq_topics_subject_id_parent_topic_id_name` |
| Topic relationship | `(source_topic_id, target_topic_id, relationship_type)` | `pk_topic_relationships` |

Every key the seed matches on is enforced by the database, so the seed and the schema cannot disagree
about what identifies a record. `uq_topics_subject_id_code` is added by migration `20260731_02`
specifically to close the one gap: the seed could match on a topic code that nothing enforced.

The two topic constraints treat NULL oppositely, and must. Name uniqueness declares
`NULLS NOT DISTINCT` so that root topics, whose parent is NULL, cannot escape it. Code uniqueness
keeps the default `NULLS DISTINCT`, because `code` is optional and a curriculum that numbers nothing
leaves every code NULL — under the other setting a subject could hold only one such topic.

### A re-run updates in place and never deletes

Applying the same file twice writes nothing: each record is compared field by field and written only
when something differs. A changed name or description in the source updates the existing row, keeping
its identifier.

**Nothing is ever deleted.** A subject or topic dropped from the source file keeps its row. Curriculum
records are reference data that learner progress, plans, revision records, and assessment evidence
point at, and `database/schema.md` already states they "should not be casually deleted once learner
records reference them". Removing curriculum a learner has studied is a deliberate, separately
approved change, never a side effect of editing a data file.

Subjects that disappear from the source are moved behind the seeded ones, so the seeded positions
stay contiguous. Because `uq_subjects_curriculum_version_id_position` is checked per statement rather
than at commit, any run that changes a subject's position first moves every subject of that version
out of the positive range, then assigns the final positions;
[database/migrations.md](../database/migrations.md#re-ordering-subjects) describes the step.

### A topic without a code that is renamed becomes a new topic

Nothing distinguishes a rename from a genuinely new topic when the only identity is the name. The
seed therefore creates a new topic and leaves the old one in place, rather than guessing. A
curriculum that expects renames gives its topics codes, which is what `uq_topics_subject_id_code`
now makes safe.

### The seed refuses to activate a rival curriculum version

Seeding a version as `active` while a different version of the same program is active fails with an
error naming both, rather than surfacing as an integrity error from the partial unique index
ADR-011 created. `published_at` is stamped once, from an injected clock, when a version first becomes
active, and is never overwritten — otherwise every run would report a change it did not make.

### Reconciliation is an application use case, not a script

The matching and comparison rules live in
`backend/app/application/use_cases/seed_curriculum.py`, behind a repository port. The SQLAlchemy
adapter stores what it is told and decides nothing; only `backend/scripts/seed_curriculum.py` reads
configuration and opens a database. The rules are therefore testable without PostgreSQL and reusable
by a future curriculum-import endpoint without being rewritten.

## Consequences

### Positive

- Re-running the seed is safe at any time — after a restore, in CI, or on a whim — which makes it
  usable as a routine setup step rather than a one-shot import.
- Learner data can never be orphaned by an edit to a data file, because the seed has no delete path.
- Every identity rule is enforced by the database, so a second writer cannot introduce a duplicate the
  seed would later mistake for an update.
- Adding a learning program, or a new syllabus year, is a reviewable data diff.
- The reconcile rules are covered by fast unit tests against a fake and by integration tests that
  apply the seed twice to a real PostgreSQL database.

### Negative

- Curriculum removed from the source accumulates in the database. Cleaning it up needs a separate,
  deliberate mechanism that does not exist yet, and until learner data exists there is nothing to
  weigh that decision against.
- Renaming an uncoded topic silently doubles it. The mitigation — give topics codes — was not applied
  to GATE CSE, whose topic names come from the official syllabus and are not expected to churn.
- Reconciling record by record costs more queries than a truncate-and-reload. At curriculum scale, 11
  subjects and 65 topics and subtopics, this does not matter; at a far larger curriculum it might.
- The seed reads a whole curriculum into memory. Acceptable for a syllabus; not a general bulk-import
  design.

### Neutral

- The curriculum tables are now written but still read by nothing. The curriculum API arrives later in
  Milestone 1 and will read what this seed produces.
- Topic relationships are supported and tested but empty for GATE CSE, because the official syllabus
  states no prerequisite order. A curated ordering can be added later as data.

## Alternatives considered

### Load the curriculum in an Alembic migration

Simple, ordered, and applied by the same command as the schema.

**Not selected:** [database/migrations.md](../database/migrations.md) already rules that migrations
should not become a general-purpose content-loading mechanism, permitting only the minimal system
records a schema genuinely requires — which a whole syllabus is not. A syllabus correction would
otherwise become a new migration, migration history would fill with content edits, and a curriculum
fix could not be applied without a schema version bump.

### Delete records the source no longer lists

Makes the file the exact truth, which is the cleanest mental model and avoids accumulating dead rows.

**Not selected:** once learner progress references a topic, deleting it either fails on a foreign key
or destroys history. The failure mode is silent and unrecoverable, and it would arrive long after the
edit that caused it. Retaining rows is recoverable; deleting them is not.

### Insert missing records only, never update

The most conservative option, and trivially idempotent.

**Not selected:** a corrected topic name or a re-ordered subject would never reach a database that had
already been seeded, so the file would stop being the source of truth after its first run. Fixing a
typo would mean editing rows by hand — exactly what the tooling exists to avoid.

### Match topics by position, or by a generated slug

Position needs no authored identifier; a slug derived from the name needs no extra field.

**Not selected:** position changes whenever the syllabus is re-ordered, which is precisely when
identity must hold. A generated slug changes whenever the name changes, which makes it a rename
detector that fails at renames. Both would silently re-point learner progress.

### Keep the curriculum in Python rather than JSON

Types, comments, and no parsing layer.

**Not selected:** it makes curriculum content a code change, contradicting DEC-003, and puts syllabus
text where a reviewer reads code rather than data. JSON also needs no new dependency, unlike YAML.

## Implementation notes

- Migration `20260731_02_add_topic_code_unique_constraint` adds `uq_topics_subject_id_code`. It is
  additive and safe on populated tables.
- The seed validates a file before writing: topic names unique among siblings, topic codes unique
  across the whole subject, subject codes unique, controlled values known, and relationship endpoints
  resolvable. The two topic rules are checked at the scope their constraint uses, which differ.
- The whole run is one transaction, committed only on success. `--dry-run` rolls back instead.
- Integration tests apply the curriculum twice and assert identical row counts and identical
  identifiers; the CI `database` job runs them against an ephemeral PostgreSQL service.
- Open for a later decision, and deliberately not settled here: how curriculum removed from a source
  file is eventually retired, and whether a curriculum-import API endpoint should reuse this use case.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-003: Use PostgreSQL for structured persistence](ADR-003-postgresql-persistence.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — created the tables this seed fills
- [Database schema](../database/schema.md) — the constraints this record relies on
- [Database migrations](../database/migrations.md) — the seed's commands and operational rules
- [Domain model](../domain/domain-model.md) — curriculum is curated and verified
- [Functional requirements](../requirements/functional.md) — curriculum is loaded from the database, not hardcoded
- [Architecture decision register](../architecture/decisions.md) — DEC-003, DEC-004, DEC-025
