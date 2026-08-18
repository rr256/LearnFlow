---
title: "ADR-034: Show the Checkpoint-Practice History as a Paged Reading of Stored Attempts, Counting Nothing"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-18
related:
  - ../00-project-context.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-023-daily-study-view.md
  - ADR-026-monthly-study-view.md
  - ADR-029-progress-overview.md
  - ADR-030-learning-stages-by-subject-panel.md
  - ADR-031-priority-focus-panel.md
  - ADR-033-checkpoint-practice-workflow.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-034: Show the Checkpoint-Practice History as a Paged Reading of Stored Attempts, Counting Nothing

## Status

Accepted — 2026-08-18

Supersedes nothing. It extends
[ADR-033](ADR-033-checkpoint-practice-workflow.md), which is **accepted**, and reopens none of it:
no question becomes editable, no quiz is assembled differently, no attempt is re-marked, and no
score appears. It adds one screen and changes no contract.

## Context

[ADR-033](ADR-033-checkpoint-practice-workflow.md) shipped checkpoint practice with an attempt list
on `/practice`: a quiz title linked to its result, a state word, and the submitted date. That list
was deliberately thin, and the ADR recorded the consequence in its own words — **"QZ-006 returns
every question of every listed attempt … although the history screen shows only a title and a
status."** *The history screen* there is that `/practice` panel, which was the only one there was;
[terminology](../domain/terminology.md) now reserves **checkpoint practice history** for the screen
this decision adds, so the older phrase is read as naming the panel wherever ADR-033 uses it. The
payload a learner already pays for carries what became of every question, and nothing reads it.

Two gaps follow from that. A learner cannot tell one *Practice: CPU scheduling* from the next
without opening each in turn, because the entries differ only by date. And "earlier" attempts are
whatever fits in one request: the screen asks for the maximum page and shows what comes back, so an
attempt beyond it is unreachable from the interface even though QZ-006 has always accepted `offset`.

The hard question is not either of those. It is that **a history is the shape most likely to become
a score**. Once several attempts sit on one screen, the obvious next features are all forbidden:
how many quizzes the learner has taken, how many questions they got right in each, a run of good
ones, a comparison with last week.
[terminology.md](../domain/terminology.md) forbids each by name — "no percentage complete, no
completion rate, no '14 of 60 done', no streak, no score" — and says of this area specifically that
**"nothing counts a learner's quizzes, no quiz count appears in the interface, and no attempt is set
against another."** A history screen that quietly acquires one of them would undo the hardest thing
ADR-033 decided.

There is a mechanical trap alongside the design one. Every collection response carries a
`pagination` block with a `total`, per [ADR-014](ADR-014-api-response-contract.md), and `total` on
QZ-006 is exactly the count of the learner's quizzes that terminology forbids showing. Any paging
design that reaches for `total` to decide whether a next page exists is one careless render away
from displaying it.

## Decision

### The history is a reading; no contract changes

`/practice/history` reads QZ-006 exactly as catalogued and links to the `/practice/attempts/{id}`
result view ADR-033 already built. It adds **no endpoint, no changed response shape, no column, no
migration, and no backend file change at all** — the shape [ADR-026](ADR-026-monthly-study-view.md),
[ADR-029](ADR-029-progress-overview.md), [ADR-030](ADR-030-learning-stages-by-subject-panel.md), and
[ADR-031](ADR-031-priority-focus-panel.md) each used. Every fact on the screen is already a field of
a response QZ-006 has returned since ADR-033, so [ADR-023](ADR-023-daily-study-view.md)'s bar for a
new endpoint is not cleared.

This also disposes of the "separate summary shape" ADR-033 named as the eventual fix for QZ-006's
payload. The payload is not the problem it was expected to be, because the screen now *uses* what it
carries: a lighter list shape would have to be added back the moment the outcomes were wanted.

### Nothing is counted, and `pagination.total` is never read

The screen states **no figure about the learner at all**: no score, no mark, no percentage, no count
of quizzes taken, no count of questions answered or answered correctly, no streak, no average, and
no comparison between two attempts. No page is numbered, because numbering pages counts them.

Whether an older page exists is decided by **asking QZ-006 for one record more than a page shows**
and seeing whether it came back. `pagination.total` is deliberately never read, not merely never
rendered: the safest way not to display a count of a learner's quizzes is not to hold one. The
frontend's `unwrapCollection` already discards the block, and nothing here reaches past it.

### A page is not a cap

[ADR-031](ADR-031-priority-focus-panel.md) refuses to cap the priority list, because choosing which
few of a set to show *is* a ranking. Paging is not that, and the distinction is worth stating so the
two are not confused later:

- The order is **QZ-006's own** — newest first, which is chronological rather than a judgement.
- **Every attempt stays reachable**, by walking back one page at a time.
- Nothing is selected on merit, and nothing is left out.

The `/practice` panel keeps the same discipline: it shows the most recent attempts and links to the
whole history, rather than being the whole history. It says *that* there are earlier ones — which is
a fact about the list, not a figure about the learner — and never how many.

### An entry says what the attempt covered, and what became of each question, in words

Each entry names the topics the attempt covered, when it happened, and its state; and it carries a
`<details>` disclosure, closed to begin with, listing each question's prompt with its outcome stated
in the words ADR-033 fixed — *You chose the expected answer*, *Not the expected answer*, *You did not
answer this one*. **An unanswered question is still not a wrong one**, and the three stay apart here
exactly as they do on the result.

`<details>` is used rather than a scripted panel because every practice screen works with JavaScript
disabled and a browser opens this one on its own. It starts closed so that a page of attempts reads
as a list of attempts, and opening one is the learner's choice rather than the screen's.

**The expected answer and the explanation stay on the result view.** A history that repeated the
whole result would leave nothing to open, and would make `/practice/attempts/{id}` redundant while
duplicating its wording in a second place to keep in step. The disclosure links there instead.

**Nothing is coloured by outcome**, on the entry or inside the disclosure. The words carry the
meaning, so a page of attempts cannot be read as a pattern of wins and losses by anyone, including a
learner who cannot see the styling.

### An attempt that was never submitted reads back as nothing

An `in_progress` attempt has no marked outcomes. Rendering its questions through the same list would
report every one of them as unanswered, which states something the learner never did — the same
mistake ADR-033 refused when it kept `is_correct` null rather than writing `false`. The entry says
the attempt was never submitted and stops there.

### Read-only, and nothing else moves

There is **no control on the screen at all**: no `<button>`, `<form>`, `<input>`, or `<select>`.
A record of what happened is not edited afterwards, which is ADR-033's rule for the result view, and
nothing here records a learning stage, moves a plan or a plan item, or schedules a revision.

### An offset that makes no sense is the newest page, not a `404`

`?offset=` is read as a whole number of records at or after the newest. A missing, negative,
fractional, or unparseable value — and the repeated parameter Next.js hands over as an array — reads
as the newest page. A mistyped address is a learner who wants their history, not a missing resource,
and this screen has no identifier to fail to find. Walking back from an offset that falls between
pages steps to the newest rather than past it.

### `/progress` gains nothing, and FR-011's quiz-history criterion stays unmet

[FR-011](../requirements/functional.md#fr-011-progress-overview)'s unmet criterion asks for recent
quiz history **on the progress overview**. This change does not touch `/progress`, so that criterion
stays **not met**, exactly as [endpoints.md](../api/endpoints.md) records. The reason is unchanged
from ADR-033 and ADR-029: summarising attempts beside a learner's plan, stages, and priorities is
where a screen is tempted to add them up, and PRG-001 still waits on stored mistake evidence.
A history a learner opens deliberately, on the practice screen, is not the same thing as a panel
that follows them onto an overview.

### The day is the timestamp's own

The date shown is the API's timestamp, printed as sent and marked up with `<time>`, performing **no
timezone conversion** — the position the practice screens have taken since ADR-033. The learner's
own calendar date is `learnerToday`, which needs LRN-001, and this screen deliberately reads nothing
the practice area did not already read. Conversion, if it is ever wanted, belongs to the whole
practice area at once rather than to one screen of it.

## Consequences

### Positive

- A learner can find an earlier attempt by what it covered and read what became of each question
  without opening several results in turn.
- Every attempt is reachable from the interface, which it was not before.
- The payload ADR-033 flagged as a cost is now the thing the screen is built from.
- No contract moves, so nothing that reads QZ-006 today can break, and the change is entirely
  reviewable as frontend markup and pure functions.
- The counting rule is enforced structurally rather than by care: `pagination.total` is not held, and
  the paging functions carry no field that could become a count.
- The whole screen works with JavaScript disabled, including the disclosures and the paging links.

### Negative

- The `/practice` panel now shows fewer attempts than before — the most recent page rather than up to
  a hundred — so a learner who scrolled that panel now follows a link instead.
- One page costs one extra attempt's payload, which on QZ-006's uniform shape means one extra
  attempt's questions and options.
- Walking back is one page at a time, with no way to jump: a numbered pager would be a count, and a
  date filter would be a new query parameter and therefore a contract change.
- A learner with many attempts still walks back through them in order to reach an old one. Searching
  or filtering a history is a real want that this deliberately does not answer.
- Two components now render an attempt entry — the compact panel and the history — sharing their
  wording through `features/practice/history.ts` rather than through one component, because the two
  differ in what they disclose.

### Neutral

- **FR-009 is unchanged.** This stores nothing and marks nothing, so every criterion stands exactly
  as ADR-033 left it. **FR-009 is still not met in full.**
- **FR-011 is unchanged**, and still not met in full, for the reason above.
- `quiz_attempts.status` still permits `submitted` and `abandoned`, which nothing writes; the history
  falls back to the stored word for a status this build does not recognise, rather than inventing a
  reading for one.
- QZ-004 stays unimplemented, and an unfinished attempt is still resumed by starting the quiz again
  from `/practice`. The history says so and offers no control of its own.

## Alternatives considered

### Show the per-question outcomes inline on the `/practice` panel

Expand the existing panel in place, with no new route.

**Rejected:** `/practice` is where a learner writes questions and starts a quiz, and ADR-033 fixed it
as that. A panel that grew to hold every attempt's questions would push that work below a history,
and it would still leave attempts beyond one request unreachable — which is half the problem.

### Read `pagination.total` to decide whether an older page exists

Use the count the envelope already carries, and simply never render it.

**Rejected:** it is the count of the learner's quizzes, which terminology forbids showing by name.
Holding it in a props object one render away from the markup makes the rule a matter of care rather
than of structure. Asking for one extra record costs one attempt's payload and cannot leak a figure.

### Number the pages

"Page 2 of 7", or numbered links.

**Rejected:** a page count is a count of the learner's quizzes divided by a page size, which is the
forbidden figure with an extra step. *Earlier* and *more recent* say where a link goes without
saying how far the list runs.

### Add a summary line to each entry

"Two of these went the way you expected."

**Rejected:** this is "3 of 5" in a longer sentence, and it fails all three of terminology's tests —
its subject is the learner, it is meaningless for an attempt nobody made, and on a page of attempts
it invites exactly the comparison the third test rules out. A history is the place that temptation is
strongest, which is why it is refused here explicitly rather than left to be rediscovered.

### Filter the history by topic

A topic picker over the history, using a new QZ-006 query parameter.

**Rejected here, not forever:** it needs a contract change, so it belongs to a decision that takes
one, and a per-topic history is one step from a per-topic verdict. The topics each attempt covered
are named on every entry, which is what makes the list readable without one.

### Show recent quiz history on `/progress`

Meet FR-011's unmet criterion by putting a panel on the overview.

**Rejected:** unchanged from ADR-029 and ADR-033. An overview gathers a learner's situation, which is
where a screen is tempted to summarise; a list of attempts there would want a figure to be worth its
space. The criterion stays honestly unmet.

## Implementation notes

- `frontend/features/practice/history.ts` holds the pure functions: `readHistoryOffset`,
  `selectHistoryPage`, `historyHref`, `attemptStateLabel`, `attemptMoment`, and `coveredTopics`.
  Plain functions, so they are testable without a running server — the reason
  `features/resources/by-topic.ts` and `features/progress/stages.ts` are separate modules too.
  `HistoryPage` carries exactly three fields: the attempts, and the two offsets. Assert that in a
  test, so a count cannot be added to it quietly.
- `frontend/features/practice/PracticeHistory.tsx` is the screen body;
  `frontend/features/practice/AttemptHistory.tsx` keeps the compact `/practice` panel and gains a
  `hasMore` flag, which changes wording only and carries no figure.
- `frontend/app/practice/history/page.tsx` is `force-dynamic`, like every other practice route, and
  declares its own `<Suspense>` boundary rather than a `loading.tsx` segment file, per
  [folder-structure.md](../development/folder-structure.md). Nothing on it calls `notFound()`.
- `listQuizAttempts` is used unchanged: `limit` and `offset` were already parameters.
- Test that no `<button>`, `<form>`, `<input>`, or `<select>` renders, that no `%`, no `n of m`, and
  no page number appears, and that an unsubmitted attempt renders no outcome list — the three ways
  this screen could stop being honest.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-033: Assemble checkpoint practice from the learner's own questions, and report outcomes rather than a score](ADR-033-checkpoint-practice-workflow.md) — the workflow this reads, and the payload cost it recorded
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](ADR-026-monthly-study-view.md) — the frontend-only reading shape
- [ADR-029: Show the progress overview as a reading of what is stored, counting nothing of its own](ADR-029-progress-overview.md) — why `/progress` gains no quiz panel
- [ADR-031: Draw priority focus from facts backend rules already decided, ranking nothing](ADR-031-priority-focus-panel.md) — the capping rule, and why paging is not one
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the `pagination` block this deliberately does not read
- [Domain terminology](../domain/terminology.md) — checkpoint practice history, and the rule against a number that rates the learner
- [API endpoints](../api/endpoints.md) — QZ-006 and QZ-007, read unchanged
- [Repository and folder structure](../development/folder-structure.md) — the route and the feature module
- [Delivery milestones](../roadmap/milestones.md) — Milestone 5, unchanged by this
- [Architecture decision register](../architecture/decisions.md)
