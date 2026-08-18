"""Shared fixtures for the checkpoint-practice use-case tests.

A learner, a two-topic curriculum shaped like the curated GATE CSE one, a fixed
clock, and the two use cases bound to one store. Both use cases share the store
deliberately: writing a question and assembling a quiz from it is the sequence
the practice screen performs, and a test that could not do both would have to
fake the half it skipped.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.application.dto.checkpoint_practice import NewQuestion, PracticeTopic
from app.application.use_cases.manage_checkpoint_quizzes import ManageCheckpointQuizzes
from app.application.use_cases.manage_practice_questions import ManagePracticeQuestions
from tests.unit.fake_checkpoint_practice_repository import FakeCheckpointPracticeRepository
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner

NOW = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)


class AdvancingClock:
    """A clock that reports a later instant on each read.

    A question's `written_at` is what a quiz is ordered by, so a fixed clock would
    write every question at the same instant and leave the order to the
    identifier tie-break. Advancing by a second per read makes the order a test
    asserts the order the learner actually wrote in.
    """

    def __init__(self, start: datetime = NOW, step: timedelta = timedelta(seconds=1)) -> None:
        self.instant = start
        self.step = step

    def now(self) -> datetime:
        reading = self.instant
        self.instant += self.step
        return reading


class Practising:
    """A learner, two topics, and somewhere to put questions, quizzes, and attempts.

    The grouping topic sits beside the trackable one deliberately: a question may
    cover either, which is where QZ-008 follows RES-001 rather than PRG-004.
    """

    def __init__(self) -> None:
        self.learner = learner()
        self.learners = FakeLearnerRepository((self.learner,))
        self.subject_id = uuid.uuid4()
        self.topic = PracticeTopic(
            id=uuid.uuid4(),
            code=None,
            name="CPU scheduling",
            subject_id=self.subject_id,
            subject_name="Operating Systems",
        )
        self.other_topic = PracticeTopic(
            id=uuid.uuid4(),
            code=None,
            name="Page replacement",
            subject_id=self.subject_id,
            subject_name="Operating Systems",
        )
        self.heading = PracticeTopic(
            id=uuid.uuid4(),
            code=None,
            name="Operating Systems",
            subject_id=self.subject_id,
            subject_name="Operating Systems",
        )
        self.practice = FakeCheckpointPracticeRepository(
            topics=[self.topic, self.other_topic, self.heading]
        )
        self.clock = AdvancingClock()

    def author(self) -> ManagePracticeQuestions:
        return ManagePracticeQuestions(
            learners=self.learners, practice=self.practice, clock=self.clock
        )

    def quizzes(self) -> ManageCheckpointQuizzes:
        return ManageCheckpointQuizzes(
            learners=self.learners, practice=self.practice, clock=self.clock
        )


def a_question(**fields: object) -> NewQuestion:
    """A writable question, overridable field by field."""
    defaults: dict[str, object] = {
        "prompt": "How many bits address 1 KiB?",
        "option_texts": ("8", "10", "16", "1024"),
        "correct_option_index": 1,
        "explanation": "1 KiB is 2^10 bytes, so ten bits address it.",
        "topic_ids": (),
    }
    defaults.update(fields)
    return NewQuestion(**defaults)  # type: ignore[arg-type]
