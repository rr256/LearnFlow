"""Unit tests for the learner profile use case (LRN-001, LRN-002).

They run against `FakeLearnerRepository`, so they exercise the rules -- what a
read does when nothing is stored, what a partial update leaves alone, and when
the local learner is undefined -- without a database.
"""

import pytest

from app.application.dto.learner_profile import LearnerProfileChanges
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_learner_profile import (
    EmptyProfileUpdateError,
    ManageLearnerProfile,
)
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner

DEFAULT_TIMEZONE = "Asia/Kolkata"


def build(*learners) -> tuple[ManageLearnerProfile, FakeLearnerRepository]:
    repository = FakeLearnerRepository(tuple(learners))
    return ManageLearnerProfile(repository, default_timezone=DEFAULT_TIMEZONE), repository


# -- LRN-001: read ---------------------------------------------------------


def test_reading_reports_no_profile_before_setup_has_created_one():
    profiles, _ = build()

    assert profiles.read() is None


def test_reading_does_not_create_the_learner_it_did_not_find():
    """A page load must not leave a record behind; LRN-002 creates the learner."""
    profiles, repository = build()

    profiles.read()

    assert repository.learners == []


def test_reading_returns_the_stored_learner():
    stored = learner(display_name="Asha", timezone="Europe/Lisbon")
    profiles, _ = build(stored)

    profile = profiles.read()

    assert profile is not None
    assert (profile.id, profile.display_name, profile.timezone) == (
        stored.id,
        "Asha",
        "Europe/Lisbon",
    )


def test_reading_refuses_when_more_than_one_learner_is_stored():
    """Choosing one arbitrarily would show a learner somebody else's profile."""
    profiles, _ = build(learner(), learner())

    with pytest.raises(AmbiguousLocalLearnerError):
        profiles.read()


# -- LRN-002: update -------------------------------------------------------


def test_updating_creates_the_learner_when_none_exists_yet():
    profiles, repository = build()

    profile = profiles.update(LearnerProfileChanges(display_name="Asha"))

    assert profile.display_name == "Asha"
    assert [record.id for record in repository.learners] == [profile.id]


def test_a_created_learner_takes_the_configured_default_timezone():
    """The composition root supplies it; application code reads no configuration."""
    profiles, _ = build()

    profile = profiles.update(LearnerProfileChanges(display_name="Asha"))

    assert profile.timezone == DEFAULT_TIMEZONE


def test_a_created_learner_takes_a_requested_timezone_over_the_default():
    profiles, _ = build()

    profile = profiles.update(LearnerProfileChanges(timezone="Europe/Lisbon"))

    assert profile.timezone == "Europe/Lisbon"


def test_updating_one_field_leaves_the_others_alone():
    """A form that omitted the timezone must not move every future plan by hours."""
    profiles, _ = build(learner(display_name="Asha", timezone="Europe/Lisbon"))

    profile = profiles.update(LearnerProfileChanges(display_name="Asha Rao"))

    assert profile.display_name == "Asha Rao"
    assert profile.timezone == "Europe/Lisbon"


def test_clearing_the_display_name_removes_it():
    profiles, _ = build(learner(display_name="Asha"))

    profile = profiles.update(LearnerProfileChanges(clear_display_name=True))

    assert profile.display_name is None


def test_updating_refuses_a_request_that_changes_nothing():
    profiles, _ = build(learner())

    with pytest.raises(EmptyProfileUpdateError):
        profiles.update(LearnerProfileChanges())


def test_updating_writes_nothing_when_the_stored_values_already_match():
    profiles, repository = build(learner(display_name="Asha", timezone=DEFAULT_TIMEZONE))
    before = tuple(repository.learners)

    profiles.update(LearnerProfileChanges(display_name="Asha"))

    assert tuple(repository.learners) == before


def test_updating_refuses_when_more_than_one_learner_is_stored():
    profiles, _ = build(learner(), learner())

    with pytest.raises(AmbiguousLocalLearnerError):
        profiles.update(LearnerProfileChanges(display_name="Asha"))
