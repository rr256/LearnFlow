---
title: "ADR-041: Let a Learner Permanently Remove a Stored File or a Note"
status: accepted
owner: architecture-and-ai
last_updated: 2026-08-22
related:
  - ../00-project-context.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-022-plan-adaptation.md
  - ADR-032-learning-resource-catalogue.md
  - ADR-035-practice-question-correction.md
  - ADR-037-learner-written-resource-notes.md
  - ADR-040-learner-uploaded-resource-files.md
  - ../api/endpoints.md
  - ../architecture/decisions.md
  - ../architecture/provider-pattern.md
  - ../domain/entities.md
  - ../domain/domain-model.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../deployment/docker.md
  - ../development/folder-structure.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../roadmap/milestones.md
---

# ADR-041: Let a Learner Permanently Remove a Stored File or a Note

## Status

Accepted — 2026-08-22. Proposed 2026-08-21.

This is the **first capability in LearnFlow that destroys a learner's record.**
Every prior decision in the product refuses to: a superseded plan is kept
([ADR-022](ADR-022-plan-adaptation.md)), a skipped plan item is kept, an asked
question is retired rather than rewritten
([ADR-035](ADR-035-practice-question-correction.md)), material is put aside
reversibly ([ADR-032](ADR-032-learning-resource-catalogue.md)), a note is
archived and its text stays stored
([ADR-037](ADR-037-learner-written-resource-notes.md)), and a stored file's bytes
survive being archived ([ADR-040](ADR-040-learner-uploaded-resource-files.md)).

It adds **RES-018 and RES-019** — two `DELETE` endpoints, each naming exactly one
record — a `remove`/`delete_file`/`delete_note` method on three existing ports,
and one shared confirmation control on `/resources`.

It needs **no migration, no column, and no table.** Deleting a row is a `DELETE`
statement against tables that already exist.

**It is two removals, not a general delete.** RES-005 — removing a whole
resource — stays unimplemented, and nothing here approximates it.

## Context

ADR-040 closed with a consequence it named plainly: *"Nothing is deleted, and
that has a cost. A learner who uploads the wrong file sets it aside; the bytes
remain."* It recorded safe permanent deletion as the next thing the area needed.

The cost arrived immediately. In the first week of real use the project owner
uploaded a PDF against the wrong material, and then registered a resource with
the wrong title and topic. Neither could be undone through the product. The file
could be archived — but archiving is *shelving*, and it still counted against the
20-file ceiling and still occupied the volume. The resource had to be deleted by
hand, in SQL, against the live database. **A product whose only answer to a
mistake is "open a database client" has not answered it.**

The two records this ADR covers are the ones where correction is not available:

- **A stored file cannot be corrected in place.** Its bytes are what it is. A
  learner who picked the wrong document has no edit to make — there is only
  *keep it* or *be rid of it*.
- **A note can be corrected in place**, and usually should be. But a note added
  against the wrong material, or created by a stray double-submit, is not a note
  to rewrite; it is one that should not exist.

Everything else in the product has a reversible answer that genuinely fits, which
is why this ADR does not touch anything else.

### Why archiving is not the answer here

Archiving answers *"I am finished with this for now."* It is a **study decision**,
and its reversibility is the point. Deletion answers *"this should not be in
LearnFlow at all."* Those are different statements, and collapsing them costs
both: a learner who archives to tidy up would find their shelf is really a
deletion queue, and a learner who wants a mistake gone would find it is still
there, still counted, still taking space.

**Both answers therefore stay, side by side, and archiving is offered first.**

## Decision

### Two endpoints, each naming exactly one record

`DELETE /api/v1/resource-files/{file_id}` (RES-018) and
`DELETE /api/v1/resource-notes/{note_id}` (RES-019). Both answer `204` with no
body. Neither accepts a `learner_id`; the effective learner is resolved
server-side, as everywhere else.

**There is no bulk removal and no cascade.** Removing a file leaves its resource,
its topic links, and its notes exactly as they were; removing a note leaves the
material standing. A caller who wants two records gone asks twice.

### Active and archived alike may be removed

The `status` of the file or note is **not consulted**. Shelving and removing are
different answers to the same mistake, and requiring a learner to archive first
would turn the shelf into a deletion queue — the exact conflation the *Context*
above rejects.

**What does refuse is archived *material*.** A file or note whose **resource** is
`archived` is refused with `409`, because archived material is read-only
everywhere in LearnFlow — RES-004's rule, and the same refusal RES-012 and
RES-017 already give. The learner puts the material back, then removes.

A record that is not the learner's, or that is already gone, is `404`. Asking
twice is therefore `204` and then `404`: the second attempt names something that
no longer exists, which is a different statement from a request that changed
nothing.

### Two deliberate actions, and copy that names what is lost

One shared control, `RemoveControl`, serves both. The button sits inside a
**closed `<details>` disclosure**, so removing something takes opening it and then
confirming.

**That disclosure is the confirmation step.** A `window.confirm` was rejected: it
does not exist when JavaScript is switched off, it cannot be styled, and it is
read inconsistently by assistive technology. A `<details>` element opens natively
and the form posts natively, and the "Removing…" pending state is the only part
that needs hydration.

**How far this survives JavaScript being switched off was measured, not assumed,
and the answer is qualified.** The standalone run confirms that the disclosure,
its summary, and every line of the warning copy are **server-rendered**, that the
confirm form and its `$ACTION_*` fields are **served in the document**, and that
posting that form natively — with no client bundle involved — reaches RES-018 and
RES-019 and removes exactly one record.

**What it also found is that React streams most of this page's forms into a
hidden segment.** On the run recorded below, **9 of 13 forms** on `/resources`
arrived inside `<div hidden id="S:n">` with an inline `$RS(...)` script to move
them into place — the remove form among them, and alongside pre-existing controls
from [ADR-032](ADR-032-learning-resource-catalogue.md),
[ADR-037](ADR-037-learner-written-resource-notes.md), and
[ADR-040](ADR-040-learner-uploaded-resource-files.md): *Add to my material*, *Save
changes*, *Save this note*, *Set this PDF aside*, and *Bring this PDF back*. With
scripting fully disabled that relocation never runs, so those buttons are not
reachable.

**In an ordinary browser, with JavaScript enabled, every control on the screen
works** — this one included. That is the case a learner is actually in, and
nothing here degrades it. The limitation below is about the scriptless case
alone.

**This is a pre-existing, page-wide property of `/resources` that this change
neither introduces nor worsens**, and which forms are affected varies between
renders: one verification run recorded 9 of 13, and a second — after two records
had been removed, leaving a smaller page — recorded 8 of 8. It is recorded here
rather than fixed, because fixing it is a change to how the whole screen renders
and belongs to no one feature. **What must not happen is a claim that outruns
it**: say the control is server-rendered and posts natively, not that the screen
is fully usable without JavaScript.

The copy names the item, states that it is permanent, says what is lost, says
LearnFlow keeps no copy, says it cannot be undone, and **points at the reversible
alternative**:

> Removing **Chapter 3.pdf** is permanent. The file and its contents are deleted
> from this computer. LearnFlow keeps no copy, and this cannot be undone.
>
> To keep it but stop using it, set it aside instead — that is reversible.

A **typed confirmation** was considered and rejected: the typing gate can only be
enforced in the browser, so with JavaScript off it silently degrades to a single
click — worse than the disclosure in exactly the case the disclosure was chosen
to survive.

### A row and its bytes cannot be made atomic, so each failure is stated

A note is one row, so removing it has no ordering to get wrong. A **stored file is
a row in PostgreSQL and bytes on a volume**, and a filesystem does not join a
database transaction. The two can be sequenced; they cannot be made atomic.

The order is **row first, bytes second**, both inside the request, with the
provider committing when its block exits. That yields exactly two failures, and
**neither loses the learner's file silently**:

| Failure | What it leaves | How it clears |
| --- | --- | --- |
| The unlink fails | The exception propagates, the provider rolls back, and **nothing is deleted** — row and bytes both survive | The learner asks again |
| The commit fails after the unlink | The row survives with its bytes gone | `read_file` already reports this as a missing file rather than a fault, and asking again removes the row |

**The guarantee offered is that every failure leaves a state the learner can act
on, not that no failure leaves one.** Both are covered by tests, including one
that makes a real unlink raise against a real PostgreSQL database and asserts
that the row and the bytes both survive.

**The row-with-no-bytes state was already reachable and already handled** before
this change: ADR-040 documented it as what a volume restored from a backup older
than the database looks like.

### Nothing is recoverable, and the copy says so

There is **no soft delete, no grace period, no recycle bin, and no copy kept
anywhere**. "Permanent" in the confirmation text is literal.

A soft delete was rejected: it needs a column, a migration, a purge job, and a
rule for whether a removed file still counts against the 20-file ceiling — and it
would make the word *permanent* false while leaving the learner's mistake on
disk, which is the thing they asked to be rid of.

**The only recovery is a backup the learner took themselves**, and even that is
partial: restoring the `resource_files` volume brings back bytes with no row,
which nothing in the product can reach. `docs/deployment/docker.md` says so
rather than implying that a volume copy is an undo.

### The storage adapter deletes one file and never a directory

`LocalResourceFileStorage.remove` validates the key against the shape the module
itself issues **before** joining it to the root — the same guard `read` uses, now
extracted into one `_within_root` helper so there is a single place for it to
drift rather than two, and `remove` is the one where drift would be destructive.

**It never removes a directory.** An empty shard costs nothing, and a routine that
prunes directories is a routine that can delete more than it was asked to.

**A key naming nothing is success, not an error**, because deletion has to be safe
to repeat. **Every other failure raises**, because the exception is what rolls the
row deletion back.

## Alternatives considered

**Leave deletion unbuilt and implement RES-005 instead.** Rejected *for this
change*, not on the merits: RES-005 removes a resource together with its files,
its notes, its topic links, and one day its derived chunks and vectors, which is a
cascade decision of its own. Building the two leaf removals first is the narrower
step, and RES-005 will need them.

**Archive-then-delete.** Rejected — see *Active and archived alike*.

**Soft delete with a grace period.** Rejected — see *Nothing is recoverable*.

**`window.confirm` for the confirmation.** Rejected — see *Two deliberate
actions*.

**A typed confirmation.** Rejected — same section.

**Delete the bytes first, then the row.** Rejected: a failure between the two
would leave a row whose download always fails, and a learner meets that as a
broken record rather than as a retry.

**Commit the row deletion before unlinking, via a post-commit hook.** Rejected for
now, and it is the strongest alternative. It would make the documented ordering
literally true and confine every failure to *stranded bytes*, which is the milder
orphan. It was set aside because it puts a post-commit callback into the
composition root and adds a use-case method that exists only for the provider to
call — real complexity, to convert one rare failure into another rare failure that
is only slightly milder. **Revisit if a commit-after-unlink failure is ever
observed.**

**Report a failed unlink as a success and clean up later.** Rejected: it needs a
reconciliation job that does not exist, and it tells the learner their file is
gone when it is not.

**Delete the empty shard directories too.** Rejected — see above.

## Consequences

**LearnFlow now destroys learner data, in exactly two places.** The rule that
nothing is destroyed no longer holds without qualification, and every document
stating it needs the exception named. That is a real loss of a simple property,
accepted because the alternative was a product that cannot undo a mistake.

**Archiving keeps its meaning.** Because removal is offered beside it rather than
through it, *put aside* still means shelving and stays reversible.

**Three ADRs are narrowed, and none is overturned.** ADR-037's *"Nothing is
deleted"*, ADR-040's *"The lifecycle keeps every byte"*, and ADR-032's *"the
product still has no destructive endpoint"* each gain a dated *Implementation
status* note pointing here; no decision body is rewritten.

**ADR-032's actual position on resources is untouched**, which is the distinction
that matters: *nothing is deleted; material is put aside* was written about a
**resource**, and RES-005 stays unimplemented, so a resource still cannot be
deleted through the product. What is removed here is the **file** and the **note**
kept *against* material — never the material itself.

**ADR-037's correction argument is unaffected.** Nothing derived from a note is
stored, so removing one cannot leave anything orphaned — which is also why a note
was always correctable in place, and why correcting remains the better answer for
a note that merely says the wrong thing.

**A removed file frees a place against the 20-file ceiling**, which archiving did
not. That is the practical difference a learner will notice first.

**A pre-existing limit on `/resources` is now documented rather than assumed.**
Verifying this change measured how much of that screen works with JavaScript
switched off, and found that most of its forms — this change's and every earlier
one's — are streamed into a hidden segment relocated by an inline script. Nothing
here caused it and nothing here fixes it; it is written down so no future record
repeats the claim that the screen is fully usable without JavaScript.

**Backup guidance changes.** A learner who wants an undo needs their own volume
and database copies, taken together, and `docs/deployment/docker.md` now says
what a volume-only restore actually produces.

**`storage_key`, `metadata`, and `resource_ingestions` stay absent.** RES-005 to
RES-008 stay unimplemented. No extraction, OCR, chunking, embedding, indexing,
retrieval, or AI behaviour changes, and no background job is added.

**No functional requirement's verdict moves.** FR-007 stays partly met and FR-008
stays not met; `docs/api/endpoints.md` is authoritative for the count. This change
removes a papercut, not a gap in a requirement.

**RES-005 is still the area's most-needed next change**, and today's evidence
strengthens that: a stray *resource* is the thing a learner still cannot get rid
of.

## Implementation notes

Three ports gain one method each — `ResourceFileStorage.remove`,
`ResourceFileRepository.delete_file`, `ResourceNoteRepository.delete_note` — and
each is documented as **safe to repeat**, because a retry after a partial failure
and a row whose bytes a restore already lost must end in the same place.

Ownership is checked in the use case **before** the repository is asked, so
another learner's record is reported as missing rather than refused: existence is
itself a disclosure. `ManageResourceNotes.delete` reuses the same
`_require_material_in_the_catalogue` guard the other note writes use, so the
archived-material rule cannot drift between them.

The two server actions share `RemoveState`, which is why `RemoveControl` can serve
both. `deleteResourceFile` and `deleteResourceNote` go through a new
`requestNoContent` helper rather than `requestJson`, which parses a body a `204`
does not have.

### Verification

- Backend unit, API, and PostgreSQL integration tests, including both failure
  paths, the shard directories being left behind, and that removing one record
  leaves its neighbours, its resource, and its notes untouched.
- A frontend test asserts the disclosure starts closed, that opening it removes
  nothing, and that the form posts natively rather than through a script.
- A client test asserts that `deleteResourceFile` and `deleteResourceNote` are the
  **only** exported names matching `delete` or `remove`, so a third removal cannot
  arrive unnoticed.
- The JavaScript-disabled standalone run exercises both controls end to end
  against the production standalone build and a contract-shaped stub: 47 checks,
  all passing. It drives each removal by replaying the served form's own fields
  as a scriptless browser would, and asserts from the **stub's** request log —
  not from the page — that exactly one `DELETE` reached exactly one record, that
  rendering the page deletes nothing, and that archived material offers no
  removal at all. It also recorded the streaming finding described above.
- Two harness defects were found and fixed before any of that could be trusted:
  React splits `Remove this {kind}` with a `<!-- -->` comment, and a stored file
  carries **two** forms with a hidden `file_id` — the archive control and the
  remove control — so an early run drove the wrong one and issued a `PATCH`.

### What this deliberately leaves open

- **RES-005** — removing a whole resource, and the cascade it implies.
- **Reclaiming orphaned bytes.** RES-018 deletes the bytes a row names; an orphan
  has no row, so clearing one is a volume operation rather than an API call.
- **Whether a commit-after-unlink failure ever happens in practice**, which is
  what would justify the post-commit hook rejected above.
- **The `/resources` form streaming described under *Two deliberate actions*.**
  It predates this change, affects the whole screen, and needs a decision about
  how that page renders rather than a change to either removal.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](ADR-032-learning-resource-catalogue.md) — *put aside*, and why RES-005 stays unimplemented
- [ADR-037: Store the learner's own written notes against a learning resource](ADR-037-learner-written-resource-notes.md) — narrowed here on its "nothing is deleted" clause
- [ADR-040: Store a learner's own PDF files in a local volume, beside their metadata](ADR-040-learner-uploaded-resource-files.md) — narrowed here on its "the lifecycle keeps every byte" clause
- [ADR-022: Adapt a Study Plan by Rebuilding It Around What Happened](ADR-022-plan-adaptation.md) — the keep-everything position this is the exception to
- [ADR-035: Let a practice question be corrected until a quiz has asked it](ADR-035-practice-question-correction.md) — correcting versus setting aside, decided for questions
- [API endpoint catalogue](../api/endpoints.md) — RES-018 and RES-019
- [Database schema](../database/schema.md) — the lifecycle of `resource_files` and `resource_notes`
- [Docker strategy](../deployment/docker.md) — what a volume-only restore produces
- [Terminology](../domain/terminology.md) — *remove*, and why it is not *archive*
- [Architecture decisions register](../architecture/decisions.md) — DEC-053
