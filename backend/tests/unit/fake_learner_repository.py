"""An in-memory stand-in for the learner profile repository port.

Learners are held in a list rather than a dictionary so the "more than one
learner is stored" case -- which the use case must refuse rather than resolve --
can be set up directly.
"""

import uuid

from app.application.ports.study_goal_repository import LearnerRecord


class FakeLearnerRepository:
    """Stores learner records in a list, oldest first."""

    def __init__(self, learners: tuple[LearnerRecord, ...] = ()) -> None:
        self.learners: list[LearnerRecord] = list(learners)

    def list_learners(self) -> tuple[LearnerRecord, ...]:
        return tuple(self.learners)

    def add_learner(self, record: LearnerRecord) -> None:
        self.learners.append(record)

    def update_learner(self, record: LearnerRecord) -> None:
        for index, stored in enumerate(self.learners):
            if stored.id == record.id:
                self.learners[index] = record
                return
        raise AssertionError(f"learner {record.id} is not stored")


def learner(display_name: str | None = "Asha", timezone: str = "Asia/Kolkata") -> LearnerRecord:
    """A stored learner, for a test that does not care about the identifier."""
    return LearnerRecord(id=uuid.uuid4(), display_name=display_name, timezone=timezone)
