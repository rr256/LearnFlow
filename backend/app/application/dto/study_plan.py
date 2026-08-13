"""Input and output structures for a learner's study plans.

These carry what PLN-001, PLN-002, and PLN-003 generate and read, what PLN-004
moves, and what PLN-005 adapts. They are framework-independent by design, as the other DTOs in
this package are: the API schemas that serialise them are a separate
representation, so a change to the HTTP contract does not reach back into the use
case.

A plan is learner-owned and belongs to one study goal, so every structure here
carries both identifiers. Nothing inbound carries a `learner_id`: the effective
learner is resolved server-side (docs/api/conventions.md).

The controlled values below mirror the `CHECK` constraints on `study_plans` and
`plan_items`, the way `LEARNING_STAGES`, `WEEKDAYS`, and
`TOPIC_SEQUENCING_CHOICES` mirror theirs. A value the application forgot to check
is refused by the database rather than stored and trusted later.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

PLAN_TYPES: tuple[str, ...] = ("roadmap", "monthly", "weekly", "daily")
"""The plan types `study_plans.plan_type` accepts.

All four are approved (DEC-021). Two are generated today — see `ROADMAP` and
`WEEKLY` below — and `monthly` and `daily` arrive with the plan views Milestone 3
adds. The constraint carries all four so adding one is a use-case change rather
than a migration.
"""

PLAN_STATUSES: tuple[str, ...] = ("draft", "active", "superseded", "archived")
"""The statuses `study_plans.status` accepts.

Generation writes `active` and moves what it replaces to `superseded`. `draft`
and `archived` are approved and unused: nothing proposes a plan before adopting
it, and nothing files one away by hand.
"""

PLAN_ITEM_ACTIONS: tuple[str, ...] = ("study", "practice", "revise", "review_mistakes")
"""The actions `plan_items.action_type` accepts.

Every item generated today is `study`. The other three name work the product does
not yet model — practice needs checkpoint quizzes, revision needs revision
records, and mistake review needs mistake evidence — so nothing writes them, and
the constraint holds them ready.
"""

PLAN_ITEM_STATUSES: tuple[str, ...] = ("planned", "completed", "skipped", "postponed")
"""The statuses `plan_items.status` accepts.

Every item is written `planned`. **PLN-004 moves one to `completed`, `skipped`,
or `postponed`, and back again**: all four are things the learner says about
their own work, and each is reversible while the plan is active. **PLN-005 also
writes `postponed`**, on the plan it supersedes, for items whose day passed with
the work unsettled — so that status has two writers saying the same thing about
a line, one because the learner asked and one because a day went by. The
constraint has carried all four since `20260806_03`, so each arrived as a
use-case change rather than a migration.
"""

PLAN_ITEM_STATUS_CHANGES: tuple[str, ...] = PLAN_ITEM_STATUSES
"""The statuses PLN-004 accepts as a target.

**Now the whole of `PLAN_ITEM_STATUSES`, where it was a strict subset.** The two
names are kept apart because they still answer different questions — what a
learner may *ask for*, and what the column may *hold* — and the `CHECK` mirrors
only the second. That they currently coincide is a fact about the product having
run out of statuses only adaptation writes, not a reason to collapse them: a
fifth value added to the column would arrive unwritable until somebody decided
it should be askable.

A learner may move an item to any of these from any of them, including
backwards, which is the position ADR-017 takes on a learning stage and ADR-021
took on completion: nothing in LearnFlow treats a statement about work as a
verdict, and a control a mis-tap makes permanent would be one.
"""

ROADMAP = "roadmap"
WEEKLY = "weekly"
ACTIVE = "active"
SUPERSEDED = "superseded"
PLANNED = "planned"
COMPLETED = "completed"
SKIPPED = "skipped"
POSTPONED = "postponed"
STUDY = "study"

SETTLED_STATUSES: frozenset[str] = frozenset({COMPLETED, SKIPPED, POSTPONED})
"""The statuses in which nothing should carry an item forward on its own.

Either the work happened, or the learner decided it would not, or they decided
it would not happen *yet*. Adaptation reads this to decide what is *not* overdue:
an item in one of these must not be re-marked `postponed`, because that would
overwrite a statement with an inference about a day that passed.

`postponed` is here for both of the reasons the other two are, and for one of its
own. A learner who postponed an item has said what should become of it, so it is
settled in exactly the sense this set means. An item adaptation itself postponed
sits on a superseded plan, which adaptation never reads again — so including the
status costs nothing there and prevents a learner's own postponement being
rewritten as though a date had decided it.

`planned` is the only status not here: it is the one about which nothing has been
said.
"""

DEFAULT_SESSION_MINUTES = 60
"""The session length the planner uses when the learner has set none.

**Not a stored default.** `study_goals.preferred_session_minutes` stays NULL
until a learner sets it, so a preference nobody chose never reads as one somebody
did (ADR-019). This is the planner choosing for itself, in code a contributor can
read, and it says so in the plan it writes.
"""

PLAN_WEEK_DAYS = 7
"""How many days the first weekly plan covers, counting the day it is generated.

A week rather than a fortnight because the learner's availability is recorded a
week at a time, so seven days is the longest span the stored input describes
without repeating itself.
"""

FEASIBILITY_VERDICTS: tuple[str, ...] = ("sufficient", "insufficient", "unknown")
"""What PLN-006 can conclude about a saved week reaching a goal's horizon.

Not a stored value: no column holds these, and nothing is written when one is
computed. They are named here beside the stored vocabularies because they are a
controlled set the API contract commits to, and a client switching on them is
entitled to the same guarantee.

`unknown` is a first-class answer rather than a failure. A goal with no horizon
and a learner who has saved no availability are both questions the product cannot
answer honestly, and inventing a verdict for either would be worse than saying so.
"""

SUFFICIENT = "sufficient"
INSUFFICIENT = "insufficient"
UNKNOWN = "unknown"

NO_HORIZON = "no_horizon"
NO_AVAILABILITY_SAVED = "no_availability_saved"

UNKNOWN_REASONS: tuple[str, ...] = (NO_HORIZON, NO_AVAILABILITY_SAVED)
"""Why a feasibility question could not be answered, when it could not.

Two different gaps, kept apart because they ask the learner for different things:
a goal aiming at nothing needs a date, and a goal with no saved week needs a week.
Collapsing them into one `unknown` would leave the screen guessing which to say.

A week the learner saved and deliberately kept free is **not** here. That is an
answer -- zero minutes -- and reporting it as unknown would erase the distinction
[ADR-018](../../../docs/adr/ADR-018-weekly-availability-slots.md) exists to keep.
"""


@dataclass(frozen=True, slots=True)
class PlanItemTopic:
    """The topic a plan item recommends work on, named well enough to display.

    Embedded rather than left as a bare identifier, for the reason a goal embeds
    its program: a client showing a plan would otherwise need the whole curriculum
    tree to put a name against every line.
    """

    id: uuid.UUID
    code: str | None
    name: str
    subject_id: uuid.UUID
    subject_name: str


@dataclass(frozen=True, slots=True)
class PlanItemDetail:
    """One recommended action within a plan.

    `scheduled_for` is null on a roadmap item: a roadmap says what order to work
    in, not which day to do it on. A weekly item always carries a date.

    `recommendation_reason` is the sentence FR-003 asks for — why this item, here.
    It is written when the plan is generated and never rewritten, so a superseded
    plan still explains itself in the terms that produced it.

    `status` and `completed_at` are the one part of an item a learner moves, and
    they travel together: an item is `completed` at an instant or it is not
    completed at all, so a `skipped`, `postponed`, or `planned` item never
    carries one. Completing an item says its planned work happened, skipping it
    says the learner decided it would not, and postponing it says they decided it
    would not happen yet; none of the three says anything about how well they
    understand the topic, which is rule 4 of the domain model and the reason
    nothing here touches their learning stage.

    There is deliberately no `skipped_at` and no `postponed_at`. Nothing records
    *when* an item was skipped or postponed — the question a plan answers is what
    became of the work, not at what hour the learner said so.
    """

    id: uuid.UUID
    topic: PlanItemTopic | None
    action_type: str
    scheduled_for: date | None
    estimated_minutes: int | None
    priority: int
    status: str
    recommendation_reason: str | None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class StudyPlanDetail:
    """One stored plan, optionally with its ordered items.

    `items` is empty on a listed plan and filled on one read singly: a collection
    response carrying every plan's items would be an unbounded payload inside a
    paginated one, which the pagination contract cannot describe. `item_count`
    is therefore always reported, so a listed plan still says how large it is.

    `period_end` is null only when the goal's horizon cannot be dated — an
    examination schedule that publishes no sitting day, and no target date beside
    it. `generation_reason` says so when it happens.
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    study_goal_id: uuid.UUID
    plan_type: str
    period_start: date | None
    period_end: date | None
    status: str
    generation_reason: str | None
    item_count: int
    items: tuple[PlanItemDetail, ...] = ()


@dataclass(frozen=True, slots=True)
class StudyPlanPage:
    """One requested window over the learner's plans.

    `total` counts every plan matching the filters, not the window, so a client
    can tell a complete list from a truncated one.
    """

    plans: tuple[StudyPlanDetail, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class StudyPlanFilters:
    """Which of a learner's plans a listing asks for.

    Every filter is optional and narrowing. A filter naming a value nothing
    matches returns an empty page rather than a failure, as PRG-002's unknown
    curriculum version does: a filter that matches nothing is an empty result,
    not a missing record.
    """

    study_goal_id: uuid.UUID | None = None
    plan_type: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class PlanGenerationRequest:
    """A learner asking for a plan to be generated (PLN-001).

    The goal is named because a learner may hold several; whether it is theirs is
    resolved server-side.
    """

    study_goal_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlanItemStatusChange:
    """A learner saying what became of one plan item (PLN-004).

    `completed`, `skipped`, `postponed`, or the `planned` that takes any of them
    back. The item is named in the path rather than here, and no learner is named
    at all: the effective learner is resolved server-side, and whether the item is
    theirs is decided by the use case.

    Only the status is carried. `completed_at` is the server's record of *when*
    the learner said so, so accepting one from a client would let a caller
    backdate work; the use case reads it from the clock instead. **Postponing
    carries no date**, because the work moves to the plan the learner's next
    adaptation writes rather than to a day they name here — naming one would make
    an item's own content learner-writable, which no endpoint does. Skipping and
    postponing carry no reason either: asking a learner why would invite the
    product to form a view about the answer.
    """

    status: str


@dataclass(frozen=True, slots=True)
class GeneratedStudyPlans:
    """What one generation produced.

    `generated_on` is the date in the learner's own timezone, which is the date
    the plans are built around: a plan generated late on a Sunday evening in
    `Asia/Kolkata` must not start on Sunday because the server was still on
    Saturday in UTC.

    `superseded_plan_ids` names the plans this generation replaced. Reported
    rather than left to be inferred, so a client can say plainly that an earlier
    plan was set aside instead of appearing to have lost it.
    """

    study_goal_id: uuid.UUID
    generated_on: date
    plans: tuple[StudyPlanDetail, ...]
    superseded_plan_ids: tuple[uuid.UUID, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class AdaptedStudyPlans:
    """What one adaptation produced (PLN-005).

    The same pair of plans a generation writes, plus the three facts that make an
    adaptation explainable in a way a plain regeneration is not: what it set
    aside, what it postponed, and how much work the learner has already put
    behind them.

    `postponed_plan_item_ids` names the items whose day passed with the work
    undone. They stay on the superseded plan, marked `postponed`, and their topics
    are re-placed on the new one — so the history says what happened to each line
    rather than leaving a missed day indistinguishable from one never due.

    The two counts are **descriptions of the plan, not measurements of the
    learner**. They say how much of the curriculum this plan covers and why it is
    shorter than the last one; nothing ranks, scores, or congratulates. That is
    the same line ADR-020 drew when it let a plan state "60 topics" while refusing
    to total a day or a week.
    """

    study_goal_id: uuid.UUID
    adapted_on: date
    plans: tuple[StudyPlanDetail, ...]
    superseded_plan_ids: tuple[uuid.UUID, ...] = field(default=())
    postponed_plan_item_ids: tuple[uuid.UUID, ...] = field(default=())
    completed_topic_count: int = 0
    remaining_topic_count: int = 0


@dataclass(frozen=True, slots=True)
class PlanFeasibility:
    """Whether the learner's saved week reaches their goal's horizon (PLN-006).

    This answers
    [FR-004](../../../docs/requirements/functional.md#fr-004-plan-adaptation)'s
    third acceptance criterion — highlighting meaningful trade-offs when time is
    insufficient. **It is a reading and writes nothing**: no plan, no
    availability, no preference, and no item status moves because this was asked.

    **Every number here is a count or a duration.** There is deliberately no
    percentage, no ratio, and no proportion: docs/domain/terminology.md rules that
    a denominator invites a comparison and a comparison turns a description of
    work into a measurement of a person. `coverable_topic_count` and
    `remaining_topic_count` are two counts a caller may state side by side; they
    are never to be rendered as one over the other.

    Every field describes **the plan and the time**, never the learner. A week
    that cannot reach a horizon is a fact about arithmetic, not a verdict on
    effort.

    Attributes:
        study_goal_id: The goal assessed.
        assessed_on: The learner's own date the assessment was made for, from
            their stored timezone. The answer depends on it, so it is reported
            rather than left implicit.
        verdict: One of `FEASIBILITY_VERDICTS`.
        unknown_reason: Why no verdict could be reached, from `UNKNOWN_REASONS`,
            and `None` whenever the verdict is not `unknown`.
        horizon_ends_on: The date the work has to be done by — the earlier of the
            examination window's first sitting day and the goal's target date
            (ADR-020). `None` when the goal aims at neither.
        remaining_topic_count: Topics still to be worked through on the active
            roadmap. A completed topic is not one; a skipped or postponed one is,
            because the next plan places its work again.
        session_minutes: How long one session was taken to run.
        session_minutes_chosen_by_planner: Whether that length is the planner's
            own choice because the learner has set no preference. Reported so the
            screen can say whose decision it was, which is ADR-019's distinction
            between an unset preference and a default.
        study_days: Calendar days from `assessed_on` to the horizon, inclusive.
        available_minutes: What the saved week offers across those days.
        required_minutes: One session for each remaining topic.
        shortfall_minutes: How much more time the work needs than the week
            offers; zero when the week is enough, and never negative.
        coverable_topic_count: How many remaining topics the available time holds
            a whole session for.
        reason: The sentence the learner reads, composed where the numbers are.
    """

    study_goal_id: uuid.UUID
    assessed_on: date
    verdict: str
    reason: str
    unknown_reason: str | None = None
    horizon_ends_on: date | None = None
    remaining_topic_count: int = 0
    session_minutes: int = DEFAULT_SESSION_MINUTES
    session_minutes_chosen_by_planner: bool = True
    study_days: int = 0
    available_minutes: int = 0
    required_minutes: int = 0
    shortfall_minutes: int = 0
    coverable_topic_count: int = 0
