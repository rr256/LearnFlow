"""Checkpoint-assessment constraints against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260818_01``: it runs against an empty database, its keys, constraints, and
indexes are verified, and the downgrade path is exercised by the fixture
teardown.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one that
is, until real learner data depends on it.

ADR-033's departures from docs/database/schema.md are asserted directly: the
columns that are **not** created because nothing maintains them, and the one
column that **is** created beyond the approved shape.
"""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.persistence.assessment import (
    ATTEMPT_STATUSES,
    QUESTION_STATUSES,
    QUESTION_TYPES,
    QUIZ_STATUSES,
    SOURCE_TYPES,
    CheckpointQuiz,
    CheckpointQuizTopic,
    Question,
    QuestionTopicLink,
    QuizAttempt,
    QuizAttemptAnswer,
    QuizQuestion,
)
from app.infrastructure.persistence.curriculum import (
    CurriculumVersion,
    LearningProgram,
    Subject,
    Topic,
)
from app.infrastructure.persistence.learner_planning import Learner

ASSESSMENT_TABLES = (
    "checkpoint_quizzes",
    "checkpoint_quiz_topics",
    "questions",
    "question_topic_links",
    "quiz_questions",
    "quiz_attempts",
    "quiz_attempt_answers",
)


class Fixture:
    """A learner and a topic for a question and a quiz to belong to and cover."""

    def __init__(self, learner: Learner, topic: Topic, heading: Topic) -> None:
        self.learner = learner
        self.topic = topic
        self.heading = heading


def make_fixture(session: Session) -> Fixture:
    """Store the reference data and learner an assessment row points at."""
    program = LearningProgram(code=f"gate-{uuid.uuid4().hex[:8]}", name="GATE Computer Science")
    session.add(program)
    session.flush()
    version = CurriculumVersion(
        learning_program_id=program.id, version_label="2027", status="active"
    )
    session.add(version)
    session.flush()
    subject = Subject(
        curriculum_version_id=version.id, code="operating-systems", name="OS", position=1
    )
    session.add(subject)
    session.flush()
    heading = Topic(subject_id=subject.id, name="Operating Systems", position=1, is_trackable=False)
    session.add(heading)
    session.flush()
    topic = Topic(
        subject_id=subject.id,
        parent_topic_id=heading.id,
        name="CPU scheduling",
        position=1,
        is_trackable=True,
    )
    session.add(topic)
    learner = Learner(display_name="Local learner", timezone="Asia/Kolkata")
    session.add(learner)
    session.commit()
    return Fixture(learner, topic, heading)


def make_question(fixture: Fixture, **overrides) -> Question:
    """A question of the fixture's learner, with one field varied at a time."""
    values = {
        "author_learner_id": fixture.learner.id,
        "question_type": "multiple_choice",
        "source_type": "curated",
        "prompt": "How many bits address 1 KiB?",
        "options": [{"key": "a", "text": "8"}, {"key": "b", "text": "10"}],
        "expected_answer": {"option_key": "b"},
        "explanation": "1 KiB is 2^10 bytes.",
        "status": "ready",
    }
    values.update(overrides)
    return Question(**values)


def make_quiz(fixture: Fixture, **overrides) -> CheckpointQuiz:
    """A quiz of the fixture's learner."""
    values = {
        "learner_id": fixture.learner.id,
        "title": "Practice: CPU scheduling",
        "source_type": "curated",
        "status": "ready",
    }
    values.update(overrides)
    return CheckpointQuiz(**values)


def make_attempt(fixture: Fixture, quiz: CheckpointQuiz, **overrides) -> QuizAttempt:
    """An attempt at the given quiz."""
    values = {
        "learner_id": fixture.learner.id,
        "checkpoint_quiz_id": quiz.id,
        "status": "in_progress",
    }
    values.update(overrides)
    return QuizAttempt(**values)


@pytest.fixture
def fixture(session: Session) -> Fixture:
    return make_fixture(session)


# -- shape --------------------------------------------------------------------


def test_upgrade_creates_every_assessment_table(migrated_database: Engine):
    tables = set(inspect(migrated_database).get_table_names())

    assert set(ASSESSMENT_TABLES) <= tables


def test_no_mark_scheme_columns_are_created(migrated_database: Engine):
    """A result states per-question outcomes and no total at all (ADR-033)."""
    inspector = inspect(migrated_database)
    attempt_columns = {column["name"] for column in inspector.get_columns("quiz_attempts")}
    quiz_question_columns = {column["name"] for column in inspector.get_columns("quiz_questions")}
    answer_columns = {column["name"] for column in inspector.get_columns("quiz_attempt_answers")}

    assert "score" not in attempt_columns
    assert "max_score" not in attempt_columns
    assert "max_marks" not in quiz_question_columns
    assert "awarded_marks" not in answer_columns


def test_no_attempt_duration_is_created(migrated_database: Engine):
    """`started_at` and `submitted_at` already bound an attempt."""
    columns = {column["name"] for column in inspect(migrated_database).get_columns("quiz_attempts")}

    assert "duration_seconds" not in columns


def test_no_question_difficulty_is_created(migrated_database: Engine):
    """No controlled vocabulary decides one, and it would rank two questions."""
    columns = {column["name"] for column in inspect(migrated_database).get_columns("questions")}

    assert "difficulty" not in columns


def test_no_per_answer_feedback_is_created(migrated_database: Engine):
    """A question is never edited, so its explanation cannot drift."""
    columns = {
        column["name"] for column in inspect(migrated_database).get_columns("quiz_attempt_answers")
    }

    assert "feedback" not in columns


def test_a_question_records_who_wrote_it(migrated_database: Engine):
    """Added beyond the approved shape, mirroring `resources.owner_learner_id`."""
    columns = {column["name"] for column in inspect(migrated_database).get_columns("questions")}

    assert "author_learner_id" in columns


def test_a_quiz_has_no_topic_column(migrated_database: Engine):
    """ADR-008: `checkpoint_quiz_topics` is the only quiz-to-topic link."""
    columns = {
        column["name"] for column in inspect(migrated_database).get_columns("checkpoint_quizzes")
    }

    assert "topic_id" not in columns


def test_both_required_indexes_exist(migrated_database: Engine):
    """The two docs/database/schema.md lists under Required Indexes for this area."""
    inspector = inspect(migrated_database)
    quiz_topic_indexes = {
        index["name"] for index in inspector.get_indexes("checkpoint_quiz_topics")
    }
    attempt_indexes = {index["name"] for index in inspector.get_indexes("quiz_attempts")}

    assert "ix_checkpoint_quiz_topics_topic_id_checkpoint_quiz_id" in quiz_topic_indexes
    assert "ix_quiz_attempts_learner_id_checkpoint_quiz_id_created_at" in attempt_indexes


def test_the_lookup_indexes_this_build_needs_exist(migrated_database: Engine):
    inspector = inspect(migrated_database)
    question_indexes = {index["name"] for index in inspector.get_indexes("questions")}
    link_indexes = {index["name"] for index in inspector.get_indexes("question_topic_links")}

    assert "ix_questions_author_learner_id_status" in question_indexes
    assert "ix_question_topic_links_topic_id_question_id" in link_indexes


def test_downgrade_removes_every_assessment_table(
    migrated_database: Engine, alembic_config: Config
):
    """Alembic keeps its own version table, so the assertion is on ours."""
    command.downgrade(alembic_config, "base")

    assert not set(inspect(migrated_database).get_table_names()) & set(ASSESSMENT_TABLES)

    command.upgrade(alembic_config, "head")


# -- permitted values ---------------------------------------------------------


@pytest.mark.parametrize("question_type", QUESTION_TYPES)
def test_every_documented_question_type_is_permitted(
    session: Session, fixture: Fixture, question_type: str
):
    """All four are carried although only `multiple_choice` is written."""
    session.add(make_question(fixture, question_type=question_type))
    session.commit()


@pytest.mark.parametrize("source_type", SOURCE_TYPES)
def test_every_documented_source_type_is_permitted(
    session: Session, fixture: Fixture, source_type: str
):
    session.add(make_question(fixture, source_type=source_type))
    session.commit()


@pytest.mark.parametrize("status", QUESTION_STATUSES)
def test_every_documented_question_status_is_permitted(
    session: Session, fixture: Fixture, status: str
):
    session.add(make_question(fixture, status=status))
    session.commit()


@pytest.mark.parametrize("status", QUIZ_STATUSES)
def test_every_documented_quiz_status_is_permitted(session: Session, fixture: Fixture, status: str):
    session.add(make_quiz(fixture, status=status))
    session.commit()


@pytest.mark.parametrize("status", ATTEMPT_STATUSES)
def test_every_documented_attempt_status_is_permitted(
    session: Session, fixture: Fixture, status: str
):
    quiz = make_quiz(fixture)
    session.add(quiz)
    session.flush()
    session.add(make_attempt(fixture, quiz, status=status))
    session.commit()


# -- refusals -----------------------------------------------------------------


def test_an_unknown_question_type_is_refused(session: Session, fixture: Fixture):
    session.add(make_question(fixture, question_type="essay"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_an_unknown_question_status_is_refused(session: Session, fixture: Fixture):
    session.add(make_question(fixture, status="published"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_an_unknown_attempt_status_is_refused(session: Session, fixture: Fixture):
    quiz = make_quiz(fixture)
    session.add(quiz)
    session.flush()
    session.add(make_attempt(fixture, quiz, status="marked"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_a_question_may_be_placed_only_once_in_a_quiz(session: Session, fixture: Fixture):
    quiz = make_quiz(fixture)
    question = make_question(fixture)
    session.add_all([quiz, question])
    session.flush()
    session.add(QuizQuestion(checkpoint_quiz_id=quiz.id, question_id=question.id, position=1))
    session.flush()
    session.add(QuizQuestion(checkpoint_quiz_id=quiz.id, question_id=question.id, position=2))

    with pytest.raises(IntegrityError):
        session.commit()


def test_two_questions_cannot_share_a_position(session: Session, fixture: Fixture):
    quiz = make_quiz(fixture)
    first = make_question(fixture)
    second = make_question(fixture)
    session.add_all([quiz, first, second])
    session.flush()
    session.add(QuizQuestion(checkpoint_quiz_id=quiz.id, question_id=first.id, position=1))
    session.flush()
    session.add(QuizQuestion(checkpoint_quiz_id=quiz.id, question_id=second.id, position=1))

    with pytest.raises(IntegrityError):
        session.commit()


def test_a_position_counts_from_one(session: Session, fixture: Fixture):
    """What survives of the approved `max_marks > 0` guard."""
    quiz = make_quiz(fixture)
    question = make_question(fixture)
    session.add_all([quiz, question])
    session.flush()
    session.add(QuizQuestion(checkpoint_quiz_id=quiz.id, question_id=question.id, position=0))

    with pytest.raises(IntegrityError):
        session.commit()


def test_one_answer_per_question_per_attempt(session: Session, fixture: Fixture):
    quiz = make_quiz(fixture)
    question = make_question(fixture)
    session.add_all([quiz, question])
    session.flush()
    attempt = make_attempt(fixture, quiz)
    session.add(attempt)
    session.flush()
    session.add(
        QuizAttemptAnswer(
            quiz_attempt_id=attempt.id, question_id=question.id, submitted_answer=None
        )
    )
    session.flush()
    session.add(
        QuizAttemptAnswer(
            quiz_attempt_id=attempt.id, question_id=question.id, submitted_answer=None
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_a_quiz_covers_a_topic_only_once(session: Session, fixture: Fixture):
    quiz = make_quiz(fixture)
    session.add(quiz)
    session.flush()
    session.add(CheckpointQuizTopic(checkpoint_quiz_id=quiz.id, topic_id=fixture.topic.id))
    session.flush()
    session.add(CheckpointQuizTopic(checkpoint_quiz_id=quiz.id, topic_id=fixture.topic.id))

    with pytest.raises(IntegrityError):
        session.commit()


def test_a_question_link_must_name_a_stored_topic(session: Session, fixture: Fixture):
    question = make_question(fixture)
    session.add(question)
    session.flush()
    session.add(QuestionTopicLink(question_id=question.id, topic_id=uuid.uuid4()))

    with pytest.raises(IntegrityError):
        session.commit()


def test_an_attempt_must_name_a_stored_quiz(session: Session, fixture: Fixture):
    session.add(
        QuizAttempt(
            learner_id=fixture.learner.id,
            checkpoint_quiz_id=uuid.uuid4(),
            status="in_progress",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


# -- what the tables hold -----------------------------------------------------


def test_a_question_may_cover_a_topic_that_only_groups_subtopics(
    session: Session, fixture: Fixture
):
    """Deliberately unlike `learner_topic_progress`, which needs a trackable topic."""
    question = make_question(fixture)
    session.add(question)
    session.flush()
    session.add(QuestionTopicLink(question_id=question.id, topic_id=fixture.heading.id))
    session.commit()


def test_the_option_payloads_survive_a_round_trip(session: Session, fixture: Fixture):
    question = make_question(fixture)
    session.add(question)
    session.commit()
    session.expunge_all()

    stored = session.get(Question, question.id)

    assert stored is not None
    assert stored.options == [{"key": "a", "text": "8"}, {"key": "b", "text": "10"}]
    assert stored.expected_answer == {"option_key": "b"}


def test_an_unanswered_question_is_stored_as_neither_correct_nor_wrong(
    session: Session, fixture: Fixture
):
    """The distinction the nullable `is_correct` exists to keep."""
    quiz = make_quiz(fixture)
    question = make_question(fixture)
    session.add_all([quiz, question])
    session.flush()
    attempt = make_attempt(fixture, quiz)
    session.add(attempt)
    session.flush()
    answer = QuizAttemptAnswer(
        quiz_attempt_id=attempt.id,
        question_id=question.id,
        submitted_answer=None,
        is_correct=None,
    )
    session.add(answer)
    session.commit()
    session.expunge_all()

    stored = session.get(QuizAttemptAnswer, answer.id)

    assert stored is not None
    assert stored.is_correct is None
    assert stored.submitted_answer is None
