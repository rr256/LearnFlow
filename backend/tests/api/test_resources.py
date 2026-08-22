"""Contract tests for the learning-resource endpoints (RES-001 to RES-004).

These run over the real application factory and the real use case, with only the
repositories replaced, so they exercise routing, validation, response mapping,
and error mapping over the code the running backend uses. The database
counterpart is tests/integration/test_resource_api.py.

The privacy rule this catalogue rests on is asserted here as well as in the
use-case tests, because it is the endpoint that must not return a location on the
learner's own machine: docs/api/endpoints.md requires resource endpoints to
expose safe metadata only.
"""

import uuid

RESOURCES = "/api/v1/resources"


def register(client, **fields):
    body = {"resource_type": "note", "title": "Notes", "source_label": "Blue binder"}
    body.update(fields)
    return client.post(RESOURCES, json=body)


def change(client, resource_id, **fields):
    return client.patch(f"{RESOURCES}/{resource_id}", json=fields)


# -- registering --------------------------------------------------------------


def test_registering_returns_the_stored_resource(resource_client):
    response = register(resource_client, title="Process scheduling notes")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Process scheduling notes"
    assert data["resource_type"] == "note"
    assert data["status"] == "registered"
    assert data["topics"] == []


def test_a_registered_resource_names_the_topics_it_covers(resource_client, cataloguing):
    data = register(resource_client, topic_ids=[str(cataloguing.topic.id)]).json()["data"]

    assert [topic["name"] for topic in data["topics"]] == ["CPU scheduling"]
    assert data["topics"][0]["subject_name"] == "Operating Systems"


def test_a_resource_may_cover_a_topic_that_only_groups_subtopics(resource_client, cataloguing):
    """Where RES-001 differs from PRG-004, which refuses a stage on a heading."""
    response = register(resource_client, topic_ids=[str(cataloguing.heading.id)])

    assert response.status_code == 201


def test_a_web_link_is_stored_as_given(resource_client):
    data = register(resource_client, external_reference="https://example.test/os-notes.pdf").json()[
        "data"
    ]

    assert data["external_reference"] == "https://example.test/os-notes.pdf"


def test_a_local_filesystem_path_is_refused(resource_client):
    """No resource endpoint may return an absolute local path, so none is stored."""
    response = register(resource_client, external_reference="D:\\GATE\\os-notes.pdf")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "body.external_reference"
    assert error["details"][0]["type"] == "unsupported_reference_scheme"


def test_a_rejected_link_is_not_echoed_back(resource_client):
    body = register(resource_client, external_reference="file:///home/asha/notes.pdf").json()

    assert "/home/asha/notes.pdf" not in body["error"]["message"]
    assert "/home/asha/notes.pdf" not in body["error"]["details"][0]["message"]


def test_a_resource_naming_no_location_is_refused(resource_client):
    response = resource_client.post(RESOURCES, json={"resource_type": "note", "title": "Notes"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "missing_location"


def test_a_kind_of_material_this_build_does_not_catalogue_is_refused(resource_client):
    response = register(resource_client, resource_type="attachment")

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.resource_type"


def test_a_topic_that_is_not_stored_is_refused(resource_client):
    response = register(resource_client, topic_ids=[str(uuid.uuid4())])

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "unknown_topic"


def test_a_topic_named_twice_is_refused(resource_client, cataloguing):
    topic_id = str(cataloguing.topic.id)

    response = register(resource_client, topic_ids=[topic_id, topic_id])

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "duplicate_topic"


def test_an_unknown_field_is_refused_rather_than_ignored(resource_client):
    response = register(resource_client, storage_key="uploads/notes.pdf")

    assert response.status_code == 422


def test_a_status_cannot_be_chosen_when_registering(resource_client):
    """Every resource is written `registered`; putting one aside is RES-004."""
    response = register(resource_client, status="archived")

    assert response.status_code == 422


def test_no_learner_identifier_is_accepted(resource_client):
    response = register(resource_client, owner_learner_id=str(uuid.uuid4()))

    assert response.status_code == 422


# -- listing ------------------------------------------------------------------


def test_a_learner_with_no_material_reads_an_empty_page(resource_client):
    body = resource_client.get(RESOURCES).json()

    assert body["data"] == []
    assert body["pagination"] == {"limit": 25, "offset": 0, "total": 0}


def test_listing_returns_the_newest_first(resource_client):
    register(resource_client, title="First")
    register(resource_client, title="Second")

    titles = [item["title"] for item in resource_client.get(RESOURCES).json()["data"]]

    assert titles == ["Second", "First"]


def test_listing_by_topic_finds_the_material_associated_with_it(resource_client, cataloguing):
    register(resource_client, title="Scheduling notes", topic_ids=[str(cataloguing.topic.id)])
    register(resource_client, title="Unlinked notes")

    body = resource_client.get(RESOURCES, params={"topic_id": str(cataloguing.topic.id)}).json()

    assert [item["title"] for item in body["data"]] == ["Scheduling notes"]
    assert body["pagination"]["total"] == 1


def test_listing_by_a_topic_nothing_covers_is_an_empty_page(resource_client):
    register(resource_client)

    body = resource_client.get(RESOURCES, params={"topic_id": str(uuid.uuid4())}).json()

    assert body["data"] == []


def test_an_unknown_type_filter_is_refused(resource_client):
    response = resource_client.get(RESOURCES, params={"resource_type": "scroll"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "query.resource_type"


def test_an_unknown_status_filter_is_refused(resource_client):
    response = resource_client.get(RESOURCES, params={"status": "ready"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "query.status"


def test_a_limit_outside_the_documented_bounds_is_refused(resource_client):
    assert resource_client.get(RESOURCES, params={"limit": 0}).status_code == 422
    assert resource_client.get(RESOURCES, params={"limit": 101}).status_code == 422


# -- reading one --------------------------------------------------------------


def test_reading_one_returns_it_with_its_topics(resource_client, cataloguing):
    registered = register(resource_client, topic_ids=[str(cataloguing.topic.id)]).json()["data"]

    data = resource_client.get(f"{RESOURCES}/{registered['id']}").json()["data"]

    assert data["id"] == registered["id"]
    assert [topic["name"] for topic in data["topics"]] == ["CPU scheduling"]


def test_reading_a_resource_that_is_not_stored_is_a_404(resource_client):
    response = resource_client.get(f"{RESOURCES}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_path_segment_that_is_not_a_uuid_is_refused(resource_client):
    assert resource_client.get(f"{RESOURCES}/not-a-uuid").status_code == 422


# -- changing one -------------------------------------------------------------


def test_a_title_can_be_corrected(resource_client):
    registered = register(resource_client).json()["data"]

    data = change(resource_client, registered["id"], title="Corrected title").json()["data"]

    assert data["title"] == "Corrected title"


def test_archiving_puts_material_aside_and_is_reversible(resource_client):
    registered = register(resource_client).json()["data"]

    archived = change(resource_client, registered["id"], status="archived").json()["data"]
    assert archived["status"] == "archived"

    restored = change(resource_client, registered["id"], status="registered").json()["data"]
    assert restored["status"] == "registered"


def test_an_archived_resource_is_still_stored_and_readable(resource_client):
    registered = register(resource_client).json()["data"]
    change(resource_client, registered["id"], status="archived")

    assert resource_client.get(f"{RESOURCES}/{registered['id']}").status_code == 200
    body = resource_client.get(RESOURCES, params={"status": "archived"}).json()
    assert [item["id"] for item in body["data"]] == [registered["id"]]


def test_a_resource_can_be_removed_permanently(resource_client):
    """RES-005 — the widest destruction in LearnFlow, and the reversal of this
    module's former guard that no way to delete a resource existed. See ADR-042;
    ADR-032's archiving decision is narrowed, not overturned."""
    registered = register(resource_client).json()["data"]

    response = resource_client.delete(f"{RESOURCES}/{registered['id']}")

    assert response.status_code == 204, response.text
    assert response.content == b""
    assert resource_client.get(f"{RESOURCES}/{registered['id']}").status_code == 404


def test_removing_a_resource_that_is_already_gone_is_not_found(resource_client):
    """Asking twice is 204 then 404 — and the same answer a second browser tab
    acting on a stale list receives."""
    registered = register(resource_client).json()["data"]
    assert resource_client.delete(f"{RESOURCES}/{registered['id']}").status_code == 204

    assert resource_client.delete(f"{RESOURCES}/{registered['id']}").status_code == 404


def test_an_archived_resource_can_still_be_removed(resource_client):
    """The one place archived material is not read-only. Shelving and removing
    are different answers, and requiring an archive first would turn the shelf
    into a deletion queue."""
    registered = register(resource_client).json()["data"]
    change(resource_client, registered["id"], status="archived")

    assert resource_client.delete(f"{RESOURCES}/{registered['id']}").status_code == 204


def test_removing_one_resource_leaves_the_others(resource_client):
    """No bulk removal: one request names one resource."""
    register(resource_client, title="Keep")
    drop = register(resource_client, title="Drop").json()["data"]

    assert resource_client.delete(f"{RESOURCES}/{drop['id']}").status_code == 204

    listed = resource_client.get(RESOURCES).json()["data"]
    assert [r["title"] for r in listed] == ["Keep"]


def test_another_learners_resource_cannot_be_removed(resource_client):
    """Reported as missing rather than forbidden: existence is a disclosure."""
    assert (
        resource_client.delete(f"{RESOURCES}/00000000-0000-0000-0000-000000000001").status_code
        == 404
    )


def test_supplying_topics_replaces_the_whole_set(resource_client, cataloguing):
    registered = register(resource_client, topic_ids=[str(cataloguing.topic.id)]).json()["data"]

    data = change(
        resource_client, registered["id"], topic_ids=[str(cataloguing.heading.id)]
    ).json()["data"]

    assert [topic["name"] for topic in data["topics"]] == ["Operating Systems"]


def test_an_empty_topic_list_unlinks_every_topic(resource_client, cataloguing):
    registered = register(resource_client, topic_ids=[str(cataloguing.topic.id)]).json()["data"]

    data = change(resource_client, registered["id"], topic_ids=[]).json()["data"]

    assert data["topics"] == []


def test_omitting_the_topics_leaves_the_links_alone(resource_client, cataloguing):
    registered = register(resource_client, topic_ids=[str(cataloguing.topic.id)]).json()["data"]

    data = change(resource_client, registered["id"], title="Renamed").json()["data"]

    assert [topic["name"] for topic in data["topics"]] == ["CPU scheduling"]


def test_a_null_link_clears_it_when_a_label_remains(resource_client):
    registered = register(resource_client, external_reference="https://example.test/notes").json()[
        "data"
    ]

    data = change(resource_client, registered["id"], external_reference=None).json()["data"]

    assert data["external_reference"] is None
    assert data["source_label"] == "Blue binder"


def test_clearing_the_last_location_is_refused(resource_client):
    registered = register(resource_client).json()["data"]

    response = change(resource_client, registered["id"], source_label=None)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "missing_location"


def test_a_null_title_is_refused_rather_than_treated_as_a_clear(resource_client):
    registered = register(resource_client).json()["data"]

    assert change(resource_client, registered["id"], title=None).status_code == 422


def test_an_update_naming_nothing_is_refused(resource_client):
    registered = register(resource_client).json()["data"]

    response = resource_client.patch(f"{RESOURCES}/{registered['id']}", json={})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "empty_update"


def test_an_ingestion_status_cannot_be_asked_for(resource_client):
    registered = register(resource_client).json()["data"]

    response = change(resource_client, registered["id"], status="ready")

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.status"


def test_changing_a_resource_that_is_not_stored_is_a_404(resource_client):
    assert change(resource_client, uuid.uuid4(), title="New").status_code == 404


# -- learner resolution -------------------------------------------------------


def test_registering_before_setup_is_a_conflict(resource_client, cataloguing):
    cataloguing.learners.learners.clear()

    response = register(resource_client)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_more_than_one_learner_is_refused_rather_than_guessed(resource_client, cataloguing):
    from tests.unit.fake_learner_repository import learner

    cataloguing.learners.add_learner(learner("Ravi"))

    assert resource_client.get(RESOURCES).status_code == 409
