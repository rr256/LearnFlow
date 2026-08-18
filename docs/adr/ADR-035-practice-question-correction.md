---
title: "ADR-035: Let a Practice Question Be Corrected Until a Quiz Has Asked It"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-18
related:
  - ../00-project-context.md
  - ADR-018-weekly-availability-slots.md
  - ADR-019-study-goal-planning-preferences.md
  - ADR-032-learning-resource-catalogue.md
  - ADR-033-checkpoint-practice-workflow.md
  - ADR-034-checkpoint-practice-history.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../database/schema.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-035: Let a Practice Question Be Corrected Until a Quiz Has Asked It

## Status

Accepted — 2026-08-18

**Amends [ADR-033](ADR-033-checkpoint-practice-workflow.md)**, which is accepted, on one named
point: its rule *"a question is never edited"* becomes *"a question is never edited **once a quiz has
asked it**"*. ADR-033's reasoning is not overturned — it is applied more precisely. Everything else
in it stands: the learner still writes every question, nothing is generated or shipped, no score
exists, and nothing is deleted.

It supersedes no other decision and changes nothing in
[ADR-034](ADR-034-checkpoint-practice-history.md).

## Context

[ADR-033](ADR-033-checkpoint-practice-workflow.md) refused question editing outright, and gave one
reason: `quiz_attempt_answers` references a question by identifier, so editing one *"would silently
rewrite the history of every attempt already marked against it — a learner could open a result from
last week and find it saying something they never answered."*

That reason is real, and this decision verified it in the code rather than trusting the prose. A past
result is assembled in `manage_checkpoint_quizzes._outcomes`, which reads `question.prompt`,
`question.options`, `question.expected_option_key`, and `question.explanation` **from the live
question row**. Nothing is snapshotted: `quiz_attempt_answers` stores only `submitted_answer` and
`is_correct`, and `quiz_questions` stores only `position`. Two concrete failures follow from editing
in place:

- Editing the expected answer leaves a stored `is_correct: true` displayed beside an option that is
  no longer the expected one.
- `submitted_answer` stores an option **key**, and keys are assigned by position, so reordering or
  removing an option re-points a learner's recorded answer at different text.

But the reason is narrower than the rule ADR-033 drew from it. **A question no quiz has ever asked
has no history to rewrite.** `quiz_questions` holds no row for it, so no attempt can reference it,
so no result can change. The common case — a learner writes a question, spots a typo, and wants to
fix it before ever practising — was refused by a rule protecting something that did not exist.

The cost of the blanket rule is not theoretical. ADR-033 recorded it as a negative consequence
itself: *"A question cannot be corrected in place, which will surprise anyone who has used
`/resources`."*

## Decision

### A question may be corrected until a quiz has asked it

`has_been_asked` — a new repository port method, answering a **boolean, never a count** — decides it.
While no `quiz_questions` row names the question, QZ-010 accepts a whole new content group. Once one
does, a correction is refused with `409` and the learner does exactly what ADR-033 prescribed: sets
the question aside and writes another, so both stay readable.

The refusal says why, in the learner's terms: a quiz has already asked this, so changing it would
alter what an attempt already marked against it says.

**No snapshot is introduced**, and no column is added. Snapshotting the asked wording onto
`quiz_questions` would make editing always available, but it is a migration of four columns and a
change to how every attempt is read — far wider than the problem, and it would settle by accident the
numeric-precision question ADR-033 deliberately left open.

### A question set aside is read-only until it is brought back

Correcting a `retired` question is refused with `409` too. This is the two-step
[ADR-032](ADR-032-learning-resource-catalogue.md) fixed for archived material: the learner brings it
back, then corrects it. Setting aside stays reversible, so nothing is lost, and the rule keeps one
answer to "can I change this?" across resources and questions.

Both refusals are read from **what is stored**, never from the request, so a caller cannot slip an
edit past by asking to bring the question back in the same call.

### The content is corrected as a whole

`prompt`, `options`, `correct_option_index`, and `topic_ids` travel together or not at all, and an
`explanation` left out of a supplied group is **cleared**. That is the group-replacement rule
[ADR-019](ADR-019-study-goal-planning-preferences.md) fixed for planning preferences and
[ADR-018](ADR-018-weekly-availability-slots.md) for a study week.

They travel together because option keys are assigned by position and the expected answer is an index
into *this request's* options: pairing a supplied index with options the caller did not send would
mark a different answer as expected. A partly supplied group is `422`, not a merge.

Option keys are **reassigned by position** on a correction, exactly as on a write, so a stored
expected answer always names an option the question offers.

### What a correction is not

A correction is **the same question said better**: the identifier does not change, no second row is
written, and `written_at` does not move — a quiz is ordered by it, so moving it would reorder one.
Copy-on-write was considered and rejected below.

**Nothing else moves.** No quiz, no attempt, no learning stage, no plan, no plan item, and no
revision — and **no past result changes, by construction rather than by care**, because the only
questions that can be corrected are the ones nothing references.

### The contract and the screen

QZ-010's existing `PATCH /api/v1/practice-questions/{question_id}` carries it. **No endpoint is
added**, no path moves, and no status code changes for the request shapes that already worked. The
body gains the content fields alongside `status`; both may travel in one request.

**No migration.** `questions` already holds every column a correction writes, and
`question_topic_links` is replaced by the method a write already uses. `questions.status` is
untouched: *archiving* a question remains `retired`, the value ADR-033 shipped, and no second word is
introduced for one idea — `archived` stays the resources word.

On `/practice`, the correction form sits behind a `<details>` disclosure beside each question in use,
which a browser opens with no JavaScript — the shape `/resources` already uses. `QuestionForm` serves
both writing and correcting, as `ResourceForm` serves both adding and editing.

**The screen cannot see whether a quiz has asked a question**, because QZ-009 does not report it and
this decision adds no field to say so. The form is therefore offered for every question in use, and a
refusal is shown when it comes back. That is a deliberate trade: the rule is explained at the moment
it bites, and the read contract stays untouched.

## Consequences

### Positive

- The common correction — a typo caught before practising — takes one form instead of retire,
  rewrite, and re-link.
- `/practice` and `/resources` now behave alike where they can, and differ only where a real reason
  forces it, which is what made ADR-033's blanket rule surprising.
- No past result can change, and this is now structural: the only correctable questions are the ones
  nothing references.
- No migration, no column, no new endpoint, no snapshot, and no change to how an attempt is read.
- ADR-033's numeric-precision question stays open, and its `score` columns stay uncreated.

### Negative

- **A question a quiz has asked still cannot be corrected**, which is the case a learner is most
  likely to hit after a while of practising. The answer stays retire-and-rewrite.
- **The learner cannot tell in advance** which of their questions is still correctable: the form is
  offered and the refusal arrives on submission. Reporting it would mean a field on QZ-009.
- A correction is invisible afterwards — nothing records that a question was corrected, or what it
  said before. Nothing needs it today, and storing it would be a history table.
- "Never edited" was a rule that fitted in one sentence, and now has a condition attached.

### Neutral

- **FR-009 is unchanged** and still not met in full: this stores no score and no mistake evidence.
- `questions.status` still permits `draft`, which nothing writes.
- Correcting a question changes which questions a **future** quiz asks only in wording; a quiz
  already assembled is untouched, because assembly is by topic and the link set is replaced only for
  questions no quiz holds.

## Alternatives considered

### Snapshot the asked wording onto `quiz_questions`

Add `asked_prompt`, `asked_options`, `asked_expected_answer`, and `asked_explanation`, written at
assembly, and read attempts from the snapshot. Editing would then always be safe.

**Rejected:** a four-column migration and a change to how every attempt is read, to serve a case the
narrow rule already covers. It also duplicates question content per quiz, and it would settle the
numeric-precision detail ADR-033 deliberately left open. Worth revisiting only if correcting an asked
question becomes a real want.

### Copy-on-write: a correction writes a new question and retires the old

Any question stays correctable, and past attempts keep the old row.

**Rejected:** the question's identifier would change silently under the learner, the bank would fill
with retired near-duplicates, and "edit" would mean two different things depending on history. It is
also exactly what ADR-033 already tells a learner to do by hand, so it adds a button rather than a
capability.

### Let only the explanation be edited

The explanation is shown after marking, so changing it feels harmless.

**Rejected:** it is rendered *on a past result*, beside the answer the learner gave, so changing it
changes what that result says — the same defect in a smaller frame. And it would not deliver the
correction a learner actually wants, which is usually to the prompt or the options.

### Let topic links alone be edited, at any time

Topic links are not rendered in any result, so editing them changes no history.

**Rejected as the *whole* answer**, though it is true: it delivers none of the wording, choices,
answer, or explanation editing that was asked for. Topic links are included in the content group
here, and follow the same rule as the rest, so one condition governs a correction rather than two.

### Introduce an `archived` status for questions

Match the word `/resources` uses.

**Rejected:** `retired` already does exactly this and is live and reversible. Adding `archived` needs
a migration widening the `CHECK` and leaves LearnFlow with two words for one idea, which
[terminology.md](../domain/terminology.md) exists to prevent.

## Implementation notes

- `QuestionContent` is a new DTO beside `QuestionChanges`; `QuestionChanges` gains `content`.
- `has_been_asked` is on `CheckpointPracticeRepository`, implemented with `EXISTS` over
  `quiz_questions` so it stops at the first row, and returns a **boolean** so no count can leak.
- `update_question` in the repository now writes the `jsonb` payloads as well as `status`, shaped
  exactly as `add_question` shapes them — still the only place that shape is known.
- Both refusals are `409`: `QuestionAlreadyAskedError` and `RetiredQuestionEditError`.
- Assert in an API test that a question a quiz has asked is refused, **and** that it can still be set
  aside — the path the learner is redirected onto must stay open.
- The frontend reuses `QuestionForm` for both jobs and `readQuestionSubmission` for both readings;
  `readQuestionCorrection` adds only the question identifier.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-033: Assemble checkpoint practice from the learner's own questions, and report outcomes rather than a score](ADR-033-checkpoint-practice-workflow.md) — the decision this amends, and the reasoning it keeps
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](ADR-032-learning-resource-catalogue.md) — the archived-is-read-only two-step, and the editable-resource precedent
- [ADR-019: Store planning preferences as typed columns replaced as a group](ADR-019-study-goal-planning-preferences.md) — the group-replacement rule the content follows
- [ADR-034: Show the checkpoint-practice history as a paged reading of stored attempts, counting nothing](ADR-034-checkpoint-practice-history.md) — the results this protects, unchanged by it
- [Domain terminology](../domain/terminology.md) — the question vocabulary, and why `retired` is not renamed
- [API endpoints](../api/endpoints.md) — QZ-010
- [Database schema](../database/schema.md) — why no migration is needed
- [Architecture decision register](../architecture/decisions.md)
