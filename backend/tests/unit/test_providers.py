"""Unit tests for the composition root's request-scoped providers.

The learner-owned providers own the transaction, so no route has to remember to
commit. That is worth a test of its own: a provider that committed regardless of
the outcome would persist a half-written record while the API reported a failure,
which `docs/development/coding-standards.md` forbids outright.

The counterpart API test is `tests/api/test_provider_transactions.py`, which
checks that a failure raised inside a route actually reaches the provider.
"""

import pytest

from app.composition.providers import (
    build_learner_profile_provider,
    build_read_curriculum_provider,
    build_study_goals_provider,
    build_topic_progress_provider,
)


class RecordingSession:
    """A stand-in session that records the transaction calls made on it."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def __enter__(self) -> RecordingSession:
        return self

    def __exit__(self, *_exception: object) -> None:
        self.closed = True

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def session_factory() -> tuple[object, RecordingSession]:
    session = RecordingSession()
    return (lambda: session), session


def test_a_writing_provider_commits_when_the_caller_returns_cleanly():
    factory, session = session_factory()
    provider = build_study_goals_provider(factory)  # type: ignore[arg-type]

    with provider():
        pass

    assert (session.commits, session.rollbacks) == (1, 0)
    assert session.closed


def test_a_writing_provider_rolls_back_when_the_caller_raises():
    """A route that reported a failure must leave nothing behind."""
    factory, session = session_factory()
    provider = build_study_goals_provider(factory)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError), provider():
        raise RuntimeError("the route failed")

    assert (session.commits, session.rollbacks) == (0, 1)
    assert session.closed


def test_the_learner_profile_provider_commits_when_the_caller_returns_cleanly():
    factory, session = session_factory()
    provider = build_learner_profile_provider(factory, default_timezone="Asia/Kolkata")  # type: ignore[arg-type]

    with provider():
        pass

    assert (session.commits, session.rollbacks) == (1, 0)


def test_the_learner_profile_provider_rolls_back_when_the_caller_raises():
    factory, session = session_factory()
    provider = build_learner_profile_provider(factory, default_timezone="Asia/Kolkata")  # type: ignore[arg-type]

    with pytest.raises(RuntimeError), provider():
        raise RuntimeError("the route failed")

    assert (session.commits, session.rollbacks) == (0, 1)


def test_the_topic_progress_provider_commits_when_the_caller_returns_cleanly():
    factory, session = session_factory()
    provider = build_topic_progress_provider(factory)  # type: ignore[arg-type]

    with provider():
        pass

    assert (session.commits, session.rollbacks) == (1, 0)


def test_the_topic_progress_provider_rolls_back_when_the_caller_raises():
    """A rejected stage must leave no record behind."""
    factory, session = session_factory()
    provider = build_topic_progress_provider(factory)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError), provider():
        raise RuntimeError("the route failed")

    assert (session.commits, session.rollbacks) == (0, 1)


def test_a_read_provider_never_commits():
    """Closing the session ends the transaction it opened; nothing was written."""
    factory, session = session_factory()
    provider = build_read_curriculum_provider(factory)  # type: ignore[arg-type]

    with provider():
        pass

    assert session.commits == 0
