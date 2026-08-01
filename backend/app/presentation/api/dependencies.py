"""Request-scoped dependencies for the API layer.

A route needs a use case, not a database. The composition root installs a
provider on the application state during startup, and the dependency below opens
one for the duration of a request and closes it afterwards.

Nothing here imports SQLAlchemy, a repository implementation, or configuration.
Which implementation fulfils a port is the composition root's decision alone
(docs/architecture/dependency-rules.md), so this module never learns what is
behind the provider it calls.
"""

from collections.abc import Iterator

from fastapi import Request

from app.application.use_cases.read_curriculum import ReadCurriculum

# The attribute the composition root installs on ``app.state``. Named once here
# so the two layers cannot drift apart over a typo.
READ_CURRICULUM_PROVIDER = "read_curriculum_provider"


def provide_read_curriculum(request: Request) -> Iterator[ReadCurriculum]:
    """Yield a curriculum reader bound to this request's unit of work.

    The provider is a context manager, so the unit of work it opened is released
    once the response has been produced, including when the route raised.
    """
    provider = getattr(request.app.state, READ_CURRICULUM_PROVIDER)
    with provider() as use_case:
        yield use_case
