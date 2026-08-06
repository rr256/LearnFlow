"""Input and output structures for a learner's weekly study availability.

Availability is *when the learner can study*, recorded against the study goal
they are studying toward. docs/domain/terminology.md calls it a planning input,
not a measure of commitment or ability, and nothing here judges it: no total is
computed, no week is compared with another, and no plan is derived. Milestone 3's
planning code is what consumes it.

A week is described one day at a time. A day the learner has not set is absent
from the week rather than reported as zero, and a day carrying zero minutes is
one they deliberately marked unavailable -- the same distinction learner topic
progress draws between no record and an explicit `not_explored`.

Nothing here decides how a week is stored. `day_of_week` is the `snake_case` day
name, which is what the database column holds and what goes on the wire, so no
numbering convention exists for a reader or a client to get wrong (ADR-018).
"""

import uuid
from dataclasses import dataclass

WEEKDAYS: tuple[str, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
"""The seven days `availability_slots.day_of_week` accepts, in week order.

Mirrors the database `CHECK` and the values docs/api/endpoints.md documents. The
order is the order a week is shown in; it is not stored, and nothing ranks one
day above another.
"""

MINUTES_IN_A_DAY = 24 * 60
"""Upper bound on `available_minutes`, mirroring the database `CHECK`.

A day holds 1440 minutes, so a larger value is a mistake rather than an ambitious
learner. Zero is accepted and meaningful.
"""


@dataclass(frozen=True, slots=True)
class AvailabilitySlotEntry:
    """The study time available on one day of the week.

    Attributes:
        day_of_week: One of `WEEKDAYS`, as the stored `snake_case` name.
        available_minutes: Minutes available that day, from 0 to
            `MINUTES_IN_A_DAY`. Zero records a day deliberately kept free.
    """

    day_of_week: str
    available_minutes: int


@dataclass(frozen=True, slots=True)
class WeeklyAvailabilityRequest:
    """The complete week a learner is asking to save (GOAL-005).

    This is a *replacement*, not a merge: the days named become the learner's
    week, and any day they do not name is removed. An empty tuple therefore
    clears the goal's availability, which is how a learner takes it all back.

    A whole-week write is one request and one transaction, so a learner editing
    three days cannot end up with one saved and two lost.
    """

    slots: tuple[AvailabilitySlotEntry, ...]


@dataclass(frozen=True, slots=True)
class WeeklyAvailability:
    """The week currently stored against one study goal.

    `slots` is in week order, Monday first, and holds only the days the learner
    has set. It is empty for a goal whose availability has never been saved,
    which is a real state rather than a failure.
    """

    study_goal_id: uuid.UUID
    slots: tuple[AvailabilitySlotEntry, ...]

    @property
    def is_empty(self) -> bool:
        """Whether the learner has set no day at all."""
        return not self.slots
