"""Contract tests for topic-note retrieval (RES-013).

These run over the real application factory and the real use case, with only the
repositories replaced, so they exercise routing, validation, response mapping,
and error mapping over the code the running backend uses. The database
counterpart is tests/integration/test_note_search_api.py, which proves the
full-text search itself.

The route-ordering test below is load-bearing: `/resource-notes/search` sits
under the same prefix as `/resource-notes/{note_id}`, and a path parameter
matches any segment before it is validated as a UUID.
"""

import uuid

RESOURCES = "/api/v1/resources"
SEARCH = "/api/v1/resource-notes/search"


def register(client, topic_ids, **fields):
    body = {
        "resource_type": "note",
        "title": "Operating Systems notes",
        "source_label": "Blue binder",
        "topic_ids": [str(topic_id) for topic_id in topic_ids],
    }
    body.update(fields)
    response = client.post(RESOURCES, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def write_note(client, resource_id, *, title="Scheduling", body="Round robin scheduling."):
    response = client.post(f"{RESOURCES}/{resource_id}/notes", json={"title": title, "body": body})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def search(client, topic_id):
    return client.get(SEARCH, params={"topic_id": str(topic_id)})


# -- routing ------------------------------------------------------------------


def test_the_search_path_is_not_captured_by_the_note_by_identifier_route(
    resource_client, cataloguing
):
    """`/resource-notes/search` must reach the search, not `/{note_id}`.

    Starlette matches a path parameter against any segment and validates it as a
    UUID only afterwards, so the wrong order would surface as a 422 about a
    malformed identifier rather than as a route that never ran.
    """
    response = search(resource_client, cataloguing.topic.id)

    assert response.status_code == 200, response.text
    assert "topic_id" in response.json()["data"]


# -- what comes back ----------------------------------------------------------


def test_a_matching_passage_names_where_it_came_from(resource_client, cataloguing):
    resource = register(resource_client, [cataloguing.topic.id])
    note = write_note(resource_client, resource["id"], body="Round robin scheduling is fair.")

    data = search(resource_client, cataloguing.topic.id).json()["data"]

    assert data["outcome"] == "found"
    assert len(data["passages"]) == 1
    passage = data["passages"][0]
    assert passage["note_id"] == note["id"]
    assert passage["note_title"] == "Scheduling"
    assert passage["resource_id"] == resource["id"]
    assert passage["resource_title"] == "Operating Systems notes"
    assert passage["resource_type"] == "note"
    assert passage["topic_name"] == "CPU scheduling"
    assert passage["subject_name"] == "Operating Systems"
    assert "Round robin scheduling" in passage["passage"]


def test_the_response_carries_no_relevance_figure(resource_client, cataloguing):
    """Relevance decided the order and nothing else."""
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"])

    body = search(resource_client, cataloguing.topic.id).text

    for forbidden in ("rank", "score", "relevance", "similarity", "confidence"):
        assert forbidden not in body


def test_the_response_carries_no_count_of_the_learners_notes(resource_client, cataloguing):
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"])

    data = search(resource_client, cataloguing.topic.id).json()["data"]

    assert "total" not in data
    assert "count" not in data
    assert "pagination" not in search(resource_client, cataloguing.topic.id).json()


def test_a_passage_is_an_exact_substring_of_the_stored_note(resource_client, cataloguing):
    """The fidelity guarantee, over the wire.

    Nothing between the database and the response renders, escapes, highlights,
    or re-encodes a learner's text.
    """
    resource = register(resource_client, [cataloguing.topic.id])
    body = "Scheduling uses std::vector<int> for the queue, and a < b decides order."
    written = write_note(resource_client, resource["id"], body=body)

    passage = search(resource_client, cataloguing.topic.id).json()["data"]["passages"][0]

    assert passage["passage"] in body
    assert "vector<int>" in passage["passage"]
    assert "a < b" in passage["passage"]
    assert passage["note_id"] == written["id"]


def test_code_like_text_survives_the_whole_round_trip(resource_client, cataloguing):
    """`vector<int>` is the case that made this rewrite necessary.

    An earlier build rendered the passage with `ts_headline`, whose parser reads
    `<int>` as an HTML tag and drops it.
    """
    resource = register(resource_client, [cataloguing.topic.id])
    body = "Scheduling: ready queue is vector<int>, and <em>not</em> a list."
    write_note(resource_client, resource["id"], body=body)

    response = search(resource_client, cataloguing.topic.id)
    passage = response.json()["data"]["passages"][0]["passage"]

    assert "vector<int>" in passage
    assert "<em>not</em>" in passage
    # Angle brackets are JSON data, so they are neither escaped nor stripped.
    assert "&lt;" not in response.text


def test_a_passage_carries_no_markup_of_its_own(resource_client, cataloguing):
    """No highlighting is added, so a learner's own tags are all there is."""
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"], body="Scheduling <b>matters</b> a lot.")

    passage = search(resource_client, cataloguing.topic.id).json()["data"]["passages"][0]

    assert "<b>matters</b>" in passage["passage"]
    assert "<b>Scheduling</b>" not in passage["passage"]


def test_searching_leaves_the_stored_note_byte_for_byte(resource_client, cataloguing):
    resource = register(resource_client, [cataloguing.topic.id])
    body = "Scheduling with vector<int> and <b>bold</b> markup."
    note = write_note(resource_client, resource["id"], body=body)

    search(resource_client, cataloguing.topic.id)
    search(resource_client, cataloguing.topic.id)

    read_back = resource_client.get(f"/api/v1/resource-notes/{note['id']}").json()["data"]
    assert read_back["body"] == body
    assert read_back == note


# -- the three empty answers --------------------------------------------------


def test_no_linked_material_says_so(resource_client, cataloguing):
    data = search(resource_client, cataloguing.topic.id).json()["data"]

    assert data["outcome"] == "no_linked_material"
    assert data["passages"] == []


def test_linked_material_with_no_notes_says_so(resource_client, cataloguing):
    register(resource_client, [cataloguing.topic.id])

    data = search(resource_client, cataloguing.topic.id).json()["data"]

    assert data["outcome"] == "no_active_notes"


def test_notes_that_mention_nothing_say_so(resource_client, cataloguing):
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"], title="Groceries", body="Milk and bread.")

    data = search(resource_client, cataloguing.topic.id).json()["data"]

    assert data["outcome"] == "no_matching_passage"


def test_a_note_put_aside_drops_out_of_the_search(resource_client, cataloguing):
    resource = register(resource_client, [cataloguing.topic.id])
    note = write_note(resource_client, resource["id"])
    resource_client.patch(f"/api/v1/resource-notes/{note['id']}", json={"status": "archived"})

    data = search(resource_client, cataloguing.topic.id).json()["data"]

    assert data["outcome"] == "no_active_notes"


def test_material_put_aside_drops_out_of_the_search(resource_client, cataloguing):
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"])
    resource_client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    data = search(resource_client, cataloguing.topic.id).json()["data"]

    assert data["outcome"] == "no_linked_material"


# -- refusals -----------------------------------------------------------------


def test_an_unknown_topic_is_not_found(resource_client, cataloguing):
    response = search(resource_client, uuid.uuid4())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_missing_topic_parameter_is_refused(resource_client):
    response = resource_client.get(SEARCH)

    assert response.status_code == 422


def test_a_malformed_topic_parameter_is_refused(resource_client):
    response = resource_client.get(SEARCH, params={"topic_id": "not-a-uuid"})

    assert response.status_code == 422


def test_no_note_text_appears_in_any_refusal(resource_client, cataloguing):
    """The rule that matters most where the data is a learner's study material."""
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"], body="s3cret-study-note about scheduling")

    for response in (
        search(resource_client, uuid.uuid4()),
        resource_client.get(SEARCH, params={"topic_id": "not-a-uuid"}),
        resource_client.get(SEARCH),
    ):
        assert "s3cret-study-note" not in response.text


# -- what the endpoint does not do --------------------------------------------


def test_the_search_accepts_no_free_text_query(resource_client, cataloguing):
    """The topic is the query. A typed query is a different feature."""
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"])

    with_query = resource_client.get(
        SEARCH, params={"topic_id": str(cataloguing.topic.id), "q": "scheduling"}
    )

    # An unknown query parameter is ignored rather than honoured: the answer is
    # the same as without it.
    assert with_query.status_code == 200
    assert with_query.json() == search(resource_client, cataloguing.topic.id).json()


def test_the_search_accepts_no_learner_identifier(resource_client, cataloguing):
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"])

    response = resource_client.get(
        SEARCH, params={"topic_id": str(cataloguing.topic.id), "learner_id": str(uuid.uuid4())}
    )

    assert response.status_code == 200
    assert response.json() == search(resource_client, cataloguing.topic.id).json()


def test_searching_writes_nothing(resource_client, cataloguing):
    resource = register(resource_client, [cataloguing.topic.id])
    note = write_note(resource_client, resource["id"])
    before = resource_client.get(f"/api/v1/resource-notes/{note['id']}").json()["data"]

    search(resource_client, cataloguing.topic.id)
    search(resource_client, cataloguing.topic.id)

    after = resource_client.get(f"/api/v1/resource-notes/{note['id']}").json()["data"]
    assert after == before
    assert resource_client.get(f"{RESOURCES}/{resource['id']}").json()["data"] == resource


def test_the_search_is_read_only_over_http(resource_client, cataloguing):
    """No verb but GET reaches it, and none of them can remove anything.

    `DELETE` no longer answers `405`: RES-019 added
    `DELETE /resource-notes/{note_id}`, and `search` is matched against that path
    parameter before it is validated. It is refused as a malformed identifier, so
    the search path still cannot be written to or deleted through — the outcome
    this test exists for.
    """
    for method in (resource_client.post, resource_client.put):
        assert method(SEARCH).status_code == 405
    assert resource_client.delete(SEARCH).status_code == 422


def test_retrieval_itself_still_answers_nothing(resource_client, cataloguing):
    """RES-013 retrieves and does not answer, which MNT-001 has not changed.

    MNT-001 now exists and asks a model — on its own route, through its own use
    case. This endpoint gained nothing from it: no answer, no generated text, and
    no field that could carry one. The mentor's own contract is covered by
    tests/api/test_mentor.py.

    MNT-002 stays unimplemented.
    """
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"])

    data = search(resource_client, cataloguing.topic.id).json()["data"]

    assert set(data) == {"topic_id", "topic_name", "subject_name", "outcome", "passages"}
    assert "answer" not in data
    assert resource_client.get("/api/v1/mentor/availability").status_code == 404


def test_asking_twice_returns_the_same_answer(resource_client, cataloguing):
    resource = register(resource_client, [cataloguing.topic.id])
    write_note(resource_client, resource["id"])

    first = search(resource_client, cataloguing.topic.id).json()
    second = search(resource_client, cataloguing.topic.id).json()

    assert first == second
