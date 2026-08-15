---
title: "ADR-030: Gather the Recorded Learning Stages by Subject, Listing Them Rather Than Counting Them"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-15
related:
  - ../00-project-context.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-023-daily-study-view.md
  - ADR-026-monthly-study-view.md
  - ADR-027-plan-feasibility.md
  - ADR-029-progress-overview.md
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

# ADR-030: Gather the Recorded Learning Stages by Subject, Listing Them Rather Than Counting Them

## Status

Accepted — 2026-08-15. Proposed 2026-08-15.

Accepted once the decision below was verified rather than merely argued. **Nothing in the decision
changed on acceptance.** The whole canonical check set is green — the backend suite with warnings as
errors (**901 passed, 257 skipped**), Ruff lint and format across the backend and `scripts/`, the
frontend lint, type check, **592 tests**, and production build, and the documentation validator. The
**scriptless standalone-frontend run was performed** against a contract-shaped stub API with the
server on `TZ=UTC`: **59 checks passed**. The run enforced "no JavaScript" by never running any — it
issued raw HTTP requests and read the served HTML, so a control that only worked once hydrated could
not have passed.

Verified structurally rather than by inspection: `/progress` renders **no `<button>`, no `<form>`, no
`<select>`, and no `<input>`**; **every request it issued was a `GET`**, none carried a `learner_id`,
and PRG-001 was never reached; the panel **states no figure at all** once the curriculum's own subject
and topic codes are removed; and **no API address appeared** in the served HTML. Also verified:
subjects render in CUR-003's order though PRG-002 returned them newest-first; a recorded subtopic is
placed at depth; a trackable topic with no record and a subject holding no record are both absent; a
stage this build does not recognise is skipped and its `snake_case` value never reaches the HTML; a
record whose topic the tree no longer holds is kept under its own heading; the empty and unreadable
states are distinguished, with the unreadable one leaving the other five panels standing; and the
curriculum view still carries its stage control.

The counting assertion was checked against a **negative control** — a per-subject count and percentage
were injected into a subject heading, the build repeated, and all five counting checks confirmed to
fail — then reverted and the run repeated green. ADR-029 recorded two of its own harness assertions as
weak when found mid-run, which is why this one was proven rather than trusted.

**The PostgreSQL integration tests were not run, and are not relevant**: no backend file changed — no
route, use case, DTO, domain rule, model, or migration — so there is no SQL for them to exercise.

This answers the question [ADR-029](ADR-029-progress-overview.md) left open by name — "whether a
learning-stages-by-subject panel should be added" — and meets
[FR-011](../requirements/functional.md#fr-011-progress-overview)'s **first** acceptance criterion,
for the progress LearnFlow stores. It adds **no endpoint, no column, no table, no migration, and no
backend change at all**.

**FR-011 is still not met in full.** Two of its four criteria are now met. See
[What FR-011 asks, and what this meets](#what-fr-011-asks-and-what-this-meets).

## Context

[ADR-029](ADR-029-progress-overview.md) built the progress overview as a reading of six existing
contracts, and recorded this panel twice as deliberately unbuilt: once under *Alternatives* —

> **Not selected for this change**, by the project owner's decision at the delivery gate. It adds a
> sixth data source and a join for a fact already visible where it is recorded, and it would need care
> to list stages without tallying them per subject, which would be a learner score. It is a compatible
> addition: the panel is additive, needs no contract change, and would meet FR-011's first criterion
> when it lands.

— and once in its implementation notes, among what was "open and deliberately not settled here". Its
FR-011 table names the same gap: "Recorded learning stages stay where they are written, beside each
topic in the curriculum view."

So a learner could see how far along they judge themselves to be on one topic only while browsing the
whole syllabus, one topic at a time. Nothing gathered the answer to *which topics have I recorded
anything about, and where do they sit*. That is the gap this closes, and the reasons ADR-029 gave for
deferring it are the two this record has to discharge: a sixth data source, and the risk of a per-subject
tally.

Four questions had to be answered, and the project owner decided each at the delivery gate.

1. **Whether the existing reads suffice, or a read-only aggregation endpoint is needed.**
2. **How the panel handles no recorded stages, and topics the curriculum no longer places.**
3. **The panel's ordering, and where it links to.**
4. **Whether this needs an ADR.**

### The finding that shaped the shape

**Terminology's counting rule bites harder here than anywhere it has been applied yet.**

A stages-by-subject panel is the single place in the product where a per-subject figure is most
natural to write and most clearly forbidden. *Plan coverage counts are not learner scores* permits a
count that describes **a plan** and forbids "no percentage complete, no completion rate, no '14 of 60
done', no streak, no score". A count beside a subject name — "Operating Systems, 4 topics recorded" —
passes none of terminology's three tests: its subject is the learner, it would be zero for a learner
who had done nothing, and it invites comparison against the subject below it.

The panel therefore **lists and names**, exactly as ADR-029's *what you have marked* panel does, and
for the reason that record gave: an overview that may not tally must explain instead.

## Decision

### It reads PRG-002 and CUR-003; PRG-001 still is not built

The panel consumes two contracts the product already serves, through the same server-side client every
view uses. `/progress` now makes **eight** reads: LRN-001, GOAL-002, PLN-002, PLN-003, PLN-006,
REV-001, and now PRG-002 and CUR-003. **PRG-001, the catalogued
`GET /api/v1/progress/overview`, stays unimplemented.**

This is ADR-029's shape applied a second time, and it meets no part of the bar
[ADR-023](ADR-023-daily-study-view.md) set for a new endpoint — that the screen "needs something the
current reads cannot express". PRG-002 returns each record with its topic's `id`, `name`, `code`, and
`subject_id`, and accepts a `curriculum_version_id`; CUR-003 returns the subject names and the order the
syllabus teaches them in. The only work left is a join by identifier, a grouping, and a choice of
words — which is the same join the curriculum view has performed since
[ADR-017](ADR-017-topic-progress-api-and-schema.md), read the other way round.

**The version is addressed from the goal**, whose response already carries `curriculum_version.id`, so
nothing extra is read to find it and PRG-002 is filtered to the version the learner is actually working
through.

### The seventh and eighth reads are not fatal to the page

A failure of PRG-002 or CUR-003 empties **this panel and nothing else**. The other six state facts of
their own, and losing one learner-owned read should cost the reader that panel rather than the screen.

(ADR-029's quoted alternative called this "a sixth data source", counting sources rather than reads:
PLN-003 is one contract addressed twice, once per plan.)

This is ADR-017's call about the same pair, applied to a second screen: there, a failed PRG-002 costs
the reader the stage controls rather than the whole syllabus. The panel says **"could not be read"**,
which is deliberately distinct from **"you have recorded nothing"** — reporting the first as the second
would tell a learner their study history is empty when it is not.

### Only recorded topics appear, and only subjects holding one

**A topic the learner has recorded nothing against is not listed.** It reads as *Not explored*, the
neutral starting state, and it stays where it is: in the curriculum view, beside the control that would
record one. Listing every topic here would reproduce that screen and would present the absence of a
record as a gap in the learner rather than as the neutral state terminology defines.

**A subject with no recorded topic is left out entirely**, not shown empty. "None yet" beside a subject
name is one word away from the count the section below refuses, and a screen with fifteen empty subject
headings reads as fourteen omissions.

### Nothing is counted, and nothing is ranked

**No count beside a subject**, no percentage of a subject recorded, no fraction, no rate, no streak,
no score, and no bar — the stylesheet declines a `<progress>` and a `<meter>` for the reason
[ADR-027](ADR-027-plan-feasibility.md) gave, that a bar is a percentage drawn rather than written.
The grouping code computes list lengths to decide whether a subject has anything to show; **none of
them reaches the screen**, which is the rule ADR-029 wrote for the same module.

**No ordering, grouping, or colouring by stage.** The five stages are never compared: a learner may move
to any of them from any of them, including backwards, and
[ADR-017](ADR-017-topic-progress-api-and-schema.md) recorded that "no code treats the order as a
ranking". Sorting a subject's topics by stage would say a topic at *Building foundation* is behind one
at *Practice-ready*, and a colour scale would say it in a way a stylesheet cannot be tested for as
easily — so every stage is styled identically and carries its meaning **in the word alone**.

**The label is the learner's, the value is the wire's.** The panel renders the five labels
[terminology](../domain/terminology.md) defines, from the table the curriculum control already uses. A
stage this build does not recognise is **skipped rather than shown raw**, which is what
`features/progress/stages.ts` already does with the same set: the API's catalogue could gain a value
before this build knows the label for it, and a `snake_case` identifier is not something to show a
learner.

### The order is the curriculum's, arrived at by walking rather than sorting

Subjects appear in the order CUR-003 returned them and each subject's topics in the order it nests
them, subtopics included at any depth. The grouping **walks the tree and picks up a recorded stage
where one exists**, rather than sorting PRG-002's list — so the syllabus order arrives from the backend
and is rendered, never recomputed, which is the rule
[coding standards](../development/coding-standards.md#ui-responsibilities) states: "Ordering is a
curriculum rule."

That matters because PRG-002's own order is **newest first**, which is an order to read a change log in
and not a syllabus.

A record whose topic the tree no longer holds — reachable when a curriculum re-seed drops a topic a
learner had already recorded — is kept, under one final group named for that situation. Dropping it
would under-report what is stored, and showing a bare identifier under a missing subject would say
nothing to a learner.

### It writes nothing, and the control stays where a learner records one

The panel renders **no `<button>`, no `<form>`, no `<select>`, and no `<input>`**. It links to the
learning program's curriculum page — the screen that carries the stage control beside each trackable
topic — rather than to the program list a learner would then have to choose from.

This is ADR-026's read-only decision applied a third time, and ADR-029's rule that "every panel names
where its action lives and links to it". Recording a stage stays in one place, so a second surface does
not acquire its own `422` handling for a grouping topic, its own optimistic state, and its own place in
every future change to that control.

**A record on a topic whose `is_trackable` has since become false is still listed.** The learner
recorded it while it was trackable, and hiding it would misreport what is stored; no control is offered
beside it either way, so nothing here can write the stage PRG-004 would now refuse.

### What FR-011 asks, and what this meets

| Acceptance criterion | State after this change |
| --- | --- |
| View progress by subject and topic | **Met, for the progress LearnFlow stores.** The recorded learning stages are gathered under the subject each topic belongs to, in syllabus order. What is stored is the *stage* alone: `learner_topic_progress.material_status` is not created and `study_activities` does not exist, so material completion and study activity are not part of any answer yet. |
| View upcoming study tasks and revisions due | **Met**, by [ADR-029](ADR-029-progress-overview.md). |
| View priority focus areas based on available evidence | **Not met, and not buildable.** Nothing stores quiz outcomes, external test results, or mistake evidence, and ranking topics against each other is refused by terminology. |
| View recent quiz history and manually entered external test results | **Not met.** FR-009 and FR-010 do not exist; no quiz attempt or external test result is stored. |

**Do not write that FR-011 is complete.** Two of its four criteria are met.

## Consequences

### Positive

- **A learner can see every stage they have recorded in one place**, under the subject it belongs to,
  instead of finding them one at a time down a syllabus of sixty-five topics and subtopics.
- **No endpoint, no column, no table, no migration, and no backend file changes.** Nothing stored is
  reinterpreted and no public contract moves, so this change is reversible by deleting a panel.
- **PRG-001 stays undecided rather than decided by accident**, keeping its shape free for the change
  that can also deliver the priority focus areas its purpose names — exactly as ADR-029 left it.
- **The counting line is enforced by tests rather than by review**, at the place it is hardest to hold:
  the panel tests assert no per-subject count, no percentage, no fraction, no `<progress>`, no
  `<meter>`, and no copy describing the learner.
- **One join, read both ways.** The client-side join ADR-017 introduced now serves two screens, and the
  second one reuses PRG-002 and CUR-003 unchanged rather than asking for a shape of its own.
- **No AI provider is involved and no configuration variable is read.** The same records produce the
  same panel.

### Negative

- **`/progress` now makes eight API calls**, up from six, and it was already the busiest page in the
  product. The two new ones join the existing concurrent batch, so the page waits no additional round
  trip, but the backend serves two more reads per view.
- **CUR-003 is a whole curriculum tree read to supply subject names.** The panel uses the subjects and
  their nesting and discards the descriptions and the relationships. That is the cost of not changing
  PRG-002's contract, and it is paid on a screen that is already dynamic.
- **The panel and the curriculum view now show the same stages**, so a wording change to a stage label
  has two screens to be right on — mitigated by both reading the *same* label table in
  `types/progress.ts` rather than copies.
- **A learner may want the per-subject figure this refuses.** "How much of Operating Systems have I
  recorded?" is a reasonable question, and the answer here is a list. The reasoning is terminology's and
  is quoted above, but the refusal will be felt, exactly as ADR-029 predicted for the counts it refused.
- **A large curriculum would need paging.** PRG-002 is requested at the client's `MAX_PAGE_SIZE` of 100,
  which covers the curated GATE CSE curriculum in one page; a larger one would silently show only the
  first page, and the `pagination` block is what would reveal it. This is ADR-017's existing caveat,
  now applying to a second screen.

### Neutral

- Nothing here totals, counts, ranks, or scores. The panel introduces no figure at all.
- Nothing writes a learning stage, and PRG-004 is untouched. `stage_source` is still written and read
  by nothing that branches on it.
- `material_status`, `material_completed_at`, and `last_studied_at` remain uncreated, and ACT-001 and
  ACT-002 remain uncontracted; each arrives with the code that writes it, per
  [ADR-011](ADR-011-sqlalchemy-persistence-implementation.md).
- The backend is untouched: no route, no use case, no DTO, no domain rule, no model, no migration.
- No learner flow changed. Setup, the curriculum view, the plan screens, the daily and monthly views,
  and the revision screen are all exactly as they were.

## Alternatives considered

### Add a `subject_id` filter, or a subject name, to PRG-002

The catalogue's original intent line named `subject_id` and `learning_stage` filters, and
[ADR-017](ADR-017-topic-progress-api-and-schema.md) left them as "compatible additions… left to the
screen that needs them". A `subject_name` on the record would remove the join entirely.

**Not selected:** neither is needed. A filter narrows a collection this screen wants in full, and a
subject name on a progress record would duplicate curriculum reference data inside a learner-owned
response — the separation ADR-017 made when it refused to add `learning_stage` to CUR-003, in the other
direction. Both are public contract that is breaking to change afterwards, and this screen can be built
without either.

### Implement PRG-001 as a read-only aggregation endpoint

Compose the stages, the subjects, the plan, and the revisions into one response.

**Not selected**, for the reasons ADR-029 gave and which have not changed: every fact is already a field
of an existing response, so it clears none of ADR-023's bar; and its catalogued purpose promises
priority focus areas that nothing can supply, so the shape fixed now is the shape that would have to
break when the evidence arrives.

### Show a count or a proportion per subject

"Operating Systems — 4 of 9 topics recorded", or a small bar beside each subject.

**Not selected**, and this is the alternative the record exists to refuse. It fails all three of
terminology's tests: its subject is the learner rather than a plan; it would read as zero for a learner
who has recorded nothing, which says nothing; and it invites a comparison against the subject below it.
It is also the forbidden "14 of 60 done" almost verbatim. A *plan coverage count* is permitted because a
plan describes itself; a subject is not a plan, and a learner's records are not its coverage.

### Order or group a subject's topics by stage

Strongest first, or a heading per stage inside each subject.

**Not selected:** it ranks the five stages against each other, which nothing in LearnFlow does. ADR-017
recorded that "the five stages are never compared" and that a learner may move to any stage from any
stage, including backwards. An order is the clearest possible statement that one end is better than the
other.

### List every topic, marking the unrecorded ones *Not explored*

A complete picture of the syllabus, with the neutral state shown explicitly.

**Not selected:** it reproduces the curriculum view on a screen whose purpose is to gather, and it turns
a neutral starting state into sixty-odd lines that read as omissions. Terminology draws the distinction
deliberately — a topic with no record and one deliberately set to `not_explored` are different — and
listing them identically would erase it.

### Put the stage control on the panel

The learner is already looking at the stages; letting them change one here saves a navigation.

**Not selected:** `/progress` writes nothing at all, which is ADR-029's decision and ADR-026's before
it. A second place to record a stage is a second place to handle PRG-004's `422` for a grouping topic, a
second optimistic state, and a second thing to change whenever that control changes.

### Leave the stages where they are and close FR-011's criterion differently

Argue that the curriculum view already shows progress by subject and topic.

**Not selected:** it shows one topic's stage beside that topic, which is where a stage is *recorded*, not
where a learner's position is *read*. FR-011 asks for a view of progress by subject and topic, and
ADR-029 already recorded that the criterion was not met by the curriculum view.

## Implementation notes

- **No backend file changes.** PRG-002 and CUR-003 are consumed exactly as catalogued in
  [api/endpoints.md](../api/endpoints.md#progress-and-study-activity-endpoints), which stays
  authoritative for their fields and error codes. No API client function was added: both already existed.
- `frontend/features/progress/subject-stages.ts` holds `selectStagesBySubject` — a plain function over
  plain values, tested without a running server. Its module docstring records that the group lengths it
  uses to decide whether a subject has content never reach the screen.
- `frontend/features/progress/LearningStagesBySubject.tsx` renders the panel with its CSS Module. It
  renders no control. `CurriculumTree.tsx` and `TopicStageControl.tsx` are untouched: extracting a shared
  topic-and-stage component from two screens is a refactor, and this is a feature change — the same call
  ADR-023 through ADR-029 each made.
- `frontend/app/progress/page.tsx` gains the two reads, joined to the existing concurrent batch, and
  passes the curriculum link built from the goal's `learning_program.id`. The route stays
  `force-dynamic` for the reason [folder-structure.md](../development/folder-structure.md#frontendapp)
  records.
- Covered by `frontend/tests/subject-stages.test.ts` — the grouping, the curriculum's order against
  PRG-002's, a subtopic at depth, an unrecognised stage, a subject with nothing recorded, a topic the
  tree no longer holds, and that stage never decides an order — and
  `frontend/tests/LearningStagesBySubject.test.tsx`, which asserts the canonical labels, that **no
  control of any kind is rendered**, that **nothing is counted**, that no copy describes the learner, and
  each of the three states. `frontend/tests/StudyProgressOverview.test.tsx` covers the panel in place,
  including that an unreadable pair leaves the other five panels standing.
- Open and deliberately not settled here: whether the overview should become the home screen; what
  PRG-001 returns if it is ever built; whether material status and study activity join this panel when
  they are stored; and whether marks on superseded plans should be readable anywhere.
- Recorded as DEC-042 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this panel inherits
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the stages this panel gathers, the client-side join it reuses, and why the five are never compared
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](ADR-023-daily-study-view.md) — the bar a new endpoint must clear, which this panel does not clear and does not need to
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](ADR-026-monthly-study-view.md) — the read-only shape this panel follows
- [ADR-029: Show the progress overview as a reading of what is stored, counting nothing of its own](ADR-029-progress-overview.md) — the screen this extends, and the open question it recorded that this answers
- [API conventions](../api/conventions.md) — the envelope and the error codes the two reads answer in
- [API endpoint catalog](../api/endpoints.md) — PRG-002 and CUR-003, neither of which changes, and PRG-001, which stays unimplemented
- [API versioning](../api/versioning.md) — what would make a change to PRG-002 breaking, had a filter been added here
- [Terminology](../domain/terminology.md) — the five stage labels, and the counts a screen may not carry
- [Functional requirements](../requirements/functional.md) — FR-011, two of whose four criteria are now met
- [Coding standards](../development/coding-standards.md) — the rule that ordering is a curriculum rule the frontend renders
- [Repository and folder structure](../development/folder-structure.md) — where the module, the component, and their tests live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 2 item this advances
- [Architecture decision register](../architecture/decisions.md) — DEC-042
