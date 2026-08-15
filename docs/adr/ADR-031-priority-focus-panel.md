---
title: "ADR-031: Draw Priority Focus From Facts Backend Rules Already Decided, Ranking Nothing"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-15
related:
  - ../00-project-context.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-022-plan-adaptation.md
  - ADR-023-daily-study-view.md
  - ADR-026-monthly-study-view.md
  - ADR-027-plan-feasibility.md
  - ADR-028-revision-workflow.md
  - ADR-029-progress-overview.md
  - ADR-030-learning-stages-by-subject-panel.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-031: Draw Priority Focus From Facts Backend Rules Already Decided, Ranking Nothing

## Status

Accepted — 2026-08-15. Proposed 2026-08-15.

Accepted once the decision below was verified rather than merely argued. **Nothing in the decision
changed on acceptance.** The whole canonical check set is green — the backend suite with warnings as
errors (**901 passed, 257 skipped**), Ruff lint and format across the backend and `scripts/`, the
frontend lint, type check, **623 tests**, and production build, and the documentation validator. The
**scriptless standalone-frontend run was performed** against a contract-shaped stub API with the
server on `TZ=UTC`: **89 checks passed**. The run enforced "no JavaScript" by never running any — it
issued raw HTTP requests and read the served HTML, so a control that only worked once hydrated could
not have passed.

Verified structurally rather than by inspection: `/progress` renders **no `<button>`, no `<form>`, no
`<select>`, and no `<input>`**; **every request it issued was a `GET`**, none carried a `learner_id`,
PRG-001 was never reached, and the page made exactly **nine requests across the eight catalogued
contracts and nothing else**; the panel **states no figure of its own**, and **no stage label appears
in it** while the stages panel still carries all five; and **no API address appeared** in the served
HTML. Also verified: each of the three signals with its neutral fact and the record's own sentence; a
settled item and a review whose day has not come both absent; the fixed group order; both empty
states; the `unknown` branch naming the missing input and sending the learner to `/setup`; and a
learner in `Pacific/Kiritimati` shown **their own date** while the server ran on UTC a day behind.

The counting and ranking assertions were checked against a **negative control** — a per-group count
and an ordered list were injected into the panel, the build repeated, and both checks confirmed to
fail — then reverted and the run repeated green. That control also **found a real gap**: the original
counting assertions passed a bare `(2)` in a heading, so they were tightened to require that the
panel's own copy carry no figure at all before the control was trusted. ADR-029 recorded two of its
own harness assertions as weak when found mid-run, which is why this one was proven rather than
trusted.

**The PostgreSQL integration tests were not run, and are not relevant**: no backend file changed — no
route, use case, DTO, domain rule, model, or migration — so there is no SQL for them to exercise.
This is [ADR-030](ADR-030-learning-stages-by-subject-panel.md)'s precedent.

This adds **no endpoint, no column, no table, no migration, and no backend change at all**. It is a
third application of the frontend-only reading shape
[ADR-026](ADR-026-monthly-study-view.md) fixed and [ADR-029](ADR-029-progress-overview.md) and
[ADR-030](ADR-030-learning-stages-by-subject-panel.md) each applied.

**FR-011 is still not met in full**, and this record is explicit about what it does and does not
close. See [What FR-011 asks, and what this meets](#what-fr-011-asks-and-what-this-meets).

## Context

[FR-011](../requirements/functional.md#fr-011-progress-overview)'s third acceptance criterion — "The
learner can view priority focus areas based on the available evidence" — is the criterion whose blocker was
believed to be a design question rather than a missing table. It is not the only one unserved — the
fourth, quiz and external-test history, waits on FR-009 and FR-010 — and Milestone 2's
progress-overview item stays open on material status and study activity as well. But it is the last
reason [PRG-001](../api/endpoints.md#prg-001-prg-003-act-001-and-act-002-not-implemented) was said to
be unbuildable rather than merely unbuilt.

**Two accepted records state that it cannot be built.** ADR-029 and ADR-030 each carry the same row:

> **Not met, and not buildable.** Nothing stores quiz outcomes, external test results, or mistake
> evidence, and ranking topics against each other is refused by terminology.

That sentence gives **two** reasons, and this record has to answer both before it may propose
anything. It concludes that the second reason is decisive against one design and irrelevant to
another, and that the first is true of one kind of evidence and false of another.

### The finding that reopened the question

**"Priority focus" was read as a ranking because the only designs considered were rankings.**

Terminology's *Priority focus area* row defines the term as "a topic or action currently likely to
benefit the learner **most**", and *most* is a superlative over topics. Read that way, the criterion
asks for exactly what terminology forbids elsewhere — "Nothing in LearnFlow ranks two topics against
each other" — and ADR-029's conclusion follows immediately. The quiz, test, and mistake evidence
FR-009 and FR-010 would store is what such a ranking would be scored from, which is why the two
reasons were stated together: they are the same reason, one design deep.

But LearnFlow already holds facts that say something needs attention **without comparing anything to
anything**. Each is a boolean a backend domain rule already decided and stored:

- `select_overdue` decides that an item's day has passed with nothing said about it. That is a fact
  about a **date**, not a comparison between topics, and terminology already permits saying it: "Say
  an *item* is overdue, never that the learner is behind."
- `is_due` decides that a review is owed now, and ADR-028 fixed it as "a recommendation, not a
  failure notice", read by a screen rather than derived.
- PLN-006's `assess_horizon_coverage` decides that a saved week does not reach a goal's horizon. It
  is "a statement about **the plan and the time**, never about the learner".

Every one of these is already rendered somewhere. What no screen does is **gather them and say why
each is there**. Gathering three booleans is not ranking: nothing is ordered by strength, nothing is
scored, and no topic is placed above another.

So the first reason — no stored evidence — is true of quiz, test, and mistake evidence and **false**
of plan dates, revision dates, and saved availability. And the second reason — ranking is refused —
rules out a *scored* priority list and says nothing about a *gathered* one.

Six questions had to be answered, and the project owner decided each at the delivery gate.

1. **Which existing facts may make an area a priority.**
2. **Whether priorities are topics, subjects, or both.**
3. **How a reason is shown without judging the learner.**
4. **How the empty states work, and whether an unavailable one exists.**
5. **Whether the existing reads suffice, or a read-only aggregation endpoint is needed.**
6. **Whether this needs an ADR.**

## Decision

### Three facts, each already decided by a backend rule

The panel is built from exactly three signals, and **the frontend decides none of them**:

| Signal | The rule that decided it | What the entry says |
| --- | --- | --- |
| Work whose day has passed with nothing said about it | `select_overdue`, through the existing `selectDailyWork` partition | The day the plan named, and that it has passed |
| A review the backend reports as owed now | `is_due` on REV-001, read and never derived | The day it has been ready from |
| A saved week that does not reach the horizon, or a question that cannot be answered | PLN-006's `verdict` | Which of the two, and which input is missing |

Each entry is a **filter on a boolean plus a choice of words**. Nothing is computed, weighted,
combined, or compared, and there is no composite of the three.

**A `sufficient` verdict yields nothing**, because a week that reaches the date needs no attention. A
verdict this build does not recognise also yields nothing, in **either** direction: claiming a
priority from a value that cannot be interpreted would put a demand in front of a learner that no
rule made, and the feasibility panel below still renders the reading in full.

### The learning stage is deliberately not a signal

**This is the decision the record exists to make.** Treating *Building foundation* and *Developing
confidence* as priorities, and *Practice-ready* and *Strong understanding* as not, would rank the
five stages against each other — which is precisely what
[ADR-017](ADR-017-topic-progress-api-and-schema.md) recorded ("no code treats the order as a
ranking") and [ADR-030](ADR-030-learning-stages-by-subject-panel.md) refused for the panel next to
this one ("No ordering, grouping, or colouring by stage"). A learner may move to any stage from any
stage, including backwards, so no stage is behind another, and a product that quietly sorted them
would have decided otherwise on the learner's behalf.

It is also the design that would make the *weak topic* wording terminology bans structurally true:
a panel headed "what needs attention" listing every topic at the lowest two stages **is** a weak-topic
list, whatever it is called.

**The stage still reaches the learner here**, and without being reinterpreted: where a recorded stage
explains a plan item, it is already inside that item's own `recommendation_reason`, written when the
plan was generated ([ADR-020](ADR-020-initial-study-plan-generation.md)) and rendered unchanged. The
panel repeats the plan's sentence rather than forming a second opinion from the same fact.

### Priorities are named items and reviews, never subjects

Entries are individual plan items and individual reviews — topics, named one at a time. **No subject
roll-up.**

A subject-level priority needs one of two things, and both are refused. Either a count per subject —
"Operating Systems, 4 items outstanding" — which fails all three of terminology's tests and is the
figure ADR-030 refused verbatim for the panel beside this one; or an unquantified claim that a
subject needs work, which is a comparison against the subjects it is shown above and beside.

### Two sentences per entry, both from records

Each entry carries a **neutral fact** naming the stored record that put it there — "Your plan placed
this on 2026-08-13, and that day has passed with nothing said about it" — and then **the sentence the
backend wrote**: the plan item's `recommendation_reason`, the revision's, or PLN-006's `reason`,
rendered unchanged.

This is the rule every screen in the product already follows for `generation_reason`. A screen that
composed its own explanation could disagree with the record it is explaining.

**The subject of every sentence is a record.** An item's day passed; a review is ready; a week falls
short of a date. The learner is never behind, never weak, never at risk, and is never asked why.

### Nothing is ordered, counted, or ranked

The three groups appear in a **fixed presentation order**, held in the module in the same sense that
Monday comes first in a week. It ranks nothing, and the panel says so in copy a test asserts: *"They
are not in any order of importance."* Within a group the backend's own order is kept — day order for
items, API order for reviews.

**No entry is numbered, no group is called urgent or most important, and there is no top-anything.**
No count of how many things need attention, no percentage, no fraction, no streak, and no bar — the
stylesheet declines a `<progress>` and a `<meter>` for the reason
[ADR-027](ADR-027-plan-feasibility.md) gave. Every group is styled identically, deliberately: a
heavier border or a warning colour on one would be a ranking drawn rather than written.

The module computes list lengths to decide whether a group has anything to show; **none of them
reaches the screen**, which is the rule ADR-029 wrote for the same directory.

### It writes nothing, and sits above the panels that answer *where am I*

The panel renders **no `<button>`, no `<form>`, no `<input>`, and no `<select>`** — ADR-026's
read-only decision applied a fourth time. **Every group names where its action lives and links to
it**: outstanding work to `/plan/today`, reviews to `/revisions`, a shortfall to `/plan`, and an
unanswerable time question to `/setup`.

It is rendered **first** on `/progress`. A learner opening the screen is asking what to pick up; the
panels below answer where they are.

### Two empty states, kept apart — and no invented third

- **Nothing flagged** — said as a fact about the records rather than as praise, naming what would
  appear here so an empty panel does not read as a broken one.
- **No weekly plan** — a distinct sentence, because with nothing dated there is no day for anything
  to have passed on. Saying "nothing is waiting" alone would imply the learner is up to date.

**A third state was designed, built, and then removed**, and the reason is worth recording. The panel
first reported "the time check could not be read" apart from a `sufficient` verdict — ADR-030's
"could not be read" against "you have recorded nothing", applied to a different pair. Verification
showed the state is **unreachable**: `readPlanFeasibility` throws an `ApiError` rather than resolving
to null, and `/progress` lets that reach the page-level handler, which is
[ADR-029](ADR-029-progress-overview.md)'s decision about an unreachable API. Copy for a state that
cannot occur is worse than no copy, and **making that read non-fatal — as the PRG-002 and CUR-003
pair is — would change an error behaviour ADR-029 verified**, which belongs to a change about
feasibility rather than to this one. The selection function still tolerates a null reading, because
the prop it comes from is typed that way, and contributes no entry rather than a claim in either
direction. Whether the feasibility read should become non-fatal on this screen is left open below.

### The existing reads suffice; PRG-001 still is not built

Every fact the panel states is **already a field of a response `/progress` fetches**. It reads
nothing new: `/progress` still reads the same **eight contracts** — LRN-001, GOAL-002, PLN-002, PLN-003,
PLN-006, REV-001, PRG-002, and CUR-003 — over the same **nine requests**, since PLN-003 is addressed
once per plan. No API client function was added.

It clears no part of [ADR-023](ADR-023-daily-study-view.md)'s bar for a new endpoint, which is that
the screen "needs something the current reads cannot express". **PRG-001 stays unimplemented**, and
its remaining gap narrows to exactly one thing: the quiz, test, and mistake evidence its purpose also
promises, which FR-009 and FR-010 would store and which does not exist.

### What FR-011 asks, and what this meets

| Acceptance criterion | State after this change |
| --- | --- |
| View progress by subject and topic | **Met, for the progress LearnFlow stores**, by [ADR-030](ADR-030-learning-stages-by-subject-panel.md). |
| View upcoming study tasks and revisions due | **Met**, by [ADR-029](ADR-029-progress-overview.md). |
| View priority focus areas based on available evidence | **Partly met — for the evidence LearnFlow stores.** Work whose day has passed, reviews the backend reports as due, and a saved week that falls short are gathered and explained. Quiz outcomes, external test results, and mistake evidence are still stored nowhere, so no priority is drawn from them. |
| View recent quiz history and manually entered external test results | **Not met.** FR-009 and FR-010 do not exist; no quiz attempt or external test result is stored. |

**Do not write that FR-011 is complete.** Two of its four criteria are met and a third is partly met.

### This supersedes one row of ADR-029 and ADR-030, and nothing else

Both accepted records state that priority focus areas are "**not buildable**". **That conclusion is
superseded by this record on the narrow ground stated above** — the ranking objection does not reach
a design that ranks nothing, and plan dates, revision dates, and saved availability are stored
evidence.

**Neither record is edited.** Their text stands as the reasoning that was correct for the designs
they considered, which is what an ADR is for. Instead, each gains an **`## Implementation status`
note** in the form [ADR-022](ADR-022-plan-adaptation.md) and [ADR-023](ADR-023-daily-study-view.md)
already use: a dated section recording what later changed, leaving every word of the decision above
it untouched. The register's DEC-041 and DEC-042 rows carry the same pointer, because the register is
a navigation aid rather than a decision record. Everything else in both — the read-only shape, the
counting rule, the refusal to fix PRG-001's contract, and ADR-030's refusal to order by stage —
is **unchanged and load-bearing here**, and this record follows all of it.

## Consequences

### Positive

- **A learner has one place that answers *what should I pick up*.** Three facts that were spread
  across a note, a panel, and a second panel are gathered with the reason each is there.
- **No endpoint, no column, no table, no migration, and no backend file changes.** Nothing stored is
  reinterpreted and no public contract moves, so this change is reversible by deleting a panel.
- **The last blocker on Milestone 2's progress-overview item narrows to one thing.** What remains is
  quiz, test, and mistake evidence, rather than an unresolved question about whether the criterion is
  buildable at all.
- **No new rule and no new mirror.** `select_overdue` gains no second frontend mirror: the panel
  calls the existing `selectDailyWork`, so `/plan/today`, the overview's today panel, and this panel
  cannot disagree about which work is outstanding. `is_due` and the feasibility verdict are read.
- **The ranking line is enforced by tests rather than by review**, at the place it is most tempting
  to cross: the panel tests assert no count, no percentage, no fraction, no `<progress>`, no
  `<meter>`, no ranking wording, and no copy describing the learner.
- **No AI provider is involved and no configuration variable is read.** The same records and the same
  instant produce the same panel.

### Negative

- **The panel repeats what two panels below it already show.** A due review appears here and under
  *Ready to review*; outstanding work appears here and as a note under *Today*. That is what a
  summary is, and ADR-029 accepted the same cost, but a wording change now has two places to land.
  Mitigated by rendering from the *same selection functions*, never from copies.
- **A learner may read the panel as a ranking anyway**, because "priority" invites it. The copy says
  the entries are in no order of importance, but a heading cannot fully control how a list is read.
- **"Priority focus area" now names something narrower than its terminology definition suggests.**
  The row says "likely to benefit the learner **most**", and this panel makes no claim about *most*.
  The row is amended in the same change to say what is actually built.
- **A week with many items whose days have passed unsettled produces a long list.** Every
  outstanding item is named, with no cap and no paging, because capping would require choosing which
  to show — a ranking. A plan spanning seven days bounds it in practice.
- **Nothing here helps a learner who is doing well.** The panel is empty for them, which is correct
  and may read as anticlimactic.

### Neutral

- Nothing totals, counts, ranks, or scores. The panel introduces no figure at all.
- The backend is untouched: no route, use case, DTO, domain rule, model, or migration.
- `monthly` and `daily` remain approved and unwritten `plan_type` values. `plan_items.status`, the
  revision statuses, and `stage_source` are untouched, and nothing writes a learning stage.
- No learner flow changed. Setup, the curriculum view, the plan screens, the daily and monthly views,
  and the revision screen are all exactly as they were.
- `material_status`, `material_completed_at`, and `last_studied_at` remain uncreated, and ACT-001 and
  ACT-002 remain uncontracted.

## Alternatives considered

### Rank topics by recorded learning stage

List every topic at *Building foundation* and *Developing confidence*, weakest first.

**Not selected**, and this is the alternative the record exists to refuse. It ranks the five stages
against each other, which ADR-017 and ADR-030 both rule out, and it is the *weak topic* list
terminology bans by name with a different heading on it. A learner may move to any stage from any
stage; a product that sorted them would have decided that one end is worse, which nothing in
LearnFlow does.

### Score each topic and show the highest

Combine stage, overdue count, and revision history into a number, and sort by it.

**Not selected:** it is a learner score, which terminology's third test rules out — it invites a
comparison against last week, against a target, and against another learner. It would also need the
quiz, test, and mistake evidence that does not exist to be anything but arbitrary.

### Show priority by subject

"Operating Systems needs attention", with a count of what is outstanding in it.

**Not selected:** the count fails all three of terminology's tests and is the figure ADR-030 refused
for the panel beside this one, and the claim without the count is a comparison against the subjects
around it.

### Implement PRG-001 as a read-only aggregation endpoint

Compose the plan, the revisions, the feasibility reading, and the priorities into one response.

**Not selected**, for the reasons ADR-029 and ADR-030 both gave and which have not changed: every
fact is already a field of an existing response, so it clears none of ADR-023's bar, and its
catalogued purpose still promises evidence-based priority focus areas that nothing can supply. The
shape fixed now is the shape that would have to break when quiz and test evidence arrives, which
[versioning](../api/versioning.md#breaking-changes) makes expensive.

### Cap the list, or show only the first few

"Your three most pressing items."

**Not selected:** choosing which three is a ranking, and *most pressing* is the superlative this
record spent its length avoiding.

### Leave the criterion unmet until quiz and test evidence exists

Accept ADR-029's conclusion unchanged.

**Not selected:** it treats "not buildable" as a fact about the requirement when it was a fact about
the designs then considered. LearnFlow stores dates, statuses, and availability, and FR-011 asks for
priority focus "based on **the available** evidence" — a phrase that describes evidence that exists
rather than evidence that is wished for. Waiting would also leave a learner with no gathered answer
to *what should I pick up* for as long as FR-009 and FR-010 go unbuilt.

## Implementation notes

- **No backend file changes.** The eight contracts are consumed exactly as catalogued in
  [api/endpoints.md](../api/endpoints.md), which stays authoritative for their fields and error
  codes. No API client function was added.
- `frontend/features/progress/priority-focus.ts` holds `selectPriorityFocus` — a plain function over
  plain values, tested without a running server. Its module docstring records that the list lengths
  it uses to decide whether a group has content never reach the screen, and why the learning stage is
  not a signal.
- `frontend/features/progress/PriorityFocus.tsx` renders the panel with its CSS Module and no
  control. `StudyProgressOverview.tsx` renders it first and passes the values it already holds;
  `DailyStudyView.tsx`, `RevisionList.tsx`, and `PlanFeasibility.tsx` are untouched — extracting a
  shared entry component is a refactor, and this is a feature change, the same call ADR-023 through
  ADR-030 each made.
- `frontend/app/progress/page.tsx` changes only its lead copy and two docstrings; it reads nothing
  new and stays `force-dynamic`.
- Covered by `frontend/tests/priority-focus-selection.test.ts` — each signal, a settled item, today's
  work and a day still ahead, an unrecognised item status and an unrecognised verdict, both unknown
  reasons, the fixed group order, an undated roadmap, a topic no longer stored, and that no figure is
  returned — and `frontend/tests/PriorityFocus.test.tsx`, which asserts the headings, both reason
  sentences, the action links, that **no control of any kind is rendered**, that **nothing is
  counted**, that **nothing is ranked**, that no copy describes the learner, and each of the three
  states. `frontend/tests/StudyProgressOverview.test.tsx` covers the panel in place and its position.
- Open and deliberately not settled here: whether the overview should become the home screen; what
  PRG-001 returns if it is ever built, and whether this panel would then consume it; whether quiz,
  test, and mistake evidence join this panel when they are stored, and whether that changes the
  no-ranking decision; whether a failed PLN-006 read should empty this panel's time signal rather
  than the whole screen, as a failed PRG-002 or CUR-003 read empties the stages panel; and whether marks on superseded plans should be readable anywhere.
- Recorded as DEC-043 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this panel inherits
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — why the five stages are never compared, which is why the stage is not a signal here
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the item reasons this panel renders, and the rule that a stage explains an item without reordering it
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — `select_overdue`, the rule behind the first signal, and the adaptation this panel links to rather than performing
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](ADR-023-daily-study-view.md) — the bar a new endpoint must clear, and the `selectDailyWork` partition this panel reuses
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](ADR-026-monthly-study-view.md) — the read-only shape this panel follows
- [ADR-027: Report whether the saved week reaches the horizon, as a read-only planning rule](ADR-027-plan-feasibility.md) — the verdict behind the third signal, and the counts-not-ratios rule
- [ADR-028: Schedule revisions from finished work, on the learner's ask](ADR-028-revision-workflow.md) — `is_due`, the rule behind the second signal, and why a review is a recommendation rather than a failure notice
- [ADR-029: Show the progress overview as a reading of what is stored, counting nothing of its own](ADR-029-progress-overview.md) — the screen this extends, and the one row this record supersedes
- [ADR-030: Gather the recorded learning stages by subject, listing them rather than counting them](ADR-030-learning-stages-by-subject-panel.md) — the panel beside this one, its refusal to order by stage, and the "could not be read" distinction this reuses
- [API conventions](../api/conventions.md) — the envelope and the error codes the reads answer in
- [API endpoint catalog](../api/endpoints.md) — the eight contracts this screen consumes, none of which changes, and PRG-001, which stays unimplemented
- [API versioning](../api/versioning.md) — what would make a change to PRG-001 breaking, had it been fixed here
- [Terminology](../domain/terminology.md) — *priority focus area*, and the counts and rankings a screen may not carry
- [Functional requirements](../requirements/functional.md) — FR-011, whose third criterion this partly meets
- [Coding standards](../development/coding-standards.md) — the rule that keeps planning and progress calculation in the backend
- [Repository and folder structure](../development/folder-structure.md) — where the module, the component, and their tests live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 2 item this advances
- [Architecture decision register](../architecture/decisions.md) — DEC-043
