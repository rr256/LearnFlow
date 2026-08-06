"""The learner setup endpoints against a real PostgreSQL database.

The API tests prove the contract against fakes. These prove the part a fake
cannot: that the SQL the repositories emit writes and reads the learner, the
goal, and the week of availability the seeds actually created, that the database
`CHECK` constraints agree with the rules the use cases enforce, and that a request
reporting a failure commits nothing -- all through the same composition root the
running backend uses.

Skipped unless ``TEST_DATABASE_URL`` names a disposable database; see
tests/integration/conftest.py.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.application.use_cases.seed_curriculum import SeedCurriculum
from app.application.use_cases.seed_examination_schedule import SeedExaminationSchedule
from app.composition.app_factory import create_app
from app.composition.config import Settings
from app.infrastructure.persistence.curriculum_seed_repository import (
    SqlAlchemyCurriculumSeedRepository,
)
from app.infrastructure.persistence.examination_schedule_seed_repository import (
    SqlAlchemyExaminationScheduleSeedRepository,
)
from app.infrastructure.persistence.learner_planning import AvailabilitySlot, Learner, StudyGoal
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed
from scripts.examination_schedule_file import (
    GATE_CSE_EXAMINATION_SCHEDULE_FILE,
    load_examination_schedule,
)

LEARNER = "/api/v1/learner"
SCHEDULES = "/api/v1/examination-schedules"
GOALS = "/api/v1/study-goals"
CURRICULUM = "/api/v1/curriculum"
SEED_TIME = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def seeded_reference_data(session: Session) -> None:
    """Load the curriculum and the published schedule, as the seed commands do."""
    SeedCurriculum(SqlAlchemyCurriculumSeedRepository(session), clock=lambda: SEED_TIME)(
        load_curriculum_seed(GATE_CSE_CURRICULUM_FILE)
    )
    session.commit()
    SeedExaminationSchedule(SqlAlchemyExaminationScheduleSeedRepository(session))(
        load_examination_schedule(GATE_CSE_EXAMINATION_SCHEDULE_FILE)
    )
    session.commit()


@pytest.fixture
def client(
    migrated_database: Engine, database_url: str, seeded_reference_data: None
) -> Iterator[TestClient]:
    """A client wired to the test database through the real composition root."""
    app = create_app(Settings(database_url=database_url))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def gate_cse(client: TestClient) -> dict:
    """The seeded GATE CSE program, read back through CUR-001."""
    programs = client.get(f"{CURRICULUM}/programs").json()["data"]
    return next(program for program in programs if program["code"] == "gate-cse")


@pytest.fixture
def gate_2027(client: TestClient, gate_cse: dict) -> dict:
    """The seeded GATE 2027 schedule, read back through EXM-001."""
    body = client.get(f"{SCHEDULES}?learning_program_id={gate_cse['id']}").json()
    return next(schedule for schedule in body["data"] if schedule["cycle_label"] == "2027")


# -- EXM-001 over seeded data ----------------------------------------------


def test_the_seeded_schedule_is_readable_with_its_provenance(gate_2027):
    assert gate_2027["name"] == "GATE 2027"
    assert gate_2027["schedule_status"] == "provisional"
    assert gate_2027["source_reference"].startswith("https://")
    assert gate_2027["organising_body"]


def test_the_seeded_schedule_reports_a_window_spanning_its_sitting_weekends(gate_2027):
    """Three weekends, one window, and no single examination date; ADR-013."""
    window = gate_2027["examination_window"]
    sittings = [period for period in gate_2027["periods"] if period["period_type"] == "examination"]

    assert len(sittings) == 3
    assert window["starts_on"] == min(period["starts_on"] for period in sittings)
    assert window["ends_on"] == max(period["ends_on"] for period in sittings)


def test_the_seeded_schedule_reports_its_registration_deadlines(gate_2027):
    types = {period["period_type"] for period in gate_2027["periods"]}

    assert {"registration", "late_registration", "results"} <= types


# -- LRN-001 and LRN-002 over a real database ------------------------------


def test_the_profile_is_absent_until_setup_creates_it(client, session):
    body = client.get(f"{LEARNER}/profile").json()

    assert body["data"] is None
    assert session.scalar(select(func.count()).select_from(Learner)) == 0


def test_updating_the_profile_writes_the_learner_row(client, session):
    body = client.patch(
        f"{LEARNER}/profile", json={"display_name": "Asha", "timezone": "Europe/Lisbon"}
    ).json()

    stored = session.scalar(select(Learner))
    assert stored is not None
    assert (str(stored.id), stored.display_name, stored.timezone) == (
        body["data"]["id"],
        "Asha",
        "Europe/Lisbon",
    )


def test_a_created_learner_takes_the_configured_default_timezone(client, session):
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})

    stored = session.scalar(select(Learner))
    assert stored is not None
    assert stored.timezone == "Asia/Kolkata"


# -- GOAL-001 to GOAL-004 over a real database -----------------------------


def test_creating_a_goal_writes_the_row_bound_to_the_active_curriculum_version(
    client, session, gate_cse, gate_2027
):
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})

    body = client.post(
        GOALS,
        json={
            "learning_program_id": gate_cse["id"],
            "examination_schedule_id": gate_2027["id"],
        },
    ).json()

    stored = session.scalar(select(StudyGoal))
    assert stored is not None
    assert str(stored.curriculum_version_id) == gate_cse["active_curriculum_version"]["id"]
    assert str(stored.examination_schedule_id) == gate_2027["id"]
    assert body["data"]["curriculum_version"]["status"] == "active"


def test_a_created_goal_reports_the_seeded_examination_window(client, gate_cse, gate_2027):
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})

    body = client.post(
        GOALS,
        json={
            "learning_program_id": gate_cse["id"],
            "examination_schedule_id": gate_2027["id"],
        },
    ).json()

    assert body["data"]["examination"]["examination_window"] == gate_2027["examination_window"]


def test_a_goal_survives_a_round_trip_through_the_read_endpoints(client, gate_cse, gate_2027):
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})
    created = client.post(
        GOALS,
        json={
            "learning_program_id": gate_cse["id"],
            "examination_schedule_id": gate_2027["id"],
            "target_date": "2027-01-31",
        },
    ).json()["data"]

    read_back = client.get(f"{GOALS}/{created['id']}").json()["data"]
    listed = client.get(GOALS).json()

    assert read_back == created
    assert listed["data"] == [created]
    assert listed["pagination"]["total"] == 1


def test_updating_a_goal_writes_only_what_it_names(client, session, gate_cse, gate_2027):
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})
    created = client.post(
        GOALS,
        json={
            "learning_program_id": gate_cse["id"],
            "examination_schedule_id": gate_2027["id"],
            "target_date": "2027-01-31",
        },
    ).json()["data"]

    client.patch(f"{GOALS}/{created['id']}", json={"status": "paused"})

    session.expire_all()
    stored = session.scalar(select(StudyGoal))
    assert stored is not None
    assert stored.status == "paused"
    assert str(stored.examination_schedule_id) == gate_2027["id"]


def test_a_rejected_goal_leaves_no_row_behind(client, session, gate_cse):
    """A request that reported a failure must commit nothing."""
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})

    response = client.post(GOALS, json={"learning_program_id": gate_cse["id"]})

    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(StudyGoal)) == 0


def test_a_conflicting_second_goal_leaves_the_first_untouched(client, session, gate_cse, gate_2027):
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})
    body = {
        "learning_program_id": gate_cse["id"],
        "examination_schedule_id": gate_2027["id"],
    }
    client.post(GOALS, json=body)

    response = client.post(GOALS, json=body)

    assert response.status_code == 409
    assert session.scalar(select(func.count()).select_from(StudyGoal)) == 1


def test_a_goal_referencing_an_unknown_schedule_is_refused_before_the_database_sees_it(
    client, session, gate_cse
):
    """The use case names the offending field; a foreign key would only raise a 500."""
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})

    response = client.post(
        GOALS,
        json={
            "learning_program_id": gate_cse["id"],
            "examination_schedule_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.examination_schedule_id"
    assert session.scalar(select(func.count()).select_from(StudyGoal)) == 0


# -- GOAL-005 over a real database -----------------------------------------


@pytest.fixture
def goal(client: TestClient, gate_cse: dict, gate_2027: dict) -> dict:
    """A learner with a goal, which is what a week of availability hangs off."""
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})
    return client.post(
        GOALS,
        json={
            "learning_program_id": gate_cse["id"],
            "examination_schedule_id": gate_2027["id"],
        },
    ).json()["data"]


def stored_week(session: Session) -> dict[str, int]:
    session.expire_all()
    return {
        slot.day_of_week: slot.available_minutes
        for slot in session.scalars(select(AvailabilitySlot))
    }


def test_saving_a_week_writes_the_availability_rows(client, session, goal):
    client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={
            "slots": [
                {"day_of_week": "monday", "available_minutes": 120},
                {"day_of_week": "saturday", "available_minutes": 240},
            ]
        },
    )

    assert stored_week(session) == {"monday": 120, "saturday": 240}


def test_a_saved_week_survives_a_round_trip_through_the_goal_endpoints(client, goal):
    saved = client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={"slots": [{"day_of_week": "monday", "available_minutes": 120}]},
    ).json()["data"]

    read_back = client.get(f"{GOALS}/{goal['id']}").json()["data"]
    listed = client.get(GOALS).json()["data"]

    assert read_back["availability"] == saved
    assert listed[0]["availability"] == saved


def test_saving_a_week_deletes_the_days_it_does_not_name(client, session, goal):
    client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={
            "slots": [
                {"day_of_week": "monday", "available_minutes": 120},
                {"day_of_week": "tuesday", "available_minutes": 60},
            ]
        },
    )

    client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={"slots": [{"day_of_week": "monday", "available_minutes": 120}]},
    )

    assert stored_week(session) == {"monday": 120}


def test_an_unchanged_day_keeps_its_row_and_creation_timestamp(client, session, goal):
    """A day whose minutes have not moved is left alone, so its identifier and
    `created_at` survive -- which a delete-and-reinsert would discard."""
    client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={"slots": [{"day_of_week": "monday", "available_minutes": 120}]},
    )
    session.expire_all()
    before = session.scalar(select(AvailabilitySlot))
    assert before is not None
    identifier, created_at = before.id, before.created_at

    client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={
            "slots": [
                {"day_of_week": "monday", "available_minutes": 120},
                {"day_of_week": "tuesday", "available_minutes": 60},
            ]
        },
    )

    session.expire_all()
    monday = session.scalar(
        select(AvailabilitySlot).where(AvailabilitySlot.day_of_week == "monday")
    )
    assert monday is not None
    assert (monday.id, monday.created_at) == (identifier, created_at)


def test_an_empty_week_deletes_every_row(client, session, goal):
    client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={"slots": [{"day_of_week": "monday", "available_minutes": 120}]},
    )

    client.put(f"{GOALS}/{goal['id']}/availability", json={"slots": []})

    assert session.scalar(select(func.count()).select_from(AvailabilitySlot)) == 0


def test_a_rejected_week_leaves_no_row_behind(client, session, goal):
    """A request that reported a failure must commit nothing, even the days it
    named before the one that was wrong."""
    response = client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={
            "slots": [
                {"day_of_week": "monday", "available_minutes": 120},
                {"day_of_week": "moonday", "available_minutes": 60},
            ]
        },
    )

    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(AvailabilitySlot)) == 0


def test_a_week_the_database_would_refuse_is_refused_before_it_sees_it(client, session, goal):
    """The use case mirrors the `CHECK`, so the failure names the day rather than
    surfacing as an unexplained 500."""
    response = client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={"slots": [{"day_of_week": "monday", "available_minutes": 1441}]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.slots"
    assert session.scalar(select(func.count()).select_from(AvailabilitySlot)) == 0


# -- planning preferences over a real database ------------------------------


def stored_preferences(session: Session) -> tuple[int | None, str | None]:
    session.expire_all()
    stored = session.scalar(select(StudyGoal))
    assert stored is not None
    return stored.preferred_session_minutes, stored.topic_sequencing


def test_creating_a_goal_writes_the_preference_columns(client, session, gate_cse, gate_2027):
    client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})

    client.post(
        GOALS,
        json={
            "learning_program_id": gate_cse["id"],
            "examination_schedule_id": gate_2027["id"],
            "planning_preferences": {
                "preferred_session_minutes": 90,
                "topic_sequencing": "prerequisites_first",
            },
        },
    )

    assert stored_preferences(session) == (90, "prerequisites_first")


def test_a_goal_created_without_preferences_stores_nulls(client, session, goal):
    """Not a stored default. A planner meeting NULL chooses its own default
    visibly rather than reading a value nobody chose."""
    assert goal["planning_preferences"] == {
        "preferred_session_minutes": None,
        "topic_sequencing": None,
    }
    assert stored_preferences(session) == (None, None)


def test_saved_preferences_survive_a_round_trip_through_the_goal_endpoints(client, goal):
    saved = client.patch(
        f"{GOALS}/{goal['id']}",
        json={
            "planning_preferences": {
                "preferred_session_minutes": 45,
                "topic_sequencing": "syllabus_order",
            }
        },
    ).json()["data"]["planning_preferences"]

    read_back = client.get(f"{GOALS}/{goal['id']}").json()["data"]
    listed = client.get(GOALS).json()["data"]

    assert read_back["planning_preferences"] == saved
    assert listed[0]["planning_preferences"] == saved


def test_replacing_the_group_clears_the_column_it_does_not_name(client, session, goal):
    client.patch(
        f"{GOALS}/{goal['id']}",
        json={
            "planning_preferences": {
                "preferred_session_minutes": 90,
                "topic_sequencing": "syllabus_order",
            }
        },
    )

    client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"topic_sequencing": "prerequisites_first"}},
    )

    assert stored_preferences(session) == (None, "prerequisites_first")


def test_an_update_naming_no_preferences_leaves_the_columns_alone(client, session, goal):
    client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"preferred_session_minutes": 60}},
    )

    client.patch(f"{GOALS}/{goal['id']}", json={"status": "paused"})

    assert stored_preferences(session) == (60, None)


def test_a_rejected_preference_leaves_the_stored_columns_untouched(client, session, goal):
    """The provider owns the transaction, so a refused request commits nothing."""
    client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"preferred_session_minutes": 60}},
    )

    response = client.patch(
        f"{GOALS}/{goal['id']}",
        json={
            "planning_preferences": {
                "preferred_session_minutes": 9000,
                "topic_sequencing": "syllabus_order",
            }
        },
    )

    assert response.status_code == 422
    assert stored_preferences(session) == (60, None)


def test_a_preference_the_database_would_refuse_is_refused_before_it_sees_it(client, session, goal):
    """The use case mirrors the `CHECK`, so the failure names the preference rather
    than surfacing as an unexplained 500."""
    response = client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"topic_sequencing": "alphabetical_order"}},
    )

    assert response.status_code == 422
    assert (
        response.json()["error"]["details"][0]["field"]
        == "body.planning_preferences.topic_sequencing"
    )
    assert stored_preferences(session) == (None, None)
