---
title: "ADR-033: Assemble Checkpoint Practice from the Learner's Own Questions, and Report Outcomes Rather Than a Score"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-18
related:
  - ../00-project-context.md
  - ADR-008-assessment-and-mistake-evidence-model.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-021-plan-item-completion.md
  - ADR-022-plan-adaptation.md
  - ADR-028-revision-workflow.md
  - ADR-029-progress-overview.md
  - ADR-031-priority-focus-panel.md
  - ADR-032-learning-resource-catalogue.md
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

# ADR-033: Assemble Checkpoint Practice from the Learner's Own Questions, and Report Outcomes Rather Than a Score

## Status

Accepted — 2026-08-18

Supersedes nothing. It is the first change to open
[Milestone 5](../roadmap/milestones.md#milestone-5-quiz-and-external-test-evidence), and opens that
milestone's **first two items only**, exactly as
[ADR-032](ADR-032-learning-resource-catalogue.md) opened Milestone 4's first item.

It is constrained throughout by [ADR-008](ADR-008-assessment-and-mistake-evidence-model.md), which is
**accepted** and already fixes how a quiz links to topics and where quiz evidence may and may not be
written. Nothing here reopens any of that.

## Context

[FR-009](../requirements/functional.md#fr-009-topic-checkpoint-practice) asks that a learner be able
to test their understanding after studying a topic: request a short topic-focused checkpoint quiz,
submit answers, receive basic feedback, and have objective answers scored automatically.

Everything the schema needs was approved long ago. The *Assessment* area of
[schema.md](../database/schema.md) has held seven tables since the first schema pass, and ADR-008
settled its two contested modelling questions. [endpoints.md](../api/endpoints.md) catalogues QZ-001
to QZ-007. What had never been decided is the part that is not modelling at all, and three questions
had to be answered before a line could be written.

**Where do the questions come from?** The repository holds no question content and no seed that could
produce any. `questions.source_type` permits `generated`, `verified_pyq`, and `curated`. `generated`
needs an AI provider, which does not exist and which the MVP deliberately keeps out of the
deterministic path. `verified_pyq` means real previous-year GATE questions, which are third-party
content with a licensing position this project has never taken and does not want to take. That leaves
`curated`, and nobody had said who curates.

**What may a result say?** This is the sharpest conflict in the repository.
[terminology.md](../domain/terminology.md) forbids, **by name**, "no percentage complete, no
completion rate, no '14 of 60 done', no streak, no score". [schema.md](../database/schema.md)
approves `quiz_attempts.score` and `max_score`. FR-009 asks that the product store "the attempt,
answers, score, and identified mistakes". Two approved documents and a requirement disagree, and a
quiz score is the single most obvious number in the product that rates a learner rather than
describing their work.

**How much of FR-009 can honestly be met?** Its fifth criterion asks for stored *mistakes*.
`mistake_evidence` has four discovery-source foreign keys, two of which — `external_test_results` and
`study_activities` — reference tables that do not exist. It cannot be created without creating them,
which is Milestone 5's second half and FR-010's whole subject.

### One finding that shaped the answers

`quiz_attempt_answers` references a question by identifier. That single fact decides more than it
looks: if a question's prompt, options, or expected answer could be edited, editing one would
silently rewrite the history of every attempt already marked against it — a learner could open a
result from last week and find it saying something they never answered. Every decision below about
question lifecycle follows from refusing that.

## Decision

### The learner writes every question; nothing curated ships

A practice question is authored by the learner, through a new endpoint, and stored with
`source_type = curated`. **No question content enters this repository**: no seed, no data file, no
bundled previous-year paper, and no external fetch. That is the position ADR-032 took when it shipped
no curated resources, and it keeps LearnFlow clear of third-party question licensing entirely.

`generated` and `verified_pyq` remain in the `CHECK`, unwritten, so offering either later is a
use-case change rather than a migration.

This makes `questions` learner-owned, and the schema's own *Conventions* require a learner identifier
on learner-owned records. `questions.author_learner_id` is therefore **added**, nullable, mirroring
`resources.owner_learner_id` exactly — nullable so the shared or curated bank the table was originally
designed for still has somewhere to live.

### A question is never edited — only set aside, and rewritten

QZ-010 changes `status` and nothing else. The prompt, the options, the expected answer, the
explanation, and the topics are all fixed at the moment of writing, for the reason the finding above
gives: a result must stay true to what the learner answered.

A learner corrects a question by retiring it and writing another. Both stay readable, which is the
position [ADR-022](ADR-022-plan-adaptation.md) takes for a superseded plan. This is a deliberate
departure from [ADR-032](ADR-032-learning-resource-catalogue.md), which *does* let a resource be
edited: a resource has no history depending on its wording, and a question has.

**Nothing is deleted.** `retired` is reversible, and a quiz already assembled goes on asking a retired
question, because attempts are marked against it.

### A quiz asks every ready question for the chosen topics, in the order they were written

Assembly is deterministic and involves no AI provider: the same topics, over the same question bank,
always produce the same quiz with the same questions in the same order. That is the promise
[ADR-020](ADR-020-initial-study-plan-generation.md) made for a study plan, kept for an assessment.

**LearnFlow selects none of the learner's questions and leaves none out.** Choosing which few to ask
would be a ranking, and nothing in LearnFlow ranks; there is no sampling, no shuffling, and no cap.
The length of a quiz is the learner's own decision — how many topics they pick, and how many questions
they have written. The order is *the order they were written*, which is explainable in one sentence,
cannot be read as a judgement, and is stable.

A question covering two chosen topics is asked once. A quiz naming no topic is refused, which is
ADR-008's rule; so is one for topics with no ready question, because a quiz that asks nothing cannot
be attempted.

### The result states per-question outcomes and no total at all

This resolves the terminology/schema conflict **in terminology's favour**, and narrows the schema
accordingly.

A marked attempt reports, for each question: what the learner chose, whether it matches the expected
answer, the expected answer, and the explanation the question was written with. There is **no score,
no mark, no count of correct answers, no percentage, and no comparison** with an earlier attempt —
on the API, in the domain, in the database, or on any screen.

`quiz_attempts.score`, `quiz_attempts.max_score`, `quiz_questions.max_marks`, and
`quiz_attempt_answers.awarded_marks` are therefore **not created**. Three tests in terminology's own
section decide it: the subject of "you got 3 of 5" is the learner, not the work; it would be
meaningless for an attempt nobody had made; and it invites a comparison with last week's attempt.
A per-question outcome fails none of the three.

Leaving those columns uncreated has a second, welcome effect: the **one open detail**
[schema.md](../database/schema.md) still records — numeric precision for score and marks columns —
stays open, rather than being settled by a change that would never read the answer.

**FR-009's "objective answers can be scored automatically" is met**: every objective answer is scored,
as correct or not correct, deterministically. What is not met is the storage of a *total*.

### An unanswered question is not a wrong one

A question the learner leaves alone is stored with `submitted_answer` null and `is_correct` null,
which is what the nullable column is for, and reads back in words as "You did not answer this one".
Writing `false` there would state something about the learner that they did not. No option is
pre-selected on the quiz form, because making a learner guess to satisfy a form is not practice.

### Only `multiple_choice`, and option keys are assigned by position

One of the four documented question forms is written. `multiple_select` and `numeric` need marking
rules this build deliberately does not write; `short_answer` cannot have one at all without judging
free text, which nothing here may do. The `CHECK` carries all four.

Option keys — `a`, `b`, `c`, … — are assigned by LearnFlow from each option's position and never
accepted from a caller, so a stored expected answer always names an option the question actually
offers. Two options with identical wording are refused, because a learner choosing the other one would
be marked wrong for the same answer.

### Nothing else moves, and nothing claims a topic is understood

Writing a question, assembling a quiz, attempting one, and marking it write **no learning stage, no
plan, no plan item, and no revision**. This is FR-005's and FR-009's shared rule — the product does
not claim permanent mastery from one quiz — and it is enforced by the code having no path to any of
them.

A quiz is **not a plan item**: `plan_items.action_type = 'practise'` stays unwritten, no quiz enters a
plan, and PLN-005 is untouched, which is exactly the position
[ADR-028](ADR-028-revision-workflow.md) took for a revision.

### Nine endpoints: six catalogued, three new, one departure

QZ-001, QZ-002, QZ-003, QZ-005, QZ-006, and QZ-007 are implemented as catalogued.

**QZ-004 is not implemented.** Saving one answer before submission needs a client that keeps an
attempt open across requests; a learner submits the whole attempt in one form post instead, which is
what makes the flow work with no JavaScript. QZ-005 therefore **accepts the answers in its request
body**, which is the one departure from the catalogue — the same kind of departure
[ADR-022](ADR-022-plan-adaptation.md) recorded for `/adapt`.

**QZ-008 to QZ-010 are new**, at `/api/v1/practice-questions`: write, list, and set aside. The
catalogue had no endpoint for creating a question at all, because it had never been decided who writes
one.

**Starting an attempt is safe to ask for twice.** QZ-003 returns an unfinished attempt at the same
quiz rather than creating a second, answering with `200` instead of `201` — the position REV-004 takes
for a review already waiting. Submitting twice is refused with `409`: a record of what happened is not
edited afterwards.

### Where practice lives

`/practice` alone: write a question, see what you have written, set one aside or bring it back, choose
topics and start a quiz, and see the quizzes you have taken. `/practice/quizzes/{id}` is where a quiz
is answered, and `/practice/attempts/{id}` is the result, which is **read-only** — no control at all,
because a result is not edited and nothing on it records a learning stage.

The curriculum, plan, month, day, revision, resource, and progress screens are **unchanged**. In
particular `/progress` gains nothing: PRG-001 still waits on stored mistake evidence, and adding a
quiz panel there would need exactly the counting this decision refuses.

## Consequences

### Positive

- A learner can practise a topic today, with no AI provider, no network access, and no third-party
  content — the deterministic core the product is built around.
- The repository stays free of question content and of any licensing question about it.
- The terminology/schema conflict is resolved once, explicitly, in a document rather than
  rediscovered by each change that touches an assessment.
- Marking is a pure function over plain values, so it can be tested exhaustively and explained to a
  learner who disagrees with it.
- A result cannot drift: questions are immutable, so an attempt reads back exactly as it was marked.
- The migration is purely additive — seven `CREATE TABLE`s, no `ALTER`, no rewritten row — so no
  existing learner data is touched or reinterpreted.
- `mistake_evidence` and the external-evidence area stay untouched and unconstrained by anything
  decided here.

### Negative

- **FR-009 is not met in full.** Its fifth criterion asks for stored mistakes, which needs
  `mistake_evidence`, which cannot exist until `external_test_results` and `study_activities` do. Its
  second criterion — "the quiz can use relevant notes/PYQs as context" — needs retrieval, which does
  not exist.
- A learner starts with an empty question bank and must write questions before they can practise. The
  screen says so, but the first use of `/practice` is work rather than reward.
- A learner writing a question also writes its answer, so the quiz tests recall of their own
  material rather than an independent check. This is honest but limited, and no wording can make it
  otherwise.
- A question cannot be corrected in place, which will surprise anyone who has used `/resources`.
- Only `multiple_choice` is offered, so numeric GATE questions — a large share of the real paper —
  cannot be written yet.
- Nine endpoints and seven tables is a large single change, larger than any since the planning area.
- **QZ-006 returns every question of every listed attempt.** The attempt schema is uniform, so a page
  of attempts carries each one's outcomes — prompts and options included — although the history
  screen shows only a title and a status. The uniformity is deliberate: a list that silently omits a
  field the same schema populates elsewhere reads as "this attempt had no questions". The cost is a
  payload that grows with the learner's own question bank, and the fix, if it becomes one, is a
  separate summary shape rather than a quietly emptied field.

### Neutral

- **FR-006 is still not met in full.** Its second criterion wants resource *and practice* suggestions
  on a revision. This supplies practice questions to the product but deliberately does not surface
  them on `/revisions`, because doing so would mean recommending a quiz for a topic, and nothing in
  LearnFlow recommends. The criterion stays open.
- `checkpoint_quizzes.status` permits `draft` and `archived`, and `quiz_attempts.status` permits
  `submitted` and `abandoned`, none of which anything writes. Each is reachable by a use-case change.
- Nothing counts a learner's quizzes, and no quiz count appears in the interface at all.

## Alternatives considered

### Ship a curated question bank authored in this repository

Author a set of original GATE-CSE-style questions, seeded idempotently like the curriculum.

**Rejected:** the questions would be subject content nobody had reviewed, presented with the
authority of the product; they would cover a handful of the curriculum's 65 topics, so most topics
would still yield an empty quiz; and "original but GATE-style" is a licensing position dressed as an
engineering one. Learner-authored questions need none of that, and follow ADR-032's precedent exactly.

### Use verified previous-year questions

Populate `verified_pyq` from real GATE papers.

**Rejected:** third-party content with an unresolved licensing position, and no verification process
exists to make the value honest. The `CHECK` keeps the value available for a decision that actually
takes that position.

### Generate questions with the AI provider

Populate `generated` from Ollama.

**Rejected:** no AI provider is wired, and FR-009's marking must stay deterministic and usable with
none reachable. A generated question also has no reliable expected answer, so marking it would be
guesswork presented as a result. This waits on Milestone 4's mentor work.

### Store `score` and `max_score`, and show a per-attempt count

One mark per question; report "you answered 3 of these 5 correctly in this attempt".

**Rejected:** "3 of 5" is structurally the shape [terminology.md](../domain/terminology.md) forbids
by name, and it fails all three of that document's own tests. It would also require amending an
`approved` document to permit the very figure it was written to exclude. The columns stay uncreated
rather than created and left unread, so no future change inherits a half-decided mark scheme — and the
open question of numeric precision stays open.

### Let a question be edited

Allow QZ-010 to change the prompt, options, and expected answer.

**Rejected:** `quiz_attempt_answers` references a question by identifier, so an edit would silently
rewrite every past result marked against it. Retire-and-rewrite keeps both readable, which is what
the product does everywhere else it could have overwritten a record.

### Cap the number of questions a quiz asks

Ask the first ten, or a sample.

**Rejected:** choosing which few to ask is a ranking, whatever the rule. The learner controls the
length by choosing topics and by how many questions they have written, which is a decision they can
predict.

### Include questions linked to a chosen topic's subtopics

Walk the curriculum tree when assembling.

**Rejected:** it makes the quiz's contents depend on curriculum shape the learner cannot see while
choosing. Asking exactly what was linked to exactly what was chosen is a rule a learner can hold in
their head. Choosing a parent *and* its subtopics remains possible and explicit.

### Record a learning stage from a result

Move a topic to `practice_ready` when a learner answers its questions correctly.

**Rejected:** FR-005 and FR-009 both refuse it, ADR-017 makes the stage the learner's own statement,
and a quiz over questions the learner wrote themselves is the weakest possible evidence for an
inference like that. The result links to the curriculum screen instead.

## Implementation notes

- The rules live in `backend/app/domain/checkpoint_marking.py`, the **third** module of the domain
  layer, alongside `study_planning.py` and `revision_scheduling.py`. It holds option keying, quiz
  ordering, and answer marking, and it holds no score.
- Two use cases share one repository port: `manage_practice_questions.py` (QZ-008 to QZ-010) and
  `manage_checkpoint_quizzes.py` (QZ-001 to QZ-007).
- The `jsonb` payloads — `options`, `expected_answer`, `submitted_answer` — are read and written
  **only** in `checkpoint_practice_repository.py`. `QuestionRecord` carries flat values, so no layer
  above persistence knows the stored shape.
- `QuizQuestionView` and `QuizQuestionSchema` have **no field** for the expected answer or the
  explanation, so QZ-002 cannot leak one by forgetting to strip it. Assert this in an API test rather
  than trusting the mapping.
- Every timestamp comes from the server's clock through the `Clock` port, including a question's
  `written_at` — a caller able to set that could reorder a quiz.
- Migration `20260818_01` creates all seven tables and four indexes, alters nothing, and drops
  children before parents on downgrade.
- The frontend reuses `features/resources/topic-options.ts` for the topic pickers. It is the same
  presentation problem, and a second copy would be a second thing to keep in step with CUR-003.
- The result screen renders no colour by outcome: the words carry the meaning, so nothing is lost by
  a learner who cannot see the styling.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-008: Model assessment topics and mistake evidence sources explicitly](ADR-008-assessment-and-mistake-evidence-model.md) — the accepted model this decision implements without reopening
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — why a column arrives with the code that maintains it
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the determinism promise kept here for an assessment
- [ADR-028: Schedule revisions from finished work, on the learner's ask](ADR-028-revision-workflow.md) — the precedent for a learner-owned record that is not a plan item
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](ADR-032-learning-resource-catalogue.md) — the "nothing curated ships" precedent, and the editing rule this one departs from
- [Functional requirements](../requirements/functional.md) — FR-009, and what of it is still unmet
- [Domain terminology](../domain/terminology.md) — the rule against a number that rates the learner
- [Database schema](../database/schema.md) — the approved assessment area and the departures from it
- [API endpoints](../api/endpoints.md) — QZ-001 to QZ-010
- [Delivery milestones](../roadmap/milestones.md) — Milestone 5, and what of it stays closed
- [Architecture decision register](../architecture/decisions.md)
