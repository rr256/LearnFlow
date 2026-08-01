"""Request-scoped provider construction.

Only the composition root decides which implementation fulfils an application
port, so the choice of a SQLAlchemy repository is made here and nowhere else
(docs/architecture/dependency-rules.md). The presentation layer receives a
callable that hands it a ready use case and never learns what is behind it.

Each call opens one unit of work and closes it when the caller is done. The
curriculum endpoints only read, so nothing commits: closing the session ends the
transaction it opened.
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy.orm import Session, sessionmaker

from app.application.use_cases.read_curriculum import ReadCurriculum
from app.infrastructure.persistence.curriculum_repository import SqlAlchemyCurriculumRepository

ReadCurriculumProvider = Callable[[], AbstractContextManager[ReadCurriculum]]


def build_read_curriculum_provider(
    session_factory: sessionmaker[Session],
) -> ReadCurriculumProvider:
    """Build the provider that hands a curriculum reader to one request.

    Args:
        session_factory: The application's shared session factory. It is bound
            once at startup, so a request pays for a pooled connection rather
            than for building an engine.
    """

    @contextmanager
    def provide() -> Iterator[ReadCurriculum]:
        with session_factory() as session:
            yield ReadCurriculum(SqlAlchemyCurriculumRepository(session))

    return provide
