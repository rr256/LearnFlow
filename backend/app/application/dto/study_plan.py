"""Input and output structures for a learner's study plans.

These carry what PLN-001, PLN-002, and PLN-003 generate and read. They are
framework-independent by design, as the other DTOs in this package are: the API
schemas that serialise them are a separate representation, so a change to the
HTTP contract does not reach back into the use case.

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
from datetime import date

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

Every item is written `planned` and stays there. Moving one is PLN-004's work,
which is FR-004 and is not implemented; the column exists because a plan item
without a state is not a plan item.
"""

ROADMAP = "roadmap"
WEEKLY = "weekly"
ACTIVE = "active"
SUPERSEDED = "superseded"
PLANNED = "planned"
STUDY = "study"

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
    """

    id: uuid.UUID
    topic: PlanItemTopic | None
    action_type: str
    scheduled_for: date | None
    estimated_minutes: int | None
    priority: int
    status: str
    recommendation_reason: str | None


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
