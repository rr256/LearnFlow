---
title: "ADR-037: Store the Learner's Own Written Notes Against a Learning Resource"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-22
related:
  - ../00-project-context.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-022-plan-adaptation.md
  - ADR-026-monthly-study-view.md
  - ADR-032-learning-resource-catalogue.md
  - ADR-033-checkpoint-practice-workflow.md
  - ADR-035-practice-question-correction.md
  - ADR-036-topic-material-on-the-plan-screens.md
  - ../rag/overview.md
  - ../rag/ingestion.md
  - ../rag/embeddings.md
  - ../rag/retrieval.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../domain/entities.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../requirements/non-functional.md
  - ../development/coding-standards.md
  - ../roadmap/milestones.md
  - ADR-039-source-grounded-study-answers.md
  - ADR-040-learner-uploaded-resource-files.md
  - ADR-041-removing-a-stored-file-or-note.md
  - ../architecture/decisions.md
---

# ADR-037: Store the Learner's Own Written Notes Against a Learning Resource

## Status

Accepted — 2026-08-19. Proposed 2026-08-19.

This is the **first RAG foundation**: the first thing LearnFlow stores that a mentor could one day
be grounded in. Learner-written **practice questions** are stored text too
([ADR-033](ADR-033-checkpoint-practice-workflow.md)), so the claim is narrow and deliberate: a
question is something the learner *made* to test themselves, while a note is material they
*study from*, and only the second is what retrieval would ever draw on. It is deliberately **storage and nothing else**. Nothing here uploads a file, fetches
an address, downloads a page, extracts text from a document, runs OCR, chunks, embeds, indexes,
searches across notes, ranks, recommends, or answers a question, and no AI provider, embedding
provider, or vector store is reached or configured.

It adds **RES-009 to RES-012**, one table (`resource_notes`), and migration `20260819_01`. It changes
no existing endpoint, no existing table, and no existing screen apart from `/resources`.

**FR-007's four acceptance criteria are unchanged**, and
[endpoints.md](../api/endpoints.md#fr-007-acceptance-criteria) stays authoritative for the count: this
adds a capability beside them rather than completing one. **FR-008 is not met at all** and this
record does not claim otherwise — every one of its criteria needs retrieval and a mentor, neither of
which exists. Do not write that either requirement is complete.

## Implementation status

**2026-08-21 — a note can now be removed permanently, and "nothing is deleted" is narrowed.**

[ADR-041](ADR-041-removing-a-stored-file-or-note.md) adds **RES-019**: a learner may permanently
remove one note they added by mistake. It is irreversible, LearnFlow keeps no copy, and there is no
soft delete.

**This record's archiving decision stands.** *Put aside* is still reversible, still keeps the text
stored, and is still what the screen offers first; removing is a separate, deliberate request behind
a closed disclosure and never a consequence of a status change.

**Three statements below are narrowed, and each is named here rather than rewritten in place.** The
`### Nothing is deleted` section is the first. The second is its claim that *"There is no `DELETE`
endpoint and **no removal method on the repository port**, so none can be reached by mistake"* —
RES-019 adds both, deliberately: `ResourceNoteRepository.delete_note` exists, and the safeguard is
now the two-step control and the ownership check rather than the absence of a method.

The third is the rejected alternative **"Offer a real delete"**, which this record set aside because
"nothing implemented in LearnFlow deletes a learner's record" and told the reader to **revisit it with
RES-005**. [ADR-041](ADR-041-removing-a-stored-file-or-note.md) revisited it **earlier and on
narrower terms**: two *leaf* removals with no cascade, rather than the resource-wide deletion RES-005
still describes. The precedent concern that argued for waiting is answered by the narrowness — a note
and a file are the two records that cannot be corrected in place — not withdrawn.

**This record's correction argument is untouched, and RES-019 depends on it.** Nothing derived from a
note is stored — no chunk, no embedding, no cached extract, no search history — which is why a note
stays correctable in place, and equally why removing one leaves nothing orphaned: the row is all there
is. **Correcting remains the better answer** for a note that merely says the wrong thing; removal is
for one that should not exist.

**Everything else this record decided is unchanged.** A note is still text the learner typed or
pasted themselves, still stored as written, still rendered as plain text, still bounded at 20,000
characters and 200 a resource, and still inherits its resource's topics. It needed **no migration**.

**The decision below is not rewritten**, and none of its reasoning is withdrawn.

## Implementation status

**2026-08-21 — uploaded PDFs are now stored too, so notes are no longer the only kind.**

[ADR-040](ADR-040-learner-uploaded-resource-files.md) adds **stored files**: a learner uploads PDFs against a piece of catalogued material and LearnFlow keeps the bytes locally.

**This record's "first study material LearnFlow stores rather than points at" stands** — a note was first, and remains the only material anything *reads*. What has moved is "deliberately the only kind": an uploaded PDF is the second.

**Everything this record decided about a note is untouched.** A note is still text the learner typed or pasted themselves, still stored as written, still rendered as plain text, still bounded at 20,000 characters and 200 a resource, still corrected in place, and still archived rather than deleted. **Nothing about a stored file changes any of that**, and no note is derived from a file: nothing extracts text from a PDF, so a stored file produces no note and never will under this change.

**The decision below is not rewritten**, and none of its reasoning is withdrawn.

**2026-08-19 — a local AI model now reads a learner's notes, when they ask.**

[ADR-039](ADR-039-source-grounded-study-answers.md) adds **MNT-001**: a learner asks a question about
one curriculum topic and receives an answer built from passages in their own notes.

**This narrows the privacy promise once more**, in the same direction
[ADR-038](ADR-038-local-topic-note-retrieval.md) already narrowed it. ADR-038 named one reader — a
topic search, local, only when asked — and rewrote the note form to say *"no AI model ever sees
them."* **That clause is now false and has been rewritten.** A model does see a learner's notes: the
passages retrieval selected, on this machine, when they ask a question. It is given **passages and
never a whole note**, and no identifier of any kind.

**The correction argument below is untouched.** Nothing derived from a note is stored — no chunk, no
embedding, no cached extract, no question, no answer, and no history — so a note may still be
corrected in place however often the learner likes, and no stored record can disagree with the
correction.

**Nothing else in this ADR changes.** Notes are still stored as written, still bounded at 20,000
characters and 200 a resource, still archived rather than deleted, still read-only on archived
material, and still rendered as plain text.

**2026-08-19 — a learner's notes can now be searched, locally and only when they ask.**

[ADR-038](ADR-038-local-topic-note-retrieval.md) adds RES-013: a learner chooses a curriculum topic
and sees passages from their own notes. It **narrows this record's `nothing reads a note` on one
point**, and the distinction matters, because that sentence was doing two jobs here.

**The privacy promise is narrowed.** The note form no longer says *"nothing reads it"*; it says the
text is stored on this computer, never sent anywhere, read by nothing except a topic search that runs
locally and only when asked, and seen by no AI model. Everything else this record decided stands:
nothing is uploaded, fetched, extracted, chunked, embedded, or indexed into a vector store, and
`storage_key`, `metadata`, and `resource_ingestions` remain absent.

**The correction argument is untouched.** *"Nothing reads a note, so no stored record can be made to
disagree with a correction"* remains true as written, because the search **stores nothing derived from
a note** — no chunk, no embedding, no cached extract, and no search history. It reads at the moment it
is asked, so a corrected note simply changes what the next search finds. A note therefore stays
correctable in place, which is still where it differs from
[ADR-035](ADR-035-practice-question-correction.md).

**One verdict below has moved.** This record's Status says *"FR-008 is not met at all"*, and that is no longer true: one of its six criteria is now **partly** met, by the retrieval half of RES-013. FR-007 is unchanged, and
[endpoints.md](../api/endpoints.md#fr-008-acceptance-criteria) stays authoritative for both counts.

**The decision below is not rewritten**, and none of its reasoning is withdrawn.

## Context

[ADR-032](ADR-032-learning-resource-catalogue.md) opened [Milestone 4](../roadmap/milestones.md#milestone-4-resources-rag-and-mentor)
with a catalogue that records **where a learner's material is** and deliberately not the material.
That was the right first step, and it left an obvious gap: a learner can say *"my Operating Systems
notes are in the blue binder, chapter 3"*, and LearnFlow holds nothing they can read.

The next item in that milestone is *"supported text-based PDF can be extracted and indexed"*, which
needs file storage, an extractor, a chunking policy, an embedding provider, and a vector store — five
new pieces of infrastructure, each replaceable, each with its own failure modes, and none of them
built. This change asks a much smaller question, and answers only that one:

**Can a learner keep their own written notes and copied-out passages against a piece of material?**

That question needs no file, no provider, and no pipeline. The learner types or pastes; LearnFlow
stores what they wrote.

### One finding shaped the whole decision

**The approved documentation said the opposite of what this feature does.**

[terminology.md](../domain/terminology.md) lists *"a resource's contents"* on its **avoid** list, with
the reason: *"A learning resource is a record of **where material is**, never the material: nothing is
uploaded, downloaded, extracted, or indexed. Wording that implies LearnFlow holds a copy describes a
capability that does not exist."* [ADR-032](ADR-032-learning-resource-catalogue.md) says the same in
its own words, and [entities.md](../domain/entities.md) repeats it.

That rule was written to keep three things out, and each of them stays out:

1. **Uploaded files**, which need storage that does not exist.
2. **Fetched or scraped web content**, which is somebody else's material and somebody else's licence.
3. **A location on the learner's own machine**, which no resource endpoint may return.

Storing text the learner **typed themselves** trips none of the three. It is not a file, it did not
come off the web, and it names no path. The rule is therefore **narrowed rather than overturned**,
and the reasoning behind it is left intact — the shape [ADR-036](ADR-036-topic-material-on-the-plan-screens.md)
used when it amended ADR-032's *"the plan screens are untouched"* sentence, and
[ADR-035](ADR-035-practice-question-correction.md) when it narrowed ADR-033's rule on correcting a
question.

The project owner decided this, and seven other questions, before anything was built.

### The approved schema had nowhere to put it

The *Resources and RAG metadata* area of [schema.md](../database/schema.md#resources) holds
`resources`, `resource_topic_links`, and `resource_ingestions`. The area anticipated **derived**
representations of learner material — chunks and embeddings in a vector index, with
`resource_ingestions` tracking the extraction that produced them.

Text a learner typed is neither derived nor a file. `resource_ingestions` tracks a process that never
ran; there is nothing to extract from a note, and no ingestion status it could honestly carry. So no
approved table could hold it, and this change **adds one beyond the approved schema** — the second
time this repository has done so, after `questions.author_learner_id` in migration `20260818_01`,
which [the assessment area review](../database/schema.md#assessment-area-review-2026-08-18) records.

## Decision

### A resource note is the learner's own text, kept against one resource

The canonical term is **resource note**: text the learner typed or pasted themselves — their own
notes on a piece of study material, or a passage they transcribed from it — belonging to exactly one
learning resource.

A note **carries no topic links of its own**. It inherits the topics its resource covers, so a
learner correcting what a resource covers moves its notes with it and the two can never disagree.
Linking notes to topics directly was rejected for the same reason: it would create a second place
the same claim is made, and a note with no material behind it is a different feature.

`terminology.md`'s avoid-list row is narrowed to **files and fetched content**, which is what it was
protecting against. Every sentence it keeps stays true: nothing is uploaded, downloaded, extracted,
or indexed, and no location on the learner's machine is stored.

### It stores text and does nothing else with it

This is the boundary, and it is stated positively so that crossing it is visible:

- **No file input, no upload, no `storage_key`, no `metadata`, no `resource_ingestions`.** All three
  absent columns and the absent table stay absent, exactly as ADR-032 left them.
- **No address is fetched.** Nothing downloads a page, follows a link, scrapes a site, or reads a
  file from the learner's machine. `external_reference` still holds a web address that a *learner*
  clicks, and nothing server-side ever requests it.
- **No chunking, embedding, indexing, or retrieval.** No `EmbeddingProvider`, no vector store, no
  ChromaDB service, and no similarity search. The `chromadb` Compose service still does not exist.
- **No AI provider.** The mentor does not exist, MNT-001 and MNT-002 stay unimplemented, and nothing
  reads a note at all.
- **No search across notes**, which would be retrieval with a different name.

`ManageResourceNotes` binds three repositories and **no provider**, so a note has no path out of the
process. A unit test asserts exactly that, so adding an AI, embedding, or retrieval port to that
constructor is a visible decision rather than a quiet one — which is what NFR-001 asks for.

### The text is stored as the learner wrote it

Two things happen to it and **nothing else**: line terminators are canonicalised to `LF`, and
surrounding whitespace is removed. Line breaks, blank lines, indentation, and non-ASCII characters
survive to the database and back.

**Canonicalising line terminators is not rewriting what the learner wrote** — it undoes a choice the
*transport* made. The HTML form-data encoding algorithm normalises newlines to `CRLF`, so a form
posted with JavaScript disabled delivers `CRLF` where the same note submitted through a hydrated
server action delivers `LF`. Without it, one note would be stored two different ways depending on
whether a browser ran JavaScript, and a learner who wrote a note one way and corrected it the other
would find the stored text changing under them. A `CRLF` and an `LF` are the same line break, and the
learner sees no difference either way.

**This was found by the production standalone run with JavaScript disabled**, which is the only check
that submits a real multipart form; 873 frontend tests and the whole backend suite passed over it.

[ingestion.md](../rag/ingestion.md)'s normalisation step — collapsing whitespace and stripping
extraction noise — is deliberately **not** applied: it belongs to a pipeline reading files, and
rewriting what a learner typed would change what they wrote. Nothing here touches a character the
learner can see.

### Notes are read and written on `/resources` and nowhere else

Each note sits in a **closed disclosure** on the catalogue, so a piece of material with several long
notes stays as scannable as one with none.

The curriculum view, `/revisions`, `/plan`, and `/plan/today` go on showing a topic's material
**unchanged** — title, kind, where it is — and gain **no** note text. `/plan/month` still shows no
material at all. Those screens exist to help a learner *find* their material; pages of text under
every item would bury exactly what they are for, which is the reasoning
[ADR-036](ADR-036-topic-material-on-the-plan-screens.md) used to keep material off the monthly view
entirely.

### Stored text is rendered as text

The body is interpolated into JSX, which escapes it. **Nothing calls `dangerouslySetInnerHTML`,
parses Markdown, or interprets the content in any way**, and CSS `white-space: pre-wrap` — not
generated `<br>` elements — is what preserves the learner's line breaks. A pasted `<script>` tag is
therefore something a learner reads, never something a browser runs. A component test asserts it.

### Nothing is deleted

A note the learner is finished with is `archived`, and archiving is **reversible**. There is no
`DELETE` endpoint and no removal method on the repository port, so none can be reached by mistake.
That is ADR-022's position for a superseded plan, ADR-032's for a resource, and ADR-033's for a
question, applied to the text kept against one.

**Material that is put aside is read-only, notes included.** A learner puts the material back before
writing or correcting a note on it, which is RES-004's rule for archived material and
[ADR-035](ADR-035-practice-question-correction.md)'s for a retired question. Both refusals are `409`,
and both are read from **what is stored**, never from the request. The notes of archived material
stay **readable**: putting material aside stops it being written to and hides nothing.

### A note is corrected in place, however often the learner likes

This is where a note differs from a practice question. ADR-035 fixes a question's wording once a quiz
has asked it, because a stored attempt is assembled from the live row and rewriting the prompt would
rewrite a result the learner has already read. **Nothing reads a note**, so no stored record can be
made to disagree with a correction, and no such rule is needed.

### The bounds, and why they exist

- **20,000 characters per note** — roughly eight pages. Generous for a transcribed passage, and
  bounded.
- **200 notes per resource.** A bound on one note is no bound at all without a bound on their number.
  Notes put aside are counted towards it, because a bound that ignored them could be stepped around
  by archiving.

`body` is unbounded `text` in the column, as schema.md requires of learner-facing prose, so **raising
either bound later is a use-case change rather than a migration** — the argument ADR-020 made for
`plan_items.status`. What the table enforces is only that a note is not empty.

**This is the one field in LearnFlow a form can fill without limit**, which is why it is the one that
needed a limit.

### A refusal never echoes the learner's text

[conventions.md](../api/conventions.md) forbids echoing a rejected value in any error. That rule
matters more here than anywhere else in the product, because the value is the learner's own study
material — a refusal that quoted it would put it in a log, a proxy trace, and a browser console.
Every refusal names the field and the rule and quotes nothing. Both the use-case tests and the API
tests assert it.

### The contract

Four endpoints, extending the RES family because a note is reached through its resource:

| ID | Method and path |
| --- | --- |
| RES-009 | `POST /api/v1/resources/{resource_id}/notes` |
| RES-010 | `GET /api/v1/resources/{resource_id}/notes` |
| RES-011 | `GET /api/v1/resource-notes/{note_id}` |
| RES-012 | `PATCH /api/v1/resource-notes/{note_id}` |

Nested for creating and listing, flat for reading and correcting one — the shape RES-006 to RES-008
already sketch for ingestions. **No request accepts a `learner_id`**: the effective learner is
resolved server-side, and a note's owner is its resource's owner. A note whose material belongs to
somebody else is reported as **missing**, not forbidden, the rule every learner-owned read follows.

### The RAG documents record the file-free path

[ingestion.md](../rag/ingestion.md)'s approved lifecycle begins *register → validate → store the
original file → extract text*, and pasted text skips all four steps. Both it and
[overview.md](../rag/overview.md) gain a short section recording learner-written text as a second,
**file-free** source that needs no extraction — and stating plainly that nothing chunks, embeds, or
indexes it yet. The addition is **additive**: no approved decision in either document is withdrawn,
and the next RAG change finds an accurate map instead of a pipeline that cannot describe what is
stored.

## Consequences

**Positive.**

- LearnFlow holds something a mentor could be grounded in, without committing to a storage provider,
  an extractor, a chunking policy, an embedding model, or a vector store.
- The one genuinely hard part of ingestion — *getting usable text out of a document* — is sidestepped
  rather than solved badly. What a learner typed needs no extraction and has no failure mode.
- A learner who keeps notes offline now has somewhere to put the parts that matter, against the
  material they came from.
- The privacy position is stated where a learner reads it, and asserted in tests rather than promised
  in prose.

**Negative.**

- **The catalogue makes one request per resource** to list notes (RES-010 is resource-scoped, and no
  endpoint lists a learner's notes across their whole catalogue). They run together rather than in
  sequence, and every call is server-to-server on the same machine, but a large catalogue would make
  this worth revisiting. A learner-scoped note endpoint is a compatible addition under
  [versioning.md](../api/versioning.md) and is deliberately not built before a screen needs it — the
  position RES-002's absent `subject_id` filter takes.
- **Typing notes is work**, and a learner with a 200-page PDF will not transcribe it. This does not
  replace extraction; it makes the product useful before extraction exists.
- **The downgrade discards learner-written text**, which no earlier migration in this repository
  does: every table dropped so far held records a learner could recreate by asking again. The
  migration says so.

**Neutral.**

- `resource_notes` is a table beyond the approved schema, recorded in a new area review.
- `active` is a new status word in the resources area. `registered` was not reused because
  *registering* is what a learner does to a resource and it names where material is; a note is
  written. `archived` **is** reused, deliberately — terminology.md reserves it for putting something
  aside.
- FR-007 and FR-008 are both unchanged in what they have met.

## Alternatives considered

**Extract text from an uploaded PDF instead.** The milestone's actual next item, and far larger: file
storage, an extractor, a chunking policy, an embedding provider, and a vector store, each replaceable
and none built. It also has an honest failure mode — a scanned PDF yields nothing — that
ingestion.md requires be made visible, which needs `resource_ingestions` and a status a resource can
leave. Rejected as a first step, not as a direction.

**Store notes against a topic rather than a resource.** Rejected: it makes the same claim in two
places, and a note with no material behind it is a different feature from a note *on* something.

**Give a note its own topic links.** Closer to the page/section reference ingestion.md wants for
future citations, but it adds a second link table and a second place topic links can disagree.
Rejected for now; a note inherits its resource's topics, and a locator can be added compatibly.

**Chunk and embed the pasted text immediately.** Rejected as exactly the scope this record exists to
hold back. Chunks and embeddings are [entities.md](../domain/entities.md) *non-entities* — derived
data belonging in a vector index, rebuildable from this table. Storing them beside the note would fix
a chunking policy and an embedding model before either has been evaluated against real GATE CSE
material, which [embeddings.md](../rag/embeddings.md) explicitly forbids.

**Offer a real delete.** Genuinely arguable for content a learner regrets pasting, and it would give
the first honest answer to *"how do I get my text out"*. Rejected on the project owner's decision:
nothing implemented in LearnFlow deletes a learner's record, and creating the product's first
destructive endpoint here — where RES-005 has been deliberately left unbuilt — would set a precedent
sideways. Revisit it with RES-005, which arrives with the files and vectors it exists to clean up.

**Leave the body unbounded, as `questions.prompt` is.** Consistent with existing code, and rejected:
a text area on a form is a different exposure from a question prompt, and an unbounded field a single
request can fill is the one denial-of-service surface this change opens.

**Render the notes as Markdown.** Rejected. It would make a stored string executable-ish content that
has to be sanitised, in exchange for formatting nobody asked for; plain text with `pre-wrap` keeps
the learner's own shape and needs no sanitiser to be correct.

## Implementation notes

- **Migration `20260819_01`** — one `CREATE TABLE` and one index; nothing existing is altered. The
  `body` check is `body ~ '[^[:space:]]'` rather than `length(btrim(body)) > 0`, because PostgreSQL's
  one-argument `btrim` strips spaces alone and a body of newlines and tabs would pass a check meant
  to refuse it.
- **Domain layer untouched.** This adds no module to `backend/app/domain/`: there is no rule about
  study here, only about what may be stored. The three existing modules are unchanged.
- **Application** — `dto/resource_note.py`, `ports/resource_note_repository.py`,
  `use_cases/manage_resource_notes.py`.
- **Infrastructure** — `ResourceNote` in `persistence/resources.py`, and
  `persistence/resource_note_repository.py`.
- **Presentation** — `api/schemas/resource_note.py`, `api/routes/resource_notes.py`, wired through
  the composition root as every other use case is.
- **Frontend** — `types/resource-note.ts`, three components and their stylesheets in
  `features/resources/`, `note-submission.ts`, three server actions, and the notes read on
  `/resources`. Every write posts natively without JavaScript.
- **Documentation** — [endpoints.md](../api/endpoints.md), [schema.md](../database/schema.md),
  [migrations.md](../database/migrations.md), [terminology.md](../domain/terminology.md),
  [entities.md](../domain/entities.md), [overview.md](../rag/overview.md),
  [ingestion.md](../rag/ingestion.md), [milestones.md](../roadmap/milestones.md), and
  [project context](../00-project-context.md).

### Verification

Beyond the repository check set, this change was driven against the **production standalone server**
(`.next/standalone`) with **JavaScript disabled**, using a contract-shaped stub API — the run every
frontend ADR here records. **30 checks, all passing.** It exercised what unit tests cannot:

- The screen renders from the real production build, and a learner's line breaks, blank lines, and
  indentation reach the page.
- A pasted `<script>` tag is served **escaped**, appears in no `<script>` element, and `**asterisks**`
  are not parsed as Markdown.
- **No API address and no `API_BASE_URL`** appears in the served page or in any of its 10 client
  scripts — [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md)'s standing
  guarantee.
- A scriptless note submission reaches **RES-009 exactly once**, at the resource the form named, with
  **no `learner_id`** and no `status`; putting a note aside reaches **RES-012 exactly once** with
  `status` alone.
- Material put aside renders **no note form and no text area** in its own list item.
- Nothing requested a search, and the screen offers no search control.

**It found one defect that every other check passed**, and that defect is the reason for the
line-terminator rule above: a native multipart form submission delivers `CRLF`, because the HTML
form-data encoding algorithm normalises newlines. Without canonicalisation the same note would have
been stored one way with JavaScript disabled and another through a hydrated server action. 873
frontend tests and the whole backend suite had passed over it. The driver now asserts the transport's
`CRLF` explicitly, so the reason the rule exists cannot be lost.

It also raised a false positive worth recording for the next such run: a fixed-length slice of the
served HTML reads content belonging to a **different** resource, because the RSC flight payload
repeats every string on the page and Suspense appends deferred markup after the list. Scope such a
check to one element and strip `<script>` first.

### What this deliberately leaves open

- **Extraction, chunking, embedding, indexing, and retrieval**, and therefore the whole of FR-008 and
  the mentor.
- **RES-005 to RES-008**, still unimplemented for the reasons ADR-032 gave.
- **A learner-scoped note endpoint**, until a screen needs one.
- **A page or section locator on a note**, which ingestion.md wants for citations and nothing yet
  reads.
- **Whether a note ever becomes retrieval context**, which is the next decision this one makes
  possible and does not pre-empt.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](ADR-032-learning-resource-catalogue.md) — the catalogue this extends, and the record whose "never the material" rule it narrows
- [ADR-036: Show a topic's material on the plan screens](ADR-036-topic-material-on-the-plan-screens.md) — the precedent for amending ADR-032 narrowly, and the reasoning for keeping long content off the plan screens
- [ADR-035: Correct a practice question until a quiz has asked it](ADR-035-practice-question-correction.md) — why a note needs no equivalent rule
- [ADR-033: Checkpoint practice workflow](ADR-033-checkpoint-practice-workflow.md) — the precedent for adding a column beyond the approved schema
- [ADR-011: SQLAlchemy persistence implementation](ADR-011-sqlalchemy-persistence-implementation.md) — why a table arrives with the code that reads it
- [RAG overview](../rag/overview.md) — the pipeline this lays a source for
- [RAG ingestion](../rag/ingestion.md) — the file-based lifecycle this deliberately does not enter
- [API endpoints](../api/endpoints.md) — RES-009 to RES-012
- [Database schema](../database/schema.md) — `resource_notes`
- [Entities](../domain/entities.md) — the *Resource Note* entity
- [Database migrations](../database/migrations.md) — `20260819_01`
- [Terminology](../domain/terminology.md) — *resource note*
- [Non-functional requirements](../requirements/non-functional.md) — NFR-001 local-first privacy
- [Architecture decisions](../architecture/decisions.md)
