---
title: "ADR-032: Catalogue Learner-Owned Study Material as Metadata, Linked to Topics"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-19
related:
  - ../00-project-context.md
  - ADR-008-assessment-and-mistake-evidence-model.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-012-curriculum-seed-and-reconciliation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-022-plan-adaptation.md
  - ADR-024-plan-item-skipping.md
  - ADR-026-monthly-study-view.md
  - ADR-028-revision-workflow.md
  - ADR-029-progress-overview.md
  - ADR-031-priority-focus-panel.md
  - ../rag/ingestion.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-032: Catalogue Learner-Owned Study Material as Metadata, Linked to Topics

## Status

Accepted — 2026-08-16. Proposed 2026-08-16.

This begins [FR-007](../requirements/functional.md#fr-007-learning-resource-organization) and
creates the first two tables of the *Resources and RAG metadata* schema area, which has had no code
since the documentation foundation. It is the first change to open
[Milestone 4](../roadmap/milestones.md#milestone-4-resources-rag-and-mentor), and it deliberately
delivers **only that milestone's first item**: no extraction, no indexing, no retrieval, and no
mentor.

**FR-007 is not met in full**, and this record does not claim it is:

- **"The learner can register PDFs, notes, PYQs, and references/paths to local video resources."**
  **Partly met.** Every one of those kinds can be registered and described. A **path** to a local
  file cannot: `external_reference` accepts an `http` or `https` address alone, because
  [endpoints.md](../api/endpoints.md#resource-and-ingestion-endpoints) forbids a resource endpoint
  returning an absolute local filesystem path. Material that is not on the web is carried by
  `source_label`, in the learner's own words. See [What a resource may point at](#what-a-resource-may-point-at).
- **"A resource can be linked to one or more subjects, topics, or subtopics."** **Met for topics and
  subtopics**, which are the same table. **Subject-level linking is not storable**: the approved
  schema has `resource_topic_links` and no subject equivalent, and inventing one would be a table no
  requirement has constrained.
- **"LearnFlow records basic resource metadata, including title, type, source location, and linked
  curriculum areas."** **Met in full.**
- **"The learner can find resources associated with a topic."** **Met in full**, by RES-002's
  `topic_id` filter and by the three screens that show a topic's material.

It also supplies **half of one deferred criterion elsewhere**.
[FR-006](../requirements/functional.md#fr-006-revision-guidance)'s second criterion — "a revision
recommendation links to a topic and, where available, relevant resource or practice suggestions" —
had its resource-and-practice half deferred by [ADR-028](ADR-028-revision-workflow.md) to FR-007 and
FR-009. The **resource half is now met**, for the material a learner has registered; the **practice
half still waits on FR-009**, which does not exist. **FR-006 is still not met in full.**

It needs **one migration**: `20260816_01`, two `CREATE TABLE`s and two indexes. Nothing existing is
altered.

## Implementation status

**2026-08-19 — a learner's own written notes are now stored against a resource.**

[ADR-037](ADR-037-learner-written-resource-notes.md) **narrows this record's "metadata, never the material" rule** on one point: a learner may keep **plain-text notes they wrote or pasted themselves** against a resource — their own notes on it, or a passage they transcribed. The text is **stored locally** and **rendered as plain text only**.

The three things that rule was written to keep out **all stay out**: nothing is uploaded, nothing is fetched or scraped from the web, and no location on the learner's own machine is stored. Nothing extracts, chunks, embeds, indexes, or searches a note either, and `storage_key`, `metadata`, and `resource_ingestions` remain absent.

**The decision below is not rewritten**, and none of its reasoning is withdrawn.

**2026-08-18 — a topic's material is now also shown on `/plan` and `/plan/today`.**

Active topic-linked resources are shown **read-only** beside the plan items that name their topic, on
the plan screen and the daily study view, alongside the curriculum view and `/revisions` this
record already named. **Archived material remains excluded** from all of them, exactly as decided
below; `/resources` remains the only place material is registered, corrected, or put aside; and
nothing is recommended, ranked, or counted on the added surfaces.

[ADR-036](ADR-036-topic-material-on-the-plan-screens.md) records the added surface, its reasoning,
and the sentences of this record it leaves short — including *"The plan screens are untouched"* under
[Where material appears, and where it can be changed](#where-material-appears-and-where-it-can-be-changed).
`/plan/month` is unchanged.

**The decision below is not rewritten**, and none of its reasoning is withdrawn.

## Context

`resources`, `resource_topic_links`, and `resource_ingestions` have been approved tables with no code
since Milestone 0, and [schema.md](../database/schema.md#implementation-status) has carried the whole
area as *Not implemented — arrives with Milestone 4*.

The question this change answers is narrower than that area: **where is a learner's study material,
and which topics does it cover?** Everything else the area anticipates — extracting text from a PDF,
embedding it, retrieving it for a mentor answer — is a second capability with its own provider, its
own storage, and its own failure modes.

Three decisions had to be made before anything could be built, and the project owner decided each of
them.

1. **What a resource may point at**, which is a privacy decision as much as a modelling one.
2. **Whether curated material ships with the product**, which decides whether external content has to
   be obtained.
3. **How a learner removes something**, which decides whether this change creates the product's first
   destructive endpoint.

### One finding that shaped the answers

**LearnFlow has no material of its own, and cannot get any.** Every other record this product stores
is either curated reference data it can transcribe from a published source — a syllabus, an
examination calendar — or something the learner did. Study material is neither: it is the learner's
own books, notes, and links, most of it copyrighted and none of it LearnFlow's to distribute.

That settles more than it first appears. It is why nothing is seeded, why nothing is recommended, and
why the catalogue records *where material is* rather than holding it.

## Decision

### What a resource may point at

`external_reference` accepts an **`http` or `https` address and nothing else**. A `file:` address, a
Windows path, a POSIX path, and a bare host are each refused with a `422`, and the rejected value is
never echoed back.

**Nothing about the learner's own machine is stored or returned.**
[endpoints.md](../api/endpoints.md#resource-and-ingestion-endpoints) has required since Milestone 0
that resource endpoints "must not return absolute local filesystem paths", and the straightforward
way to keep that promise is never to accept one. A validator that stored a path and hid it on the way
out would leave it in the database, in backups, and in any future export.

**Material that is not on the web is carried by `source_label`**, in the learner's own words — "Blue
binder, chapter 3", "Kanodia OS notes", "the lecture series on the external drive". A resource must
carry **at least one** of a label and a link, which is the approved *at least one of `storage_key` or
`external_reference`* constraint read for a catalogue that stores no files.

**The cost is stated plainly**: FR-007's "references/paths to local video resources" is only partly
met, and the local-file half arrives with the storage and ingestion change that gives a file
somewhere to live and an opaque `storage_key` to name it. That change has to handle files anyway; it
is the right place for the question.

### Nothing curated is shipped, so no seed exists

The catalogue starts **empty** and holds only what the learner registers. There is **no seed script
and no data file**, which is why this change adds no fourth step to the documented setup order and
raises no idempotency question — the property [ADR-012](ADR-012-curriculum-seed-and-reconciliation.md)
established for curriculum and the examination schedule.

Shipping a curated list of free GATE CSE links was considered and **not selected**, under
*Alternatives*. It would mean transcribing external content into the repository, unverified against
its sources and liable to rot, and it would put LearnFlow in the position of recommending material —
which is exactly what [the no-recommendation rule](#nothing-is-recommended-ranked-or-counted) below
refuses.

`resources.owner_learner_id` stays **nullable**, as the approved schema specifies, so curated or
shared content has somewhere to live later without a migration. **Nothing writes an ownerless row
today**: the use case requires an owner on every write, because a resource belonging to nobody would
be invisible to every learner-scoped read.

### Nothing is deleted; material is put aside

There is **no `DELETE`**. RES-005 stays unimplemented, and a learner who is finished with something
moves it to `status: archived` through RES-004. Archiving is **reversible**, and archived material
stays in the catalogue screen while dropping out of the curriculum and revision screens.

This is the position [ADR-022](ADR-022-plan-adaptation.md) took for a superseded plan and
[ADR-024](ADR-024-plan-item-skipping.md) for a skipped item: the record is kept, and the learner's
statement about it can be taken back. It also keeps the promise
[schema.md](../database/schema.md#referential-integrity-and-lifecycle-notes) makes — "deleting a
learner-owned resource requires coordinated cleanup of file storage and derived vector records" —
true by construction rather than by care, because there is no deletion to coordinate.

RES-005 arrives with the files and vectors it exists to clean up.

### A resource is metadata, never the material

Nothing is uploaded, downloaded, extracted, embedded, or indexed. `storage_key` and `metadata` are
**not created**, and neither is `resource_ingestions`.

Creating a column before the code that maintains it fixes a shape no requirement has yet constrained,
which is the trap [ADR-011](ADR-011-sqlalchemy-persistence-implementation.md) exists to avoid and the
reason `learner_topic_progress` was created without three of its documented columns
([ADR-017](ADR-017-topic-progress-api-and-schema.md)). A `storage_key` invented now would fix a
storage provider before one exists.

### Nothing is recommended, ranked, or counted

**A topic's material is the material the learner linked to it**, listed in the order the API returned
and nothing else. LearnFlow suggests none of its own, promotes none above another, and shows nothing
at all for a topic with nothing linked — rather than an invented suggestion it cannot support.

**Nothing is counted.** No figure appears beside a subject, a topic, or a review: the line
[terminology](../domain/terminology.md#plan-coverage-counts-are-not-learner-scores) draws applies
here as it does to the stages panel, and a count of a learner's material measures the learner.

`resource_topic_links.relationship_type` carries all four approved roles — `primary`, `supporting`,
`practice`, `revision` — and **only `primary` is written**. A learner links material to a topic and is
not asked to grade how central it is: nothing would read the answer, and the question invites a
judgement the product has no use for.

### A resource may cover any topic, including a heading

RES-001 accepts a link to **any stored topic**, whether or not `topics.is_trackable`.

This is deliberately unlike [PRG-004](../api/endpoints.md#prg-004-patch-apiv1progresstopicstopic_id),
which refuses a learning stage on a topic that only groups subtopics. A stage claims something about
*understanding a unit of work*, and a heading is not one; a textbook may genuinely cover the whole of
Operating Systems. The two rules differ because the claims differ.

### Where material appears, and where it can be changed

Material is **written on `/resources` and read everywhere else**:

- **`/resources`** — the catalogue. Registering, **correcting**, putting aside, and putting back all
  live here, and nowhere else.
- **The curriculum view** — a topic's material sits beneath it, read-only, with a note naming the
  catalogue and linking to it.
- **`/revisions`** — a review shows the material for the topic it names, read-only.

That is the shape [ADR-026](ADR-026-monthly-study-view.md) fixed for the monthly view and
[ADR-029](ADR-029-progress-overview.md) for the progress overview: a screen that reports states where
its action lives rather than growing a second control for it. The alternative — a stage control and a
resource control on every topic in the curriculum tree — would put two write paths on a screen whose
job is reading a syllabus.

**A learner corrects material in place, on the same form that registered it.** One component serves
both, because both ask for the same six things — title, resource type, source label, link, and
topics — and only where the answers go differs: RES-001 or RES-004. The edit form starts from what is
stored, including the topics already selected, and **sends every field**, because RES-004 replaces a
supplied link set whole: what the learner sees selected is what is saved.

It sits behind a native `<details>` disclosure per resource, which needs no JavaScript, so correcting
material works on a page that never hydrates — the rule every write path in this product follows.

**The edit form cannot archive**, and the archive control cannot edit. `status` is not among the
fields the edit form sends, and the archive control sends nothing else, so correcting a typo and
deciding to stop using something stay separate actions with separate confirmations.

**Material put aside is read-only.** It keeps its status control and loses its edit form, so the way
to correct it is to put it back first. Editing a record the learner has said they are not using would
blur the one statement archiving makes.

**The plan screens are untouched.** `/plan`, `/plan/today`, and `/plan/month` render exactly as they
did, and nothing here writes a plan, a plan item, a learning stage, or a revision status.

### Four endpoints, all four catalogued

RES-001 to RES-004 are implemented at the paths and methods
[endpoints.md](../api/endpoints.md#resource-and-ingestion-endpoints) catalogues. **No endpoint is
added and none is moved**, where ADR-022 moved PLN-005 and ADR-028 added REV-004. RES-005 to RES-008
stay unimplemented for the reasons above.

**Two of the catalogue's intent lines are narrower than they read**, and endpoints.md now records
both. RES-001's "upload/store an eligible source file" is **not** implemented — nothing is
uploaded — and RES-002's `subject` filter is **not** accepted, because subject-level links are not
stored and neither screen reading the endpoint wants a narrower collection. Both are compatible
additions under [versioning](../api/versioning.md#compatible-changes-within-a-major-version) rather
than departures from a fixed contract, since neither was ever implemented.

The screens read through the same server-side API client every view uses, and both write paths post
to a `"use server"` module. The browser issues no request to the backend, so
`API_CORS_ALLOWED_ORIGINS` stays planned. This inherits
[ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) through ADR-031 rather than
renegotiating them, and every form works without JavaScript.

## Consequences

### Positive

- **FR-007 is begun**, and three of its four acceptance criteria are met — one partly. The *Resources
  and RAG metadata* schema area gains its first two tables.
- **The resource half of FR-006's second criterion is met**, discharging half of what ADR-028
  deferred. A review now shows the learner's own material for the topic it names.
- **Nothing about the learner's machine is stored.** The privacy rule endpoints.md set in Milestone 0
  is kept by refusing the input rather than by filtering the output.
- **Nothing is deleted, so nothing can be lost.** The product still has no destructive endpoint.
- **No external content entered the repository**, so nothing here can rot, mislead, or infringe.
- **Nothing existing changed.** No plan, plan item, availability, preference, goal, stage, or
  revision behaves differently, and the migration alters no existing table.
- No new error code was needed: `validation_error`, `not_found`, and `conflict` all existed.

### Negative

- **A fifth endpoint group is public contract.** Changing any of the four is breaking under
  [versioning](../api/versioning.md#breaking-changes).
- **A learner with mostly offline material gets a catalogue of labels.** "Blue binder, chapter 3" is
  a note to themselves, not a link LearnFlow can open, and until the ingestion change lands that is
  all a local PDF can be.
- **Material put aside cannot be corrected until it is put back.** The edit form is offered for
  material in the catalogue alone, because changing a record the learner has said they are not
  using conflates two statements; the cost is that a correction to archived material takes two
  steps, and the *Put aside* panel says so.
- **Another learner-facing route** is one more surface that must keep its loading, empty, error, and
  success states in step with the contract behind it.
- **The topic picker is a long multiple-selection list.** The curated curriculum has 65 topics, and
  choosing several from a `<select multiple>` is workable but not pleasant. It was chosen because it
  works without JavaScript, which every write path in this product does.
- **Two tables were created and one deliberately was not.** `resource_ingestions` is now the only
  table of its area still missing, and schema.md and the migration must be read together to see which
  columns of `resources` exist.

### Neutral

- Nothing here totals, counts, ranks, or scores. No "12 resources", no most-used material, no
  suggestion that one piece is better than another.
- No AI provider is involved, no vector index is touched, and no configuration variable is read.
- `image`, `attachment`, `processing`, `ready`, `failed`, `storage_key`, `metadata`,
  `resource_ingestions`, and three of the four link roles are all constrained or absent and unwritten,
  as `monthly`, `daily`, `practice`, `review_mistakes`, `scheduled`, and `scheduled_for` remain.
- `study_activities` is still absent, so the *Progress and revision* area is still incomplete, and
  PRG-001 still waits on quiz, external-test, and mistake evidence.
- No command-line tool registers a resource.

## Alternatives considered

### Accept a local filesystem path

`external_reference` would take any free text, so "references/paths to local video resources" would be
met in full today.

**Not selected:** it contradicts an approved rule in endpoints.md that predates this change, and
amending that rule to permit what it was written to prevent is a privacy decision that deserves its
own argument rather than being carried along by a feature. A stored path also outlives the screen that
showed it — it is in the database, in every backup, and in any future export — while the learner's
actual need, *finding the material again*, is met by a label they wrote themselves.

### Ship a curated catalogue of free GATE CSE material

A seed file of NPTEL courses, official PYQ archives, and open textbooks, loaded idempotently like the
curriculum.

**Not selected:** it requires transcribing external content into the repository, which cannot be
verified against its sources on every build and which rots silently. It would also make LearnFlow the
recommender of material it has never assessed — and a curated list is a ranking whether or not it is
presented as one, which is the thing [ADR-031](ADR-031-priority-focus-panel.md) most recently refused.
The model keeps the door open: `owner_learner_id` is nullable, so curated rows need no migration when
a decision to curate is made deliberately.

### Implement RES-005 and delete

`DELETE /api/v1/resources/{id}` returning `204`, as the catalogue reserves.

**Not selected** *for this change*: it would be the first endpoint in LearnFlow that destroys learner
data, and archiving meets the same need reversibly. RES-005's own stated purpose — "safe removal of a
resource and related derived artifacts" — is about artifacts that do not exist yet, so implementing it
now would implement half of it and leave the name promising the rest.

### Put the register control in the curriculum view

Add material from beside the topic it covers, so the learner never leaves the syllabus.

**Not selected:** the curriculum view is a reading of reference data that already carries one write
path (the stage control), and a second would make a screen about the syllabus into a screen about the
learner's belongings. It also fits badly: one piece of material commonly covers several topics, and a
control anchored to one topic invites registering the same book three times.

### Store material as an attachment LearnFlow holds

Upload the file, keep it under a `storage_key`, and serve it back.

**Not selected** *for this change*: it needs a storage provider, a size and type policy, a cleanup
path, and a decision about what leaves the machine — none of which FR-007's four criteria require, and
all of which FR-008's retrieval will force anyway. It is the change `storage_key`, `metadata`, and
`resource_ingestions` are waiting for.

### Ask the learner what role each linked topic plays

Offer `primary`, `supporting`, `practice`, and `revision` on the link form.

**Not selected:** nothing reads the answer, so it would be a question asked for its own sake, and
grading how central a book is to a topic is a judgement the product has no use for. The `CHECK`
carries all four values, so offering them later is a use-case change rather than a migration — the
argument [ADR-020](ADR-020-initial-study-plan-generation.md) made for `plan_items.status`, which paid
off three times.

## Implementation notes

- Endpoint fields and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#resource-and-ingestion-endpoints), which stays authoritative.
- Migration `20260816_01_create_learning_resource_tables` creates two tables and two indexes and
  alters nothing. Its downgrade drops the links first — they reference `resources` — and names no
  constraint, which keeps it clear of the `ck` naming convention that bit revision `20260806_02`.
  [migrations.md](../database/migrations.md#commands) records that trap.
- `RESOURCE_TYPES`, `RESOURCE_STATUSES`, `RESOURCE_TOPIC_ROLES`, and `MAX_TOPIC_LINKS` live in
  `application/dto/resource.py` and are mirrored by the model's `CHECK`s, the way the plan and
  revision vocabularies are.
- The line between a value carried in a `CHECK` and one left out is drawn deliberately: a value a
  later **use-case** change alone could write is carried (the three unused link roles); a value that
  needs storage which does not exist is left out (`image`, `attachment`, and the three ingestion
  statuses).
- `ManageResources` serves all four endpoints, so the rule deciding whether a resource belongs to the
  effective learner stays in one place. Its provider in `composition/providers.py` owns the
  transaction, so registering material and linking it to several topics cannot half-succeed. It binds
  no `Clock`: nothing about a resource depends on the date.
- `SqlAlchemyResourceRepository` filters by topic with an `EXISTS` rather than a join, so a resource
  covering a topic appears once however many links it holds — a join would repeat it and make the page
  window count the same resource twice.
- The frontend is `app/resources/page.tsx` with `features/resources/` —
  `ResourceCatalogue.tsx`, `ResourceForm.tsx`, `ResourceStatusControl.tsx`,
  `TopicResources.tsx`, `actions.ts`, `by-topic.ts`, `topic-options.ts`, and the form state in
  `submission.ts` because a `"use server"` module may export only async functions, which
  `frontend/tests/server-actions.test.ts` enforces. `ResourceForm.tsx` serves both registering and
  editing: it takes an optional resource, and `submission.ts` reads the six shared fields once for
  both `registerResourceAction` and `saveResourceEdit`.
- The topic picker indents a subtopic with **no-break spaces**, written as escapes in the source: a
  browser collapses ordinary leading whitespace inside an `<option>`, so the indent would vanish in
  the one control it exists for.
- The curriculum and revision screens read the whole catalogue once and join it by topic in the
  client, rather than asking RES-002 per topic — the join the curriculum view already performs for
  PRG-002, and the reason RES-002 returns each resource with its topics.
- Covered at four levels: use-case tests against fakes; API contract tests over the real application
  factory; PostgreSQL integration tests over the migration, its constraints, its indexes, and the
  catalogue read back over HTTP against the seeded GATE CSE curriculum; and frontend tests over the
  catalogue, the per-topic list, the form parsing, the topic grouping, and the API client. There is
  deliberately **no domain-level test**: nothing here is a planning or scheduling calculation, and
  `backend/app/domain/` is untouched.
- Open and deliberately not settled here: whether a local file path is ever accepted once storage
  exists; whether curated or shared material is ever seeded; whether RES-005 deletes once files and
  vectors exist; whether archived material ever becomes editable in place; whether the three
  unwritten link roles are ever offered; and whether a resource may be linked to a *subject* rather
  than to its topics.
- Recorded as DEC-044 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the migrate-with-the-code rule this change follows, and the validated-text rule it applies again
- [ADR-012: Load curriculum as reconciled reference data from a versioned file](ADR-012-curriculum-seed-and-reconciliation.md) — the seed shape this change deliberately does not use, because nothing curated ships
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope these four contracts answer in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology these screens inherit
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the trackable-topic rule this change deliberately does not share, and the deferred-column precedent it follows
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the carry-the-value argument behind the three unwritten link roles
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — the keep-rather-than-delete position archiving follows
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](ADR-024-plan-item-skipping.md) — the reversibility every learner statement in this product carries
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](ADR-026-monthly-study-view.md) — the read-only screen shape the curriculum and revision surfaces follow
- [ADR-028: Schedule revisions from finished work, on the learner's ask](ADR-028-revision-workflow.md) — the criterion half this discharges, and the deferral it recorded
- [ADR-029: Show the progress overview as a reading of what is stored, counting nothing of its own](ADR-029-progress-overview.md) — the naming-where-the-action-lives pattern these screens reuse
- [ADR-031: Draw priority focus from facts backend rules already decided, ranking nothing](ADR-031-priority-focus-panel.md) — the refusal to rank that this change applies to material
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the four contracts this implements, the four it leaves unimplemented, and the two intent lines it narrows
- [API versioning](../api/versioning.md) — what makes a change to them breaking
- [Database schema](../database/schema.md) — the approved tables, and the departures this record makes from them
- [Database migrations](../database/migrations.md) — the migration this record introduces
- [Domain model](../domain/domain-model.md) — the learning resource, and rule 3 this change applies
- [Domain entities](../domain/entities.md) — the entity this persists
- [Terminology](../domain/terminology.md) — *learning resource*, and the counts a screen may not carry
- [Functional requirements](../requirements/functional.md) — FR-007's four criteria, and the FR-006 half this discharges
- [RAG ingestion](../rag/ingestion.md) — the change `storage_key`, `metadata`, and `resource_ingestions` wait for, whose description of registration predates this decision
- [Coding standards](../development/coding-standards.md) — the UI responsibility rule that keeps recommendation out of the frontend
- [Repository and folder structure](../development/folder-structure.md) — where the route and the feature live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 4 item this opens
- [Architecture decision register](../architecture/decisions.md) — DEC-044
