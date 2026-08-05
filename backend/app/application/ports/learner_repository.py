"""The persistence port the learner profile use case works through.

It reuses `LearnerRecord` from `study_goal_repository`, which declared it first,
rather than describing the same row twice -- the same reuse `curriculum_
repository` makes of the seed port's records.

This port is separate from `StudyGoalRepository` because the two answer different
questions. The study-goal port resolves reference data by *code*, which is what a
command-line seed holds; the profile is addressed without any lookup at all,
because a single-learner installation has exactly one. Merging them would give
each caller methods it must be trusted not to use.
"""

from typing import Protocol

from app.application.ports.study_goal_repository import LearnerRecord


class LearnerRepository(Protocol):
    """Reads and writes the local learner's identity and preferences."""

    def list_learners(self) -> tuple[LearnerRecord, ...]:
        """Every stored learner, oldest first.

        The MVP has one. Returning them all rather than "the" learner keeps the
        decision about what to do with none, one, or several in the use case,
        where it can be tested without a database.
        """
        ...

    def add_learner(self, record: LearnerRecord) -> None:
        """Store a new learner."""
        ...

    def update_learner(self, record: LearnerRecord) -> None:
        """Overwrite the stored learner identified by ``record.id``."""
        ...
