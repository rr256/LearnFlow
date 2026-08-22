---
title: "ADR-040: Store a Learner's Own PDF Files in a Local Volume, Beside Their Metadata"
status: accepted
owner: architecture-and-ai
last_updated: 2026-08-22
related:
  - ../00-project-context.md
  - ADR-002-provider-pattern.md
  - ADR-009-configuration-naming-and-validation.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-032-learning-resource-catalogue.md
  - ADR-037-learner-written-resource-notes.md
  - ADR-038-local-topic-note-retrieval.md
  - ADR-039-source-grounded-study-answers.md
  - ADR-041-removing-a-stored-file-or-note.md
  - ADR-042-removing-a-whole-resource.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../architecture/dependency-rules.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../deployment/docker.md
  - ../deployment/environments.md
  - ../domain/terminology.md
  - ../rag/ingestion.md
  - ../rag/overview.md
  - ../architecture/provider-pattern.md
  - ../domain/entities.md
  - ../domain/domain-model.md
  - ../requirements/functional.md
  - ../requirements/non-functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-040: Store a Learner's Own PDF Files in a Local Volume, Beside Their Metadata

## Status

Accepted — 2026-08-21. Proposed 2026-08-20.

This is the **first file LearnFlow stores**. A learner chooses one or more PDFs in
a file picker, LearnFlow validates each, keeps the bytes in a Docker named volume
on the backend, records what describes them in PostgreSQL, lists them on
`/resources`, and hands them back on request.

It adds **RES-014 to RES-017**, a `resource_files` table with migration
`20260821_01`, a named volume `resource_files`, two dependencies, and file
controls on `/resources`.

**Upload and store, and nothing else.** Nothing is extracted, OCR'd, chunked,
embedded, indexed, retrieved, or sent to a model; no URL is fetched and no
background job runs.

**Nothing is deleted.** Safe permanent deletion is recorded as a future feature —
see *Consequences*.

## Context

[ADR-032](ADR-032-learning-resource-catalogue.md) built a catalogue that records
**where material is**, never the material, and kept out three things: uploaded
files, fetched web content, and locations on the learner's own machine.

[ADR-037](ADR-037-learner-written-resource-notes.md) narrowed the first of those
for text the learner **typed themselves**, and said plainly that files stayed
out. [ADR-038](ADR-038-local-topic-note-retrieval.md) made those notes findable
and [ADR-039](ADR-039-source-grounded-study-answers.md) let a local model answer
from them.

This is the change that narrows the file clause. The reason is
[FR-007](../requirements/functional.md#fr-007-learning-resource-organization)'s
first criterion — *"the learner can register PDFs…"* — which the catalogue has
only ever met as a **description** of a PDF sitting somewhere else.

**Two of ADR-032's three exclusions stay exactly as they were.** Nothing is
fetched from the web, and **no location on the learner's machine is stored**: a
browser hands over bytes and a display name, never a path, and LearnFlow could
not learn one if it tried.

### The approved schema does not fit

`docs/database/schema.md` anticipated stored files, and put `storage_key` and
`metadata` on **`resources` itself** — one file per resource. A learner keeps a
textbook chapter, a problem set, and three past papers against one piece of
material, which a 1:1 column pair cannot hold.

Those two columns therefore stay **uncreated**, as they have been since
`20260816_01`, rather than being half-built into a shape they cannot support.

## Decision

### A table, not two columns

`resource_files` holds one row per stored file: `storage_key`,
`original_filename`, `byte_size`, `page_count`, `content_type`, `checksum`,
`status`, and the resource it belongs to.

**It carries no owner column and no topic links.** A file hangs off a resource,
the resource carries the owner and the topics, and duplicating either would
create a second place for them to disagree.

This is the **third addition beyond the schema document's approved set**, after
`questions.author_learner_id` (a column) and `resource_notes` — and the **second
whole table**.

### Bytes on a volume, metadata in PostgreSQL

The bytes live in a Docker **named volume**, `resource_files`, mounted at
`/var/lib/learnflow/resources` **into the backend service alone** — not the
frontend, which never reads a file, and not `postgres`, whose data this must stay
separable from.

**A `bytea` column was rejected.** Binaries bloat every dump and every backup,
and the two halves are better backed up by their own means.

**The stored name is a server-generated identifier, sharded two levels**
(`ab/cd/<uuid>.pdf`). A filename from a browser is untrusted input: used as a
path it invites traversal, collisions, reserved Windows names, and unicode
surprises. The learner's own name is metadata in PostgreSQL, where it is data
rather than a location.

### What is accepted

Four gates, all server-side and all before anything is written: the name ends
`.pdf`, the bytes begin `%PDF-`, `pypdf` parses the document, and it is **not
encrypted**. At most **25 MB**, **1500 pages**, and **20 files per resource**.

**The size check runs while the upload streams**, between chunks, so an oversized
request is refused without ever being held in full.

**An encrypted PDF is refused rather than stored.** Keeping a document LearnFlow
can never open would be storing something on a promise it cannot meet.

**A refused upload writes nothing** — no row and no bytes — and **no refusal
echoes the filename** or any byte of the file.

### The lifecycle keeps every byte

A file is `active` or `archived`. Archiving is the learner setting it aside and is
**reversible**; the bytes stay either way. Archiving the **resource** makes its
files read-only — no upload, no status change — while leaving them **listed and
downloadable**, because hiding a learner's own file from a list is not a reason to
withhold it from them.

### Downloads are proxied and ownership-checked

The browser asks a Next.js route, which calls the API server-side, so **no API
address is browser-visible** — ADR-015's guarantee, kept for files. The backend
resolves the effective learner and reports another learner's file as `404`.

The response is `Content-Disposition: attachment` with
`X-Content-Type-Options: nosniff`, so the browser **saves** the PDF rather than
rendering it in LearnFlow's origin. A PDF is an active-content format, and not
rendering it in-origin is the mitigation this build offers.

### Two dependencies

`python-multipart`, without which FastAPI cannot parse an upload at all, and
`pypdf` — pure Python, no system libraries — for the page count and the
encryption check. **`pypdf` is never asked to extract text**, and a test asserts
the adapter contains no such call.

## Alternatives considered

**Use `resources.storage_key` and `resources.metadata` as approved.** Rejected: it
caps a resource at one file, which is not what a learner has, and `metadata` as
free-form `jsonb` validates nothing.

**Store bytes in PostgreSQL as `bytea`.** Rejected: one backup story instead of
two, at the cost of bloating every dump and every restore with binaries.

**Bind-mount a host directory instead of a named volume.** Rejected: files would
be directly visible in Explorer, which is convenient, but it risks committing a
learner's PDFs and drags in NTFS permission and path-length problems.

**Accept encrypted PDFs and store them opaquely.** Rejected — see above.

**Render the PDF inline in the browser.** Rejected: nicer to read, and it renders
learner-supplied active content in LearnFlow's own origin.

**Scan uploads for malware.** Not done, and *stated* rather than implied. It would
need a scanner, a signature feed, and a quarantine state; the mitigations this
build offers instead are that LearnFlow never executes a PDF, never renders one
in-origin, and reads only its structure.

**Extract text on upload.** Deliberately out of scope. It is a separate decision
with its own storage, privacy, and correctness questions, and this change is
already the largest surface the resource area has gained.

## Consequences

**FR-007's first criterion is now met for PDFs.** A learner can register a PDF as
a *file* rather than as a description of one. References and paths to local
**video** resources are still carried by `source_label` in words, so **FR-007 is
not met in full**; `docs/api/endpoints.md` is authoritative for the count.

**Backup is now two things.** A `pg_dump` alone is **no longer a complete backup**
of a learner's material: the rows are in PostgreSQL and the bytes are in the
volume, and restoring one without the other leaves rows naming files that are not
there. LearnFlow reports that state honestly — a download returns `404` and the
row stays listed — rather than deleting the record.

**The volume survives normal operation and one command destroys it.** It is
untouched by `docker compose down`, by an image rebuild, and by container
recreation. **`docker compose down -v` deletes it**, along with `postgres_data`,
which is why that is not a routine stop command.

**The backend image now creates the storage directory and owns it.** A named
volume is initialised from the image's directory, ownership included; without
that, a fresh volume would be root-owned and the unprivileged process could not
write a single file. This was found by the Docker check, not by reasoning.

**No malware scanning is performed**, and the documentation says so.

**Nothing is deleted, and that has a cost.** A learner who uploads the wrong file
sets it aside; the bytes remain. **RES-005 — safe permanent deletion — is
recorded as the next feature this area needs**, and it must coordinate rows and
bytes together, since a file is now the first learner data that can outlive its
row.

**Terminology changes.** The avoid-list row forbidding *upload* is narrowed: a
learner **does** upload a PDF now. The rest of that row stands — nothing is
fetched from the web, and no path on their machine is stored.

**`resource_ingestions` stays absent**, RES-006 to RES-008 stay unimplemented, and
no retrieval, note, or mentor behaviour changes.

## Implementation status

**2026-08-22 — removing a resource now removes its stored files and their bytes.**

[ADR-042](ADR-042-removing-a-whole-resource.md) implements **RES-005**. Where RES-018 removes one
file the learner named, this removes every file a resource holds together with the resource — and so
clears more bytes from the volume at once than anything else in the product.

**The ordering this record established is reused and extended.** The storage keys are read *before*
any row is deleted, because once the rows are gone nothing can name the files; the bytes are unlinked
last; a failed unlink rolls the whole removal back; and a commit failing after one leaves the
row-with-no-bytes state this record already documented as a handled `404`. **An archived file is
removed with its resource** like any other, because a shelved file still occupies the volume.

**Every other decision in this record stands**, and its decision body is not rewritten.

**2026-08-21 — a stored file can now be removed permanently, and "the lifecycle keeps every byte" is
narrowed.**

[ADR-041](ADR-041-removing-a-stored-file-or-note.md) adds **RES-018**: a learner may permanently
remove one stored file, row and bytes together. It is irreversible, LearnFlow keeps no copy, and
there is no soft delete.

**Two statements in this record are narrowed, and neither is rewritten.** Its `## Status` section
closes with **"Nothing is deleted."** — a file may now be removed permanently — and *Consequences* above
says "Nothing is deleted, and that has a cost… **RES-005 — safe permanent deletion — is recorded as
the next feature this area needs**." The cost was met in the first week of real use, and what shipped is
narrower than RES-005: two **leaf** removals, one per record, with no cascade. **RES-005 itself stays
unimplemented**, and now waits only on the cascade it implies rather than on a reason to delete.

**Archiving keeps its meaning.** Setting a file aside is still reversible, still leaves the bytes in
the volume, and is still what the screen offers first. A file's own status is not consulted when
removing, because shelving and removing are different answers to the same mistake — but archived
**material** refuses removal with `409`, exactly as it refuses every other write here.

**The row-with-no-bytes state this record documented is now load-bearing.** *Consequences* above
already recorded that a volume restored from an older backup leaves rows naming files that are not
there, and that LearnFlow reports it honestly with a `404`. That handled state is what makes the one
imperfect removal failure recoverable: a commit failing after an unlink leaves exactly it, and asking
again clears the row.

**Backup guidance gains a limit.** A backup was already necessary; it is now explicitly **not an
undo**, because restoring the volume alone returns bytes with no row that nothing in the product can
reach. See [the Docker strategy](../deployment/docker.md).

**Everything else this record decided is unchanged**: what is accepted, the volume, the ownership
checks, the proxied download, the two dependencies, and the absence of extraction, OCR, scanning, and
`resource_ingestions`. It needed **no migration**, and `20260821_01` is unaltered.

**The decision below is not rewritten**, and none of its reasoning is withdrawn.

## Implementation status

**2026-08-21 — the upload now reports that it is working.**

[NFR-003](../requirements/non-functional.md) requires that a large upload show an
understandable in-progress, completed, or failed state. It did not. A 25 MB file
is sent to the Next.js server, forwarded to the API, checked against four rules
and parsed for its page count before anything comes back — and the screen said
nothing for all of it, which reads as a broken page rather than as work in
progress.

The upload control now reports **Adding…**, disables itself while the request is
in flight, and shows a line in an `aria-live` region so the state is announced
rather than only shown. The archive and restore control does the same. A stored
file's confirmation now says where to find it.

**This changes no rule and no contract.** It is presentation only: no limit, no
validation gate, no status, and no endpoint moves. **With JavaScript switched off
none of it runs** — the form posts natively and the page reloads with the result,
exactly as before.

**2026-08-21 — "refuse encrypted PDFs" is narrowed to "refuse what cannot be
opened", and `cryptography` is added.**

This record decided that an encrypted PDF is refused, *because keeping a document
LearnFlow can never open would be a promise it cannot meet*. That reason is kept,
and the rule now follows it exactly.

**Most encrypted study material is not locked.** A publisher or scanned PDF is
commonly encrypted with an **empty** user password and carries only permission
restrictions — no printing, no copying. It opens in any reader, and LearnFlow can
read and store it like any other file. Only a document that genuinely needs a
password cannot be opened, and only that is refused.

The adapter now attempts an **empty password** on an encrypted document. Success
means readable; failure — including a missing crypto backend — means locked, so an
undecidable file is treated as locked rather than assumed readable. **Nothing is
decrypted on disk**: the attempt unlocks the in-memory reader to read a page
count, and the bytes stored are the learner's original file, unchanged.

**`cryptography` is added** as a runtime dependency, approved at Stop Gate 1. It is
optional to `pypdf`, and without it an AES document raises `DependencyError`
*from inside the parser* rather than reporting whether it is readable.

**That raise was also a defect, and is fixed.** `DependencyError` extends
`Exception` rather than `PyPdfError`, so a tidy tuple of named pypdf exceptions
let it escape: an AES-encrypted PDF became an unhandled error and the learner met
*"An unexpected error occurred"*. The inspector now answers **any** parser
failure with the same refusal, which is the correct boundary for code reading a
file LearnFlow did not produce.

**Everything else this record decided stands**: the limits, the other three
validation gates, the storage design, the lifecycle, and the refusal message for a
genuinely password-protected file.

**2026-08-21 — the framework's own body limit had to be raised.**

Next.js caps a **server-action request body at 1 MB** by default. The upload goes
through a server action, so every PDF above that was rejected by the framework
before reaching any LearnFlow code: the learner saw an unstyled *"This page
couldn't load"* page, and the backend never saw the request at all. The 25 MB
limit this record decided was therefore unreachable in practice.

`next.config.ts` now sets `experimental.serverActions.bodySizeLimit` to **26 MB**,
deliberately **above** `MAX_FILE_BYTES` rather than equal to it: the backend must
be the thing that refuses an oversized file, because it is the only place that can
say so in words a learner can act on. The headroom covers multipart framing.

**Nothing this record decided changes.** The limits, the validation gates, the
storage design, and the lifecycle are all as written; what was wrong was a
framework default sitting in front of them.

**Why no test caught it.** Every fixture and every driver used a PDF of a few
kilobytes — the one size at which the default never bites. A test now asserts the
configured limit clears `MAX_FILE_BYTES`, and the JavaScript-disabled run was
repeated with a real 3 MB file.

**A second defect surfaced immediately behind it, and is fixed too.** Raising the
framework limit moved the cliff without removing it: a file over the limit was
still refused by the framework *before* any action code ran, so the size check in
the submission reader never executed and the learner met an unexplained error
rather than a message naming the rule. The size is now checked **in the browser,
on the chosen file, before anything is sent**, which is the only place that can
name it; an over-large file disables the submit control and says how large it is
against the limit.

That check is a **courtesy, not the rule** — the backend still refuses whatever a
browser allowed. **With JavaScript switched off it does not run**, so a file above
`bodySizeLimit` still meets the framework's own error there. That degradation is
accepted and recorded rather than hidden: the no-JavaScript path keeps working for
every file the feature actually supports.

## Implementation notes

- **Migration `20260821_01`** — one CREATE TABLE and one index; additive, altering
  nothing. Its downgrade drops the table and **leaves the bytes in the volume**,
  which is the honest asymmetry: a downgrade that deleted a learner's files to
  undo a schema change would be worse than leaving reclaimable orphans.
- **Application** — `dto/resource_file.py`, `ports/resource_file_storage.py`
  (three ports: bytes, structure, rows), `use_cases/manage_resource_files.py`.
- **Infrastructure** — `storage/local_file_storage.py`, a new package and **the
  only filesystem-touching code in the backend**; `persistence/resource_file_repository.py`.
- **Presentation** — `api/schemas/resource_file.py`, `api/routes/resource_files.py`.
  `storage_key` appears in **no** response schema, which is what keeps the
  no-filesystem-path rule true by construction.
- **Configuration** — `RESOURCE_STORAGE_PROVIDER` and `RESOURCE_STORAGE_PATH`,
  both catalogued as planned since ADR-009 and now read.
- **Frontend** — `types/resource-file.ts`, `features/resources/ResourceFiles.tsx`,
  its server actions and submission reader, and
  `app/resources/files/[fileId]/route.ts`, which proxies the download.

### Verification

- Backend `pytest -W error`, `ruff check`, and `ruff format --check` pass.
- **PostgreSQL integration tests** against a disposable database exercise the
  whole path with a **real filesystem** and a **real `pypdf`**: a genuine PDF
  round-trips, a truncated one and an encrypted one are refused with nothing
  written, and the table's constraints hold.
- **Migration upgrade, downgrade, and upgrade again** verified; the other three
  resource tables are untouched by the downgrade.
- **Docker volume persistence** verified three ways: a marker survives container
  removal, survives an image rebuild, and a **fresh** volume is writable by the
  unprivileged user.
- Frontend lint, typecheck, tests, and `next build` pass.
- The screen was driven against the production standalone server **with
  JavaScript disabled**, including a native multipart upload.

### What this deliberately leaves open

- **RES-005**, safe permanent deletion, now the most-needed next step.
- **Text extraction, `resource_ingestions`, and RES-006 to RES-008.**
- **Malware scanning.**
- **Non-PDF files.** `image` and `attachment` stay approved-but-unwritten.
- **A learner-scoped file endpoint.** `/resources` reads one list per resource,
  which a large catalogue would want replaced.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-032: Learning resource catalogue](ADR-032-learning-resource-catalogue.md)
- [ADR-037: Learner-written resource notes](ADR-037-learner-written-resource-notes.md)
- [Database schema](../database/schema.md)
- [API endpoints](../api/endpoints.md)
- [Docker strategy](../deployment/docker.md)
- [Environments](../deployment/environments.md)
- [Terminology](../domain/terminology.md)
- [Architecture decisions](../architecture/decisions.md)
