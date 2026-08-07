"""The deterministic rules that turn a curriculum and a week into planned work.

Two rules live here, and both are pure functions over plain values: which order
the topics are worked through, and which day each session lands on. They are
domain rules rather than application plumbing because they are the part a learner
would recognise as *the plan* — everything around them is reading records and
writing them back.

Being pure is the point. FR-003 requires a plan the learner can see the reasons
for, and docs/ai/learnflow-agents.md requires the planner to work with "core
scheduling and prioritization ... deterministic application rules" that stay
usable when no AI provider is reachable. A function whose output depends only on
its arguments can be tested exhaustively, replayed, and explained; one that reads
a clock or a database cannot.

Nothing here knows about days of the week, learning stages, examination windows,
or storage. A capacity arrives as a calendar date and a number of minutes, so the
seven day *names* — which belong to the availability contract, not to arithmetic
— stay in the application layer that owns them (ADR-018).
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
