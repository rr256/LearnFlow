"""SQLAlchemy implementation of the learner profile repository port.

Maps the application's plain `LearnerRecord` onto the `learners` ORM model and
back. It decides nothing: which learner counts as "the local learner", and what
a partial update means, are settled above this layer
(docs/architecture/dependency-rules.md).

The session's transaction is owned by the caller. Nothing here commits.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.study_goal_repository import LearnerRecord
from app.infrastructure.persistence.learner_planning import Learner


class SqlAlchemyLearnerRepository:
    """Reads and writes learner records through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def list_learners(self) -> tuple[LearnerRecord, ...]:
        """Every stored learner, oldest first."""
        models = self._session.scalars(select(Learner).order_by(Learner.created_at))
        return tuple(
            LearnerRecord(id=model.id, display_name=model.display_name, timezone=model.timezone)
            for model in models
        )

    def add_learner(self, record: LearnerRecord) -> None:
        """Store a new learner."""
        self._session.add(
            Learner(id=record.id, display_name=record.display_name, timezone=record.timezone)
        )

    def update_learner(self, record: LearnerRecord) -> None:
        """Overwrite the stored learner identified by ``record.id``."""
        model = self._session.get(Learner, record.id)
        if model is None:
            raise LookupError(f"Learner {record.id} is not stored.")
        model.display_name = record.display_name
        model.timezone = record.timezone
