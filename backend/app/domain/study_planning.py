"""The deterministic rules that turn a curriculum and a week into planned work.

Four rules live here, and all of them are pure functions over plain values: which
order the topics are worked through, which day each session lands on, what makes
an item overdue, and whether a saved week holds enough time to reach the goal's
horizon. They are domain rules rather than application plumbing because they are
the part a learner would recognise as *the plan* — everything around them is
reading records and writing them back.

Being pure is the point. FR-003 requires a plan the learner can see the reasons
for, and docs/ai/learnflow-agents.md requires the planner to work with "core
scheduling and prioritization ... deterministic application rules" that stay
usable when no AI provider is reachable. A function whose output depends only on
its arguments can be tested exhaustively, replayed, and explained; one that reads
a clock or a database cannot.

Nothing here knows about days of the week, learning stages, examination windows,
or storage. A capacity arrives as a calendar date and a number of minutes, so the
seven day *names* — which belong to the availability contract, not to arithmetic
— stay in the application layer that owns them (ADR-018). The one rule that has
to reason about a repeating week takes it as seven minute counts in
`date.weekday()` order and says so, which keeps the naming decision outside.
"""

import heapq
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

MINIMUM_PLANNED_MINUTES = 1
"""The shortest session worth scheduling.

`plan_items.estimated_minutes` is constrained to be greater than zero, so a day
with nothing left to give contributes no session rather than one of length zero.
"""


@dataclass(frozen=True, slots=True, order=True)
class SyllabusPosition:
    """Where a topic sits in the syllabus, as something sortable.

    `subject_position` and `path` are the stored `position` columns: the
    subject's own, then each topic's position from the root of its branch down to
    the topic itself. Comparing the pair walks the syllabus exactly as a reader
    does — subject by subject, and inside a subject, parent before child.

    `topic_id` breaks a tie that the positions alone cannot. Two topics sharing a
    parent cannot share a position in a correct curriculum, but a total order must
    not depend on that being true: an ordering that varies between two runs over
    identical data is not a deterministic plan.
    """

    subject_position: int
    path: tuple[int, ...]
    topic_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlannableTopic:
    """One trackable topic a plan can schedule work against.

    A topic that only groups subtopics is not one of these. `topics.is_trackable`
    decides that, and the application filters on it before building this value,
    for the same reason PRG-004 refuses a stage against a grouping heading.
    """

    topic_id: uuid.UUID
    position: SyllabusPosition


@dataclass(frozen=True, slots=True)
class TopicOrdering:
    """An ordered run of topics, and what the ordering rule actually managed to do.

    The counts exist so the plan can say something true about itself. A learner
    who asked for prerequisites first and received syllabus order — because no
    prerequisite link is stored — is owed that sentence rather than an order that
    silently is not the one they chose.

    Attributes:
        topics: Every topic given, in the order to work through them.
        prerequisites_applied: How many prerequisite links constrained the result.
            Zero means the order is syllabus order by another name.
        held_back_by_a_cycle: Topics that no prerequisite order could place,
            because their prerequisites form a loop. They are appended in syllabus
            order rather than dropped: a plan that silently omits a topic is worse
            than one that admits it could not order it.
    """

    topics: tuple[PlannableTopic, ...]
    prerequisites_applied: int
    held_back_by_a_cycle: tuple[PlannableTopic, ...]


@dataclass(frozen=True, slots=True)
class DayCapacity:
    """How many minutes of study one calendar day holds.

    A quantity, not a sitting between two clock times — the same value an
    availability slot carries, resolved onto a date. Nothing here records when in
    the day the work falls (ADR-018).
    """

    on: date
    available_minutes: int


@dataclass(frozen=True, slots=True)
class PlannedSession:
    """One topic placed on one day, for a length of time.

    `estimated_minutes` is the preferred session length, or the whole of what the
    day had left when the day is shorter than one session. A day too short for a
    full session still gets one topic rather than none, because a learner with
    thirty minutes a day is planning, not failing.
    """

    topic_id: uuid.UUID
    scheduled_for: date
    estimated_minutes: int


def order_by_syllabus(topics: Iterable[PlannableTopic]) -> TopicOrdering:
    """The topics in the order the syllabus teaches them.

    Subject by subject in stored `position` order, and inside each subject parent
    before child, again by `position`. This is the order CUR-003 renders and the
    order the frontend is forbidden to re-sort, so a plan that walked it
    differently would disagree with the curriculum screen beside it.
    """
    return TopicOrdering(
        topics=tuple(sorted(topics, key=lambda topic: topic.position)),
        prerequisites_applied=0,
        held_back_by_a_cycle=(),
    )


def order_by_prerequisites(
    topics: Iterable[PlannableTopic],
    prerequisites: Mapping[uuid.UUID, frozenset[uuid.UUID]],
) -> TopicOrdering:
    """The topics in an order that puts each one after what it depends on.

    A topological order over the prerequisite links, choosing the earliest
    syllabus position among the topics that are ready at each step. The tie-break
    is what makes the result a single defined order rather than one of many valid
    ones: two runs over the same curriculum produce the same plan.

    With no links stored the result is exactly `order_by_syllabus`, and
    `prerequisites_applied` says so, so a caller can report that the learner's
    chosen order changed nothing rather than implying it did.

    Args:
        topics: The topics to order.
        prerequisites: For each topic, the topics that must come before it.
            An entry naming a topic outside `topics` is ignored — a prerequisite
            that is not being planned cannot hold anything back — so a curriculum
            linking a trackable topic to a grouping heading still orders.

    Returns:
        The ordering, including any topics a loop of prerequisites made
        unplaceable. Those are appended in syllabus order, so every topic given is
        returned exactly once whatever the links say.
    """
    by_position = tuple(sorted(topics, key=lambda topic: topic.position))
    planned = {topic.topic_id: topic for topic in by_position}

    # Only links between two topics being planned constrain anything, and a link
    # is counted once even if it is stored twice.
    blocking: dict[uuid.UUID, set[uuid.UUID]] = {
        topic_id: {
            required
            for required in prerequisites.get(topic_id, frozenset())
            if required in planned and required != topic_id
        }
        for topic_id in planned
    }
    unblocks: dict[uuid.UUID, list[uuid.UUID]] = {topic_id: [] for topic_id in planned}
    for topic_id, required_ids in blocking.items():
        for required in required_ids:
            unblocks[required].append(topic_id)
    applied = sum(len(required_ids) for required_ids in blocking.values())

    ready = [
        (topic.position, topic.topic_id) for topic in by_position if not blocking[topic.topic_id]
    ]
    heapq.heapify(ready)

    ordered: list[PlannableTopic] = []
    while ready:
        _, topic_id = heapq.heappop(ready)
        ordered.append(planned[topic_id])
        for dependent in unblocks[topic_id]:
            blocking[dependent].discard(topic_id)
            if not blocking[dependent]:
                heapq.heappush(ready, (planned[dependent].position, dependent))

    placed = {topic.topic_id for topic in ordered}
    held_back = tuple(topic for topic in by_position if topic.topic_id not in placed)
    return TopicOrdering(
        topics=tuple(ordered) + held_back,
        prerequisites_applied=applied,
        held_back_by_a_cycle=held_back,
    )


def schedule_sessions(
    topic_ids: Sequence[uuid.UUID],
    capacities: Sequence[DayCapacity],
    *,
    session_minutes: int,
) -> tuple[PlannedSession, ...]:
    """Place topics onto days, in order, until one of the two runs out.

    Each day is filled with whole sessions while it has room for one. A day with
    some time left but less than a full session gets a single shorter session
    **only if nothing else was placed on it**, so a learner whose whole day is
    twenty minutes still receives a topic, while a longer day does not end in an
    offcut too small to study.

    Topics are taken in the order given and never reordered, split across days, or
    revisited: the ordering rule above already decided what comes first, and a
    scheduler that reshuffled it would make the plan's stated order untrue.

    Args:
        topic_ids: The topics to place, most important first.
        capacities: The days available, in the order they occur.
        session_minutes: The learner's preferred session length, or the length the
            caller chose on their behalf. Must be positive.

    Returns:
        One session per topic placed, in date order. Topics that did not fit are
        simply absent — reporting the shortfall is the caller's business, because
        only it knows what the missing work means.

    Raises:
        ValueError: `session_minutes` is not positive, which would either place
            nothing or never terminate.
    """
    if session_minutes < MINIMUM_PLANNED_MINUTES:
        raise ValueError("A session must be at least one minute long.")

    sessions: list[PlannedSession] = []
    remaining = iter(topic_ids)
    for capacity in capacities:
        left = capacity.available_minutes
        placed_today = 0
        while left >= session_minutes or (placed_today == 0 and left >= MINIMUM_PLANNED_MINUTES):
            topic_id = next(remaining, None)
            if topic_id is None:
                return tuple(sessions)
            minutes = min(session_minutes, left)
            sessions.append(
                PlannedSession(
                    topic_id=topic_id, scheduled_for=capacity.on, estimated_minutes=minutes
                )
            )
            left -= minutes
            placed_today += 1
    return tuple(sessions)


@dataclass(frozen=True, slots=True)
class DatedItem:
    """One plan item reduced to what deciding "behind" needs.

    An identifier, the day the plan asked for the work, and whether anything has
    already been said about what became of it. Nothing else about an item bears
    on the question.
    """

    plan_item_id: uuid.UUID
    scheduled_for: date | None
    is_settled: bool


def select_overdue(items: Iterable[DatedItem], today: date) -> tuple[uuid.UUID, ...]:
    """The items whose day has passed and which nobody has settled.

    This is the definition of an item being *overdue*, kept here rather than inside the
    use case because it is a rule about a plan rather than a database read, and
    because a rule this consequential should be exhaustively testable without a
    clock (FR-004).

    Three boundaries are decided rather than left to be discovered:

    - **Today is not behind.** An item dated today still has the day to happen in,
      so it is not overdue until tomorrow. Adapting in the morning must not
      declare the day already lost.
    - **An undated item is never behind.** A roadmap item says what order to work
      in, not which day; it cannot be late for a day it never named.
    - **A settled item is never behind.** Work that happened is not late, however
      late it was completed; work the learner chose to *skip* is not late either,
      because they have already said it is not going to fill that day; and work
      they *postponed* is not late, because they have already said it is moving.

    That last boundary is why the field is `is_settled` rather than `is_done`.
    Completing, skipping, and postponing are three different statements about
    three different things, but they answer this question the same way: something
    has already been said about the work, so nothing should carry it forward on
    the learner's behalf and overwrite what they said with an inference about a
    date.

    Returns:
        The identifiers, in the order given, so a caller writing them back does so
        deterministically.
    """
    return tuple(
        item.plan_item_id
        for item in items
        if not item.is_settled and item.scheduled_for is not None and item.scheduled_for < today
    )


DAYS_IN_WEEK = 7
"""How many minute counts a repeating week is described by.

`assess_horizon_coverage` takes exactly this many, in `date.weekday()` order —
Monday first — because that is how Python indexes the type it is already given.
Which stored day *name* fills which position is the application's decision, and
[ADR-018](../../../docs/adr/ADR-018-weekly-availability-slots.md) keeps it there.
"""


@dataclass(frozen=True, slots=True)
class HorizonCoverage:
    """Whether a repeating week reaches a horizon, and by how much it misses.

    Every field is a count or a duration, never a ratio, a percentage, or a
    proportion. That is the line docs/domain/terminology.md draws: a denominator
    invites a comparison, and a comparison turns a description of work into a
    measurement of a person. A caller that wants to say how much is covered says
    it as two counts.

    Attributes:
        study_days: Calendar days from the start date to the horizon, inclusive.
            Zero when the horizon has already passed.
        available_minutes: What the saved week offers across those days.
        required_minutes: One session for each topic still to be worked through.
        shortfall_minutes: How much more time the work needs than the week
            offers. Zero when the week is enough, never negative — a surplus is
            reported by `is_sufficient` rather than as a negative shortfall,
            because "twelve hours spare" is a different statement from "twelve
            hours short" and a sign is a poor way to tell a learner which.
        coverable_topics: How many of the remaining topics the available time
            holds a whole session for. Never more than were asked about.
        is_sufficient: Whether the available time meets or exceeds what the
            remaining work needs.
    """

    study_days: int
    available_minutes: int
    required_minutes: int
    shortfall_minutes: int
    coverable_topics: int
    is_sufficient: bool


def assess_horizon_coverage(
    *,
    remaining_topics: int,
    session_minutes: int,
    weekly_minutes: Sequence[int],
    starts_on: date,
    ends_on: date,
) -> HorizonCoverage:
    """Whether the saved week holds enough time for the work left before a date.

    This is the rule behind
    [FR-004](../../../docs/requirements/functional.md#fr-004-plan-adaptation)'s
    third acceptance criterion — highlighting meaningful trade-offs when time is
    insufficient. It is a domain rule for the same reason the ordering and
    placement rules are: it is arithmetic a learner would recognise as part of
    their plan, it depends on nothing but its arguments, and
    docs/domain/terminology.md says explicitly that totalling available time is
    planning arithmetic the *planner* should perform rather than a screen.

    **The whole span is counted by weekday rather than walked day by day.** A
    goal aimed years out would otherwise mean an unbounded loop to answer one
    question; counting how often each weekday falls in the span is exact, is
    seven multiplications, and cannot drift from the day-by-day answer because it
    is the same sum in a different order.

    Three boundaries are decided here rather than left to be discovered:

    - **Both ends are inclusive.** Today can still be studied, and so can the day
      the horizon names — an examination window's first sitting day is when the
      studying has to be *done by*, and declaring today already lost would be the
      same error `select_overdue` refuses when it rules that today is not behind.
    - **A horizon that has passed offers no days**, rather than negative ones.
      The work is then short by all of what it needs, which is true and sayable.
    - **A partial session covers no topic.** Time enough for half a session is
      not a topic covered, so `coverable_topics` floors rather than rounds. A
      plan that claimed a topic it had forty minutes for would be the optimism
      this rule exists to replace.

    Args:
        remaining_topics: Topics still to be worked through. A completed topic is
            not one of these; a skipped or postponed one is, because the next
            plan places its work again (ADR-022, ADR-024, ADR-025).
        session_minutes: How long one session runs — the learner's preference, or
            the length the caller chose on their behalf and names as its own.
            Must be positive.
        weekly_minutes: Seven minute counts in `date.weekday()` order, Monday
            first. A day the learner never set and a day they deliberately kept
            free both arrive as zero: neither is a statement that they can study,
            and keeping them distinct is the *caller's* business, because only it
            knows which of the two happened.
        starts_on: The first day that may be studied, normally the learner's own
            today.
        ends_on: The horizon — the date the work has to be done by.

    Returns:
        The coverage, as counts and durations only.

    Raises:
        ValueError: `session_minutes` is not positive, which would make
            `coverable_topics` meaningless; `remaining_topics` is negative; or
            `weekly_minutes` does not describe exactly seven days.
    """
    if session_minutes < MINIMUM_PLANNED_MINUTES:
        raise ValueError("A session must be at least one minute long.")
    if remaining_topics < 0:
        raise ValueError("A plan cannot have a negative number of topics remaining.")
    if len(weekly_minutes) != DAYS_IN_WEEK:
        raise ValueError(f"A week must be described by exactly {DAYS_IN_WEEK} minute counts.")

    study_days = max(0, ends_on.toordinal() - starts_on.toordinal() + 1)
    available = sum(
        minutes * _weekday_occurrences(starts_on, study_days, weekday)
        for weekday, minutes in enumerate(weekly_minutes)
    )
    required = remaining_topics * session_minutes

    return HorizonCoverage(
        study_days=study_days,
        available_minutes=available,
        required_minutes=required,
        shortfall_minutes=max(0, required - available),
        coverable_topics=min(remaining_topics, available // session_minutes),
        is_sufficient=available >= required,
    )


def _weekday_occurrences(starts_on: date, study_days: int, weekday: int) -> int:
    """How often one weekday falls in a span of consecutive days.

    Every weekday occurs once per whole week the span holds. The days left over
    run forward from `starts_on`, so a weekday is owed one more when it falls
    inside that remainder.
    """
    whole_weeks, remainder = divmod(study_days, DAYS_IN_WEEK)
    offset = (weekday - starts_on.weekday()) % DAYS_IN_WEEK
    return whole_weeks + (1 if offset < remainder else 0)
