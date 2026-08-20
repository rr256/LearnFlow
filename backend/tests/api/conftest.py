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
from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.dto.resource import ResourceTopic
from app.application.dto.revision import RevisionTopic
from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
    SubjectRecord,
    TopicRecord,
    TopicRelationshipRecord,
)
from app.application.use_cases.answer_topic_question import AnswerTopicQuestion
from app.application.use_cases.manage_checkpoint_quizzes import ManageCheckpointQuizzes
from app.application.use_cases.manage_practice_questions import ManagePracticeQuestions
from app.application.use_cases.manage_resource_notes import ManageResourceNotes
from app.application.use_cases.manage_resources import ManageResources
from app.application.use_cases.manage_revisions import ManageRevisions
from app.application.use_cases.manage_study_plans import ManageStudyPlans
from app.application.use_cases.manage_topic_progress import ManageTopicProgress
from app.application.use_cases.read_curriculum import ReadCurriculum
from app.application.use_cases.retrieve_topic_notes import RetrieveTopicNotes
from app.composition.app_factory import create_app
from app.presentation.api.dependencies import (
    CHECKPOINT_QUIZZES_PROVIDER,
    PRACTICE_QUESTIONS_PROVIDER,
    READ_CURRICULUM_PROVIDER,
    RESOURCE_NOTES_PROVIDER,
    RESOURCES_PROVIDER,
    REVISIONS_PROVIDER,
    STUDY_ANSWER_PROVIDER,
    STUDY_PLANS_PROVIDER,
    TOPIC_NOTE_RETRIEVAL_PROVIDER,
    TOPIC_PROGRESS_PROVIDER,
)
from tests.api.onboarding_fixtures import Onboarding, install_onboarding
from tests.unit.fake_ai_provider import FakeAIProvider
from tests.unit.fake_curriculum_repository import FakeCurriculumRepository
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_note_search_repository import FakeNoteSearchRepository
from tests.unit.fake_resource_note_repository import FakeResourceNoteRepository
from tests.unit.fake_resource_repository import FakeResourceRepository
from tests.unit.fake_revision_repository import FakeRevisionRepository
from tests.unit.fake_topic_progress_repository import FakeTopicProgressRepository, topic
from tests.unit.planning_fixtures import FixedClock, Planning
from tests.unit.practice_fixtures import Practising

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


class Revising:
    """A learner, the work they finished, and somewhere to put revisions.

    The fixed instant is the one the planning fixtures use, so a due date asserted
    in an API test is the same date the use-case tests assert.
    """

    def __init__(self) -> None:
        self.learner = learner()
        self.learners = FakeLearnerRepository((self.learner,))
        self.topic_id = uuid.uuid4()
        self.revisions = FakeRevisionRepository(
            topics=[
                RevisionTopic(
                    id=self.topic_id,
                    code=None,
                    name="CPU scheduling",
                    subject_id=uuid.uuid4(),
                    subject_name="Operating Systems",
                )
            ],
            completed_work=[(self.topic_id, uuid.uuid4(), date(2026, 8, 13))],
        )
        self.clock = FixedClock(datetime(2026, 8, 20, 9, 0, tzinfo=UTC))

    def reviser(self) -> ManageRevisions:
        return ManageRevisions(learners=self.learners, revisions=self.revisions, clock=self.clock)


@pytest.fixture
def revising() -> Revising:
    """The learner and finished work the revision endpoints work from."""
    return Revising()


@pytest.fixture
def revision_client(revising: Revising) -> Iterator[TestClient]:
    """A client whose revision endpoints share one set of stores.

    Shared across requests deliberately: a test can schedule over REV-004, list
    over REV-001, and move one over REV-003, which is the sequence the revisions
    screen performs.
    """
    app = create_app()

    @contextmanager
    def provide() -> Iterator[ManageRevisions]:
        yield revising.reviser()

    setattr(app.state, REVISIONS_PROVIDER, provide)
    with TestClient(app) as client:
        yield client


class Cataloguing:
    """A learner, a topic to link material to, and somewhere to put resources.

    The grouping topic is beside the trackable one deliberately: a resource may
    cover either, which is where RES-001 differs from PRG-004.
    """

    def __init__(self) -> None:
        self.learner = learner()
        self.learners = FakeLearnerRepository((self.learner,))
        self.subject_id = uuid.uuid4()
        self.topic = ResourceTopic(
            id=uuid.uuid4(),
            code=None,
            name="CPU scheduling",
            subject_id=self.subject_id,
            subject_name="Operating Systems",
        )
        self.heading = ResourceTopic(
            id=uuid.uuid4(),
            code=None,
            name="Operating Systems",
            subject_id=self.subject_id,
            subject_name="Operating Systems",
        )
        self.resources = FakeResourceRepository(topics=[self.topic, self.heading])
        self.notes = FakeResourceNoteRepository()

    def cataloguer(self) -> ManageResources:
        return ManageResources(learners=self.learners, resources=self.resources)

    def note_keeper(self) -> ManageResourceNotes:
        return ManageResourceNotes(
            learners=self.learners, resources=self.resources, notes=self.notes
        )

    def retriever(self) -> RetrieveTopicNotes:
        """Topic-note retrieval over the same material, notes, and links.

        Built from the *same* stores the catalogue writes through, so a test can
        register a resource, write a note against it, and then search for it --
        the sequence the screens perform.
        """
        return RetrieveTopicNotes(
            learners=self.learners,
            resources=self.resources,
            notes=FakeNoteSearchRepository(
                resources=self.resources.resources,
                notes=self.notes.notes,
                topics=self.resources.topics,
                links=dict(self.resources.links),
            ),
        )


@pytest.fixture
def cataloguing() -> Cataloguing:
    """The learner and topics the resource endpoints work from."""
    return Cataloguing()


@pytest.fixture
def resource_client(cataloguing: Cataloguing) -> Iterator[TestClient]:
    """A client whose resource endpoints share one set of stores.

    Shared across requests deliberately: a test can register over RES-001, list
    over RES-002, change one over RES-004, and keep a note against it over
    RES-009, which is the sequence the catalogue screen performs.

    The note use case is installed over the **same** resource store, because a
    note is reached through its resource and ownership is the resource's.
    """
    app = create_app()

    @contextmanager
    def provide() -> Iterator[ManageResources]:
        yield cataloguing.cataloguer()

    @contextmanager
    def provide_notes() -> Iterator[ManageResourceNotes]:
        yield cataloguing.note_keeper()

    @contextmanager
    def provide_retrieval() -> Iterator[RetrieveTopicNotes]:
        # Built per request, so a search sees whatever the test wrote before it.
        yield cataloguing.retriever()

    setattr(app.state, RESOURCES_PROVIDER, provide)
    setattr(app.state, RESOURCE_NOTES_PROVIDER, provide_notes)
    setattr(app.state, TOPIC_NOTE_RETRIEVAL_PROVIDER, provide_retrieval)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def study_mentor() -> FakeAIProvider:
    """The AI provider the mentor endpoint is bound to.

    **A fake, always.** No API test reaches Ollama, or any network: a test that
    needed one running would fail on a machine that had not installed it, and
    would make the suite's answer depend on a model's. A test asks this what it
    was sent, and asserts it was not asked at all where no passage was found.
    """
    return FakeAIProvider()


@pytest.fixture
def mentor_client(cataloguing: Cataloguing, study_mentor: FakeAIProvider) -> Iterator[TestClient]:
    """A client whose mentor endpoint reads the same catalogue the notes live in.

    The resource and note endpoints are installed beside it so one test can
    register material over RES-001, write a note over RES-009, and then ask a
    question over MNT-001 — the sequence a learner actually performs.
    """
    app = create_app()

    @contextmanager
    def provide() -> Iterator[ManageResources]:
        yield cataloguing.cataloguer()

    @contextmanager
    def provide_notes() -> Iterator[ManageResourceNotes]:
        yield cataloguing.note_keeper()

    @contextmanager
    def provide_mentor() -> Iterator[AnswerTopicQuestion]:
        # Built per request, so a question sees whatever the test wrote before it.
        yield AnswerTopicQuestion(retrieval=cataloguing.retriever(), provider=study_mentor)

    setattr(app.state, RESOURCES_PROVIDER, provide)
    setattr(app.state, RESOURCE_NOTES_PROVIDER, provide_notes)
    setattr(app.state, STUDY_ANSWER_PROVIDER, provide_mentor)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def practising() -> Practising:
    """The learner and topics the checkpoint-practice endpoints work from."""
    return Practising()


@pytest.fixture
def practice_client(practising: Practising) -> Iterator[TestClient]:
    """A client whose practice endpoints share one set of stores.

    Both use cases are installed over the same store deliberately: a test can
    write a question over QZ-008, assemble a quiz from it over QZ-001, attempt it
    over QZ-003, and submit it over QZ-005, which is the sequence the practice
    screens perform.
    """
    app = create_app()

    @contextmanager
    def provide_questions() -> Iterator[ManagePracticeQuestions]:
        yield practising.author()

    @contextmanager
    def provide_quizzes() -> Iterator[ManageCheckpointQuizzes]:
        yield practising.quizzes()

    setattr(app.state, PRACTICE_QUESTIONS_PROVIDER, provide_questions)
    setattr(app.state, CHECKPOINT_QUIZZES_PROVIDER, provide_quizzes)
    with TestClient(app) as client:
        yield client
