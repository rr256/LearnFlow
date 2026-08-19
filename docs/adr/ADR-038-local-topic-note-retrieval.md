---
title: "ADR-038: Retrieve Passages From a Learner's Own Notes Locally, When They Ask"
status: accepted
owner: architecture-and-ai
last_updated: 2026-08-19
related:
  - ../00-project-context.md
  - ADR-002-provider-pattern.md
  - ADR-004-ollama-local-ai-provider.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-032-learning-resource-catalogue.md
  - ADR-033-checkpoint-practice-workflow.md
  - ADR-034-checkpoint-practice-history.md
  - ADR-035-practice-question-correction.md
  - ADR-036-topic-material-on-the-plan-screens.md
  - ADR-037-learner-written-resource-notes.md
  - ../rag/overview.md
  - ../rag/ingestion.md
  - ../rag/retrieval.md
  - ../rag/embeddings.md
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
  - ../architecture/decisions.md
---

# ADR-038: Retrieve Passages From a Learner's Own Notes Locally, When They Ask

## Status

Accepted — 2026-08-19. Proposed 2026-08-19.

This is **the first retrieval in LearnFlow**. A learner chooses a curriculum topic and sees passages
from their own notes, each named with the material and topic it came from.

It is **retrieval and nothing else**. No answer is generated, nothing is summarised, paraphrased, or
explained, and **no AI model, embedding service, vector database, external API, URL fetcher, file
uploader, OCR system, or scraper is reached or configured**. The search is PostgreSQL's own
full-text search, running on the learner's machine, and it runs only when they ask.

It adds **RES-013**, migration `20260820_01` — one index, no table and no column — and a screen at
`/resources/search`.

**It advances [FR-008](../requirements/functional.md#fr-008-grounded-mentor-assistance) by one
criterion and meets none of the others.** *"LearnFlow retrieves relevant indexed material before
generating an answer when relevant material exists"* is met for the half that retrieves; there is no
answer to generate it before. Asking a question, explaining a concept, citing sources in an answer,
and the Ollama provider all remain unbuilt, and **there is still no mentor**. FR-007's four criteria
are unchanged. Do not write that either requirement is complete.

## Context

[ADR-037](ADR-037-learner-written-resource-notes.md) gave LearnFlow its first study material: notes
the learner types or pastes against a resource. It deliberately stopped there, and said so — *"No
search across notes, which would be retrieval with a different name."*

This is that change, and the question it answers is narrow: **can a learner find the part of their
own notes that is about a topic?** Not *what does this mean*, not *explain this to me* — those need a
mentor, a provider, and a position on what an answer may claim. Finding a passage needs none of them.

### The promise that has to change

ADR-037's `nothing reads a note` is quoted in eight places, and it is doing **two different jobs**.

**As a privacy promise**, it is the sentence a learner reads on the note form: *"It is stored on this
computer, it is not sent anywhere, and nothing reads it."* Retrieval makes the last clause false.
Leaving it there would be worse than having never made it.

**As a correctness argument**, it is why a note may be corrected in place however often the learner
likes, where [ADR-035](ADR-035-practice-question-correction.md) freezes a practice question once a
quiz has asked it: *"Nothing reads a note, so no stored record can be made to disagree with a
correction."*

That second job **survives untouched**, and the distinction is the reason this change is safe. ADR-035's
problem was a *stored* record — a quiz attempt assembled from the live question row, which a later
edit would silently rewrite. This search **stores nothing derived from a note**: no chunk, no
embedding, no vector, no cached extract, and no search history. It reads the note at the moment it is
asked, so correcting a note changes what the next search finds, which is right rather than
inconsistent. An integration test asserts exactly that sequence.

So the promise is **narrowed, not withdrawn**: nothing *stores* anything derived from a note, and one
local reader reads it when the learner asks.

## Decision

The project owner decided eight questions before anything was built.

### 1. Relevance means linked material first, text order within it

Only notes on resources the learner **linked to the chosen topic** are searched, ordered by text
relevance within that set. Every passage therefore comes from material the learner themselves said
covers this topic, so no result is a surprise and every one can be explained.

Searching all notes by topic name was rejected: it retrieves on a name collision — *Trees* in data
structures and in a graphics note — and cannot say why a passage surfaced.

### 2. PostgreSQL full-text search, with an expression index

`to_tsvector('english', title || ' ' || body)` matched with `websearch_to_tsquery`, ordered by
`ts_rank`, with a **GIN index over that expression**. The `english` configuration is built in, so
**no extension is installed** and no dependency is added.

**An index and not a stored column.** A generated `tsvector` column would have been marginally
faster and would have meant altering a learner-owned table to hold a **derived representation of note
text** — precisely what ADR-037 kept out of the schema. An expression index keeps the derived form as
something PostgreSQL maintains for itself.

Stemming is the reason for `english` over `simple`: a topic called *Process Scheduling* finds a note
that only ever says "schedulers".

### 3. Only when the learner asks

A search runs because the learner chose a topic and submitted. **Nothing triggers one from a page
render, a save, or a plan.** That is what keeps the privacy statement a description of what LearnFlow
does rather than of what it might do while a page loads.

The screen is a plain `GET` form, so this needs **no server action** and holds no state.

### 4. Active notes on registered material

A note is searched when it is `active`, its resource is `registered` and owned by the learner, and
that resource is linked to the topic. Archived material drops out exactly as it does from the
curriculum, revision, and plan screens, so **putting something aside means one thing everywhere**.

### 5. A bounded, exact substring, in relevance order, with no figure

**A passage is one contiguous stretch of the note, character for character.** It is cut in the
application from the stored body — about sixty words, on word boundaries, with a third of that as
run-up before the match — ordered by `ts_rank` and capped at twenty passages.

**`ts_headline` is deliberately not used.** It was, and it had to be removed before this record could
be accepted: PostgreSQL's default parser reads `<int>` as an HTML tag and `ts_headline` **drops what
it classifies that way**, so a note containing `vector<int>` came back mangled. Nothing renders a
passage now. The database matches and orders; the application cuts. Every literal — angle brackets,
operators, entities, tabs — survives, and an integration test proves it against a real database.

**Nothing interprets a passage as markup, at any layer.** The database renders nothing; the API
returns the characters as they were stored, in JSON; and the screen puts them through JSX, which
escapes them — no `dangerouslySetInnerHTML`, no Markdown parser, and no sanitiser, because there is
nothing to sanitise when nothing is ever parsed. A learner's `<em>` is text they read, and CSS
`white-space: pre-wrap` — not generated markup — preserves their line breaks.

Two consequences of cutting rather than rendering, both accepted deliberately:

- **The whole body is transferred** for each matching note, bounded by `MAX_NOTE_BODY_LENGTH` and by
  the twenty-passage cap. `ts_headline` would send less and cost fidelity, which is the wrong trade
  for a learner's own writing.
- **Locating the match is approximate.** PostgreSQL matched with real stemming; character offsets are
  not something a `tsvector` gives back, so the cut is placed by comparing leading characters. When
  that cannot find the stemmed word, the passage is the **start of the note** — honest, still exact,
  and never a change to *which* notes came back.

**The rank is used to order and is then discarded.** It is absent from the projection, absent from the
DTO, and absent from the contract, so no screen can render a number beside a learner's own writing.
That is [terminology](../domain/terminology.md)'s rule against a figure that rates the learner, and it
applies with more force to their own words than to a plan.

Three empty answers are **told apart** — no linked material, no active notes, no matching passage —
because they ask the learner to link something, write something, or try another topic.

### 6. The privacy statement names its reader

> Stored on this computer and never sent anywhere. Nothing reads your notes except the topic search
> on this machine, which runs only when you ask for it, and no AI model ever sees them.

It keeps the two claims that are still absolutely true, replaces the one that is not with something
more informative, and states the AI position explicitly rather than by implication.

### 7. This ADR, narrowing ADR-037 by a dated note

ADR-037 gains a dated *Implementation status* note recording what its promise becomes. **Its Decision
is not rewritten and none of its reasoning is withdrawn** — the shape
[ADR-036](ADR-036-topic-material-on-the-plan-screens.md) used on ADR-032. Superseding it was rejected:
storage, no-delete, the bounds, plain-text rendering, and the no-provider rule all still stand.

### 8. RES-013 in the resource family, on its own screen

`GET /api/v1/resource-notes/search?topic_id=…`, catalogued under resources because it searches
resource notes. **MNT-001 and MNT-002 stay unimplemented**, and the mentor family stays honestly
empty until something generates an answer.

The screen is `/resources/search`, reached from `/resources`.

### What is deliberately absent

- **No free-text query.** The topic is the query. A typed query is a different feature with its own
  question about what is recorded.
- **No search history.** Nothing records that a search happened, or what was looked for. A test
  asserts no such table exists.
- **No mentor, no answer, no citation of an answer**, because there is no answer.
- **No provider of any kind** in the use case, asserted by a test, so adding one is a visible decision.
- **No recommendation.** Nothing suggests a topic, a note, or what to study next.

## Consequences

**Positive.**

- The notes ADR-037 stored become findable, which is what makes writing them worth the effort.
- The genuinely hard and expensive parts of RAG — an embedding model, a vector store, a chunking
  policy, and their evaluation — are all deferred, and nothing here forecloses them.
- The privacy position is *stronger* than it was, because it is now specific: a named local reader,
  invoked explicitly, with no model involved.
- FR-008's retrieval criterion is **partly** met — the retrieving half of it — by something a learner can use today.

**Negative.**

- **The whole matching body crosses the process boundary**, because the passage is cut in the
  application rather than rendered by the database. That is what makes a passage an exact substring;
  it costs a larger result set, bounded by the note limit and the passage cap.
- **Only one window per note is shown.** Joining several would mean inserting a separator the learner
  never wrote, so a note that mentions the topic three times shows the first; `note_id` leads to the
  rest.
- **`english` stemming is a language choice.** A learner writing notes in another language gets worse
  matching. Changing the configuration later means rebuilding the index, which is a migration.
- **`or` semantics over a topic's words trade precision for recall.** Within the learner's own linked
  material this is the right trade, but a one-word match can surface a loosely related passage;
  relevance ordering puts it last rather than hiding it.
- **A note that never uses the topic's words is not found**, however relevant it is. The screen says
  so as its own outcome rather than implying the notes are lacking.

**Neutral.**

- One more index on `resource_notes`. It stores no text that was not already in the table, and
  dropping it loses nothing.
- The search adds a fourth reason to read `topic-options`, which is reused rather than copied.

## Alternatives considered

**Embeddings and a vector store**, as [rag/overview.md](../rag/overview.md) anticipates. Rejected as
the *first* retrieval, not as a direction: it needs an embedding model, a vector provider, a chunking
policy, and an evaluation set, and [embeddings.md](../rag/embeddings.md) explicitly forbids choosing
a model without evaluating it on representative GATE CSE material. It also sends note text to a
provider, which is a privacy decision of a different order. Full-text search answers the same question
today with none of that.

**Generate an answer from the passages.** The obvious next step, and deliberately not taken: it needs
a provider, a position on what a grounded answer may claim, and the honest-failure rules
[retrieval.md](../rag/retrieval.md) sets out. Retrieval is useful on its own and is a prerequisite
either way.

**Search all notes, ignoring topic links.** Better recall, no explanation. Rejected — see Decision 1.

**A stored `tsvector` column.** Rejected — see Decision 2.

**`pg_trgm` similarity.** Would match misspellings and needs no stemming configuration, but it
installs an extension, has no notion of word importance, and ranks by string distance rather than by
term frequency. Rejected as both heavier and less apt.

**Plain `ILIKE` substring matching.** No index, no migration, no configuration — and no stemming, so
*Process Scheduling* misses "schedulers", which is most of the value.

**Show the passages automatically on the curriculum and plan screens.** Rejected on the owner's
decision: it would read note text on nearly every page render, including screens opened for something
else, which is a materially weaker privacy position than an explicit ask.

## Implementation notes

- **Migration `20260820_01`** — one `CREATE INDEX`; no table, no column, no data read or rewritten.
  The indexed expression is written out in the migration and built by the repository; an integration
  test compares the two, because a mismatch silently stops the index being used rather than failing.
- **No domain module is added.** The three modules in `backend/app/domain/` hold rules about *study*;
  which words a topic contributes to a query is not one. It lives beside the use case as a pure
  function with its own tests.
- **Application** — `dto/note_retrieval.py`, `ports/note_search_repository.py`,
  `use_cases/retrieve_topic_notes.py`.
- **Infrastructure** — `persistence/note_search_repository.py`, the only place the search SQL lives.
- **Presentation** — `api/schemas/note_retrieval.py`, `api/routes/note_search.py`. The router is
  registered **before** `resource_notes`, because `/resource-notes/{note_id}` would otherwise capture
  `/resource-notes/search`; an API test holds the order.
- **Frontend** — `types/note-search.ts`, `TopicNoteSearchForm`, `NotePassages`, the page at
  `/resources/search`, and the revised privacy copy on the note form.
- **`ts_headline` is not used at all.** The cut is `extract_passage`, a pure function beside the use
  case, so a passage is an exact substring by construction rather than by trusting a renderer.

### Verification

Beyond the repository check set, this was driven against the **production standalone server** with
**JavaScript disabled**, using a contract-shaped stub API — the run every frontend ADR here records.
**28 checks, all passing.** The ones worth naming:

- **No search runs on a bare page load.** The stub records every request, and opening
  `/resources/search` without a topic makes none. This is the decision above, held to account.
- The form submits as a **`GET` to the search screen**, carries **no `$ACTION_*` fields**, and offers
  **no free-text or search input**.
- Asking reaches **RES-013 exactly once**, carrying `topic_id` and nothing else; **no request in the
  whole run carried a `learner_id` or a query parameter**.
- A learner's line breaks and indentation survive to the page; a pasted `<script>` tag arrives
  **escaped** and appears in no `<script>` element; `**asterisks**` are not parsed as Markdown.
- **No `API_BASE_URL` and no API address** appears in the page or in any of its 9 client scripts.
- An empty answer names **which** of the three reasons applies, and an unknown topic renders the
  screen with the failure in words and **no note text in it**.

Two driver artefacts were found and corrected rather than the code: React separates adjacent text
expressions with `<!-- -->`, so a raw-substring assertion has to strip them, and the stub must still
be running when the page is fetched.

**The run was repeated after `ts_headline` was removed**, with a stub passage carrying
`vector<int>`, `a < b`, and an `<em>` tag, and it asserts that all three reach the page as text.

### What this deliberately leaves open

- **The mentor**, and every FR-008 criterion that needs an answer.
- **Embeddings, chunking, a vector store, and `resource_ingestions`** — none is created, and
  ADR-037's absent columns stay absent.
- **A free-text query**, and with it the question of what a query would be recorded in.
- **Retrieval over anything but notes**: files are still not stored, so there is nothing else to
  search.
- **Whether retrieval quality is good enough**, which [retrieval.md](../rag/retrieval.md) says must be
  evaluated against representative questions before it is relied on. Nothing here claims it has been.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-037: Store the learner's own written notes against a learning resource](ADR-037-learner-written-resource-notes.md) — the storage this reads, and the promise it narrows
- [ADR-036: Show a topic's material on the plan screens](ADR-036-topic-material-on-the-plan-screens.md) — the precedent for narrowing an accepted ADR by a dated note
- [ADR-035: Correct a practice question until a quiz has asked it](ADR-035-practice-question-correction.md) — the stored-record problem this search avoids
- [ADR-032: Catalogue learner-owned study material as metadata](ADR-032-learning-resource-catalogue.md) — the linkage that bounds the search
- [RAG retrieval](../rag/retrieval.md) — the approved retrieval contract this partly implements
- [RAG overview](../rag/overview.md) — where this sits in the pipeline
- [Embeddings](../rag/embeddings.md) — the path deliberately not taken yet
- [API endpoints](../api/endpoints.md) — RES-013
- [Database migrations](../database/migrations.md) — `20260820_01`
- [Database schema](../database/schema.md) — the search index on `resource_notes`
- [Terminology](../domain/terminology.md) — *topic note search*, *passage*
- [Non-functional requirements](../requirements/non-functional.md) — NFR-001 local-first privacy
- [Architecture decisions](../architecture/decisions.md)
