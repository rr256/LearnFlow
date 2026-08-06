"""Input and output structures for a learner's planning preferences.

A planning preference is *how* the learner wants a study plan built, where they
have said. It is a planning input beside weekly availability rather than a
measure of anything: nothing here ranks two preferences, judges a choice, or
derives a plan from one. Milestone 3's planning code is what reads them.

Two fields, chosen because a planner cannot avoid either and both are answerable
from data that already exists:

`preferred_session_minutes` is how long one study block should be. A planner
slicing a day's `available_minutes` into `plan_items.estimated_minutes` has to
decide between one long block and several short ones, and only the learner knows
which they can sustain. It is a **duration**, not a time of day -- the same kind
of value as `available_minutes` -- so it does not reopen ADR-018's deliberate
refusal to store clock times.

`topic_sequencing` is which order a roadmap walks the curriculum in. Both
choices are derivable today: `syllabus_order` follows the stored `position` of
subjects and topics, and `prerequisites_first` follows the `prerequisite` edges
in `topic_relationships`. Neither needs evidence, which is why no
priority-focus-first choice is offered -- the evidence that would order topics
that way is not stored.

**A preference the learner has not set is `None`, not a default.** Nothing
invents one on their behalf, so "not set" stays distinguishable from "set to the
value we would have guessed" -- the distinction ADR-017 drew between an explicit
`not_explored` and no record, and ADR-018 drew between zero minutes and no row. A
planner meeting `None` chooses its own default visibly rather than reading a
value nobody chose.

Nothing here decides how a preference is stored. `topic_sequencing` is the
`snake_case` value, which is what the database column holds and what goes on the
wire; the label a learner reads lives in the client
(docs/domain/terminology.md).
"""

from dataclasses import dataclass

TOPIC_SEQUENCING_CHOICES: tuple[str, ...] = ("syllabus_order", "prerequisites_first")
"""The orders a roadmap may walk the curriculum in, as the stored values.

Mirrors the database `CHECK` and the values docs/api/endpoints.md documents.
There is no default: a goal that names neither leaves the choice to the planner
that eventually reads it.
"""

MINIMUM_SESSION_MINUTES = 15
"""Shortest study block a plan may be asked to produce.

Below a quarter of an hour a plan item is scheduling overhead rather than study,
and a planner given three minutes has nothing useful to place in it.
"""

MAXIMUM_SESSION_MINUTES = 480
"""Longest study block a plan may be asked to produce.

Eight hours is a full working day. A preference larger than that cannot be
honoured inside a day that also holds anything else, and a day itself is already
bounded by `available_minutes`.
"""


@dataclass(frozen=True, slots=True)
class PlanningPreferences:
    """How the learner wants a plan built, for the choices they have made.

    Every field is optional and independently unset. A learner who has answered
    one question and not the other is a real state rather than a half-filled
    form, so neither field waits for the other.

    Attributes:
        preferred_session_minutes: Length of one study block, from
            `MINIMUM_SESSION_MINUTES` to `MAXIMUM_SESSION_MINUTES`. None when
            the learner has not said.
        topic_sequencing: One of `TOPIC_SEQUENCING_CHOICES`. None when the
            learner has not said.
    """

    preferred_session_minutes: int | None = None
    topic_sequencing: str | None = None

    @property
    def is_empty(self) -> bool:
        """Whether the learner has set no preference at all."""
        return self.preferred_session_minutes is None and self.topic_sequencing is None


NO_PLANNING_PREFERENCES = PlanningPreferences()
"""The empty set of preferences, for a goal whose learner has set none.

A goal always carries a `PlanningPreferences` rather than sometimes carrying
`None`, so no reader needs a branch for a goal created before preferences
existed. This is the shape ADR-018 chose when it gave an unset week
`{"slots": []}` rather than a null.
"""
