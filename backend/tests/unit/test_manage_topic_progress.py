"""Unit tests for the topic-progress use case (PRG-002, PRG-004).

They run against fakes, so they exercise the rules -- which stages are accepted,
what a grouping topic may hold, what absence means, and when the local learner is
undefined -- without a database.
"""

import uuid

import pytest

from app.application.dto.topic_progress import TopicStageChange
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_topic_progress import (
    LEARNING_STAGES,
    LearnerNotSetUpError,
    ManageTopicProgress,
    TopicNotFoundError,
    TopicNotTrackableError,
    TopicProgressIntegrityError,
    UnknownLearningStageError,
)
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_topic_progress_repository import (
    FakeTopicProgressRepository,
    progress,
    topic,
)


def build(
    *learners,
    topics=(),
    records=(),
) -> tuple[ManageTopicProgress, FakeLearnerRepository, FakeTopicProgressRepository]:
    learner_repository = FakeLearnerRepository(tuple(learners))
    progress_repository = FakeTopicProgressRepository(tuple(topics), tuple(records))
    use_case = ManageTopicProgress(learners=learner_repository, progress=progress_repository)
    return use_case, learner_repository, progress_repository


# -- PRG-004: recording a stage --------------------------------------------


def test_recording_a_stage_creates_the_record_on_the_learners_own_action():
    asha = learner()
    trackable = topic()
    use_case, _, records = build(asha, topics=(trackable,))

    detail = use_case.record_stage(trackable.id, TopicStageChange("building_foundation"))

    assert detail.learning_stage == "building_foundation"
    assert detail.topic.id == trackable.id
    assert len(records.records) == 1


def test_a_recorded_stage_is_attributed_to_the_learner():
    """Nothing derives a stage yet, but the source is stored from the start so a
    later derived writer cannot overwrite a learner's own answer unknowingly."""
    asha = learner()
    trackable = topic()
    use_case, _, _ = build(asha, topics=(trackable,))

    detail = use_case.record_stage(trackable.id, TopicStageChange("practice_ready"))

    assert detail.stage_source == "learner"


@pytest.mark.parametrize("stage", LEARNING_STAGES)
def test_every_approved_stage_is_accepted(stage):
    asha = learner()
    trackable = topic()
    use_case, _, _ = build(asha, topics=(trackable,))

    assert use_case.record_stage(trackable.id, TopicStageChange(stage)).learning_stage == stage


def test_updating_a_stage_rewrites_the_existing_record_rather_than_adding_one():
    asha = learner()
    trackable = topic()
    existing = progress(learner_id=asha.id, topic_id=trackable.id, learning_stage="not_explored")
    use_case, _, records = build(asha, topics=(trackable,), records=(existing,))

    detail = use_case.record_stage(trackable.id, TopicStageChange("developing_confidence"))

    assert detail.id == existing.id
    assert len(records.records) == 1
    assert records.records[0].learning_stage == "developing_confidence"


def test_a_learner_may_move_back_to_an_earlier_stage():
    """The five stages guide the next action; they are not a score that only
    rises. Noticing that a topic needs more work is worth recording."""
    asha = learner()
    trackable = topic()
    existing = progress(
        learner_id=asha.id, topic_id=trackable.id, learning_stage="strong_understanding"
    )
    use_case, _, _ = build(asha, topics=(trackable,), records=(existing,))

    detail = use_case.record_stage(trackable.id, TopicStageChange("building_foundation"))

    assert detail.learning_stage == "building_foundation"


def test_resetting_to_not_explored_stores_a_record_rather_than_removing_one():
    """There is deliberately no clear. A learner who resets a stage on purpose
    stays distinguishable from a topic never touched."""
    asha = learner()
    trackable = topic()
    existing = progress(learner_id=asha.id, topic_id=trackable.id, learning_stage="practice_ready")
    use_case, _, records = build(asha, topics=(trackable,), records=(existing,))

    detail = use_case.record_stage(trackable.id, TopicStageChange("not_explored"))

    assert detail.learning_stage == "not_explored"
    assert len(records.records) == 1


def test_recording_the_stage_a_topic_already_holds_writes_nothing():
    """A repeated form submission must not fail on its second attempt."""
    asha = learner()
    trackable = topic()
    existing = progress(learner_id=asha.id, topic_id=trackable.id, learning_stage="practice_ready")
    use_case, _, records = build(asha, topics=(trackable,), records=(existing,))

    detail = use_case.record_stage(trackable.id, TopicStageChange("practice_ready"))

    assert detail.learning_stage == "practice_ready"
    assert records.records == [existing]


def test_an_unknown_stage_is_refused_and_names_the_accepted_values():
    asha = learner()
    trackable = topic()
    use_case, _, records = build(asha, topics=(trackable,))

    with pytest.raises(UnknownLearningStageError) as raised:
        use_case.record_stage(trackable.id, TopicStageChange("mastered"))

    assert "practice_ready" in str(raised.value)
    assert records.records == []


def test_a_grouping_topic_cannot_hold_a_stage_of_its_own():
    """`is_trackable` says whether progress can be recorded directly. A topic
    that only groups subtopics cannot, and no database constraint says so."""
    asha = learner()
    grouping = topic(name="Operating Systems", is_trackable=False)
    use_case, _, records = build(asha, topics=(grouping,))

    with pytest.raises(TopicNotTrackableError) as raised:
        use_case.record_stage(grouping.id, TopicStageChange("practice_ready"))

    assert "Operating Systems" in str(raised.value)
    assert records.records == []


def test_recording_against_an_unstored_topic_is_refused():
    use_case, _, _ = build(learner())

    with pytest.raises(TopicNotFoundError):
        use_case.record_stage(uuid.uuid4(), TopicStageChange("practice_ready"))


def test_recording_before_setup_has_created_a_learner_is_refused():
    """There is nobody to own the record, and a write must not invent a learner."""
    trackable = topic()
    use_case, learners, records = build(topics=(trackable,))

    with pytest.raises(LearnerNotSetUpError):
        use_case.record_stage(trackable.id, TopicStageChange("practice_ready"))

    assert learners.learners == []
    assert records.records == []


def test_recording_refuses_when_more_than_one_learner_is_stored():
    """Choosing one arbitrarily would attach a stage to somebody else's record."""
    trackable = topic()
    use_case, _, _ = build(learner(), learner(), topics=(trackable,))

    with pytest.raises(AmbiguousLocalLearnerError):
        use_case.record_stage(trackable.id, TopicStageChange("practice_ready"))


def test_an_unknown_stage_is_refused_before_the_topic_is_looked_up():
    """The cheapest rejection first, and the one whose message needs no lookup."""
    use_case, _, _ = build(learner())

    with pytest.raises(UnknownLearningStageError):
        use_case.record_stage(uuid.uuid4(), TopicStageChange("mastered"))


# -- PRG-002: listing recorded progress ------------------------------------


def test_listing_before_setup_has_created_a_learner_is_an_empty_page():
    use_case, _, _ = build()

    page = use_case.list_topic_progress(curriculum_version_id=None, limit=25, offset=0)

    assert page.records == ()
    assert page.total == 0


def test_listing_reports_only_topics_the_learner_has_recorded_something_against():
    """Untouched topics are absent rather than reported as `not_explored`. The
    curriculum is where every topic is listed; a client joins the two."""
    asha = learner()
    recorded, untouched = topic(name="CPU scheduling"), topic(name="Deadlock")
    record = progress(learner_id=asha.id, topic_id=recorded.id)
    use_case, _, _ = build(asha, topics=(recorded, untouched), records=(record,))

    page = use_case.list_topic_progress(curriculum_version_id=None, limit=25, offset=0)

    assert [entry.topic.name for entry in page.records] == ["CPU scheduling"]


def test_listing_names_the_topic_behind_every_record():
    asha = learner()
    trackable = topic(name="Process synchronisation", code="os-3")
    record = progress(
        learner_id=asha.id, topic_id=trackable.id, learning_stage="developing_confidence"
    )
    use_case, _, _ = build(asha, topics=(trackable,), records=(record,))

    page = use_case.list_topic_progress(curriculum_version_id=None, limit=25, offset=0)

    entry = page.records[0]
    assert entry.topic.name == "Process synchronisation"
    assert entry.topic.code == "os-3"
    assert entry.topic.curriculum_version_id == trackable.curriculum_version_id
    assert entry.learning_stage == "developing_confidence"


def test_listing_restricts_to_one_curriculum_version_when_asked():
    asha = learner()
    version = uuid.uuid4()
    mine = topic(name="CPU scheduling", curriculum_version_id=version)
    other = topic(name="Normalisation")
    use_case, _, _ = build(
        asha,
        topics=(mine, other),
        records=(
            progress(learner_id=asha.id, topic_id=mine.id),
            progress(learner_id=asha.id, topic_id=other.id),
        ),
    )

    page = use_case.list_topic_progress(curriculum_version_id=version, limit=25, offset=0)

    assert [entry.topic.name for entry in page.records] == ["CPU scheduling"]
    assert page.total == 1


def test_an_unstored_curriculum_version_matches_nothing_rather_than_failing():
    """A filter matching nothing is an empty result, not a missing record."""
    asha = learner()
    trackable = topic()
    use_case, _, _ = build(
        asha,
        topics=(trackable,),
        records=(progress(learner_id=asha.id, topic_id=trackable.id),),
    )

    page = use_case.list_topic_progress(curriculum_version_id=uuid.uuid4(), limit=25, offset=0)

    assert page.records == ()
    assert page.total == 0


def test_listing_reports_the_window_and_the_total_it_was_taken_from():
    """A client cannot otherwise tell a complete collection from a truncated one."""
    asha = learner()
    topics = tuple(topic(name=f"Topic {index}") for index in range(3))
    use_case, _, _ = build(
        asha,
        topics=topics,
        records=tuple(progress(learner_id=asha.id, topic_id=entry.id) for entry in topics),
    )

    page = use_case.list_topic_progress(curriculum_version_id=None, limit=2, offset=0)

    assert len(page.records) == 2
    assert (page.total, page.limit, page.offset) == (3, 2, 0)


def test_listing_refuses_when_more_than_one_learner_is_stored():
    use_case, _, _ = build(learner(), learner())

    with pytest.raises(AmbiguousLocalLearnerError):
        use_case.list_topic_progress(curriculum_version_id=None, limit=25, offset=0)


def test_a_record_whose_topic_is_gone_is_reported_rather_than_papered_over():
    """A foreign key makes this unreachable through the API. A hand-edited
    database should surface as a reported failure, not a nameless record."""
    asha = learner()
    use_case, _, _ = build(asha, records=(progress(learner_id=asha.id, topic_id=uuid.uuid4()),))

    with pytest.raises(TopicProgressIntegrityError):
        use_case.list_topic_progress(curriculum_version_id=None, limit=25, offset=0)
