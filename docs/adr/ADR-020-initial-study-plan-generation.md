---
title: "ADR-020: Generate the Initial Study Plan Deterministically as a Roadmap and a Week"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-09
related:
  - ../00-project-context.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-013-examination-schedule-and-study-goal.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-016-learner-onboarding-api-contracts.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-018-weekly-availability-slots.md
  - ADR-019-study-goal-planning-preferences.md
  - ADR-021-plan-item-completion.md
  - ADR-022-plan-adaptation.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../ai/learnflow-agents.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-020: Generate the Initial Study Plan Deterministically as a Roadmap and a Week

## Status

Accepted — 2026-08-07. Proposed 2026-08-06.

Accepted once the decision below was verified rather than merely argued. Both gaps this record
listed under [Implementation notes](#implementation-notes) as unverified are now closed, and one of
them found a defect; see the note immediately below.

This record completes the last of
[FR-002](../requirements/functional.md#fr-002-initial-learner-setup)'s five acceptance criteria: a
learner who starts with no previous progress still receives an initial plan. It is also the first
delivery against [FR-003](../requirements/functional.md#fr-003-study-timeline-and-plan), which
Milestone 3 continues.

## Implementation status — 2026-08-07

*Note added 2026-08-07 on acceptance. The decision above is unchanged; this records the verification
that was outstanding when it was proposed, and the one defect that verification found.*

**Two statements under [Implementation notes](#implementation-notes) are overtaken**, both of which
that section flagged as unverified:

- "The PostgreSQL integration tests have not been run locally … CI is the first run of the SQL and
  the migration." CI has now run them. The first run **failed**: seven integration tests raised
  `ForeignKeyViolation` on `fk_plan_items_study_plan_id_study_plans`, because a plan and its items
  were written in one flush and SQLAlchemy — having no `relationship` between `StudyPlan` and
  `PlanItem` to order them by — inserted the items first. The use case now flushes each plan before
  its items, through a `flush()` primitive on the port and adapter matching
  `CurriculumSeedRepository`. **No migration, and the foreign key is unchanged**: the constraint was
  right and the write ordering was wrong. The run is now green, `207 passed`.
- "This change has not been exercised against the production standalone frontend with a
  contract-shaped stub API." It has since been, as ADR-015 through ADR-019 each were. **Thirty checks
  passed**, and the run found a second defect, since fixed: `PlanWeek` rendered a dated item without
  the `recommendation_reason` the API returns with it, so only the roadmap answered FR-003's fourth
  criterion. Verified: `/plan` renders an existing plan; a no-JavaScript multipart submission created
  one, reaching PLN-001 exactly once with `{"study_goal_id": …}` and no `learner_id`; generating again
  superseded the previous plans while keeping them, and only the new active pair rendered; every
  roadmap and weekly item showed its own reason; no total appeared; and neither the API address nor
  `API_BASE_URL` appeared in the HTML of `/plan`, `/`, `/setup`, or `/curriculum`, nor in any of the
  eleven client scripts they load.

**Nothing in the decision changed.** Both defects were in code this record describes, not in what it
decided: the plan shape, the ordering rules, the supersede lifecycle, the contracts, and the table
shapes are all as accepted. Two test gaps were closed with them — the study-plan fake now mirrors the
foreign key, and the panel suite asserts an item's reason on both panels at once.

## Implementation status — 2026-08-08

*Note added 2026-08-08. The decision above is unchanged; this records that the two columns this record
created without a writer now have one.*

**`plan_items.status` and `plan_items.completed_at` are now written.** PLN-004 moves an item between
`planned` and `completed`, contracted by [ADR-021](ADR-021-plan-item-completion.md). It needed **no
migration**: both columns, the `status` `CHECK`, and
`ix_plan_items_study_plan_id_scheduled_for_status` were created by `20260806_03` exactly as this
record describes, and the endpoint stored what they anticipated without altering anything.

**Three statements above are overtaken**, all in the same direction:

- Under [Decision](#two-tables-with-controlled-values-guarded-by-a-check) — "`plan_items.status` and
  `completed_at` are created although nothing writes anything but `planned`." The argument this record
  made for creating them early — that "adding the column once learners have plans would mean
  backfilling rows whose state nobody recorded" — is what has now paid off, so the sentence is
  overtaken by its own reasoning rather than contradicted.
- The heading [Three endpoints, all catalogued; PLN-004 and PLN-005 stay
  unimplemented](#three-endpoints-all-catalogued-pln-004-and-pln-005-stay-unimplemented), and its
  closing line, "PLN-004 and PLN-005 belong to FR-004 and are not implemented. Nothing here moves a
  plan item's status." Both remain true **of this change**; PLN-004 arrived in a later one. PLN-005 is
  still unimplemented, as are `skipped` and `postponed`.
- Under [Consequences](#negative) — "**A weekly plan goes stale** … nothing re-plans it". Still true.
  A learner can now record that a session happened, but nothing re-plans around what they recorded,
  which is the same FR-004 work arriving later.

**Nothing in the decision changed, and one refusal was inherited.** ADR-021 keeps this record's
supersede lifecycle intact by refusing to move an item on a superseded plan: a plan kept because it
"reads exactly as it was written" cannot also be written into. The plan shape, the ordering rules, the
contracts of PLN-001 to PLN-003, and both table shapes are all as accepted.

## Implementation status — 2026-08-09

*Note added 2026-08-09. The decision above is unchanged; this records that the staleness this record
named as its own worst consequence now has a remedy.*

**A weekly plan can now be rebuilt around what happened to it.** PLN-005 supersedes a goal's active
plans and writes a new pair from the topics that remain, contracted by
[ADR-022](ADR-022-plan-adaptation.md). It reuses this
record's rules exactly — the same ordering, the same session placement, the same horizon and session
length — differing only in which topics go in. It needed **no migration**.

**Three statements above are overtaken:**

- Under [Consequences](#negative) — "**A weekly plan goes stale.** It covers seven days from the day
  it was generated, and nothing re-plans it: a learner who misses a week must generate again, which is
  FR-004's work arriving later." That work has arrived. The plan still goes stale on its own; what has
  changed is that the learner now has something better than regenerating to do about it.
- The [2026-08-08 note](#implementation-status-2026-08-08) above — "PLN-005 is still unimplemented, as
  are `skipped` and `postponed`." PLN-005 is implemented and `postponed` is written. **`skipped`
  remains unwritten.**
- The same note's "**A weekly plan goes stale** … **Still true.** A learner can now record that a
  session happened, but nothing re-plans around what they recorded." Something now does.

**One statement is *not* overtaken**, and is worth naming because a reader may expect it to be: under
[Decision](#generating-again-supersedes-it-never-refuses-and-never-deletes), "**PLN-001 accepts only a
goal identifier**" and generating again re-plans every topic. That is unchanged. Generation still
plans the whole curriculum; only adaptation leaves out what is done, which is why the two are separate
endpoints rather than one with a flag.

**Nothing in the decision changed.** The plan shape, the two pure rules, the supersede lifecycle, the
contracts of PLN-001 to PLN-003, and both table shapes are all as accepted. The domain module gained a
third rule beside the two this record placed there.

## Context

Four of FR-002's criteria have been met since
[ADR-019](ADR-019-study-goal-planning-preferences.md). The fifth was unmet for one reason: nothing
generated a plan. Everything a plan is made of was already stored and read back —
the curriculum and its topic relationships, the goal and its horizon, the weekly availability
[ADR-018](ADR-018-weekly-availability-slots.md) added, the planning preferences ADR-019 added, and
the learning stages [ADR-017](ADR-017-topic-progress-api-and-schema.md) added — and each of those
records noted, as a deliberate neutral consequence, that nothing consumed it yet. This is the change
that consumes them.

Eight questions had to be answered, and the project owner decided each of them.
[ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope, the pagination shape, and
the error catalogue, so none of those was open.

1. **What the first plan covers.** [DEC-021](../architecture/decisions.md) approves roadmap, monthly,
   weekly, and daily plans. FR-002 asks only for "an initial plan"; FR-003 asks for all four, and
   belongs to [Milestone 3](../roadmap/milestones.md#milestone-3-planning-and-revision).
2. **Which tables, and in what shape.** [schema.md](../database/schema.md#study_plans) approves
   `study_plans` and `plan_items` with `text` columns for `plan_type`, `status`, and `action_type` —
   which its own *Conventions* section and [ADR-011](ADR-011-sqlalchemy-persistence-implementation.md)
   both contradict for controlled values.
3. **What order topics go in.** ADR-019 defined `topic_sequencing` as `syllabus_order` or
   `prerequisites_first`, and described the second as following "the `prerequisite` edges in
   `topic_relationships`".
4. **How time is allocated.** A day's `available_minutes` has to become a number of
   `plan_items.estimated_minutes`, and ADR-019 chose `preferred_session_minutes` precisely because
   "a planner slicing a day's `available_minutes` into `plan_items.estimated_minutes` must choose
   between one long block and several short ones".
5. **What an unset input means.** ADR-018 and ADR-019 both established that an unset value is not a
   default. A planner meeting one "chooses its own default visibly" — which is a promise nothing had
   yet had to keep.
6. **What happens on a second generation.** [schema.md](../database/schema.md) says plans "may be
   superseded rather than deleted so the learner's plan history remains explainable", without saying
   what triggers it.
7. **Which endpoints.** PLN-001 to PLN-005 have been catalogued since the documentation foundation.
   PLN-004 and PLN-005 serve [FR-004](../requirements/functional.md#fr-004-plan-adaptation), which is
   not in scope.
8. **Where the rules live.** `backend/app/domain/` is documented in
   [folder-structure.md](../development/folder-structure.md) and has never held a file, because no
   earlier feature had a rule that was not either a repository read or a contract check.

### One finding that shaped three of the answers

**The curated GATE CSE curriculum stores no prerequisite edge at all.**
`backend/scripts/gate_cse_curriculum.json` carries `"topic_relationships": []` beside its 11 subjects
and 60 trackable topics. A learner who chooses *Prerequisites first* — a preference ADR-019 made
settable, and described as computable "today" — therefore receives syllabus order.

That is not a defect in ADR-019: the edges are a curriculum-data question, and `topic_relationships`
exists and is seedable. It does mean the planner must be honest about it, which is why the ordering
rule below reports how many prerequisites it actually applied.

## Decision

### The first plan is a roadmap and a week

One generation writes two plans: a `roadmap` ordering every trackable topic across the goal's
horizon without dating anything, and a `weekly` plan placing the first of those topics onto the next
seven days from the saved availability.

The roadmap answers *in what order*; the week answers *what now*. Together they consume every stored
input — the curriculum and its order, the horizon, the week, the session length, and the recorded
stages — which is what makes this a real answer to FR-002's criterion rather than a formality.

**A full-horizon daily plan was rejected**, under *Alternatives* below: it fixes a six-month schedule
that nothing can yet adapt, where FR-004's re-planning does not exist. **A roadmap alone was
rejected** for the opposite reason: it would consume availability only as an aspiration, and a
learner asking what to do on Monday would get an ordered list of sixty topics.

`monthly` and `daily` plans remain approved and ungenerated. Both are constrained by the `CHECK`
already, so adding one is a use-case change rather than a migration.

### The plan is deterministic, and its rules are the first domain module

The same goal, curriculum, week, preferences, and date produce the same plan every time. No AI
provider is involved, which is what [learnflow-agents.md](../ai/learnflow-agents.md) requires of the
planner: "core scheduling and prioritization are deterministic application rules", usable when Ollama
is unavailable.

The two rules that decide a plan — what order, and which day — are **pure functions in
`backend/app/domain/study_planning.py`**, which is the first file in the domain layer. They take
plain values and return plain values: no clock, no session, no configuration. That is what makes the
plan testable exhaustively rather than merely observable, and it is the layer
[dependency-rules.md](../architecture/dependency-rules.md) reserves for exactly this.

Everything else — reading records, deriving the horizon, writing the sentences, storing the result —
stays in the application use case, which may not be imported by the domain.

### Topic order: syllabus order, or a defined topological order

`syllabus_order`, and an unset preference, walk the stored `position` of subjects and topics, parent
before child. That is the order CUR-003 renders and the frontend is forbidden to re-sort, so the plan
and the curriculum screen cannot disagree.

`prerequisites_first` is a topological order over the `prerequisite` edges, taking the earliest
syllabus position among the topics ready at each step. **The tie-break is the decision**: without it,
many valid topological orders exist and the "same inputs, same plan" property would be false.

Three consequences are made explicit rather than left to be discovered:

- **A `prerequisite` edge is read as "the source topic comes before the target"**, matching how
  `recommended_before` reads. [terminology.md](../domain/terminology.md) names the type without
  fixing its direction, and no edge is stored, so this is the first code to depend on the reading.
  It is recorded as an open item below.
- **`recommended_before` and `related` do not constrain the order.** A recommendation is not a
  constraint, and a plan that treated one as a constraint could not explain the difference.
- **With no edges stored, the plan says so.** The roadmap's reason names syllabus order, and each
  item's reason does too, rather than claiming an order the plan did not follow.

A loop of prerequisites is survived rather than refused: the topics it holds back are appended in
syllabus order and counted, and the plan says how many. A plan that silently omitted a topic would be
worse than one admitting it could not order it.

### Time: one session per topic, and the planner's own default stated as its own

`estimated_minutes` is the learner's `preferred_session_minutes`, or **60 minutes when they have set
none** — chosen by the planner, in code a contributor can read, and named in the plan as the
planner's choice rather than the learner's. Nothing is written to `study_goals`, so the distinction
ADR-019 preserved survives.

Each day of the coming week is filled with whole sessions while it has room for one. **A day with
time left but less than a full session gets a single shorter session only if nothing else was placed
on it** — so a learner with thirty minutes a day still receives a topic, and a longer day does not
end in an offcut too short to study. No topic is split across days, and no topic is scheduled twice.

**A day the learner has not set and a day they deliberately kept free both hold no work.** They are
different statements about the learner, and ADR-018 keeps them distinct in storage; neither is a
statement that they can study, so the planner treats both as no capacity.

**A weekly plan is written when the coming seven days hold room for at least one session, and not
otherwise.** A learner with no saved availability meets that condition, and so does one who saved a
week and kept every day of it free; both get the roadmap alone, together with a sentence naming which
of the two happened and what to do about it — rather than a week the product invented, or an empty
plan that says nothing.

### The horizon is whichever of the two dates falls first

A goal aiming at both a published examination cycle and a target date is planned against the earlier:
the earlier one is the binding constraint, and planning against the later would quietly overrun it.

The examination is read on every generation rather than copied, so a schedule the examining body
corrects reaches the next plan (ADR-013). It is described as a **window opening on a date**, never as
the learner's paper day, and a provisional schedule says so wherever its dates appear.

A goal whose schedule publishes no sitting day and which carries no target date has no horizon. The
roadmap is still generated, with `period_end` null and a sentence saying why — `study_plans` has
nullable period columns for precisely this.

### A recorded learning stage explains an item; it does not rank one

A stage the learner recorded appears in the item's `recommendation_reason` and changes neither the
order nor the time allowed. A stage guides the next action rather than scoring a topic
([FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence)), and no
evidence beyond the learner's own statement is stored to rank anything by — which is the same reason
ADR-019 refused an evidence-ranked topic order.

**Reordering by stage and omitting `strong_understanding` topics were both rejected**, under
*Alternatives* below.

### Every plan and every item carries the reason it exists

`study_plans.generation_reason` and `plan_items.recommendation_reason` are written when the plan is
generated and never rewritten. FR-003's fourth criterion asks the learner to see why an item is
recommended; a plan that could not say where its own dates, order, and lengths came from could not
answer it.

Two consequences are deliberate. A **superseded plan still explains itself in the terms that produced
it**, which is what makes keeping one worthwhile. And the sentences contain the learner-visible stage
**labels** — the one place the backend writes a label rather than passing the stored value on. The
trade is recorded under *Negative*: a plan snapshot is learner-facing prose fixed at a moment, not a
controlled value a client interprets.

### Generating again supersedes; it never refuses and never deletes

The goal's `active` plans become `superseded` and a new pair is written. Nothing is deleted, and the
response names what was set aside.

This is what [schema.md](../database/schema.md#referential-integrity-and-lifecycle-notes) asks of
plans. It also makes generation safe to repeat, which matters more here than the refusal GOAL-001
applies to a second active goal: a learner whose availability changed has no other way to act on it
until FR-004's re-planning exists, and a repeated form submission must not fail.

### Two tables, with controlled values guarded by a `CHECK`

`study_plans` and `plan_items` are created with every column
[schema.md](../database/schema.md#study_plans) documents, and both indexes it lists under *Required
Indexes*. `plan_type`, `status`, and `action_type` are **`varchar(32)` guarded by a `CHECK` rather
than the bare `text` that document's tables describe**.

This is the departure ADR-018 made for `day_of_week` and ADR-019 for `topic_sequencing`, for the same
reason: every other controlled value in this schema is validated text
([ADR-011](ADR-011-sqlalchemy-persistence-implementation.md)), and a controlled value with nothing
but application code between it and the row is one typo from being stored and trusted later.

`plan_items.status` and `completed_at` are created although nothing writes anything but `planned`.
An item without a state is not a plan item, and adding the column once learners have plans would mean
backfilling rows whose state nobody recorded — the argument ADR-017 made for `stage_source`.

### Three endpoints, all catalogued; PLN-004 and PLN-005 stay unimplemented

PLN-001 generates, PLN-002 lists, PLN-003 reads one plan with its items. No endpoint is invented:
all three have been in [endpoints.md](../api/endpoints.md#planning-endpoints) since the documentation
foundation.

**A listed plan carries no items**; `item_count` says how large it is. A page of plans each holding
every item would be an unbounded payload inside a paginated one, which the pagination block cannot
describe.

**PLN-001 accepts only a goal identifier.** Nothing a client sends can change what the plan is built
from, so no caller can plan with a preference the learner never set. An unknown field is a `422`
rather than being ignored.

PLN-004 and PLN-005 belong to FR-004 and are not implemented. Nothing here moves a plan item's
status.

### The write goes through a Next.js server action, and the backend gains no CORS

`/plan` reads through the same server-side API client every view uses, and the generate button posts
to a `"use server"` module. The browser still issues no request to the backend, so
`API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented.

This inherits [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md), ADR-016,
ADR-017, ADR-018, and ADR-019 rather than renegotiating them. A button has no interaction a server
round trip cannot serve, and the form works without JavaScript.

## Consequences

### Positive

- **FR-002 is met in full**, all five criteria. A learner with no recorded progress receives a plan
  built from what they set up. [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries
  the count and stays authoritative for it.
- **Everything learner setup records is now consumed.** Availability, planning preferences, and
  recorded learning stages each stopped being write-only in this change, which discharges the neutral
  consequence ADR-018 and ADR-019 each recorded. ADR-017's neutral consequence is **not** discharged:
  it concerns `stage_source`, which distinguishes a learner-set stage from a derived one, and nothing
  derives a stage or reads that column. The plan reads `learning_stage`.
- **The learner-planning schema area is complete.** `study_plans` and `plan_items` were the last two
  tables it lacked.
- **The domain layer exists**, holding rules that are pure, exhaustively testable, and independent of
  FastAPI, SQLAlchemy, and the clock. A future planner that needs different rules changes functions
  rather than a use case wired to six repositories.
- **The plan is explainable end to end.** Every plan and every item says why, and a superseded plan
  keeps its own wording.
- No new error code was needed: `validation_error`, `not_found`, and `conflict` all existed. The
  three endpoints are new contracts, but each was already catalogued.
- The migration creates two empty tables and alters nothing, so no learner data is reinterpreted.

### Negative

- **Three more endpoints are public contract.** Changing a field or a status code on any of them is
  breaking under [versioning](../api/versioning.md#breaking-changes).
- **A weekly plan goes stale.** It covers seven days from the day it was generated, and nothing
  re-plans it: a learner who misses a week must generate again, which is FR-004's work arriving
  later. The screen says what rebuilding does; nothing does it automatically.
- **`prerequisites_first` currently changes nothing**, because the curated curriculum stores no
  prerequisite edge. The plan says so rather than implying otherwise, but a learner who chose that
  order is receiving syllabus order until the curriculum gains edges.
- **The direction of a `prerequisite` edge is now fixed by code** rather than by an approved
  document. No stored edge depends on it today; the first seeded edge will.
- **A stage label is written into stored prose.** Rewording a label in
  [terminology.md](../domain/terminology.md) leaves older plans carrying the older wording. That is
  arguably correct for a historical snapshot, and it is the first time the backend has written a
  label at all.
- **Generation reads six repositories in one request.** For the curated curriculum — 11 subjects,
  65 topics, at most 65 progress records, at most 7 slots — this is a handful of small queries, but
  it is the widest read in the application.
- **A plan can be generated that the learner's week cannot deliver**, and nothing says so beyond the
  roadmap running to the horizon while the week reaches only a few topics. FR-004's "highlights
  meaningful trade-offs when time is insufficient" is not met by this change.
- Two plans per generation means a goal replanned weekly accumulates rows. Nothing prunes them;
  superseding rather than deleting is the deliberate cause.

### Neutral

- Nothing here totals a week, ranks a topic, or scores a preference. The plan performs the arithmetic
  ADR-018 said belonged to a planner, and no more of it than placing work on days requires.
- `monthly` and `daily` plans are constrained and ungenerated, as `practice`, `revise`, and
  `review_mistakes` items are. Each arrives with the code that writes it.
- No command-line tool generates a plan. `scripts.set_study_goal` is untouched.
- The seven days are still never compared or weighted, and a learner may give any day any amount of
  time.

## Alternatives considered

### A single dated roadmap covering the whole horizon

One plan, every trackable topic placed on a date between today and the examination window. Fewer
moving parts than two plans, and it would answer "will I finish in time?" outright, since the topics
that did not fit would be visible.

**Not selected:** it fixes a six-month schedule that nothing can adapt. FR-004's re-planning does not
exist, so the first missed day would make every subsequent date wrong, and a learner would be reading
a plan that quietly stopped being true. It also pre-empts more of FR-003's design than FR-002's
criterion requires. Reconsidering it once adaptation exists is a use-case change, not a migration.

### A roadmap alone, with no dated work

The smallest possible answer to "receive an initial plan", and honest when no availability is saved.

**Not selected:** it consumes availability only as an aspiration and gives a learner no answer to
"what do I do today" — sixty ordered topics is a syllabus, not a plan. It would also leave
`available_minutes` unread for a second milestone running.

### All four plan types at once

Roadmap, monthly, weekly, and daily, which is FR-003's first acceptance criterion outright.

**Not selected:** several times the size, and it settles what a monthly and a daily plan *are* before
anything has been learned from a roadmap and a week in use. Milestone 3 is where that belongs.

### `text` columns with no `CHECK`, as `schema.md` writes them

The literal reading of the approved tables.

**Not selected:** for the reason ADR-018 gave for `day_of_week` and ADR-019 for `topic_sequencing`.
A controlled value guarded only by application code is stored and trusted the first time a caller
gets it wrong, and this schema's every other controlled value is validated text. Following the tables
verbatim would contradict the *Conventions* section of the same document.

### Reordering the plan by recorded learning stage

Move `strong_understanding` topics to the end, or set an item's action from the stage — `practice`
for practice-ready, `study` otherwise.

**Not selected:** it makes a stage into a ranking, which
[FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence) and
[terminology.md](../domain/terminology.md) both refuse — "a learning stage should lead to a
supportive next action, not a negative label or irreversible judgement". A `practice` item would also
promise practice the product cannot yet provide: checkpoint quizzes are Milestone 5. The stage is
reported in the reason instead, which informs the learner without the product forming an opinion.

### Omitting topics the learner marked `strong_understanding`

A shorter plan, skipping what the learner says they know.

**Not selected:** nothing schedules those topics for revision yet — `revision_records` arrives with
Milestone 3 — so omitting them would drop a topic out of the learner's plan entirely on the strength
of one self-assessment, which is exactly the "permanent mastery from one signal" FR-005 forbids.

### Refusing a second generation unless the request says `replace: true`

Mirrors GOAL-001's refusal to overwrite an active goal, so a repeated form submission cannot discard
a plan the learner was working from.

**Not selected:** a plan is not a goal. The goal is what a plan is built *from* and is expensive to
re-enter; a plan is derived, is superseded rather than destroyed, and is the only way a learner can
act on a changed week until FR-004 exists. An extra flag and an extra round trip would guard against
a loss that superseding already prevents.

### A `Clock` read directly rather than through a port

`datetime.now(UTC)` inside the use case, with no port and no adapter.

**Not selected:** every date in a plan derives from "today", so a test that cannot choose today can
only assert that the code agrees with itself. The port is four lines and makes the whole of the
dating behaviour — the week's seven days, the days remaining, the learner's own timezone at a
boundary — assertable.

### Planning rules in the application layer rather than in `domain/`

Keep `backend/app/domain/` empty and put the ordering and packing functions beside the use case.

**Not selected:** these are the rules a learner would recognise as the plan, they depend on nothing
outside themselves, and `folder-structure.md` reserves exactly that layer for "domain invariants and
calculations". Creating the folder when its first file needs it is that document's own rule.

## Implementation notes

- Endpoint fields and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#planning-endpoints), which stays authoritative. No new error
  code was needed.
- Migration `20260806_03_create_study_plan_tables` creates two tables and alters nothing. Its
  downgrade drops both, items first, and names no constraint — dropping a table takes its checks with
  it, which also keeps the downgrade clear of the `ck` naming convention that bit revision
  `20260806_02`. [migrations.md](../database/migrations.md#commands) records that trap.
- `PLAN_TYPES`, `PLAN_STATUSES`, `PLAN_ITEM_ACTIONS`, `PLAN_ITEM_STATUSES`, and
  `DEFAULT_SESSION_MINUTES` live in `application/dto/study_plan.py` and are mirrored by the model's
  `CHECK`s, the way `WEEKDAYS` and `TOPIC_SEQUENCING_CHOICES` are.
- `ManageStudyPlans` serves all three endpoints, so the rule deciding whether a goal or a plan belongs
  to the effective learner stays in one place. Its provider in `composition/providers.py` owns the
  transaction, so a generation that supersedes an old plan and writes a new one cannot half-succeed.
- `TopicProgressRepository` gained `list_recorded_stages`, unpaged: the planner explains every item of
  a whole plan, so a window over the records would leave some items unable to mention a stage the
  learner did record.
- The frontend is `app/plan/page.tsx` with `features/planner/` — `StudyRoadmap.tsx`, `PlanWeek.tsx`,
  `GeneratePlanForm.tsx`, presentation in `plan.ts`, and the form state in `submission.ts` because a
  `"use server"` module may export only async functions, which
  `frontend/tests/server-actions.test.ts` enforces.
- **The PostgreSQL integration tests have not been run locally.** They are written —
  `tests/integration/test_study_plan_migration.py` and `test_study_plan_api.py` — and CI runs them;
  they skip on a workstation with no `TEST_DATABASE_URL`. The unit and API suites, which do run,
  cover the rules and the contract but not the SQL.
- **This change has not been exercised against the production standalone frontend with a stub API**,
  as ADR-015 through ADR-019 each were. The frontend lint, type, unit, and production-build checks all
  pass, and `/plan` builds as a dynamic route; what has not been demonstrated is a no-JavaScript
  submission, the rendered plan, and the absence of any API address in the served HTML.
- **`study_plans.period_start`/`period_end` keep the names this schema documented before the
  dated-span naming rule existed**, although the columns themselves are created by this change.
  [terminology.md](../domain/terminology.md) grandfathers those two names explicitly, so following the
  rule would have meant contradicting it; renaming them is a wording decision the project owner has
  already taken, and reopening it from an implementation seat is what this repository forbids. Noted
  because a reader meeting a newly created `period_start` beside the `starts_on` rule is owed the
  reason.
- Open and deliberately not settled here: the direction of a `prerequisite` edge, which no stored data
  yet depends on; whether the curated curriculum should gain prerequisite edges at all; what a monthly
  and a daily plan contain; how a plan should report that a week cannot deliver its horizon; and
  whether superseded plans are ever pruned.
- Recorded as DEC-032 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the ordering rule this record follows, and the validated-text rule it applies again
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — the horizon this plan is built against
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope these contracts answer in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology the plan screen inherits
- [ADR-016: Fix the learner setup API contracts](ADR-016-learner-onboarding-api-contracts.md) — the goal contract a plan is generated from
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the stages a plan item's reason reports, and the refusal to rank them
- [ADR-018: Store weekly availability as named days replaced a week at a time](ADR-018-weekly-availability-slots.md) — the week this plan places work into, and the totalling it deferred to here
- [ADR-019: Store planning preferences as typed columns replaced as a group](ADR-019-study-goal-planning-preferences.md) — the session length and topic order this plan consumes
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the contracts this record decides
- [API versioning](../api/versioning.md) — what makes a change to them breaking
- [Database schema](../database/schema.md) — the approved tables, and the column types this record changes
- [Database migrations](../database/migrations.md) — the migration this record introduces
- [Domain model](../domain/domain-model.md) — the study plan and plan item concepts
- [Domain entities](../domain/entities.md) — the entities this record persists
- [Terminology](../domain/terminology.md) — *study plan*, *plan item*, and the stage labels a reason carries
- [Functional requirements](../requirements/functional.md) — FR-002's last criterion, and FR-003
- [LearnFlow product agents](../ai/learnflow-agents.md) — the planner service's inputs, outputs, and deterministic rule
- [Repository and folder structure](../development/folder-structure.md) — where the domain module and the planner feature live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 2 criterion this completes and the Milestone 3 work it starts
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](ADR-021-plan-item-completion.md) — the first code to write the `status` and `completed_at` columns this record created
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — the re-planning that answers the stale-week consequence above, reusing these rules
- [Architecture decision register](../architecture/decisions.md) — DEC-032
