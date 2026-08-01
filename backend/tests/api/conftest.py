"""Fixtures for API tests that need curriculum data behind the endpoints.

The application is built through the real factory and the real use case; only
the repository is replaced. An API test therefore exercises routing, validation,
response mapping, and error mapping over the same code the running backend uses,
without needing PostgreSQL. The database counterpart is
tests/integration/test_curriculum_api.py.
"""

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
    SubjectRecord,
    TopicRecord,
    TopicRelationshipRecord,
)
from app.application.use_cases.read_curriculum import ReadCurriculum
from app.composition.app_factory import create_app
from app.presentation.api.dependencies import READ_CURRICULUM_PROVIDER
from tests.unit.fake_curriculum_repository import FakeCurriculumRepository

PUBLISHED_AT = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


class Curriculum:
    """A small curated curriculum, shaped like the bundled GATE CSE one."""

    def __init__(self) -> None:
        self.program = LearningProgramRecord(
            id=uuid.uuid4(),
            code="gate-cse",
            name="GATE Computer Science and Information Technology",
            description="The first curated LearnFlow learning program.",
        )
        self.version = CurriculumVersionRecord(
            id=uuid.uuid4(),
            learning_program_id=self.program.id,
            version_label="2027",
            status="active",
            source_reference="https://example.test/syllabus",
            published_at=PUBLISHED_AT,
        )
        self.subject = SubjectRecord(
            id=uuid.uuid4(),
            curriculum_version_id=self.version.id,
            code="databases",
            name="Databases",
            description=None,
            position=1,
        )
        self.parent_topic = TopicRecord(
            id=uuid.uuid4(),
            subject_id=self.subject.id,
            parent_topic_id=None,
            code=None,
            name="Relational model",
            description=None,
            position=1,
            is_trackable=False,
        )
        self.subtopic = TopicRecord(
            id=uuid.uuid4(),
            subject_id=self.subject.id,
            parent_topic_id=self.parent_topic.id,
            code=None,
            name="SQL",
            description="Queries and constraints.",
            position=1,
            is_trackable=True,
        )
        self.relationship = TopicRelationshipRecord(
            source_topic_id=self.parent_topic.id,
            target_topic_id=self.subtopic.id,
            relationship_type="prerequisite",
        )

    def repository(self) -> FakeCurriculumRepository:
        return FakeCurriculumRepository(
            programs=[self.program],
            versions=[self.version],
            subjects=[self.subject],
            topics=[self.parent_topic, self.subtopic],
            relationships=[self.relationship],
        )


@pytest.fixture
def curriculum() -> Curriculum:
    """The curriculum the curriculum-endpoint tests read."""
    return Curriculum()


def install_reader(app: FastAPI, build_reader: Callable[[], ReadCurriculum]) -> None:
    """Point the application's curriculum provider at `build_reader`."""

    @contextmanager
    def provide() -> Iterator[ReadCurriculum]:
        yield build_reader()

    setattr(app.state, READ_CURRICULUM_PROVIDER, provide)


@pytest.fixture
def curriculum_client(curriculum: Curriculum) -> Iterator[TestClient]:
    """A client whose curriculum endpoints serve the fixture curriculum."""
    app = create_app()
    install_reader(app, lambda: ReadCurriculum(curriculum.repository()))
    with TestClient(app) as client:
        yield client
