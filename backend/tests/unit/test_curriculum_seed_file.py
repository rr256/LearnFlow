"""Reading a curriculum seed file, and the shape of the bundled GATE CSE data.

The GATE assertions are deliberately structural -- subject codes, ordering, and
the nesting rule -- rather than a second copy of the syllabus text. Restating
the wording here would only test that the file was copied twice.
"""

import json
from datetime import UTC, datetime

import pytest

from app.application.dto.curriculum_seed import CurriculumSeed
from app.application.use_cases.seed_curriculum import SeedCurriculum
from scripts.curriculum_seed_file import (
    GATE_CSE_CURRICULUM_FILE,
    CurriculumSeedFileError,
    build_curriculum_seed,
    load_curriculum_seed,
)
from tests.unit.fake_curriculum_seed_repository import FakeCurriculumSeedRepository

MINIMAL = {
    "program_code": "gate-cse",
    "program_name": "GATE CSE",
    "version_label": "2026",
    "version_status": "active",
    "subjects": [{"code": "databases", "name": "Databases", "topics": [{"name": "ER-model"}]}],
}


@pytest.fixture(scope="module")
def gate_cse() -> CurriculumSeed:
    return load_curriculum_seed(GATE_CSE_CURRICULUM_FILE)


def test_bundled_gate_cse_file_loads(gate_cse):
    assert gate_cse.program_code == "gate-cse"
    assert gate_cse.version_label == "2026"
    assert gate_cse.version_status == "active"
    assert "gate2026.iitg.ac.in" in (gate_cse.source_reference or "")


def test_bundled_gate_cse_file_applies_and_is_idempotent(gate_cse):
    repository = FakeCurriculumSeedRepository()
    use_case = SeedCurriculum(repository, clock=lambda: datetime(2026, 7, 31, tzinfo=UTC))

    first = use_case(gate_cse)
    second = use_case(gate_cse)

    assert first.subjects.created == len(gate_cse.subjects)
    assert first.topics.created == len(repository.topics)
    assert second.changed is False
    assert len(repository.subjects) == len(gate_cse.subjects)


def test_bundled_gate_cse_subjects_are_the_official_sections_in_order(gate_cse):
    assert [subject.code for subject in gate_cse.subjects] == [
        "engineering-mathematics",
        "digital-logic",
        "computer-organization-and-architecture",
        "programming-and-data-structures",
        "algorithms",
        "theory-of-computation",
        "compiler-design",
        "operating-system",
        "databases",
        "computer-networks",
        "general-aptitude",
    ]


def test_bundled_gate_cse_every_subject_has_topics_and_a_source_description(gate_cse):
    for subject in gate_cse.subjects:
        assert subject.topics, f"{subject.code} has no topics"
        assert subject.description, f"{subject.code} has no verbatim source text"


def test_bundled_gate_cse_grouping_topics_are_not_directly_trackable(gate_cse):
    def check(topics):
        for topic in topics:
            assert topic.is_trackable is (not topic.topics), (
                f"{topic.name!r} should be trackable only when it has no subtopics"
            )
            check(topic.topics)

    for subject in gate_cse.subjects:
        check(subject.topics)


def test_bundled_gate_cse_declares_no_topic_relationships(gate_cse):
    # The official syllabus states no prerequisite order between topics, so the
    # seed asserts none. See the $comment block in the data file.
    assert gate_cse.topic_relationships == ()


def test_comment_keys_are_ignored():
    seed = build_curriculum_seed({**MINIMAL, "$comment": ["notes about the source"]})

    assert seed.program_code == "gate-cse"


def test_topic_defaults_to_trackable_with_no_code_or_description():
    seed = build_curriculum_seed(MINIMAL)
    topic = seed.subjects[0].topics[0]

    assert topic.is_trackable is True
    assert topic.code is None
    assert topic.description is None


def test_nested_topics_are_read_recursively():
    document = {
        **MINIMAL,
        "subjects": [
            {
                "code": "databases",
                "name": "Databases",
                "topics": [
                    {
                        "name": "Relational model",
                        "is_trackable": False,
                        "topics": [{"name": "SQL"}],
                    }
                ],
            }
        ],
    }

    seed = build_curriculum_seed(document)
    parent = seed.subjects[0].topics[0]

    assert parent.is_trackable is False
    assert [child.name for child in parent.topics] == ["SQL"]


def test_relationships_are_read_as_topic_paths():
    document = {
        **MINIMAL,
        "topic_relationships": [
            {
                "source": {"subject_code": "databases", "names": ["ER-model"]},
                "target": {"subject_code": "databases", "names": ["ER-model", "Keys"]},
                "relationship_type": "prerequisite",
            }
        ],
    }

    relationship = build_curriculum_seed(document).topic_relationships[0]

    assert relationship.source.names == ("ER-model",)
    assert relationship.target.names == ("ER-model", "Keys")
    assert relationship.relationship_type == "prerequisite"


def test_published_at_is_read_as_an_aware_timestamp():
    seed = build_curriculum_seed({**MINIMAL, "published_at": "2026-02-01T00:00:00+00:00"})

    assert seed.published_at == datetime(2026, 2, 1, tzinfo=UTC)


def test_naive_published_at_is_rejected():
    with pytest.raises(CurriculumSeedFileError, match="UTC offset"):
        build_curriculum_seed({**MINIMAL, "published_at": "2026-02-01T00:00:00"})


@pytest.mark.parametrize("field", ["program_code", "program_name", "version_label"])
def test_missing_required_field_is_reported_by_name(field):
    document = {key: value for key, value in MINIMAL.items() if key != field}

    with pytest.raises(CurriculumSeedFileError, match=field):
        build_curriculum_seed(document)


def test_missing_subjects_is_reported():
    document = {key: value for key, value in MINIMAL.items() if key != "subjects"}

    with pytest.raises(CurriculumSeedFileError, match="subjects is required"):
        build_curriculum_seed(document)


def test_field_of_the_wrong_type_names_its_location():
    document = {
        **MINIMAL,
        "subjects": [{"code": "databases", "name": "Databases", "topics": [{"name": 7}]}],
    }

    with pytest.raises(CurriculumSeedFileError, match=r"subjects\[0\]\.topics\[0\]\.name"):
        build_curriculum_seed(document)


def test_non_boolean_is_trackable_is_rejected():
    document = {
        **MINIMAL,
        "subjects": [
            {
                "code": "databases",
                "name": "Databases",
                "topics": [{"name": "ER-model", "is_trackable": "yes"}],
            }
        ],
    }

    with pytest.raises(CurriculumSeedFileError, match="is_trackable"):
        build_curriculum_seed(document)


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(CurriculumSeedFileError, match="Cannot read"):
        load_curriculum_seed(tmp_path / "absent.json")


def test_invalid_json_is_reported(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(CurriculumSeedFileError, match="not valid JSON"):
        load_curriculum_seed(path)


def test_top_level_array_is_rejected(tmp_path):
    path = tmp_path / "array.json"
    path.write_text(json.dumps([MINIMAL]), encoding="utf-8")

    with pytest.raises(CurriculumSeedFileError, match="JSON object"):
        load_curriculum_seed(path)
