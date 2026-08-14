"""The deterministic rules that decide when a topic comes back for revision.

Two rules live here, and both are pure functions over plain values: how long
after finished work a topic should be revisited, and which of a learner's
revisions are due on a given day. They are domain rules for the reason the
planning rules in `study_planning` are — they are the part a learner would
recognise as *the recommendation*, and everything around them is reading records
and writing them back.

Being pure is the point.
[FR-006](../../../docs/requirements/functional.md#fr-006-revision-guidance)
requires revision the learner can act on, and
docs/ai/learnflow-agents.md requires the product's scheduling to stay
deterministic and usable with no AI provider reachable. A function whose output
depends only on its arguments can be tested exhaustively and explained; one that
reads a clock or a database cannot.

**Nothing here judges the learner.** An interval is how long until a topic is
worth seeing again, never a measure of how well it was learned, and a revision
that falls due is a recommendation rather than a failure notice
(docs/domain/terminology.md). Nothing here counts, ranks, or scores anything.
"""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

DEFAULT_REVISION_INTERVAL_DAYS = 7
"""How long after finished work a topic comes back when no stage is recorded.

**Not a stored default.** `learner_topic_progress` holds no row until the learner
records a stage, and a topic with no record reads as *Not explored* rather than
as a stage somebody chose (ADR-017). This is the scheduler choosing for itself,
in code a contributor can read, and it says so in the revision it writes — the
same promise ADR-020 keeps for an unset session length.
"""

REVISION_INTERVAL_DAYS: Mapping[str, int] = {
    "not_explored": 7,
    "building_foundation": 7,
    "developing_confidence": 10,
    "practice_ready": 14,
    "strong_understanding": 21,
}
"""How many days after finished work each recorded learning stage waits.

**These are LearnFlow's intervals, not the learner's**, and they are named as
such wherever a revision explains itself. A learner has set a stage, not a
schedule.

**A longer interval is not a better mark.** The stage says what the learner told
us about their understanding, and a topic they are confident with is worth seeing
again later than one they are still building — which is the *supportive next
action* a stage exists to guide (FR-005). Nothing here compares two topics, ranks
them, or scores the learner, and a stage still never reorders a **plan**: that
refusal belongs to `study_planning` and ADR-020, and is untouched.

A stage this build does not recognise falls back to
`DEFAULT_REVISION_INTERVAL_DAYS`, so a backend that grows a sixth stage
schedules something sensible rather than failing.
"""


@dataclass(frozen=True, slots=True)
class RevisionInterval:
    """How long a topic waits, and why it waited that long.

    The reason travels with the number because a learner is entitled to know
    where a date came from — the same guarantee every plan and plan item carries
    in `recommendation_reason`.

    Attributes:
        days: Days after the finished work before the topic is due.
        learning_stage: The stage the interval came from, or `None` when the
            learner has recorded none and the scheduler chose for itself.
        chosen_by_scheduler: Whether the interval is LearnFlow's own choice
            because no stage was recorded or the stage was not recognised.
    """

    days: int
    learning_stage: str | None
    chosen_by_scheduler: bool


def interval_for_stage(learning_stage: str | None) -> RevisionInterval:
    """How long after finished work a topic with this stage comes back.

    Args:
        learning_stage: The stage the learner recorded against the topic, or
            `None` when they have recorded none. An unrecognised value is
            treated as unrecorded rather than refused, because a scheduler that
            failed on a value a later backend added would leave the learner with
            no revisions at all.

    Returns:
        The interval, and whether LearnFlow chose it rather than the learner's
        stage deciding it.
    """
    if learning_stage is None or learning_stage not in REVISION_INTERVAL_DAYS:
        return RevisionInterval(
            days=DEFAULT_REVISION_INTERVAL_DAYS,
            learning_stage=None,
            chosen_by_scheduler=True,
        )
    return RevisionInterval(
        days=REVISION_INTERVAL_DAYS[learning_stage],
        learning_stage=learning_stage,
        chosen_by_scheduler=False,
    )


def due_on(finished_on: date, interval: RevisionInterval) -> date:
    """The day a topic finished on one date becomes due for revision.

    Args:
        finished_on: The day the work was finished — a plan item's completion, or
            an earlier revision's.
        interval: The wait, from `interval_for_stage`.

    Returns:
        The due date. Always after `finished_on`, because every interval is at
        least a day: a topic finished this morning is not owed revision this
        afternoon.
    """
    return date.fromordinal(finished_on.toordinal() + interval.days)


@dataclass(frozen=True, slots=True)
class DatedRevision:
    """One revision reduced to what deciding "due today" needs.

    An identifier, the day it falls due, and whether anything has already been
    said about it. Nothing else about a revision bears on the question.
    """

    revision_id: uuid.UUID
    due_on: date
    is_settled: bool


def select_due(revisions: Iterable[DatedRevision], today: date) -> tuple[uuid.UUID, ...]:
    """The revisions a learner could act on today, in the order given.

    Three boundaries are decided here rather than left to be discovered, and each
    mirrors one `select_overdue` fixes for a plan item, because a learner meeting
    both on one screen should not have to learn two sets of rules:

    - **A revision due today is due.** The day has not finished, so the work can
      still happen — where an *item* dated today is not yet behind, a revision
      dated today is exactly what the learner is being offered.
    - **A revision due in the future is not.** It is scheduled, not owed, and
      showing it as due would ask for work the schedule did not ask for.
    - **A settled revision is never due**, however late it was completed, and
      whether the learner completed it, skipped it, or postponed it. Something
      has already been said about it, so nothing should offer it again on its
      own.

    Returns:
        The identifiers, in the order given, so a caller rendering them does so
        deterministically.
    """
    return tuple(
        revision.revision_id
        for revision in revisions
        if not revision.is_settled and revision.due_on <= today
    )
