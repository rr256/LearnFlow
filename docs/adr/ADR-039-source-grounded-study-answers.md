---
title: "ADR-039: Answer a Learner's Question Only From Their Own Notes, With a Local Model"
status: accepted
owner: architecture-and-ai
last_updated: 2026-08-20
related:
  - ../00-project-context.md
  - ADR-002-provider-pattern.md
  - ADR-004-ollama-local-ai-provider.md
  - ADR-009-configuration-naming-and-validation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-032-learning-resource-catalogue.md
  - ADR-037-learner-written-resource-notes.md
  - ADR-038-local-topic-note-retrieval.md
  - ../ai/learnflow-agents.md
  - ../ai/prompts.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../architecture/provider-pattern.md
  - ../architecture/dependency-rules.md
  - ../rag/overview.md
  - ../rag/retrieval.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../requirements/non-functional.md
  - ../development/coding-standards.md
  - ../deployment/environments.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-039: Answer a Learner's Question Only From Their Own Notes, With a Local Model

## Status

Accepted — 2026-08-20. Proposed 2026-08-19.

This is **the first AI-generated content in LearnFlow**, and the first code anywhere in it that asks
a model anything. A learner chooses a curriculum topic, types a question, and receives an answer
built from passages in their own notes — with those passages shown beneath it.

It adds **MNT-001**, an `AIProvider` port, one Ollama adapter, four configuration variables, and a
screen at `/mentor`. It adds **no table, no column, and no migration**, because **nothing is
stored**.

**The central rule is that retrieval decides whether a model is asked at all.** Where nothing of the
learner's supports an answer, no prompt is built and no request is made; LearnFlow says it has
nothing to answer from rather than answering from what a model happens to know.

**It advances [FR-008](../requirements/functional.md#fr-008-grounded-mentor-assistance) but does not
complete it.** Do not write that FR-008 is met in full — see *Consequences*.

## Context

[ADR-037](ADR-037-learner-written-resource-notes.md) gave LearnFlow study material.
[ADR-038](ADR-038-local-topic-note-retrieval.md) made it findable. Both stopped deliberately short of
answering anything, and ADR-038 said so: *"there is still no mentor."*

This is that change. The question it answers is the one a learner actually has — *what does this
mean?* — and the reason it needs an ADR is that answering it requires three things LearnFlow has
never done: **generate text**, **ask a provider**, and **let a learner's own words leave the
application layer**.

### What was already decided

[ADR-004](ADR-004-ollama-local-ai-provider.md) is **accepted** and selects Ollama, running locally,
as LearnFlow's AI provider. It explicitly rejected *"Cloud AI Provider First"* because that
*"introduces recurring usage costs, requires credentials/internet, and conflicts with the local-first
privacy/cost objective for the MVP"*, and it required that future cloud providers arrive *"only as
explicit optional adapters with transparent privacy/cost configuration."*

**This ADR implements that decision rather than revisiting it.** ADR-004 is not amended, because
nothing about it changes: the provider is Ollama, it runs on the learner's machine, and no
credential exists anywhere in the system.

What ADR-004 did **not** decide, and this ADR does, is: whether a model may answer without evidence,
what may be sent to it, what a citation is, what happens when the provider is absent, and whether
anything is stored.

### The promise that has to change again

ADR-037 promised that nothing reads a note. ADR-038 narrowed that to *one* reader — the topic search,
local, only when asked — and rewrote the note form's copy accordingly. That copy currently ends:
*"and no AI model ever sees them."*

**This change makes that clause false.** A model does see a learner's notes: the passages retrieval
selected, locally, when they ask a question. The copy is rewritten again rather than left standing,
for the reason ADR-038 gave — a promise that quietly stopped being true would be worse than never
having made one.

The correctness argument ADR-037 built on the same sentence is **untouched**, exactly as it was under
ADR-038: a live read that stores nothing derived cannot go stale, so a note may still be corrected in
place however often the learner likes.

## Decision

### An answer is grounded, or there is no answer

Retrieval runs first, through RES-013's existing use case. **The provider is reached only on the
branch where passages were found.** The three empty retrieval outcomes are carried through as
`no_linked_material`, `no_active_notes`, and `no_matching_passage`, and on each of them **no prompt
is composed and no request leaves the process**.

This is enforced by control flow, not by a prompt, and it is asserted by tests that fail if the
provider records a single call. It is `docs/ai/prompts.md`'s rule — *"Do not claim an answer is
grounded when retrieval did not succeed"* — expressed as structure.

**There is no relevance threshold and no partial mode.** LearnFlow does not decide that evidence is
too weak to use; it either found passages or it did not. Scoring evidence would be ranking the
learner's notes, which ADR-038 refused.

### Only the question and the passages are sent

What may leave the application layer is fixed by a dataclass, `GroundedAnswerRequest`, holding
exactly four fields: the question, the topic name, the subject name, and the retrieved passages.

**Deliberately absent**: every identifier (note, resource, topic, learner), the note and resource
titles, whole note bodies, and everything about the learner's plan, progress, revisions, and
practice. A structure that cannot hold an identifier cannot leak one, and a test asserts the field
list rather than trusting this paragraph.

At most `MAX_GROUNDING_PASSAGES` (8) passages are sent — fewer than the 20 a learner may *read*,
because a prompt and a screen are different budgets. The figure is never reported.

### The citations are LearnFlow's, not the model's

The passages sent are recorded **before** the provider is asked and returned unchanged as the
answer's citations. **Nothing parses a source out of the prose**: no inline markers, no numbered
references read back, and no source name extracted.

The model is therefore given no means to name a source and is instructed not to try. An answer
**cannot cite a note that was not consulted**, which is the failure a citation scheme invites when
the model is trusted to produce it.

### Nothing is stored

No question, no answer, no transcript, no history, and no record that either happened. There is no
table, no column, no migration, and no endpoint that reads a past question back.

This is why the screen holds one answer at a time and why asking twice is simply asking twice.

### One attempt, and honest failures

A single request with a configurable timeout (`AI_REQUEST_TIMEOUT_SECONDS`, 60 seconds by default).
**No retry**: a local model that timed out will usually time out again, and a refused connection
means Ollama is not running, which a second attempt cannot change.

Four provider failures are told apart — unreachable, model missing, timed out, unusable reply —
because they ask a learner to do different things. A provider failure is reported as a **`200` with
an outcome**, not a gateway error, and **the retrieved passages are still returned**: a model that is
switched off must not cost the learner the reading of their own notes.

### It is MNT-001, narrowed

The catalogued MNT-001 promises *"mentor answer, source references, suggested next actions"*. This
implements the first two and **not the third**. Suggesting what a learner should do next is a
recommendation, which is a separate decision with its own scope; the narrowing is recorded in
`docs/api/endpoints.md` rather than left to be discovered.

**MNT-002 stays unimplemented.** Asking a question already reports whether the provider answered, so
a separate availability probe would be a second way to learn the same thing.

### The screen is called *Ask your notes*, and the route stays `/mentor`

**The learner-facing name is *Ask your notes*.** It says what the learner does and what the answer is
built from, and it is the canonical term in
[terminology.md](../domain/terminology.md) for both the capability and the screen.

***Mentor* is deliberately not the learner-facing name.** Terminology reserves that word for a
broader role — one that *"explains, plans, recommends, and reflects"* — and this builds only the
first of those four. Calling the screen *Mentor* would promise recommendations and planning that are
not there, which is the same kind of quiet overstatement this ADR refuses everywhere else.

**The route keeps `/mentor` and the endpoint family keeps `MNT-`.** Both name the *service* rather
than the screen, the catalogue already uses them, and changing a URL is a compatibility decision
worth taking on its own rather than as a side effect of naming a screen. So: *the mentor endpoint*
for `POST /api/v1/mentor/questions`, and *Ask your notes* for what a learner does.

### The provider is a port, and the choice is a configuration

`AIProvider` is a `Protocol` in the application layer; the Ollama adapter is the only implementation
and lives in `app/infrastructure/providers/`. **The composition root alone selects it**, from
`AI_PROVIDER`.

The adapter uses the standard library's `urllib.request`, so this change adds **no dependency** — no
vendor SDK and no HTTP client.

**In a container, the address is fixed rather than interpolated.** `compose.yaml` sets
`OLLAMA_BASE_URL` on the `backend` service to `http://host.docker.internal:11434`, because a
developer's own value names `127.0.0.1` — which inside a container is the container itself, not the
host running Ollama. `extra_hosts` maps `host.docker.internal` to `host-gateway`, so the same address
works on Docker Desktop and on Docker Engine for Linux, which does not provide the name natively.
`OLLAMA_CONTAINER_BASE_URL` overrides it for an Ollama elsewhere; nothing in the backend reads that
variable.

**No AI setting reaches the `frontend` service.** Its environment feeds a server that renders pages
for a browser, so the provider's address, its model, and the fact that one is configured all stay out
of it.

## Alternatives considered

**Answer from the model when retrieval finds nothing, with a disclaimer.** Rejected. It is precisely
the behaviour a grounded mentor exists to avoid, and a disclaimer beside confident prose is read as
politeness rather than as a warning.

**Inline numbered citations the model emits.** Rejected for a first version. It attributes claims
precisely when it works, but a model can cite a passage that does not support the claim, or one that
does not exist, and validating that is real work. Showing the passages beneath the answer gives the
learner the same check without trusting the model to perform it.

**Structured output binding each claim to a passage.** Rejected as premature. It is the strongest
guarantee and needs a schema, a parser, and a retry path, and local models are the least reliable at
strict JSON.

**A cloud provider.** Rejected — it is what ADR-004 already rejected, and nothing here changes that
reasoning. It would also introduce the first credential in the system.

**Storing questions and answers.** Rejected. It is a second feature with its own privacy question,
and nothing in this one needs it.

**A `GET` form, as `/resources/search` uses.** Rejected. A search carries a topic identifier; this
carries the learner's own question, and a question in the address lands in server logs and browser
history. The endpoint is a `POST` for the same reason, though it writes nothing.

## Consequences

**FR-008 is advanced and is not complete.** A learner can ask a question about one topic and receive
an answer grounded in their own notes, with sources cited, and the no-source state is truthful.

[endpoints.md](../api/endpoints.md#fr-008-acceptance-criteria) is authoritative for the count and
records **five of six criteria met, with the third partly met**. Two verdicts move with this change:
*"the learner can ask a learning question for a topic"* and *"the initial local AI provider is
Ollama"* become met, and the retrieval criterion moves from *partly met* to **met** — its generating
half now exists, and *"indexed"* is read as a difference in method rather than in what the criterion
asks for, since the search is PostgreSQL full-text rather than vector.

What is **not** met: suggested next actions, and any use of material beyond the learner's own notes —
nothing is ingested, extracted, chunked, or embedded, so a criterion met here is met over the
material LearnFlow actually stores. **Do not write that FR-008 is met in full.**

**FR-006 is still not met in full.** Its practice half remains open; this changes nothing about it.

**The privacy position changes, and the wording changes with it.** A local AI model now reads the
passages retrieval selects, when the learner asks. ADR-037 and ADR-038 each receive a dated
implementation-status note recording that, with their Decisions, Consequences, and Alternatives
untouched.

**The first outbound request in LearnFlow now exists.** Until this change no code path reached the
network at all. It reaches `localhost` only, and the adapter is the single place that could ever
reach further.

**A learner without Ollama installed sees an honest failure**, not a broken screen: the passages are
shown and the outcome says the provider could not be reached.

**Nothing else moves.** No learning stage, plan, plan item, revision, or quiz, and nothing is
counted, scored, or ranked.

## Implementation notes

- **No migration, no table, and no column.** Nothing is stored, so the schema is untouched.
- **Domain layer untouched.** This adds no module to `backend/app/domain/`: there is no rule about
  study here. The three existing modules are unchanged.
- **Application** — `ports/ai_provider.py` (the port, its four named failures, and
  `GroundedAnswerRequest`), `dto/study_answer.py`, and `use_cases/answer_topic_question.py`, which
  binds retrieval and one provider and **nothing that can write**.
- **Infrastructure** — `providers/ollama_ai_provider.py`, a new package beside `persistence/`. It is
  the only file in the backend that makes an outbound request, and it uses `urllib.request`, so this
  adds **no dependency** to `requirements.txt`.
- **Presentation** — `api/schemas/study_answer.py` and `api/routes/mentor.py`, wired through the
  composition root as every other use case is.
- **Configuration** — `AI_PROVIDER`, `AI_REQUEST_TIMEOUT_SECONDS`, `OLLAMA_BASE_URL`, and
  `OLLAMA_CHAT_MODEL` in `composition/config.py` and `.env.example`. `OLLAMA_BASE_URL` is an
  `AnyHttpUrl`, which accepts `http` and `https` only — the boundary that stops a `file://` value
  turning an outbound request into a local file read.
- **Frontend** — `types/study-answer.ts`, `features/mentor/` (a server action, its submission
  reader, and two components), and `app/mentor/page.tsx`. The directory and route keep the service's
  name; the screen's heading and its button read **Ask your notes**, and a test asserts the word
  *mentor* appears nowhere a learner reads. The screen posts through a server action
  rather than a `GET`, so a learner's question stays out of addresses, logs, and history, and it
  works with JavaScript disabled.
- **The system prompt lives in the adapter**, beside the vendor's request shape, because its wording
  is bound to the API it is sent through. `docs/ai/prompts.md` is a library for *engineering*
  assistants and is deliberately not its home.

### Verification

**No check anywhere makes a real external call.** Every provider in every test is a fake or a
contract-shaped stub, so the suite needs no Ollama installed and no model pulled, and its answer
cannot depend on a model's.

- Backend `pytest -W error`, `ruff check`, and `ruff format --check` all pass. Tests assert the
  central rule directly: on each ungrounded outcome the fake provider records **zero** calls.
- A test asserts `GroundedAnswerRequest`'s field list, so adding a field that could carry an
  identifier fails rather than passing review.
- **Against real PostgreSQL** (`tests/integration/test_mentor_api.py`, on the disposable
  `learnflow_test` database): the whole path with only the provider faked. A note that never repeats
  the topic's words is found by real stemming and answered; a note about something else produces
  `no_matching_passage` with **no provider call**, which is the branch that had until then only been
  exercised against an in-memory search. Archived notes and archived material both drop out with no
  call. Row counts across every table are unchanged by asking twice.
- **From inside the backend container** (`tests/integration/test_docker_topology.py`): a fake Ollama
  on the host, reached through `host.docker.internal`. It asserts from **outside the application**,
  on the bytes that left the container, that the request body holds exactly `model`, `system`,
  `prompt`, and `stream`; that the question and the retrieved passage are present; that no
  identifier, note title, or resource title is; and that an ungrounded question produces **no request
  at all**. It also asserts that Compose puts every AI setting on `backend`, none on `frontend`, and
  no credential anywhere.
- Frontend lint, typecheck, tests, and `next build` pass.
- The screen was driven against the production standalone server **with JavaScript disabled**,
  through a contract-shaped stub API: the answer, the passages, and each empty state render, markup
  inside a model's prose is escaped rather than executed, and only `topic_id` and `question` reach
  the API.

### What this deliberately leaves open

- **Suggested next actions**, which MNT-001 catalogues and this does not implement.
- **MNT-002**, provider availability.
- **Ingestion and embeddings** — no file, extractor, chunker, embedding provider, or vector store.
  Retrieval remains PostgreSQL full-text over the learner's own notes.
- **A canonical terminology entry** for this screen and capability, which is a naming decision for
  the project owner rather than something this change should settle.
- **Changing the `/mentor` route to match the screen's name.** Deliberately not taken here: a URL
  change is a compatibility decision of its own, and the path names the service rather than the
  screen.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-004: Ollama local AI provider](ADR-004-ollama-local-ai-provider.md)
- [ADR-037: Learner-written resource notes](ADR-037-learner-written-resource-notes.md)
- [ADR-038: Local topic-note retrieval](ADR-038-local-topic-note-retrieval.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Retrieval](../rag/retrieval.md)
- [Prompt patterns](../ai/prompts.md)
- [LearnFlow agents](../ai/learnflow-agents.md)
- [API endpoints](../api/endpoints.md)
- [Environments](../deployment/environments.md)
- [Functional requirements](../requirements/functional.md)
- [Architecture decisions](../architecture/decisions.md)
