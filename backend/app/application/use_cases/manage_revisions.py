"""Scheduling revisions from finished work, reading them, and recording what happened.

Serves REV-001 to REV-004, which together deliver
[FR-006](../../../docs/requirements/functional.md#fr-006-revision-guidance).

**The learner asks; nothing schedules on its own.** Completing a plan item
creates no revision, and neither does completing a revision — the work is done
when the learner presses the control, at a moment they chose. That is ADR-021's
"only the named item moves" applied to a second record type, and ADR-022's "the
learner asks; nothing adapts on its own" applied to a second capability. There is
no scheduler, no background job, and no side effect on another endpoint.

**Revisions are not plan items and are not planned.** They live in their own
table, they survive the supersede that adaptation performs on every plan of a
goal, and `plan_items.action_type = 'revise'` stays unwritten. A revision that
disappeared because the learner rebuilt their plan would be a record of a
decision destroyed by an unrelated action.

**Nothing here writes a learning stage.** Rule 4 of the domain model reads for a
revision as it does for a plan item: this records whether a *review happened*,
never that a topic is understood. The stage is read — it decides how long a topic
waits — and never written.

**Nothing is counted, ranked, or scored.** The one number this reports is how
many topics a scheduling run passed over because they already had a revision
waiting, which describes the run rather than the learner.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.application.dto.revision import (
    COMPLETED,
    COMPLETED_PLAN_ITEM,
    COMPLETED_REVISION,
    DUE,
    REVISION_STATUS_CHANGES,
    REVISION_STATUSES,
    SETTLED_REVISION_STATUSES,
    RevisionDetail,
    RevisionFilters,
    RevisionPage,
    RevisionRecord,
    RevisionStatusChange,
    RevisionTopic,
    ScheduledRevisions,
)
from app.application.ports.clock import Clock
from app.application.ports.learner_repository import LearnerRecord, LearnerRepository
from app.application.ports.revision_repository import RevisionRepository
from app.application.use_cases.local_learner import resolve_local_learner
from app.domain.revision_scheduling import (
    DatedRevision,
    RevisionInterval,
    due_on,
    interval_for_stage,
    select_due,
)


class RevisionManagementError(Exception):
    """Base class for the refusals this use case makes."""


class LearnerNotSetUpError(RevisionManagementError):
    """No learner is stored, so no revision can be owned."""


class RevisionNotFoundError(RevisionManagementError):
    """No such revision is stored, or it belongs to another learner."""


class UnknownRevisionStatusError(RevisionManagementError):
    """A status a learner may not ask for.

    Raised for a value outside `REVISION_STATUS_CHANGES`, which includes
    `scheduled`: the column accepts it, but nothing collects the date it would
    need, so asking for it would store a status whose companion column stays
    null.
    """


class ManageRevisions:
    """Reads and writes a learner's revisions.

    One use case serves all four endpoints, so the rule deciding whether a
    revision belongs to the effective learner stays in one place — the reason
    `ManageStudyPlans` serves the planning endpoints together.
    """

    def __init__(
        self,
        *,
        learners: LearnerRepository,
        revisions: RevisionRepository,
        clock: Clock,
    ) -> None:
        """Bind the use case to its ports."""
        self._learners = learners
        self._revisions = revisions
        self._clock = clock

    def schedule(self) -> ScheduledRevisions:
        """Create revisions for topics whose finished work is ready to come back.

        The caller owns the transaction: this writes through the repository but
        never commits.

        **What creates one.** A topic the learner completed planned work on, and
        which has no revision waiting. A topic whose latest revision the learner
        **completed** gets the next one, dated from that completion — which is
        the *prior revision history* FR-006's fourth criterion names, and what
        makes review spaced rather than single.

        **What does not.** A topic with a revision already `due` is passed over,
        so asking twice creates nothing the second time. A topic whose latest
        revision the learner **skipped or postponed** is passed over too: they
        have said what became of that review, and scheduling must not overrule
        them. Nothing is lost by it — every status is reversible through REV-003,
        so a learner who changes their mind puts the revision back themselves.

        **A learning stage is read, never written.** It decides how long the
        topic waits and nothing else.

        Raises:
            LearnerNotSetUpError: No learner exists to own a revision.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        learner = self._require_learner()
        today = _today_for(learner, self._clock)

        finished = self._revisions.list_completed_topic_work(learner.id)
        latest = _latest_by_topic(self._revisions.list_all_revisions(learner.id))
        topic_ids = [topic_id for topic_id, _, _ in finished]
        stages = self._revisions.list_recorded_stages(learner_id=learner.id, topic_ids=topic_ids)
        topics = {topic.id: topic for topic in self._revisions.list_topics(topic_ids)}

        created: list[RevisionRecord] = []
        passed_over = 0
        for topic_id, plan_item_id, completed_on in finished:
            previous = latest.get(topic_id)
            trigger = _trigger_for(previous)
            if trigger is None:
                passed_over += 1
                continue

            finished_on = completed_on
            if trigger == COMPLETED_REVISION and previous is not None:
                # The next step of a spaced review runs from when the learner
                # finished the last one, not from the original study session.
                finished_on = (
                    previous.completed_at.date()
                    if previous.completed_at is not None
                    else previous.due_on
                )

            interval = interval_for_stage(stages.get(topic_id))
            record = RevisionRecord(
                id=uuid.uuid4(),
                learner_id=learner.id,
                topic_id=topic_id,
                # A revision that follows an earlier revision names no plan item:
                # the work it came from is the review, not the original session.
                plan_item_id=plan_item_id if trigger == COMPLETED_PLAN_ITEM else None,
                due_on=due_on(finished_on, interval),
                scheduled_for=None,
                status=DUE,
                trigger_type=trigger,
                recommendation_reason=_revision_reason(
                    topic=topics.get(topic_id),
                    trigger=trigger,
                    finished_on=finished_on,
                    interval=interval,
                ),
                completed_at=None,
            )
            self._revisions.add_revision(record)
            created.append(record)

        return ScheduledRevisions(
            scheduled_on=today,
            created=tuple(self._describe(created, today)),
            already_scheduled_topic_count=passed_over,
            reason=_schedule_reason(
                created=len(created), passed_over=passed_over, finished=len(finished)
            ),
        )

    def list_revisions(self, *, filters: RevisionFilters, limit: int, offset: int) -> RevisionPage:
        """One page of the learner's revisions, earliest due date first.

        An installation where setup has not run has no learner and therefore no
        revisions, which is an empty page rather than a failure.

        Raises:
            UnknownRevisionStatusError: The status filter names a value the
                column does not hold.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if filters.status is not None and filters.status not in REVISION_STATUSES:
            raise UnknownRevisionStatusError(
                f"'{filters.status}' is not a revision status. "
                f"Use one of: {', '.join(REVISION_STATUSES)}."
            )

        learner = resolve_local_learner(self._learners)
        if learner is None:
            return RevisionPage(revisions=(), total=0)

        today = _today_for(learner, self._clock)
        records = self._revisions.list_revisions(
            learner_id=learner.id, filters=filters, limit=limit, offset=offset
        )
        return RevisionPage(
            revisions=tuple(self._describe(records, today)),
            total=self._revisions.count_revisions(learner_id=learner.id, filters=filters),
        )

    def read(self, revision_id: uuid.UUID) -> RevisionDetail:
        """One of the learner's revisions, with the topic it names.

        Raises:
            RevisionNotFoundError: No such revision is stored, or it belongs to
                another learner.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        learner = resolve_local_learner(self._learners)
        record = None if learner is None else self._revisions.find_revision(revision_id)
        if record is None or learner is None or record.learner_id != learner.id:
            raise RevisionNotFoundError(f"No revision is stored with identifier {revision_id}.")
        return self._describe([record], _today_for(learner, self._clock))[0]

    def record_status(self, revision_id: uuid.UUID, change: RevisionStatusChange) -> RevisionDetail:
        """Record what became of one revision.

        The caller owns the transaction.

        **Every move is allowed**, between `due`, `completed`, `skipped`, and
        `postponed`, from whichever the revision currently holds. Nothing is
        one-way: the four are four answers to one question rather than a
        sequence, which is the position ADR-017 took on a learning stage,
        ADR-021 on completion, and ADR-024 and ADR-025 on skipping and
        postponing.

        **Only the named revision moves.** No other revision, no plan item, no
        plan, and no learning stage — completing a review is not a claim that the
        topic is understood.

        `completed_at` is read from the server's clock rather than accepted from
        a caller, and is cleared by any move off `completed`.

        Raises:
            RevisionNotFoundError: No such revision, or it is not the learner's.
            UnknownRevisionStatusError: A status a learner may not ask for.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if change.status not in REVISION_STATUS_CHANGES:
            raise UnknownRevisionStatusError(
                f"'{change.status}' is not a status you can set on a revision. "
                f"Use one of: {', '.join(REVISION_STATUS_CHANGES)}."
            )

        learner = resolve_local_learner(self._learners)
        record = None if learner is None else self._revisions.find_revision(revision_id)
        if record is None or learner is None or record.learner_id != learner.id:
            raise RevisionNotFoundError(f"No revision is stored with identifier {revision_id}.")

        moved = RevisionRecord(
            id=record.id,
            learner_id=record.learner_id,
            topic_id=record.topic_id,
            plan_item_id=record.plan_item_id,
            due_on=record.due_on,
            scheduled_for=record.scheduled_for,
            status=change.status,
            trigger_type=record.trigger_type,
            recommendation_reason=record.recommendation_reason,
            completed_at=(self._clock.now() if change.status == COMPLETED else None),
        )
        self._revisions.update_revision(moved)
        return self._describe([moved], _today_for(learner, self._clock))[0]

    def _require_learner(self) -> LearnerRecord:
        """The local learner, or a refusal naming what is missing."""
        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError("No learner is stored, so no revision can be scheduled.")
        return learner

    def _describe(self, records: Sequence[RevisionRecord], today: date) -> list[RevisionDetail]:
        """Attach each revision's topic, and whether it is due today.

        Whether a revision is due is decided by the domain rule `select_due`
        rather than by a comparison written here, so a screen and the backend
        cannot disagree about it.

        A revision whose topic is no longer stored reports `topic: null` rather
        than failing: the record is the learner's, and losing the whole page
        because a curriculum row moved would be worse than naming one gap.
        """
        topics = {
            topic.id: topic
            for topic in self._revisions.list_topics([record.topic_id for record in records])
        }
        due = set(
            select_due(
                (
                    DatedRevision(
                        revision_id=record.id,
                        due_on=record.due_on,
                        is_settled=record.status in SETTLED_REVISION_STATUSES,
                    )
                    for record in records
                ),
                today,
            )
        )
        return [
            RevisionDetail(
                id=record.id,
                topic=topics.get(record.topic_id),
                due_on=record.due_on,
                scheduled_for=record.scheduled_for,
                status=record.status,
                trigger_type=record.trigger_type,
                recommendation_reason=record.recommendation_reason,
                completed_at=record.completed_at,
                is_due=record.id in due,
            )
            for record in records
        ]


def _latest_by_topic(records: Sequence[RevisionRecord]) -> dict[uuid.UUID, RevisionRecord]:
    """The most recent revision for each topic, by due date then identifier.

    The identifier breaks a tie two revisions falling due on one day would leave
    ambiguous, so which one counts as latest does not depend on row order.
    """
    latest: dict[uuid.UUID, RevisionRecord] = {}
    for record in sorted(records, key=lambda record: (record.due_on, record.id)):
        latest[record.topic_id] = record
    return latest


def _trigger_for(previous: RevisionRecord | None) -> str | None:
    """Why this topic would get a revision now, or None when it would not.

    - **No revision yet** — the finished study session brings it back.
    - **A completed one** — the review the learner finished brings it back, which
      is what makes revision spaced.
    - **One still waiting** (`due` or `scheduled`) — nothing to do; asking twice
      must not create a second.
    - **A skipped or postponed one** — the learner has said what became of that
      review, and scheduling does not overrule them. They can put it back with
      REV-003 whenever they like.
    """
    if previous is None:
        return COMPLETED_PLAN_ITEM
    if previous.status == COMPLETED:
        return COMPLETED_REVISION
    return None


def _revision_reason(
    *,
    topic: RevisionTopic | None,
    trigger: str,
    finished_on: date,
    interval: RevisionInterval,
) -> str:
    """The sentence a revision gives for itself.

    Written when the revision is created and never rewritten, so a record
    explains itself in the terms that produced its date — the guarantee a plan
    and a plan item each carry. That matters more here than for a plan: the due
    date was computed from the stage recorded at that moment, and a sentence
    recomputed later from a stage the learner has since changed would contradict
    the date stored beside it.

    It describes **the topic and the schedule**, never the learner. A topic
    coming back is a recommendation, not a failure notice
    (docs/domain/terminology.md).
    """
    where = "" if topic is None else f"{topic.subject_name} · {topic.name}. "
    finished = (
        f"You completed planned work on this on {finished_on}"
        if trigger == COMPLETED_PLAN_ITEM
        else f"You completed a revision of this on {finished_on}"
    )
    if interval.chosen_by_scheduler:
        wait = (
            f"LearnFlow brings a topic back after {interval.days} days when no learning stage "
            "is recorded, which it chose because you have not recorded one here"
        )
    else:
        wait = (
            f"LearnFlow brings a topic back after {interval.days} days at the learning stage "
            f"you recorded"
        )
    return f"{where}{finished}, and {wait}."


def _schedule_reason(*, created: int, passed_over: int, finished: int) -> str:
    """The sentence one scheduling run gives for itself.

    Describes **the run**, never the learner: what it looked at, what it wrote,
    and what it left alone. A run that writes nothing is the common case once a
    learner has asked twice, and it says why rather than appearing to fail.
    """
    if finished == 0:
        return (
            "No completed study work was found, so nothing is ready to come back yet. "
            "Complete some planned work and ask again."
        )
    if created == 0:
        return (
            f"Every topic you have finished already has a revision waiting or one you have "
            f"settled, so nothing new was scheduled. {passed_over} were left as they are."
        )
    settled = (
        ""
        if passed_over == 0
        else f" {passed_over} were left as they are, already waiting or already settled."
    )
    return (
        f"{created} topics you have finished are ready to come back, dated from when you "
        f"finished them and the learning stage you recorded.{settled}"
    )


def _today_for(learner: LearnerRecord, clock: Clock) -> date:
    """The learner's own date, not the server's.

    A revision due today must read as due at 23:30 in `Asia/Kolkata` however the
    process is configured. An unknown stored zone falls back to UTC rather than
    failing the request, which is the fallback every other date in this
    application applies.

    This mirrors the identical helper in `manage_study_plans`. The duplication is
    deliberate for now: extracting it is a refactor across a module this change
    otherwise does not touch, and ADR-028 records it as a known cost.
    """
    try:
        zone = ZoneInfo(learner.timezone)
    except ZoneInfoNotFoundError, ValueError:
        return clock.now().date()
    return clock.now().astimezone(zone).date()
