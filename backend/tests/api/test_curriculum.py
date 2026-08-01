"""API tests for the curriculum endpoints (CUR-001 to CUR-003).

They check the public contract: the `data` envelope, `snake_case` fields, UUID
string identifiers, the pagination block, and the documented error responses.
"""

import uuid

CURRICULUM = "/api/v1/curriculum"


# -- CUR-001: list learning programs ---------------------------------------


def test_listing_programs_returns_them_under_the_data_envelope(curriculum_client, curriculum):
    response = curriculum_client.get(f"{CURRICULUM}/programs")

    assert response.status_code == 200
    body = response.json()
    assert [program["code"] for program in body["data"]] == ["gate-cse"]
    assert body["data"][0]["id"] == str(curriculum.program.id)


def test_listing_programs_reports_the_active_curriculum_version(curriculum_client, curriculum):
    body = curriculum_client.get(f"{CURRICULUM}/programs").json()

    active = body["data"][0]["active_curriculum_version"]
    assert active["id"] == str(curriculum.version.id)
    assert active["version_label"] == "2027"
    assert active["status"] == "active"


def test_listing_programs_reports_the_applied_window_and_the_total(curriculum_client):
    body = curriculum_client.get(f"{CURRICULUM}/programs").json()

    assert body["pagination"] == {"limit": 25, "offset": 0, "total": 1}


def test_listing_programs_honours_an_explicit_window(curriculum_client):
    body = curriculum_client.get(f"{CURRICULUM}/programs?limit=5&offset=1").json()

    assert body["data"] == []
    assert body["pagination"] == {"limit": 5, "offset": 1, "total": 1}


def test_listing_programs_rejects_a_window_outside_the_supported_bounds(curriculum_client):
    for query in ("limit=0", "limit=101", "offset=-1"):
        response = curriculum_client.get(f"{CURRICULUM}/programs?{query}")

        assert response.status_code == 422, query
        assert response.json()["error"]["code"] == "validation_error"


def test_listing_programs_exposes_no_persistence_detail(curriculum_client):
    """A response is a public contract, never a rendering of a table row."""
    program = curriculum_client.get(f"{CURRICULUM}/programs").json()["data"][0]

    assert set(program) == {
        "id",
        "code",
        "name",
        "description",
        "active_curriculum_version",
    }


# -- CUR-002: read one learning program ------------------------------------


def test_reading_a_program_returns_it_under_the_data_envelope(curriculum_client, curriculum):
    response = curriculum_client.get(f"{CURRICULUM}/programs/{curriculum.program.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["code"] == "gate-cse"
    assert data["active_curriculum_version"]["id"] == str(curriculum.version.id)


def test_reading_an_unknown_program_returns_the_documented_not_found_error(curriculum_client):
    response = curriculum_client.get(f"{CURRICULUM}/programs/{uuid.uuid4()}")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["details"] == []


def test_reading_a_program_rejects_an_identifier_that_is_not_a_uuid(curriculum_client):
    response = curriculum_client.get(f"{CURRICULUM}/programs/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# -- CUR-003: read a curriculum tree ---------------------------------------


def test_tree_returns_subjects_with_nested_subtopics(curriculum_client, curriculum):
    response = curriculum_client.get(f"{CURRICULUM}/versions/{curriculum.version.id}/tree")

    assert response.status_code == 200
    data = response.json()["data"]
    subject = data["subjects"][0]
    assert subject["code"] == "databases"
    topic = subject["topics"][0]
    assert topic["name"] == "Relational model"
    assert topic["is_trackable"] is False
    assert [child["name"] for child in topic["subtopics"]] == ["SQL"]
    assert topic["subtopics"][0]["is_trackable"] is True


def test_tree_reports_the_curriculum_version_it_describes(curriculum_client, curriculum):
    data = curriculum_client.get(f"{CURRICULUM}/versions/{curriculum.version.id}/tree").json()[
        "data"
    ]

    version = data["curriculum_version"]
    assert version["id"] == str(curriculum.version.id)
    assert version["learning_program_id"] == str(curriculum.program.id)
    assert version["published_at"].startswith("2026-07-31T12:00:00")


def test_tree_reports_topic_relationships_beside_the_hierarchy(curriculum_client, curriculum):
    data = curriculum_client.get(f"{CURRICULUM}/versions/{curriculum.version.id}/tree").json()[
        "data"
    ]

    assert data["topic_relationships"] == [
        {
            "source_topic_id": str(curriculum.parent_topic.id),
            "target_topic_id": str(curriculum.subtopic.id),
            "relationship_type": "prerequisite",
        }
    ]


def test_reading_an_unknown_curriculum_version_returns_not_found(curriculum_client):
    response = curriculum_client.get(f"{CURRICULUM}/versions/{uuid.uuid4()}/tree")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# -- versioning ------------------------------------------------------------


def test_curriculum_endpoints_are_served_only_under_the_versioned_path(curriculum_client):
    assert curriculum_client.get("/curriculum/programs").status_code == 404
