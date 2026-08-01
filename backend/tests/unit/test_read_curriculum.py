"""The curriculum read use case, against a fake repository.

These cover the two rules the use case owns: the display order a learner sees,
and the assembly of a flat topic table back into nested subtopics. The database
counterpart lives in tests/integration/test_curriculum_api.py.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
    SubjectRecord,
    TopicRecord,
    TopicRelationshipRecord,
)
from app.application.use_cases.read_curriculum import (
    CurriculumVersionNotFoundError,
    LearningProgramNotFoundError,
    ReadCurriculum,
)
from tests.unit.fake_curriculum_repository import FakeCurriculumRepository

PUBLISHED_AT = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


def program(code: str = "gate-cse", name: str = "GATE CSE") -> LearningProgramRecord:
    return LearningProgramRecord(id=uuid.uuid4(), code=code, name=name, description=None)


def version(
    learning_program_id: uuid.UUID,
    *,
    status: str = "active",
    version_label: str = "2027",
) -> CurriculumVersionRecord:
    return CurriculumVersionRecord(
        id=uuid.uuid4(),
        learning_program_id=learning_program_id,
        version_label=version_label,
        status=status,
        source_reference="https://example.test/syllabus",
        published_at=PUBLISHED_AT,
    )


def subject(
    curriculum_version_id: uuid.UUID, code: str, *, position: int, name: str | None = None
) -> SubjectRecord:
    return SubjectRecord(
        id=uuid.uuid4(),
        curriculum_version_id=curriculum_version_id,
        code=code,
        name=name or code.title(),
        description=None,
        position=position,
    )


def topic(
    subject_id: uuid.UUID,
    name: str,
    *,
    position: int,
    parent_topic_id: uuid.UUID | None = None,
    is_trackable: bool = True,
) -> TopicRecord:
    return TopicRecord(
        id=uuid.uuid4(),
        subject_id=subject_id,
        parent_topic_id=parent_topic_id,
        code=None,
        name=name,
        description=None,
        position=position,
        is_trackable=is_trackable,
    )


# -- listing learning programs ---------------------------------------------


def test_listing_reports_each_program_with_its_active_curriculum_version():
    gate = program()
    active = version(gate.id)
    repository = FakeCurriculumRepository(programs=[gate], versions=[active])

    page = ReadCurriculum(repository).list_learning_programs(limit=25, offset=0)

    assert [summary.code for summary in page.programs] == ["gate-cse"]
    assert page.programs[0].active_curriculum_version is not None
    assert page.programs[0].active_curriculum_version.id == active.id
    assert page.programs[0].active_curriculum_version.published_at == PUBLISHED_AT


def test_program_without_an_active_version_reports_none_rather_than_failing():
    gate = program()
    repository = FakeCurriculumRepository(
        programs=[gate], versions=[version(gate.id, status="draft")]
    )

    page = ReadCurriculum(repository).list_learning_programs(limit=25, offset=0)

    assert page.programs[0].active_curriculum_version is None


def test_listing_reports_the_total_beyond_the_requested_window():
    programs = [program(code=f"program-{index}") for index in range(5)]
    repository = FakeCurriculumRepository(programs=programs)

    page = ReadCurriculum(repository).list_learning_programs(limit=2, offset=1)

    assert [summary.code for summary in page.programs] == ["program-1", "program-2"]
    assert page.total == 5
    assert (page.limit, page.offset) == (2, 1)


def test_listing_an_empty_store_returns_no_programs_and_a_zero_total():
    page = ReadCurriculum(FakeCurriculumRepository()).list_learning_programs(limit=25, offset=0)

    assert page.programs == ()
    assert page.total == 0


def test_offset_beyond_the_end_returns_an_empty_page_with_the_real_total():
    repository = FakeCurriculumRepository(programs=[program()])

    page = ReadCurriculum(repository).list_learning_programs(limit=25, offset=10)

    assert page.programs == ()
    assert page.total == 1


# -- reading one learning program ------------------------------------------


def test_reading_a_program_reports_its_active_curriculum_version():
    gate = program()
    active = version(gate.id)
    repository = FakeCurriculumRepository(
        programs=[gate], versions=[version(gate.id, status="retired", version_label="2026"), active]
    )

    summary = ReadCurriculum(repository).read_learning_program(gate.id)

    assert summary.code == "gate-cse"
    assert summary.active_curriculum_version is not None
    assert summary.active_curriculum_version.version_label == "2027"


def test_reading_an_unknown_program_names_the_identifier_that_was_not_found():
    missing = uuid.uuid4()

    with pytest.raises(LearningProgramNotFoundError) as raised:
        ReadCurriculum(FakeCurriculumRepository()).read_learning_program(missing)

    assert str(missing) in str(raised.value)


# -- reading a curriculum tree ---------------------------------------------


def test_tree_nests_subtopics_under_their_parent_topic():
    gate = program()
    active = version(gate.id)
    databases = subject(active.id, "databases", position=1)
    relational = topic(databases.id, "Relational model", position=1, is_trackable=False)
    sql = topic(databases.id, "SQL", position=2, parent_topic_id=relational.id)
    algebra = topic(databases.id, "Relational algebra", position=1, parent_topic_id=relational.id)
    repository = FakeCurriculumRepository(
        programs=[gate],
        versions=[active],
        subjects=[databases],
        topics=[sql, relational, algebra],
    )

    tree = ReadCurriculum(repository).read_curriculum_tree(active.id)

    root = tree.subjects[0].topics[0]
    assert root.name == "Relational model"
    assert root.is_trackable is False
    assert [child.name for child in root.subtopics] == ["Relational algebra", "SQL"]


def test_tree_orders_subjects_and_topics_by_position_not_by_store_order():
    gate = program()
    active = version(gate.id)
    second = subject(active.id, "operating-system", position=2)
    first = subject(active.id, "databases", position=1)
    later = topic(first.id, "Transactions", position=2)
    earlier = topic(first.id, "Relational model", position=1)
    repository = FakeCurriculumRepository(
        programs=[gate],
        versions=[active],
        subjects=[second, first],
        topics=[later, earlier],
    )

    tree = ReadCurriculum(repository).read_curriculum_tree(active.id)

    assert [node.code for node in tree.subjects] == ["databases", "operating-system"]
    assert [node.name for node in tree.subjects[0].topics] == [
        "Relational model",
        "Transactions",
    ]


def test_tree_reports_topic_relationships_beside_the_hierarchy():
    gate = program()
    active = version(gate.id)
    operating_system = subject(active.id, "operating-system", position=1)
    calls = topic(operating_system.id, "System calls", position=1)
    deadlock = topic(operating_system.id, "Deadlock", position=2)
    repository = FakeCurriculumRepository(
        programs=[gate],
        versions=[active],
        subjects=[operating_system],
        topics=[calls, deadlock],
        relationships=[
            TopicRelationshipRecord(
                source_topic_id=calls.id,
                target_topic_id=deadlock.id,
                relationship_type="prerequisite",
            )
        ],
    )

    tree = ReadCurriculum(repository).read_curriculum_tree(active.id)

    assert len(tree.topic_relationships) == 1
    edge = tree.topic_relationships[0]
    assert (edge.source_topic_id, edge.target_topic_id) == (calls.id, deadlock.id)
    assert edge.relationship_type == "prerequisite"


def test_topic_whose_parent_belongs_to_another_version_is_kept_as_a_root():
    """A topic must never vanish because its parent is outside the requested tree."""
    gate = program()
    active = version(gate.id)
    databases = subject(active.id, "databases", position=1)
    orphan = topic(databases.id, "SQL", position=1, parent_topic_id=uuid.uuid4())
    repository = FakeCurriculumRepository(
        programs=[gate], versions=[active], subjects=[databases], topics=[orphan]
    )

    tree = ReadCurriculum(repository).read_curriculum_tree(active.id)

    assert [node.name for node in tree.subjects[0].topics] == ["SQL"]


def test_version_with_no_subjects_returns_an_empty_tree_rather_than_an_error():
    gate = program()
    active = version(gate.id)
    repository = FakeCurriculumRepository(programs=[gate], versions=[active])

    tree = ReadCurriculum(repository).read_curriculum_tree(active.id)

    assert tree.curriculum_version.id == active.id
    assert tree.subjects == ()
    assert tree.topic_relationships == ()


def test_tree_of_a_draft_version_is_readable_and_reports_its_status():
    """A version is addressable before it is published; the status says which it is."""
    gate = program()
    draft = version(gate.id, status="draft", version_label="2028")
    repository = FakeCurriculumRepository(programs=[gate], versions=[draft])

    tree = ReadCurriculum(repository).read_curriculum_tree(draft.id)

    assert tree.curriculum_version.status == "draft"


def test_reading_an_unknown_curriculum_version_names_the_identifier_that_was_not_found():
    missing = uuid.uuid4()

    with pytest.raises(CurriculumVersionNotFoundError) as raised:
        ReadCurriculum(FakeCurriculumRepository()).read_curriculum_tree(missing)

    assert str(missing) in str(raised.value)
