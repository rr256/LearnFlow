---
title: "ADR-042: Remove a Whole Resource and Everything It Owns"
status: accepted
owner: architecture-and-ai
last_updated: 2026-08-22
related:
  - ../00-project-context.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-032-learning-resource-catalogue.md
  - ADR-037-learner-written-resource-notes.md
  - ADR-040-learner-uploaded-resource-files.md
  - ADR-041-removing-a-stored-file-or-note.md
  - ../api/endpoints.md
  - ../architecture/decisions.md
  - ../architecture/provider-pattern.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../deployment/docker.md
  - ../development/folder-structure.md
  - ../domain/terminology.md
  - ../domain/entities.md
  - ../requirements/functional.md
  - ../roadmap/milestones.md
---

# ADR-042: Remove a Whole Resource and Everything It Owns

## Status

Accepted — 2026-08-22. Proposed 2026-08-22.

This implements **RES-005**, the last unbuilt **catalogue** endpoint — the ingestion endpoints RES-006 to RES-008 remain, waiting on an extractor — and the **widest destruction in LearnFlow**: a learner removes one
piece of catalogued material and its topic links, its notes, its stored-file
records, and the PDF bytes those records named all go with it.

It adds **one endpoint**, widens `ManageResources` to reach the note and
stored-file repositories and the byte storage, and adds one control to
`/resources`.

It needs **no migration, no column, and no table.**

**It is one resource per request.** There is still no bulk removal.

## Context

[ADR-041](ADR-041-removing-a-stored-file-or-note.md) built RES-018 and RES-019 —
removing one stored file or one note — and closed by naming what was still
missing: *"RES-005 is still the area's most-needed next change"*, waiting *"only
on the cascade it implies"*.

That gap is not theoretical. In real use the project owner registered a resource
with the wrong title and the wrong topic, and there was no way to be rid of it
through the product. It was deleted **by hand, in SQL, against the live
database** — the exact operation this ADR exists to make unnecessary.
[ADR-041](ADR-041-removing-a-stored-file-or-note.md) recorded the same reasoning
for a file: *"A product whose only answer to a mistake is 'open a database
client' has not answered it."*

### This reopens an alternative ADR-032 rejected, and says why that is legitimate

[ADR-032](ADR-032-learning-resource-catalogue.md) considered **"Implement RES-005
and delete"** and rejected it on two grounds:

1. *"it would be the first endpoint in LearnFlow that destroys learner data, and
   archiving meets the same need reversibly"*
2. *"RES-005's own stated purpose — 'safe removal of a resource and related
   derived artifacts' — is about artifacts that do not exist yet, so
   implementing it now would implement half of it and leave the name promising
   the rest."*

**Both conditions have since changed, which is why this is a reopening rather
than a reversal.** ADR-041 settled (1): LearnFlow already destroys learner data,
deliberately and narrowly, and the argument that archiving *meets the same need*
was found wanting — archiving is shelving, not an undo. And (2) no longer holds
either: a resource now genuinely owns artifacts — notes since ADR-037, stored
files and their bytes since ADR-040 — so removing one is no longer half a
feature. **Derived artifacts still do not exist** (no chunk, no embedding, no
`resource_ingestions`), and when they do they join this cascade.

**ADR-032's actual decision — *nothing is deleted; material is put aside* — is
narrowed here, not overturned.** Putting material aside stays reversible, stays
the first thing the screen offers, and stays the right answer for material a
learner is merely finished with.

## Decision

### One endpoint, one resource

`DELETE /api/v1/resources/{resource_id}` (RES-005), answering `204` with no
body — exactly the contract the catalogue has reserved since Milestone 0. No
`learner_id` is accepted; the effective learner is resolved server-side.

**No bulk removal.** There is no endpoint that removes several resources, and
none that clears a resource's files or notes while keeping the resource. A
learner who wants two resources gone asks twice.

### What is deleted

Everything the resource owns, and nothing else:

| Removed | Where |
| --- | --- |
| The resource row | `resources` |
| Its topic links | `resource_topic_links` |
| Every note kept against it | `resource_notes` |
| Every stored-file record | `resource_files` |
| The bytes those records named | the `resource_files` Docker volume |

**Nothing outside the resource is touched** — no other resource, no curriculum
topic, no learning stage, no plan, no plan item, no revision, and no quiz. A
resource says where material is; removing it says nothing about what a learner
understands.

### Active and archived alike may be removed

The resource's own `status` is **not consulted**. This is the one place archived
material is *not* read-only, and deliberately so: everywhere else the read-only
rule protects a record from being changed by accident, whereas here refusing
would strand a learner who shelved something precisely because they wanted it
gone. Requiring an archive first would also turn the shelf into a deletion
queue — the conflation ADR-041 rejected for files and notes, applied to the
material itself.

### The rows are cleared in code, and the foreign keys stay `NO ACTION`

All three foreign keys into `resources` are non-cascading, and [`schema.md`](../database/schema.md) gave the reason, before this change: *"nothing deletes a resource, so a cascade would describe a deletion path that does not exist."*
That premise is what this ADR changes, so the cascade decision has to be made
rather than inherited.

**The use case deletes children in dependency order inside one transaction** —
stored-file rows, notes, topic links, then the resource — and **the constraints
stay as they are**. Two reasons:

- **A deletion path nobody reads is a deletion path nobody reviews.** In code
  the cascade is explicit, ordered, and unit-tested; as a constraint it is
  invisible at the call site.
- **The constraints become a safety net.** If the use case ever stops clearing a
  child, the `NO ACTION` foreign key makes the delete **fail loudly** instead of
  silently widening. An integration test asserts exactly this by attempting a
  raw `DELETE FROM resources` and requiring it to fail.

`ON DELETE CASCADE` was the alternative. It needs a migration altering three
existing constraints, it would make any future accidental resource delete
silently destructive, and it still leaves the **bytes** to handle explicitly,
because a filesystem is not in the transaction. It buys little and costs the
audit trail.

### The storage keys are read first, and the bytes go last

**Order is not a preference here; only one order works.** The keys are read
**before** any row is deleted, because once the rows are gone nothing can name
the files. Every status is included: an archived file still occupies the volume.

Rows are then deleted innermost-first, and the bytes are unlinked **last**, with
the provider committing after the use case returns. That gives two failure
modes, and **neither loses a learner's material silently**:

| Failure | What it leaves | How it clears |
| --- | --- | --- |
| An unlink fails | The exception propagates, the transaction rolls back, and **nothing is deleted** — every row and every byte survives | The learner asks again |
| The commit fails after unlinking | Rows survive with some bytes gone | A download reports the file missing — already a handled `404` — and asking again clears it |

A filesystem does not join a database transaction, so the two cannot be made
atomic. **The guarantee is that every failure leaves a state the learner can act
on, not that no failure leaves one** — ADR-041's position, applied to a wider
cascade.

### Nothing is recoverable

No soft delete, no grace period, no recycle bin, no `deleted_at`, and no copy.
**A backup is not an undo**: restoring the volume alone returns bytes with no
rows, which nothing in the product can reach, and restoring the database alone
returns rows whose downloads fail.

### Two deliberate actions, and copy that says what goes

The shared `RemoveControl` serves this too, so all three removals behave
identically: a **closed `<details>` disclosure** whose opening *is* the
confirmation step, then a confirm button.

**The copy itemises the loss**, because this removes more than the thing it
names:

> Removing **Operating Systems notes** is permanent. This also deletes 3 stored
> PDFs and 12 notes kept against it. LearnFlow keeps no copy, and this cannot be
> undone.
>
> To keep it but stop using it, put it aside instead — that is reversible.
>
> `[ Yes, remove this material and everything in it ]`

**Those figures describe what a destructive action will destroy, not the
learner.** Terminology's no-counting rule guards against measuring progress and
effort; hiding the scale of an irreversible action would be the wrong instinct,
and the learner needs it to decide. Nothing is stored, totalled across
resources, or shown anywhere but inside this warning. A resource holding
nothing says so in words and names no figure.

A **typed confirmation** was rejected for the reason ADR-041 gives: the gate can
only be enforced in the browser, so it silently degrades to one click with
scripting disabled.

### Repeat and concurrent removal

Removing a resource that is already gone is **`404`** — the learner is naming
something that no longer exists. **A second browser tab acting on a stale list
receives the same `404`** and re-renders without it; there is no optimistic
locking and no version token, because the honest answer to "remove this" when it
is already removed is that it is not there.

A resource that is not the learner's is also `404`, never `403`: existence is
itself a disclosure.

## Alternatives considered

**`ON DELETE CASCADE` via migration.** Rejected — see above.

**Archive-then-delete.** Rejected: it conflates shelving with a deletion queue,
and diverges from the rule ADR-041 set for files and notes.

**Refuse while the resource still owns files or notes.** Rejected: with 20 files
and 200 notes possible it is punishing, and it fails the stated goal — a learner
would still need SQL for anything with material against it.

**Soft delete with a grace period.** Rejected: it needs a column, a migration, a
purge job, and a rule for what a removed resource counts as; it makes
*permanent* false while leaving the mistake on disk.

**A dedicated `RemoveResource` use case.** Rejected, though it is close. It would
keep `ManageResources` narrow, but it duplicates the ownership check that decides
whether a resource is the learner's — and that rule living in one place is why
`ManageResources` serves all the catalogue endpoints together.

**Deleting the bytes first.** Rejected: a failure between the two leaves a
resource whose files all fail to download.

**A typed confirmation.** Rejected — see above.

**Bulk removal.** Out of scope, and not merely deferred: choosing several
records to destroy at once is a different decision with its own confirmation
problem.

## Consequences

**The learner never needs SQL to remove their own material.** That was the
stated goal, and it is met.

**`ManageResources` is wider.** It now binds the note repository, the stored-file
repository, and the byte storage — three ports that exist for this method alone.
The composition root builds the storage adapter **once** and shares it with the
stored-file provider, so both unlink through the same object.

**ADR-032 is narrowed on its "nothing is deleted" clause**, and gains a dated
*Implementation status* note. Its decision body is not rewritten. ADR-037,
ADR-040 and ADR-041 each gain one too, because each states that a whole resource
cannot be removed.

**Three guard tests asserting deletion could not exist were replaced** — in the
API resource suite, the stored-file suite, and the catalogue component suite.
That is the honest cost of reversing a decision, and each replacement asserts
the new behaviour rather than being deleted. The stored-file guard was
**narrowed rather than removed**: bulk removal is still refused, and still
tested.

**The foreign keys stay non-cascading**, so `schema.md`'s reasoning for them
changes — from *"nothing deletes a resource"* to *"the use case clears children
itself, and the constraint is the safety net"*.

**Backup guidance gains a line.** A resource removal destroys more at once than
any other action, and a volume-only restore still cannot undo it.

**`resource_ingestions` stays absent** and RES-006 to RES-008 stay unimplemented.
No extraction, OCR, chunking, embedding, indexing, retrieval, AI, or background
job is added, and no dependency arrives.

**FR-007's verdict does not move.** Its four criteria are about registering,
linking, describing and finding material; being able to remove it is none of
them. `docs/api/endpoints.md` stays authoritative for the count.

**The resource area is now complete for what it stores.** RES-001 to RES-005 and
RES-009 to RES-019 are implemented; only the ingestion endpoints remain, waiting
on an extractor.

## Implementation notes

Three port methods are added: `ResourceRepository.delete_resource`,
`ResourceNoteRepository.delete_notes_for_resource`, and
`ResourceFileRepository.delete_files_for_resource`. The two per-resource cascade methods each name **one resource** and clear what it owns — they are the cascade, and there is deliberately no method that spans resources.

Topic links are cleared through the existing
`replace_topic_links(resource_id, topic_ids=[])` rather than a new method: it
already does exactly this, and is already tested.

The use case returns a `RemovedResource` describing what went, so the caller can
state the loss without counting it again.

### Verification

- Backend unit tests over the cascade, the ordering (keys read before rows go),
  the rollback on a failed unlink, archived resources, ownership, and repeat
  removal.
- API contract tests across three suites, including that a removed resource's
  file cannot be downloaded and its notes cannot be read.
- **PostgreSQL integration tests against a disposable database with a real
  directory**, asserting the rows *and* the bytes are gone, that a raw
  `DELETE FROM resources` still fails against the non-cascading constraints, that
  another resource's bytes survive, and that a failed unlink removes nothing.
- Frontend tests over the control, the itemised copy, the closed disclosure, and
  that removal is offered for archived material.
- A client test asserting the **only** three removals in the API client are
  `deleteResource`, `deleteResourceFile`, and `deleteResourceNote`.

### What this deliberately leaves open

- **Bulk removal** of several resources.
- **Derived artifacts** — chunks, embeddings, `resource_ingestions` — which do
  not exist. When they do, they join the cascade here.
- **The `/resources` JavaScript-disabled limitation.** React streams several of
  that screen's forms into a hidden segment relocated by an inline script. With
  JavaScript enabled — the ordinary case — every control works; with scripting
  fully disabled, several are unreachable. This change **neither fixes nor
  worsens** it; see
  [ADR-041](ADR-041-removing-a-stored-file-or-note.md), which records it.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](ADR-032-learning-resource-catalogue.md) — the record whose rejected RES-005 alternative this reopens
- [ADR-041: Let a learner permanently remove a stored file or a note](ADR-041-removing-a-stored-file-or-note.md) — the two leaf removals this cascade builds on
- [ADR-037: Store the learner's own written notes against a learning resource](ADR-037-learner-written-resource-notes.md) — the notes this removes
- [ADR-040: Store a learner's own PDF files in a local volume, beside their metadata](ADR-040-learner-uploaded-resource-files.md) — the bytes this removes
- [API endpoint catalogue](../api/endpoints.md) — RES-005
- [Database schema](../database/schema.md) — why the foreign keys stay non-cascading
- [Docker strategy](../deployment/docker.md) — what a volume-only restore cannot undo
- [Terminology](../domain/terminology.md) — *remove*, and why it is not *archive*
- [Architecture decisions register](../architecture/decisions.md) — DEC-054
