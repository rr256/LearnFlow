"""Tests for the revision use case (REV-001 to REV-004).

Exercised against fakes with a fixed clock, so every due date is asserted
exactly rather than relative to whenever the suite runs. The scheduling
arithmetic is proved in `test_revision_scheduling.py`, where it is pure; what
these establish is everything that needs a record to decide — which topics come
back, which are left alone, what a learner may ask for, and that nothing else
moves.
"""

import uuid
from datetime import UTC, date, datetime

import pytest

from app.application.dto.revision import (
    COMPLETED,
    COMPLETED_PLAN_ITEM,
    COMPLETED_REVISION,
    DUE,
    POSTPONED,
    SKIPPED,
    RevisionFilters,
    RevisionRecord,
    RevisionStatusChange,
    RevisionTopic,
)
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_revisions import (
    LearnerNotSetUpError,
    ManageRevisions,
    RevisionNotFoundError,
    UnknownRevisionStatusError,
)
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_revision_repository import FakeRevisionRepository
from tests.unit.planning_fixtures import FixedClock

INSTANT = datetime(2026, 8, 20, 9, 0, tzinfo=UTC)
TODAY = date(2026, 8, 20)
FINISHED_ON = date(2026, 8, 13)

TOPIC_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_TOPIC_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
PLAN_ITEM_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")


def topic(topic_id: uuid.UUID = TOPIC_ID, name: str = "CPU scheduling") -> RevisionTopic:
    return RevisionTopic(
        id=topic_id,
        code=None,
        name=name,
        subject_id=uuid.uuid4(),
        subject_name="Operating Systems",
    )


class Revising:
    """A learner, the work they finished, and somewhere to put revisions."""

    def __init__(
        self,
        *,
        completed_work=(),
        revisions=(),
        stages=None,
        topics=None,
        learners=None,
        timezone: str = "Asia/Kolkata",
    ) -> None:
        self.learner = learner(timezone=timezone)
        self.learners = FakeLearnerRepository(
            (self.learner,) if learners is None else tuple(learners)
        )
        self.revisions = FakeRevisionRepository(
            revisions=revisions,
            topics=topics if topics is not None else [topic(), topic(OTHER_TOPIC_ID, "Deadlock")],
            completed_work=completed_work,
            stages=stages,
        )
        self.clock = FixedClock(INSTANT)

    def reviser(self) -> ManageRevisions:
        return ManageRevisions(learners=self.learners, revisions=self.revisions, clock=self.clock)

    def stored(self, topic_id: uuid.UUID = TOPIC_ID) -> RevisionRecord:
        return next(r for r in self.revisions.revisions if r.topic_id == topic_id)


def revision(
    *,
    learner_id: uuid.UUID,
    topic_id: uuid.UUID = TOPIC_ID,
    due: date = date(2026, 8, 20),
    status: str = DUE,
    completed_at: datetime | None = None,
    trigger: str = COMPLETED_PLAN_ITEM,
) -> RevisionRecord:
    return RevisionRecord(
        id=uuid.uuid4(),
        learner_id=learner_id,
        topic_id=topic_id,
        plan_item_id=PLAN_ITEM_ID,
        due_on=due,
        scheduled_for=None,
        status=status,
        trigger_type=trigger,
        recommendation_reason="Because you finished it.",
        completed_at=completed_at,
    )


# -- scheduling ---------------------------------------------------------------


def test_finished_work_brings_a_topic_back_after_the_default_interval():
    """No stage recorded, so LearnFlow's own seven days apply."""
    revising = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])

    result = revising.reviser().schedule()

    assert len(result.created) == 1
    assert result.created[0].due_on == date(2026, 8, 20)
    assert result.created[0].status == DUE
    assert result.created[0].trigger_type == COMPLETED_PLAN_ITEM


def test_a_recorded_stage_decides_how_long_the_topic_waits():
    revising = Revising(
        completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)],
        stages={TOPIC_ID: "strong_understanding"},
    )

    result = revising.reviser().schedule()

    assert result.created[0].due_on == date(2026, 9, 3)


def test_the_new_revision_names_the_plan_item_it_came_from():
    revising = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])

    revising.reviser().schedule()

    assert revising.stored().plan_item_id == PLAN_ITEM_ID


def test_each_new_revision_explains_itself():
    revising = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])

    reason = revising.reviser().schedule().created[0].recommendation_reason or ""

    assert "CPU scheduling" in reason
    assert "2026-08-13" in reason
    assert "7 days" in reason


def test_an_unrecorded_stage_is_named_as_the_schedulers_own_choice():
    revising = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])

    reason = revising.reviser().schedule().created[0].recommendation_reason or ""

    assert "you have not recorded one" in reason


def test_a_recorded_stage_is_named_as_the_learners():
    revising = Revising(
        completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)],
        stages={TOPIC_ID: "practice_ready"},
    )

    reason = revising.reviser().schedule().created[0].recommendation_reason or ""

    assert "the learning stage you recorded" in reason


def test_asking_twice_creates_nothing_the_second_time():
    revising = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])
    revising.reviser().schedule()

    second = revising.reviser().schedule()

    assert second.created == ()
    assert second.already_scheduled_topic_count == 1
    assert len(revising.revisions.revisions) == 1


def test_a_completed_revision_brings_the_topic_back_again():
    """Prior revision history, which is what makes review spaced."""
    revising = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])
    revising.reviser().schedule()
    first = revising.stored()
    revising.reviser().record_status(first.id, RevisionStatusChange(status=COMPLETED))

    result = revising.reviser().schedule()

    assert len(result.created) == 1
    assert result.created[0].trigger_type == COMPLETED_REVISION
    # Dated from the completion instant the fixed clock reports, not the original
    # study session a week earlier.
    assert result.created[0].due_on == date(2026, 8, 27)


def test_a_revision_following_a_revision_names_no_plan_item():
    revising = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])
    revising.reviser().schedule()
    first = revising.stored()
    revising.reviser().record_status(first.id, RevisionStatusChange(status=COMPLETED))

    result = revising.reviser().schedule()

    assert result.created[0] is not None
    following = [r for r in revising.revisions.revisions if r.trigger_type == COMPLETED_REVISION]
    assert following[0].plan_item_id is None


@pytest.mark.parametrize("settled", [SKIPPED, POSTPONED])
def test_a_settled_revision_is_not_overruled_by_scheduling(settled: str):
    """The learner has said what became of that review; this does not argue."""
    revising = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])
    revising.reviser().schedule()
    first = revising.stored()
    revising.reviser().record_status(first.id, RevisionStatusChange(status=settled))

    result = revising.reviser().schedule()

    assert result.created == ()
    assert result.already_scheduled_topic_count == 1


def test_scheduling_with_no_finished_work_creates_nothing_and_says_why():
    revising = Revising()

    result = revising.reviser().schedule()

    assert result.created == ()
    assert "No completed study work" in result.reason


def test_the_run_is_dated_in_the_learners_own_timezone():
    revising = Revising(timezone="Pacific/Kiritimati")

    assert revising.reviser().schedule().scheduled_on == date(2026, 8, 20)


def test_scheduling_the_same_inputs_twice_gives_the_same_dates():
    first = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])
    second = Revising(completed_work=[(TOPIC_ID, PLAN_ITEM_ID, FINISHED_ON)])

    assert (
        first.reviser().schedule().created[0].due_on
        == second.reviser().schedule().created[0].due_on
    )


def test_scheduling_needs_a_learner():
    revising = Revising(learners=())

    with pytest.raises(LearnerNotSetUpError):
        revising.reviser().schedule()


def test_scheduling_refuses_when_more_than_one_learner_is_stored():
    revising = Revising(learners=(learner(), learner()))

    with pytest.raises(AmbiguousLocalLearnerError):
        revising.reviser().schedule()


# -- reading ------------------------------------------------------------------


def test_revisions_are_listed_earliest_due_date_first():
    owner = learner()
    revising = Revising(
        revisions=[
            revision(learner_id=owner.id, due=date(2026, 9, 1), topic_id=OTHER_TOPIC_ID),
            revision(learner_id=owner.id, due=date(2026, 8, 18)),
        ],
        learners=(owner,),
    )

    page = revising.reviser().list_revisions(filters=RevisionFilters(), limit=25, offset=0)

    assert [r.due_on for r in page.revisions] == [date(2026, 8, 18), date(2026, 9, 1)]
    assert page.total == 2


def test_a_revision_whose_day_has_arrived_reads_as_due():
    owner = learner()
    revising = Revising(revisions=[revision(learner_id=owner.id, due=TODAY)], learners=(owner,))

    page = revising.reviser().list_revisions(filters=RevisionFilters(), limit=25, offset=0)

    assert page.revisions[0].is_due is True


def test_a_revision_due_later_does_not_read_as_due():
    owner = learner()
    revising = Revising(
        revisions=[revision(learner_id=owner.id, due=date(2026, 9, 1))], learners=(owner,)
    )

    page = revising.reviser().list_revisions(filters=RevisionFilters(), limit=25, offset=0)

    assert page.revisions[0].is_due is False


def test_a_settled_revision_does_not_read_as_due_however_late_its_day():
    owner = learner()
    revising = Revising(
        revisions=[revision(learner_id=owner.id, due=date(2026, 7, 1), status=SKIPPED)],
        learners=(owner,),
    )

    page = revising.reviser().list_revisions(filters=RevisionFilters(), limit=25, offset=0)

    assert page.revisions[0].is_due is False


def test_due_only_leaves_out_what_the_learner_has_settled():
    owner = learner()
    revising = Revising(
        revisions=[
            revision(learner_id=owner.id, due=date(2026, 8, 18)),
            revision(
                learner_id=owner.id,
                due=date(2026, 8, 19),
                status=COMPLETED,
                topic_id=OTHER_TOPIC_ID,
            ),
        ],
        learners=(owner,),
    )

    page = revising.reviser().list_revisions(
        filters=RevisionFilters(due_only=True), limit=25, offset=0
    )

    assert page.total == 1


def test_an_unknown_status_filter_is_refused():
    revising = Revising()

    with pytest.raises(UnknownRevisionStatusError):
        revising.reviser().list_revisions(
            filters=RevisionFilters(status="invented"), limit=25, offset=0
        )


def test_a_learner_who_has_not_set_up_has_no_revisions():
    revising = Revising(learners=())

    page = revising.reviser().list_revisions(filters=RevisionFilters(), limit=25, offset=0)

    assert page.revisions == ()
    assert page.total == 0


def test_reading_one_revision_names_its_topic():
    owner = learner()
    stored = revision(learner_id=owner.id)
    revising = Revising(revisions=[stored], learners=(owner,))

    detail = revising.reviser().read(stored.id)

    assert detail.topic is not None
    assert detail.topic.name == "CPU scheduling"


def test_another_learners_revision_is_reported_as_missing():
    owner = learner()
    revising = Revising(revisions=[revision(learner_id=uuid.uuid4())], learners=(owner,))
    stored = revising.revisions.revisions[0]

    with pytest.raises(RevisionNotFoundError):
        revising.reviser().read(stored.id)


def test_an_unknown_revision_is_reported_as_missing():
    revising = Revising()

    with pytest.raises(RevisionNotFoundError):
        revising.reviser().read(uuid.uuid4())


# -- recording what happened --------------------------------------------------


@pytest.mark.parametrize("status", [COMPLETED, SKIPPED, POSTPONED, DUE])
def test_a_learner_may_move_a_revision_to_any_of_the_four(status: str):
    owner = learner()
    stored = revision(learner_id=owner.id)
    revising = Revising(revisions=[stored], learners=(owner,))

    assert (
        revising.reviser().record_status(stored.id, RevisionStatusChange(status=status)).status
        == status
    )


def test_completing_records_the_time_from_the_server_clock():
    owner = learner()
    stored = revision(learner_id=owner.id)
    revising = Revising(revisions=[stored], learners=(owner,))

    detail = revising.reviser().record_status(stored.id, RevisionStatusChange(status=COMPLETED))

    assert detail.completed_at == INSTANT


@pytest.mark.parametrize("status", [DUE, SKIPPED, POSTPONED])
def test_moving_off_completed_clears_the_completion_time(status: str):
    owner = learner()
    stored = revision(learner_id=owner.id, status=COMPLETED, completed_at=INSTANT)
    revising = Revising(revisions=[stored], learners=(owner,))

    detail = revising.reviser().record_status(stored.id, RevisionStatusChange(status=status))

    assert detail.completed_at is None


def test_only_the_named_revision_moves():
    owner = learner()
    moved = revision(learner_id=owner.id)
    untouched = revision(learner_id=owner.id, topic_id=OTHER_TOPIC_ID, due=date(2026, 9, 1))
    revising = Revising(revisions=[moved, untouched], learners=(owner,))

    revising.reviser().record_status(moved.id, RevisionStatusChange(status=COMPLETED))

    assert revising.revisions.find_revision(untouched.id) == untouched


def test_a_revisions_due_date_is_never_rewritten_by_a_status_change():
    owner = learner()
    stored = revision(learner_id=owner.id, due=date(2026, 8, 18))
    revising = Revising(revisions=[stored], learners=(owner,))

    detail = revising.reviser().record_status(stored.id, RevisionStatusChange(status=POSTPONED))

    assert detail.due_on == date(2026, 8, 18)


def test_a_revisions_reason_is_never_rewritten():
    owner = learner()
    stored = revision(learner_id=owner.id)
    revising = Revising(revisions=[stored], learners=(owner,))

    detail = revising.reviser().record_status(stored.id, RevisionStatusChange(status=COMPLETED))

    assert detail.recommendation_reason == "Because you finished it."


def test_scheduled_is_not_a_status_a_learner_may_ask_for():
    """The column holds it, but nothing collects the date it would need."""
    owner = learner()
    stored = revision(learner_id=owner.id)
    revising = Revising(revisions=[stored], learners=(owner,))

    with pytest.raises(UnknownRevisionStatusError):
        revising.reviser().record_status(stored.id, RevisionStatusChange(status="scheduled"))


def test_an_unknown_status_is_refused_and_writes_nothing():
    owner = learner()
    stored = revision(learner_id=owner.id)
    revising = Revising(revisions=[stored], learners=(owner,))

    with pytest.raises(UnknownRevisionStatusError):
        revising.reviser().record_status(stored.id, RevisionStatusChange(status="invented"))
    assert revising.revisions.find_revision(stored.id) == stored


def test_another_learners_revision_cannot_be_moved():
    owner = learner()
    revising = Revising(revisions=[revision(learner_id=uuid.uuid4())], learners=(owner,))
    stored = revising.revisions.revisions[0]

    with pytest.raises(RevisionNotFoundError):
        revising.reviser().record_status(stored.id, RevisionStatusChange(status=COMPLETED))


def test_setting_the_status_a_revision_already_holds_changes_nothing():
    owner = learner()
    stored = revision(learner_id=owner.id, status=DUE)
    revising = Revising(revisions=[stored], learners=(owner,))

    detail = revising.reviser().record_status(stored.id, RevisionStatusChange(status=DUE))

    assert detail.status == DUE
    assert detail.completed_at is None
