"""Contract tests for the resource-note endpoints (RES-009 to RES-012).

These run over the real application factory and the real use case, with only the
repositories replaced, so they exercise routing, validation, response mapping,
and error mapping over the code the running backend uses. The database
counterpart is tests/integration/test_resource_note_api.py.

The privacy rules this feature rests on are asserted here as well as in the
use-case tests, because the endpoint is where they can actually be observed: a
learner's own text must not come back in a refusal, and nothing here may send it
anywhere.
"""

import uuid

RESOURCES = "/api/v1/resources"
NOTES = "/api/v1/resource-notes"


def register(client, **fields):
    body = {"resource_type": "note", "title": "Notes", "source_label": "Blue binder"}
    body.update(fields)
    return client.post(RESOURCES, json=body).json()["data"]


def write_note(client, resource_id, **fields):
    body = {"title": "Deadlock conditions", "body": "Mutual exclusion, hold and wait."}
    body.update(fields)
    return client.post(f"{RESOURCES}/{resource_id}/notes", json=body)


def change_note(client, note_id, **fields):
    return client.patch(f"{NOTES}/{note_id}", json=fields)


# -- writing ------------------------------------------------------------------


def test_writing_a_note_returns_it_under_the_data_envelope(resource_client):
    resource = register(resource_client)

    response = write_note(resource_client, resource["id"])

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Deadlock conditions"
    assert data["body"] == "Mutual exclusion, hold and wait."
    assert data["resource_id"] == resource["id"]
    assert data["status"] == "active"


def test_a_note_carries_no_learner_identifier_and_none_is_accepted(resource_client):
    """No request accepts a learner_id; the effective learner is resolved server-side."""
    resource = register(resource_client)

    accepted = write_note(resource_client, resource["id"]).json()["data"]
    rejected = resource_client.post(
        f"{RESOURCES}/{resource['id']}/notes",
        json={"title": "A title", "body": "Some text.", "learner_id": "whoever"},
    )

    assert "learner_id" not in accepted
    assert "owner_learner_id" not in accepted
    assert rejected.status_code == 422


def test_pasted_text_comes_back_exactly_as_it_was_sent(resource_client):
    """The whole promise of the feature, asserted over the wire.

    Line breaks, blank lines, and indentation survive the round trip. Only
    surrounding whitespace is removed.
    """
    resource = register(resource_client)
    pasted = "Banker's algorithm:\n\n    1. Request\n    2. Check safe state\n\nSee p. 42."

    data = write_note(resource_client, resource["id"], body=f"\n{pasted}\n  ").json()["data"]

    assert data["body"] == pasted


def test_carriage_returns_are_canonicalised_over_the_wire(resource_client):
    """A form posted with JavaScript disabled delivers CRLF; the store sees LF.

    Without this the same note would come back differently depending on whether
    the browser ran JavaScript.
    """
    resource = register(resource_client)

    data = write_note(resource_client, resource["id"], body="A.\r\n\r\nB.\rC.").json()["data"]

    assert data["body"] == "A.\n\nB.\nC."


def test_markup_in_a_note_is_stored_as_the_text_it_is(resource_client):
    """Nothing here parses, renders, or sanitises a note: it is plain text.

    The frontend renders it as text too, so a pasted tag is something a learner
    reads rather than something a browser runs. Storing it unchanged is what
    keeps the learner's own material intact; the rendering rule is what keeps it
    safe.
    """
    resource = register(resource_client)
    pasted = "<script>alert('x')</script> and **not bold** and <b>not bold either</b>"

    data = write_note(resource_client, resource["id"], body=pasted).json()["data"]

    assert data["body"] == pasted


def test_a_note_against_material_that_is_not_the_learners_is_not_found(resource_client):
    response = write_note(resource_client, uuid.uuid4())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_note_cannot_be_written_against_material_that_is_put_aside(resource_client):
    resource = register(resource_client)
    resource_client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    response = write_note(resource_client, resource["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_a_note_with_no_text_is_refused(resource_client):
    resource = register(resource_client)

    response = resource_client.post(
        f"{RESOURCES}/{resource['id']}/notes", json={"title": "A title", "body": ""}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_note_of_only_whitespace_is_refused_by_the_use_case(resource_client):
    resource = register(resource_client)

    response = write_note(resource_client, resource["id"], body="   \n\t  ")

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "missing_note_body"


def test_a_note_longer_than_the_bound_is_refused_and_never_echoed(resource_client):
    """docs/api/conventions.md forbids echoing a rejected value.

    This is the field where that matters most: the value is the learner's own
    study material, and a refusal that quoted it would put it in a log, a proxy
    trace, and a browser console.
    """
    resource = register(resource_client)
    secret = "s3cret-study-note " * 2000

    response = write_note(resource_client, resource["id"], body=secret)
    body = response.text

    assert response.status_code == 422
    assert "s3cret-study-note" not in body


def test_a_rejected_title_is_not_echoed_either(resource_client):
    resource = register(resource_client)

    response = write_note(resource_client, resource["id"], title="t" * 400)

    assert response.status_code == 422
    assert "tttt" not in response.text


def test_an_unknown_field_is_rejected_rather_than_ignored(resource_client):
    resource = register(resource_client)

    response = write_note(resource_client, resource["id"], embedding=[0.1, 0.2])

    assert response.status_code == 422


def test_a_note_cannot_be_created_already_put_aside(resource_client):
    """Status is not a creation field, as it is not for a resource or a plan item."""
    resource = register(resource_client)

    response = write_note(resource_client, resource["id"], status="archived")

    assert response.status_code == 422


# -- listing ------------------------------------------------------------------


def test_notes_are_listed_newest_first_with_a_pagination_block(resource_client):
    resource = register(resource_client)
    write_note(resource_client, resource["id"], title="First")
    write_note(resource_client, resource["id"], title="Second")

    body = resource_client.get(f"{RESOURCES}/{resource['id']}/notes").json()

    assert [note["title"] for note in body["data"]] == ["Second", "First"]
    assert body["pagination"] == {"limit": 25, "offset": 0, "total": 2}


def test_listing_can_be_narrowed_to_one_status(resource_client):
    resource = register(resource_client)
    kept = write_note(resource_client, resource["id"], title="Kept").json()["data"]
    aside = write_note(resource_client, resource["id"], title="Aside").json()["data"]
    change_note(resource_client, aside["id"], status="archived")

    active = resource_client.get(f"{RESOURCES}/{resource['id']}/notes?status=active").json()

    assert [note["id"] for note in active["data"]] == [kept["id"]]


def test_an_unknown_status_filter_is_refused(resource_client):
    resource = register(resource_client)

    response = resource_client.get(f"{RESOURCES}/{resource['id']}/notes?status=indexed")

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "query.status"


def test_listing_notes_of_unknown_material_is_not_found(resource_client):
    response = resource_client.get(f"{RESOURCES}/{uuid.uuid4()}/notes")

    assert response.status_code == 404


def test_the_notes_of_material_put_aside_are_still_listed(resource_client):
    resource = register(resource_client)
    write_note(resource_client, resource["id"], title="Still here")
    resource_client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    body = resource_client.get(f"{RESOURCES}/{resource['id']}/notes").json()

    assert [note["title"] for note in body["data"]] == ["Still here"]


# -- reading and correcting ---------------------------------------------------


def test_one_note_is_read_back_by_its_own_identifier(resource_client):
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"]).json()["data"]

    data = resource_client.get(f"{NOTES}/{written['id']}").json()["data"]

    assert data == written


def test_an_unknown_note_is_not_found(resource_client):
    response = resource_client.get(f"{NOTES}/{uuid.uuid4()}")

    assert response.status_code == 404


def test_a_note_is_corrected_in_place_and_keeps_its_identifier(resource_client):
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"], body="First draft.").json()["data"]

    corrected = change_note(resource_client, written["id"], body="Second draft.").json()["data"]

    assert corrected["id"] == written["id"]
    assert corrected["body"] == "Second draft."
    assert corrected["title"] == written["title"]


def test_a_correction_can_be_made_more_than_once(resource_client):
    """Where a note differs from a practice question ADR-035 fixes after a quiz."""
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"]).json()["data"]

    change_note(resource_client, written["id"], body="Second.")
    third = change_note(resource_client, written["id"], body="Third.")

    assert third.status_code == 200
    assert third.json()["data"]["body"] == "Third."


def test_putting_a_note_aside_is_reversible(resource_client):
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"], body="Worth keeping.").json()["data"]

    aside = change_note(resource_client, written["id"], status="archived").json()["data"]
    back = change_note(resource_client, written["id"], status="active").json()["data"]

    assert aside["status"] == "archived"
    assert back["status"] == "active"
    assert back["body"] == "Worth keeping."


def test_a_note_can_be_removed_permanently(resource_client):
    """RES-019 — the deliberate exception to "nothing is destroyed"."""
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"]).json()["data"]

    removed = resource_client.delete(f"{NOTES}/{written['id']}")

    assert removed.status_code == 204, removed.text
    assert removed.content == b""
    assert resource_client.get(f"{NOTES}/{written['id']}").status_code == 404


def test_removing_the_same_note_twice_is_a_404(resource_client):
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"]).json()["data"]

    assert resource_client.delete(f"{NOTES}/{written['id']}").status_code == 204
    assert resource_client.delete(f"{NOTES}/{written['id']}").status_code == 404


def test_a_note_on_archived_material_cannot_be_removed(resource_client):
    """Archived material is read-only, and deletion is no exception."""
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"]).json()["data"]
    resource_client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    assert resource_client.delete(f"{NOTES}/{written['id']}").status_code == 409


def test_no_endpoint_removes_every_note_at_once(resource_client):
    """One note at a time: there is no bulk delete."""
    resource = register(resource_client)

    assert resource_client.delete(f"{RESOURCES}/{resource['id']}/notes").status_code == 405


def test_an_update_naming_nothing_is_refused(resource_client):
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"]).json()["data"]

    response = change_note(resource_client, written["id"])

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "empty_update"


def test_no_field_of_a_note_may_be_cleared(resource_client):
    """A note always has a title, a body, and a status."""
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"]).json()["data"]

    for field in ("title", "body", "status"):
        assert change_note(resource_client, written["id"], **{field: None}).status_code == 422


def test_an_unknown_status_is_refused(resource_client):
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"]).json()["data"]

    response = change_note(resource_client, written["id"], status="ready")

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.status"


def test_a_note_cannot_be_changed_while_its_material_is_put_aside(resource_client):
    resource = register(resource_client)
    written = write_note(resource_client, resource["id"]).json()["data"]
    resource_client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    response = change_note(resource_client, written["id"], body="Corrected.")

    assert response.status_code == 409


def test_a_note_cannot_be_moved_to_another_resource(resource_client):
    resource = register(resource_client)
    other = register(resource_client, title="Somewhere else")
    written = write_note(resource_client, resource["id"]).json()["data"]

    response = change_note(resource_client, written["id"], resource_id=other["id"])

    assert response.status_code == 422


# -- what these endpoints do not do -------------------------------------------


def test_no_ingestion_or_retrieval_endpoint_exists(resource_client):
    """RES-005 to RES-008 are still unimplemented, and nothing searches notes."""
    resource = register(resource_client)

    assert resource_client.post(f"{RESOURCES}/{resource['id']}/ingestions").status_code == 404
    assert resource_client.get(f"{RESOURCES}/{resource['id']}/ingestions").status_code == 404
    assert resource_client.get("/api/v1/resource-notes?query=deadlock").status_code == 404
    assert resource_client.get(f"{NOTES}/search?q=deadlock").status_code in (404, 422)


def test_writing_a_note_leaves_the_resource_untouched(resource_client):
    """Only the note moves: no resource, no topic link, no stage, no plan."""
    resource = register(resource_client)

    write_note(resource_client, resource["id"])

    assert resource_client.get(f"{RESOURCES}/{resource['id']}").json()["data"] == resource


# -- removing the whole resource (RES-005) ------------------------------------


def test_removing_a_resource_takes_its_notes(resource_client):
    """RES-005's cascade reaches notes as well as files. See ADR-042."""
    resource = register(resource_client)
    first = write_note(resource_client, resource["id"], title="First").json()["data"]
    second = write_note(resource_client, resource["id"], title="Second").json()["data"]

    removed = resource_client.delete(f"{RESOURCES}/{resource['id']}")

    assert removed.status_code == 204, removed.text
    assert resource_client.get(f"{NOTES}/{first['id']}").status_code == 404
    assert resource_client.get(f"{NOTES}/{second['id']}").status_code == 404
    assert resource_client.get(f"{RESOURCES}/{resource['id']}").status_code == 404


def test_an_archived_note_on_a_removed_resource_goes_too(resource_client):
    resource = register(resource_client)
    note = write_note(resource_client, resource["id"]).json()["data"]
    change_note(resource_client, note["id"], status="archived")

    resource_client.delete(f"{RESOURCES}/{resource['id']}")

    assert resource_client.get(f"{NOTES}/{note['id']}").status_code == 404


def test_removing_one_resource_leaves_another_resources_notes(resource_client):
    keep = register(resource_client, title="Keep")
    drop = register(resource_client, title="Drop")
    kept = write_note(resource_client, keep["id"], title="Kept note").json()["data"]
    write_note(resource_client, drop["id"], title="Doomed note")

    resource_client.delete(f"{RESOURCES}/{drop['id']}")

    assert resource_client.get(f"{NOTES}/{kept['id']}").status_code == 200
    listed = resource_client.get(f"{RESOURCES}/{keep['id']}/notes").json()["data"]
    assert [n["title"] for n in listed] == ["Kept note"]
