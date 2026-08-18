---
title: "ADR-036: Show a Topic's Material Beside the Plan Items That Name It, Read-Only"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-19
related:
  - ../00-project-context.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-021-plan-item-completion.md
  - ADR-023-daily-study-view.md
  - ADR-026-monthly-study-view.md
  - ADR-028-revision-workflow.md
  - ADR-029-progress-overview.md
  - ADR-031-priority-focus-panel.md
  - ADR-032-learning-resource-catalogue.md
  - ADR-034-checkpoint-practice-history.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-036: Show a Topic's Material Beside the Plan Items That Name It, Read-Only

## Status

Accepted — 2026-08-19. Proposed 2026-08-19.

It **amends [ADR-032](ADR-032-learning-resource-catalogue.md) on one point of substance** and
overturns none of its reasoning. ADR-032 is **accepted**, and everything else in it stands: a
resource is still metadata rather than the material, nothing is uploaded, nothing curated ships,
nothing is deleted, and **nothing is recommended, ranked, or counted**.

The amended point is its sentence *"The plan screens are untouched. `/plan`, `/plan/today`, and
`/plan/month` render exactly as they did."* Two of those three now show a topic's material,
read-only. **`/plan/month` is deliberately left as it was**; see
[Why the month is left alone](#why-the-month-is-left-alone).

**Four further sentences in ADR-032 count or list the surfaces, and now read short rather than
wrong.** They are named here so a reader of either record can reconcile them, and none of them is a
separate decision:

- *"**Met in full**, by RES-002's `topic_id` filter and by the three screens that show a topic's
  material"* — there are now four.
- *"archived material stays in the catalogue screen while dropping out of the curriculum and revision
  screens"* — it drops out of all four.
- Its *Where material appears, and where it can be changed* list of three surfaces — `/plan` and
  `/plan/today` join it, on the same read-only terms.
- *"The curriculum and revision screens read the whole catalogue once and join it by topic in the
  client"* — the two plan screens do the same, with the same helper.

Its **FR-007 verdict is unchanged** by all four: the fourth criterion was already met in full, and
this adds surfaces rather than capability.

It adds **no endpoint, no changed response shape, no column, no table, no migration, and no backend
file changes at all**. It reads RES-002 exactly as the curriculum view and `/revisions` already read
it, through the same client and the same client-side join.

## Context

[ADR-032](ADR-032-learning-resource-catalogue.md) gave a learner somewhere to record where their own
study material is and which topics it covers, and put that material on three screens: the catalogue
at `/resources`, where it is written; the curriculum view; and `/revisions`. The plan screens were
excluded in one sentence, without argument, because that change was about the catalogue rather than
about the plan.

What that leaves is a gap between two screens a learner uses in sequence. **The plan is where a
learner decides what to study; the catalogue is where their material is.** A learner reading
*Study — CPU scheduling — 60 minutes* on `/plan/today` has to leave the screen, open `/resources`,
and find the topic there before they can start — even though they have already told LearnFlow which
material covers that topic.

FR-007's fourth acceptance criterion — *"The learner can find resources associated with a topic"* —
is already met, and this does not change that count. What it changes is **where** a topic is met. A
plan item names a topic; so does a review, and ADR-032 already answered the question there.

**This is not the practice half of [FR-006](../requirements/functional.md#fr-006-revision-guidance).**
That half is about a *revision recommendation* carrying practice suggestions, it lives on
`/revisions`, and it still waits on FR-009. Nothing here suggests anything.

## Decision

### Material appears beside a plan item, read-only

`/plan` and `/plan/today` each render, beneath a plan item's reason and above its status control,
the material the learner linked to the topic that item names.

Four sections carry it, rendered by three components: *Your week* and *Your roadmap* on `/plan`, and
the daily study view's two — today's work, and work whose day has passed, which share one item line.
**The same list component renders it in every one of them**, and it is the component ADR-032 already
wrote for the curriculum view and `/revisions`. An item reads
the same wherever a learner meets it, which is the rule [ADR-023](ADR-023-daily-study-view.md) set
when the daily view repeated the week's fields deliberately.

**Both panels of `/plan`, not just the week.** Both already carry the PLN-004 status control, for the
reason [ADR-021](ADR-021-plan-item-completion.md) gave — a plan item is a plan item, and a learner
working ahead of their week should not have to wait for it to reach one. Material follows the same
argument. A topic on both panels shows the same material twice because it is **one topic read
twice**, not because anything is emphasised.

### Nothing is recommended, ranked, or counted

This is ADR-032's rule, restated because a plan is where breaking it would be most tempting.

**A topic's material is what the learner linked to it**, in the order RES-002 returned. LearnFlow
suggests none of its own, promotes none above another, and puts **nothing at all** beside a topic
with nothing linked — not a placeholder, not a prompt to add some, and not an invented suggestion. It
holds no material and has assessed none.

**Nothing is counted.** No figure appears beside an item, a day, a subject, or a plan: no *3
resources*, no *2 of 5 topics have material*, no coverage percentage, and no progress bar. A count of
a learner's material measures the learner, which
[terminology](../domain/terminology.md#plan-coverage-counts-are-not-learner-scores) forbids — and a
plan panel is the one place a *plan coverage count* is permitted, which makes the distinction worth
stating rather than assuming.

**Material neither reorders a plan nor explains one.** An item's position is `priority`, an order the
backend decided; its `recommendation_reason` is the sentence written when the plan was generated and
never rewritten. Neither moves because a learner has or has not catalogued something, and nothing
about material enters either. **A topic with material is not preferred over a topic without.**

### The plan screens stay the plan screens; writing stays on the catalogue

**No control is added.** No `<form>`, no `<button>`, no `<input>`, no `<select>` — registering
material, correcting it, and putting it aside all stay on `/resources`, which both screens now name
in their navigation. That is the shape [ADR-026](ADR-026-monthly-study-view.md) fixed for the monthly
view, [ADR-029](ADR-029-progress-overview.md) for the progress overview, and ADR-032 itself for the
curriculum view and `/revisions`: **a screen that reports states where its action lives rather than
growing a second control for it.**

The plan screens keep the one write path they already had — the PLN-004 status control — and gain no
second. A resource control beside every item would put the catalogue on a screen whose job is the
plan, and would invite registering the same book once per plan item.

**Material put aside stays out**, exactly as it does on the curriculum view and `/revisions`. The
existing `resourcesByTopicId` drops archived material, and nothing here re-decides that: a learner
who put something aside has said they are not using it, and a plan that showed it anyway would make
putting it aside meaningless. It stays in the catalogue, where it can be brought back.

### Why the month is left alone

`/plan/month` renders as it did.

It is the screen [ADR-026](ADR-026-monthly-study-view.md) built to make **no claim beyond where the
month sits in the plan**, and most of a month is openly undated there. Its value is the shape of the
month; a list of material under every dated item and every undated roadmap topic would bury that
shape under the catalogue.

It is also not where a learner decides what to study **now**. `/plan/today` is, and `/plan` is where
they look a week ahead. The month is a bearing, and a bearing does not need the books.

This is a deliberate stopping point rather than an oversight, and it is recorded here so that
extending it later is a decision someone makes rather than a gap someone fills.

**`/progress` is left alone for a related reason.** It shows today's work and what the learner has
marked, so it renders plan items too — but it is a *reading of readings*, gathering eight contracts
into one screen, and [ADR-029](ADR-029-progress-overview.md) built it to say where things stand
rather than to be worked from. Each of its panels names where its action lives and links to it, and
the panel showing today's work links to `/plan/today`, which now carries the material. Adding a ninth
read there would lengthen the screen ADR-029 kept deliberately short.

### An unreadable catalogue costs the material, not the plan

If RES-002 fails, each screen renders the plan without material and claims nothing about it. That is
the call the curriculum view makes about the same read, and the one `/revisions` makes: **the plan is
what the learner came for**, and losing their material should not lose them their week.

The read runs **alongside** the plan reads rather than after them, because the material a learner
catalogued does not depend on which plans they have. On `/plan` it joins the two PLN-003 reads and
PLN-006 in one `Promise.all`; on `/plan/today` it joins LRN-001 and GOAL-002. Each screen costs **one
additional round trip** and no additional wait.

**The whole catalogue is read once and joined by topic in the client**, rather than asking RES-002
per topic. A roadmap over the curated GATE CSE curriculum holds 65 items, and one request each would
be 65 requests for one screen. That is the join ADR-032 chose for the curriculum view, and the reason
RES-002 returns each resource with its topics.

### Nothing else moves

No learning stage, plan, plan item, revision, quiz, or attempt is written, or read differently.
`/resources`, `/curriculum`, `/revisions`, `/progress`, `/practice`, and `/plan/month` render exactly
as they did. No AI provider is involved, no vector index is touched, no configuration variable is
read, and no request reaches the browser: the screens call the API from the Next.js server, as every
screen has since [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md).

Every part of this works with **JavaScript disabled**, because it renders nothing interactive at all.

## Consequences

### Positive

- **A learner's material is where they decide what to study.** The two screens they act on daily
  answer *what shall I study* and *with what* together, without leaving either.
- **No contract changed, and no backend file changed.** RES-002 is read as catalogued, through the
  client three screens already use; the join is the one ADR-032 already wrote.
- **No new component, and no fourth rendering of the same list.** `TopicResources` and
  `resourcesByTopicId` are now called from five components across four screens, so the rules about
  ordering, archiving, and recommending nothing are enforced in one place rather than restated in
  each.
- **The read-only shape holds.** A fourth and fifth screen report a topic's material and name where
  it is written, so `/resources` is still the only place a resource is created, corrected, or put
  aside.
- **A failure is contained.** An unreadable catalogue costs the reader the material alone, on both
  screens.

### Negative

- **`/plan` grows.** The roadmap lists every trackable topic — 65 in the curated curriculum — and a
  learner who has catalogued material broadly will find the page longer. It grows only where material
  exists, because a topic with none renders nothing, but it does grow.
- **The same material appears twice on `/plan`** when a topic sits on both the week and the roadmap,
  which reads as repetition to anyone who does not know the two panels hold different records.
- **Two more screens must keep their empty and error states in step with RES-002.** Four screens now
  depend on that contract, so a breaking change there costs four rather than two.
- **One more round trip per screen.** Small and parallel, but real, and a learner with no catalogued
  material still pays for it.
- **`/plan/month` is now the one plan screen without material**, which is a deliberate inconsistency
  and has to be read as one.

### Neutral

- Nothing here totals, counts, ranks, scores, or recommends. No figure appears beside an item, a day,
  a subject, or a plan.
- No new route, no new feature folder, no new dependency, and no new configuration variable.
- `storage_key`, `metadata`, `resource_ingestions`, the three unwritten link roles, `image`,
  `attachment`, and the three ingestion statuses all stay absent or unwritten, exactly as ADR-032
  left them.
- FR-007's four criteria are **unchanged**: the fourth was already met, and this adds surfaces rather
  than capability. **FR-007 is still not met in full**, on the local-path half of its first criterion.
- **FR-006 is still not met in full**: its practice half waits on FR-009, and nothing here touches it.
- PRG-001 still waits on quiz, external-test, and mistake evidence.

## Alternatives considered

### Leave the plan screens alone, as ADR-032 had them

Send the learner to `/resources` or the curriculum view when they want their material.

**Not selected:** it is the status quo whose cost this record exists to weigh. The learner has
already told LearnFlow which material covers a topic; making them re-find it on another screen, at
the moment they sit down to work, wastes the link they took the trouble to make. The catalogue is
organised by *resource* rather than by *what am I doing today*, so finding the topic in it is a
second search.

### Show material only on `/plan/today`

The daily view is where a learner acts, so put it there and nowhere else.

**Not selected:** the same plan item appears on `/plan`, where a learner looks ahead and prepares. An
item that renders differently on two screens is the inconsistency ADR-023 avoided when the daily view
repeated the week's fields deliberately, and a learner gathering their books for the week would be
the one person the change failed.

### Show material on the week but not the roadmap

Keep `/plan` short by leaving the 65-item roadmap as a pure ordering list.

**Not selected:** both panels already carry the status control on ADR-021's argument that a plan item
is a plan item, and splitting the two panels' contents needs a reason that argument does not supply.
Page length is a real cost, and it is recorded under *Negative* rather than paid for with an
inconsistency.

### Put the material behind a `<details>` disclosure on the plan screens

Collapse each item's material so a long roadmap stays scannable, as
[ADR-034](ADR-034-checkpoint-practice-history.md) collapsed a past attempt's questions.

**Not selected** *for this change*: it would be a second way of rendering a list that reads the same
on four screens, and what it hides is two or three lines rather than a whole quiz. ADR-034
collapsed a list that is long *by construction* — every question of every attempt — where a topic's
material is usually a handful of entries. If page length proves to be the problem the *Negative*
section anticipates, a disclosure is the change to make, and making it then is a presentation
decision rather than a migration.

### Add a resource control beside a plan item

Let a learner register material for a topic from the screen where they notice it is missing.

**Not selected:** it is the argument ADR-032 rejected for the curriculum view, and it is stronger
here. The plan screens already carry a write path — the status control — and a second would make a
screen about *what happened to planned work* into a screen about the learner's belongings. One piece
of material commonly covers several topics, and a control anchored to one plan item invites
registering the same book once per item.

### Show material on `/plan/month` as well

Complete the set, so all three plan screens read alike.

**Not selected:** see [Why the month is left alone](#why-the-month-is-left-alone). The month's value
is its shape, and material under every dated item and undated roadmap topic would bury it.

### Suggest material for a topic that has none

Offer something — a prompt to add material, or a link to what covers a neighbouring topic.

**Not selected:** LearnFlow holds no material and has assessed none, so it recommends none — ADR-032's
rule, and the refusal [ADR-031](ADR-031-priority-focus-panel.md) most recently made. A prompt beside
every empty topic would also read as a reproach on a screen whose whole vocabulary avoids one.

## Implementation notes

- Frontend only. `frontend/app/plan/page.tsx` and `frontend/app/plan/today/page.tsx` read RES-002
  through `listResources` and join it with the existing `resourcesByTopicId`;
  `frontend/features/planner/PlanWeek.tsx`, `StudyRoadmap.tsx`, and `DailyStudyView.tsx` each take an
  optional `resources` index and render `features/resources/TopicResources.tsx`.
- The index is passed as a `Map` keyed by topic identifier, which is what `resourcesByTopicId`
  already returns and what the curriculum view and `/revisions` already pass. `null` means *could not
  be read* and an empty `Map` means *nothing linked*; the two render identically and mean different
  things.
- `catalogued()` is the same guarded read `/revisions` and the curriculum view declare, repeated per
  route rather than extracted: it is four lines, and each route decides for itself what a failure
  there costs its reader.
- Both routes are already `force-dynamic`, so no cache entry has to be revalidated when material
  changes. `features/resources/actions.ts` still revalidates `/resources` alone, for that reason.
- Covered by frontend component tests on all three components: that material is listed for a plan item's
  topic, that a topic with nothing linked renders nothing, that an unreadable catalogue still renders
  the plan, that material put aside is left out, that no material control is added, and that nothing
  is counted. There is deliberately **no backend test change**, because no backend file changed.
- Verified in a production standalone run with **JavaScript disabled**, the check every frontend
  decision in this repository carries.
- Recorded as DEC-048 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology these screens inherit unchanged
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the plan whose order and reasons material does not touch
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](ADR-021-plan-item-completion.md) — the a-plan-item-is-a-plan-item argument this applies to both panels
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](ADR-023-daily-study-view.md) — the rule that an item reads the same wherever a learner meets it
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](ADR-026-monthly-study-view.md) — the read-only screen shape, and the screen deliberately left alone
- [ADR-028: Schedule revisions from finished work, on the learner's ask](ADR-028-revision-workflow.md) — the revision screen this follows, and the practice half still deferred
- [ADR-029: Show the progress overview as a reading of what is stored, counting nothing of its own](ADR-029-progress-overview.md) — the naming-where-the-action-lives pattern these screens reuse
- [ADR-031: Draw priority focus from facts backend rules already decided, ranking nothing](ADR-031-priority-focus-panel.md) — the refusal to rank, applied here to material
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](ADR-032-learning-resource-catalogue.md) — the record this amends on one point, and every other rule of which still stands
- [ADR-034: Show the checkpoint-practice history as a paged reading of stored attempts, counting nothing](ADR-034-checkpoint-practice-history.md) — the disclosure pattern considered and not taken here
- [API conventions](../api/conventions.md) — the envelope RES-002 answers in
- [API endpoint catalog](../api/endpoints.md) — RES-002, read exactly as catalogued
- [Terminology](../domain/terminology.md) — *learning resource*, *learning-resource catalogue*, and the counts a screen may not carry
- [Functional requirements](../requirements/functional.md) — FR-007's fourth criterion, already met, and the FR-006 half still open
- [Coding standards](../development/coding-standards.md) — the UI responsibility rule that keeps recommendation out of the frontend
- [Repository and folder structure](../development/folder-structure.md) — the planner components this changes
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 4 item this sits inside
- [Architecture decision register](../architecture/decisions.md) — DEC-048
