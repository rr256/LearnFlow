"""The transaction boundary holds across the whole request, not just in isolation.

`tests/unit/test_providers.py` shows the providers commit on a clean exit and roll
back on an exception. That is only useful if a failure raised *inside a route*
actually reaches the provider -- FastAPI closes dependencies with `yield` through
an exit stack, and if a raised `HTTPException` bypassed it, every reported failure
would still be committed.

These tests hold that assumption to account over the real application factory,
the real routes, and a provider shaped exactly like the composition root's.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.application.use_cases.manage_learner_profile import ManageLearnerProfile
from app.application.use_cases.manage_study_goals import ManageStudyGoals
from app.composition.app_factory import create_app
from app.presentation.api.dependencies import LEARNER_PROFILE_PROVIDER, STUDY_GOALS_PROVIDER
from tests.api.onboarding_fixtures import DEFAULT_TIMEZONE, Onboarding

GOALS = "/api/v1/study-goals"
LEARNER = "/api/v1/learner"


class TransactionLog:
    """Records what a request decided to do with its unit of work."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0


@pytest.fixture
def transaction_log() -> TransactionLog:
    return TransactionLog()


@pytest.fixture
def transactional_client(
    onboarding: Onboarding, transaction_log: TransactionLog
) -> Iterator[TestClient]:
    """A client whose providers commit and roll back exactly as the real ones do."""

    @contextmanager
    def provide_goals() -> Iterator[ManageStudyGoals]:
        try:
            yield ManageStudyGoals(
                learners=onboarding.learners,
                goals=onboarding.goals,
                schedules=onboarding.schedules,
            )
        except BaseException:
            transaction_log.rollbacks += 1
            raise
        transaction_log.commits += 1

    @contextmanager
    def provide_profile() -> Iterator[ManageLearnerProfile]:
        try:
            yield ManageLearnerProfile(onboarding.learners, default_timezone=DEFAULT_TIMEZONE)
        except BaseException:
            transaction_log.rollbacks += 1
            raise
        transaction_log.commits += 1

    app = create_app()
    setattr(app.state, STUDY_GOALS_PROVIDER, provide_goals)
    setattr(app.state, LEARNER_PROFILE_PROVIDER, provide_profile)
    with TestClient(app) as client:
        yield client


def test_a_successful_write_commits(transactional_client, transaction_log, onboarding):
    transactional_client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})
    transaction_log.commits = 0

    response = transactional_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
        },
    )

    assert response.status_code == 201
    assert (transaction_log.commits, transaction_log.rollbacks) == (1, 0)


def test_a_reported_conflict_rolls_back_rather_than_committing(
    transactional_client, transaction_log, onboarding
):
    """A 409 must leave nothing behind, however the route raised it."""
    response = transactional_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
        },
    )

    assert response.status_code == 409
    assert (transaction_log.commits, transaction_log.rollbacks) == (0, 1)


def test_a_rejected_request_rolls_back_rather_than_committing(
    transactional_client, transaction_log, onboarding
):
    transactional_client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})
    transaction_log.commits = 0

    response = transactional_client.post(
        GOALS, json={"learning_program_id": str(onboarding.schedule.learning_program_id)}
    )

    assert response.status_code == 422
    assert (transaction_log.commits, transaction_log.rollbacks) == (0, 1)


def test_a_not_found_rolls_back_rather_than_committing(
    transactional_client, transaction_log, onboarding
):
    transactional_client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})
    transaction_log.commits = 0

    response = transactional_client.patch(
        f"{GOALS}/00000000-0000-4000-8000-0000000000ff", json={"status": "paused"}
    )

    assert response.status_code == 404
    assert (transaction_log.commits, transaction_log.rollbacks) == (0, 1)
