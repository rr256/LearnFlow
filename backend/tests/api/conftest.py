"""Fixtures for API tests that need data behind the endpoints.

The application is built through the real factory and the real use cases; only
the repositories are replaced. An API test therefore exercises routing,
validation, response mapping, and error mapping over the same code the running
backend uses, without needing PostgreSQL. The database counterparts are
tests/integration/test_curriculum_api.py and
tests/integration/test_learner_onboarding_api.py.

The onboarding stores are defined in `onboarding_fixtures.py`; the two fixtures
at the foot of this module are what a test asks for.
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
from app.application.use_cases.manage_study_plans import ManageStudyPlans
from app.application.use_cases.manage_topic_progress import ManageTopicProgress
from app.application.use_cases.read_curriculum import ReadCurriculum
from app.composition.app_factory import create_app
from app.presentation.api.dependencies import (
    READ_CURRICULUM_PROVIDER,
    STUDY_PLANS_PROVIDER,
    TOPIC_PROGRESS_PROVIDER,
)
from tests.api.onboarding_fixtures import Onboarding, install_onboarding
from tests.unit.fake_curriculum_repository import FakeCurriculumRepository
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_topic_progress_repository import FakeTopicProgressRepository, topic
from tests.unit.planning_fixtures import Planning

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


@pytest.fixture
def onboarding() -> Onboarding:
    """The learner, goal, and schedule stores the onboarding endpoints share."""
    return Onboarding()


@pytest.fixture
def onboarding_client(onboarding: Onboarding) -> Iterator[TestClient]:
    """A client whose learner, goal, and schedule endpoints share one set of stores.

    They are shared deliberately: a test can create a profile over LRN-002 and
    then set a goal over GOAL-001, which is the sequence the setup screen
    performs.
    """
    app = create_app()
    install_onboarding(app, onboarding)
    with TestClient(app) as client:
        yield client


class Progress:
    """A learner, one trackable topic, and one grouping topic beside it.

    The grouping topic is what the "a heading cannot hold a stage" rejection is
    tested against, and it is the shape the curated GATE CSE curriculum actually
    has: a parent topic that only groups subtopics.
    """

    def __init__(self) -> None:
        self.learner = learner()
        self.curriculum_version_id = uuid.uuid4()
        self.subject_id = uuid.uuid4()
        self.trackable = topic(
            name="CPU scheduling",
            subject_id=self.subject_id,
            curriculum_version_id=self.curriculum_version_id,
        )
        self.grouping = topic(
            name="Operating Systems",
            is_trackable=False,
            subject_id=self.subject_id,
            curriculum_version_id=self.curriculum_version_id,
        )
        self.learners = FakeLearnerRepository((self.learner,))
        self.progress = FakeTopicProgressRepository((self.trackable, self.grouping))


@pytest.fixture
def progress() -> Progress:
    """The learner and topics the progress-endpoint tests read and write."""
    return Progress()


@pytest.fixture
def progress_client(progress: Progress) -> Iterator[TestClient]:
    """A client whose progress endpoints share one set of stores.

    Shared across requests deliberately: a test can record a stage over PRG-004
    and read it back over PRG-002, which is the sequence the curriculum screen
    performs.
    """
    app = create_app()

    @contextmanager
    def provide() -> Iterator[ManageTopicProgress]:
        yield ManageTopicProgress(learners=progress.learners, progress=progress.progress)

    setattr(app.state, TOPIC_PROGRESS_PROVIDER, provide)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def planning() -> Planning:
    """The learner, goal, curriculum, and week the plan endpoints work from.

    The same fixture the use-case tests use, so a rule proved against one cannot
    quietly differ in the other. The learner can study two hours on the Thursday
    the fixed clock reports, so a generated week has something in it.
    """
    return Planning(availability={"thursday": 120})


@pytest.fixture
def planning_client(planning: Planning) -> Iterator[TestClient]:
    """A client whose plan endpoints share one set of stores.

    Shared across requests deliberately: a test can generate a plan over PLN-001
    and then read it back over PLN-002 and PLN-003, which is the sequence the plan
    screen performs.
    """
    app = create_app()

    @contextmanager
    def provide() -> Iterator[ManageStudyPlans]:
        yield planning.planner()

    setattr(app.state, STUDY_PLANS_PROVIDER, provide)
    with TestClient(app) as client:
        yield client
