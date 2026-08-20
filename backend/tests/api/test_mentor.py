"""Contract tests for the mentor endpoint (MNT-001).

These run over the real application factory and the real use case, with only the
repositories and the AI provider replaced, so they exercise routing, validation,
response mapping, and error mapping over the code the running backend uses.

**No test here reaches a provider.** The fake records what it was asked, which is
how the endpoint's central promise is asserted end to end: a request that found
no passage must leave `study_mentor.requests` empty.
"""

import uuid

from app.application.ports.ai_provider import (
    AIProviderModelMissingError,
    AIProviderTimedOutError,
    AIProviderUnavailableError,
    AIProviderUnusableReplyError,
)

RESOURCES = "/api/v1/resources"
QUESTIONS = "/api/v1/mentor/questions"
QUESTION = "How does round robin decide which process runs next?"


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


def write_note(client, resource_id, *, title="Scheduling", body="Round robin scheduling is fair."):
    response = client.post(f"{RESOURCES}/{resource_id}/notes", json={"title": title, "body": body})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def ask(client, topic_id, question=QUESTION):
    return client.post(QUESTIONS, json={"topic_id": str(topic_id), "question": question})


def grounded(client, cataloguing, *, body="Round robin scheduling is fair."):
    """Material and a note that does mention the topic."""
    resource = register(client, [cataloguing.topic.id])
    note = write_note(client, resource["id"], body=body)
    return resource, note


# -- no evidence, no model call ----------------------------------------------


def test_no_linked_material_answers_without_asking_the_provider(
    mentor_client, cataloguing, study_mentor
):
    response = ask(mentor_client, cataloguing.topic.id)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["outcome"] == "no_linked_material"
    assert data["answer"] is None
    assert data["passages"] == []
    assert study_mentor.was_asked is False


def test_no_matching_passage_answers_without_asking_the_provider(
    mentor_client, cataloguing, study_mentor
):
    resource = register(mentor_client, [cataloguing.topic.id])
    write_note(mentor_client, resource["id"], title="Networks", body="TCP retransmits segments.")

    data = ask(mentor_client, cataloguing.topic.id).json()["data"]

    assert data["outcome"] == "no_matching_passage"
    assert data["answer"] is None
    assert study_mentor.was_asked is False


def test_an_archived_note_is_not_grounds_and_reaches_no_provider(
    mentor_client, cataloguing, study_mentor
):
    resource, note = grounded(mentor_client, cataloguing)
    archived = mentor_client.patch(
        f"/api/v1/resource-notes/{note['id']}", json={"status": "archived"}
    )
    assert archived.status_code == 200, archived.text

    data = ask(mentor_client, cataloguing.topic.id).json()["data"]

    assert data["outcome"] == "no_active_notes"
    assert study_mentor.was_asked is False


# -- an answer ----------------------------------------------------------------


def test_an_answer_carries_the_passages_it_was_grounded_in(
    mentor_client, cataloguing, study_mentor
):
    resource, note = grounded(mentor_client, cataloguing)

    data = ask(mentor_client, cataloguing.topic.id).json()["data"]

    assert data["outcome"] == "answered"
    assert data["answer"] == study_mentor.answer
    assert len(data["passages"]) == 1
    passage = data["passages"][0]
    assert passage["note_id"] == note["id"]
    assert passage["resource_id"] == resource["id"]
    assert passage["resource_title"] == "Operating Systems notes"
    assert passage["topic_name"] == cataloguing.topic.name


def test_the_question_and_topic_are_echoed_back(mentor_client, cataloguing):
    grounded(mentor_client, cataloguing)

    data = ask(mentor_client, cataloguing.topic.id).json()["data"]

    assert data["question"] == QUESTION
    assert data["topic_id"] == str(cataloguing.topic.id)
    assert data["subject_name"] == cataloguing.topic.subject_name


def test_only_the_question_and_passages_reach_the_provider(
    mentor_client, cataloguing, study_mentor
):
    resource, note = grounded(mentor_client, cataloguing)

    ask(mentor_client, cataloguing.topic.id)

    sent = study_mentor.requests[0]
    everything = " ".join((sent.question, sent.topic_name, sent.subject_name, *sent.passages))
    for identifier in (resource["id"], note["id"], str(cataloguing.topic.id)):
        assert identifier not in everything
    assert note["title"] not in everything
    assert resource["title"] not in everything


def test_a_passage_reaches_the_provider_and_the_response_unchanged(mentor_client, cataloguing):
    body = "Queues hold vector<int> and compare a < b."
    grounded(mentor_client, cataloguing, body=body)

    data = ask(mentor_client, cataloguing.topic.id, "What holds the queue?").json()["data"]

    assert "vector<int>" in data["passages"][0]["passage"]
    assert "a < b" in data["passages"][0]["passage"]


def test_no_figure_of_any_kind_appears_in_the_response(mentor_client, cataloguing):
    # No score, no confidence, no relevance, and no count of passages or notes.
    grounded(mentor_client, cataloguing)

    data = ask(mentor_client, cataloguing.topic.id).json()["data"]

    assert set(data) == {
        "topic_id",
        "topic_name",
        "subject_name",
        "question",
        "outcome",
        "answer",
        "passages",
    }
    assert "relevance" not in data["passages"][0]
    assert "score" not in data["passages"][0]


# -- provider failures --------------------------------------------------------


def test_an_unreachable_provider_is_a_200_that_keeps_the_passages(
    mentor_client, cataloguing, study_mentor
):
    """A provider that is switched off must not cost the learner their own notes."""
    _, note = grounded(mentor_client, cataloguing)
    study_mentor.fails_with = AIProviderUnavailableError("off")

    response = ask(mentor_client, cataloguing.topic.id)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["outcome"] == "provider_unavailable"
    assert data["answer"] is None
    assert data["passages"][0]["note_id"] == note["id"]


def test_each_provider_failure_reports_its_own_outcome(mentor_client, cataloguing, study_mentor):
    grounded(mentor_client, cataloguing)

    for failure, expected in (
        (AIProviderModelMissingError("no model"), "provider_unavailable"),
        (AIProviderTimedOutError("slow"), "provider_timed_out"),
        (AIProviderUnusableReplyError("empty"), "provider_unusable_reply"),
    ):
        study_mentor.fails_with = failure
        data = ask(mentor_client, cataloguing.topic.id).json()["data"]
        assert data["outcome"] == expected


def test_a_provider_failure_message_is_not_returned_to_the_caller(
    mentor_client, cataloguing, study_mentor
):
    # The adapter's message can name a host or a model; the contract reports an
    # outcome, and the screen writes its own words from that.
    grounded(mentor_client, cataloguing)
    study_mentor.fails_with = AIProviderUnavailableError("connection refused to 10.0.0.5:11434")

    body = ask(mentor_client, cataloguing.topic.id).text

    assert "10.0.0.5" not in body


# -- refusals -----------------------------------------------------------------


def test_a_blank_question_is_refused(mentor_client, cataloguing, study_mentor):
    grounded(mentor_client, cataloguing)

    response = ask(mentor_client, cataloguing.topic.id, "")

    assert response.status_code == 422, response.text
    assert study_mentor.was_asked is False


def test_a_whitespace_only_question_is_refused(mentor_client, cataloguing, study_mentor):
    # It satisfies `min_length` and is still not a question, so the use case
    # refuses it and the route maps that back to a 422 rather than a 500.
    grounded(mentor_client, cataloguing)

    response = ask(mentor_client, cataloguing.topic.id, "   \n\t ")

    assert response.status_code == 422, response.text
    assert study_mentor.was_asked is False


def test_a_question_beyond_the_limit_is_refused(mentor_client, cataloguing, study_mentor):
    grounded(mentor_client, cataloguing)

    response = ask(mentor_client, cataloguing.topic.id, "x" * 1001)

    assert response.status_code == 422, response.text
    assert study_mentor.was_asked is False


def test_an_unknown_topic_is_a_404(mentor_client, study_mentor):
    response = ask(mentor_client, uuid.uuid4())

    assert response.status_code == 404, response.text
    assert study_mentor.was_asked is False


def test_a_missing_question_field_is_refused(mentor_client, cataloguing):
    response = mentor_client.post(QUESTIONS, json={"topic_id": str(cataloguing.topic.id)})

    assert response.status_code == 422, response.text


def test_the_request_accepts_no_learner_identifier(mentor_client, cataloguing):
    """A caller cannot ask on someone else's behalf; the learner is server-side."""
    grounded(mentor_client, cataloguing)

    response = mentor_client.post(
        QUESTIONS,
        json={
            "topic_id": str(cataloguing.topic.id),
            "question": QUESTION,
            "learner_id": str(uuid.uuid4()),
        },
    )

    # The extra field is ignored rather than honoured: the answer is the local
    # learner's own, exactly as it is without it.
    assert response.status_code == 200, response.text
    assert response.json()["data"]["outcome"] == "answered"


def test_a_caller_cannot_choose_the_model_or_the_provider(mentor_client, cataloguing):
    grounded(mentor_client, cataloguing)

    response = mentor_client.post(
        QUESTIONS,
        json={
            "topic_id": str(cataloguing.topic.id),
            "question": QUESTION,
            "model": "some-other-model",
            "temperature": 2,
        },
    )

    assert response.status_code == 200, response.text


# -- what does not happen -----------------------------------------------------


def test_asking_twice_stores_nothing(mentor_client, cataloguing):
    grounded(mentor_client, cataloguing)

    first = ask(mentor_client, cataloguing.topic.id).json()["data"]
    second = ask(mentor_client, cataloguing.topic.id).json()["data"]

    assert first == second


def test_there_is_no_endpoint_that_reads_a_past_question_back(mentor_client):
    """Nothing is stored, so nothing lists it. A history would be a second feature."""
    assert mentor_client.get(QUESTIONS).status_code == 405
    assert mentor_client.get("/api/v1/mentor/answers").status_code == 404


def test_mentor_availability_is_not_implemented(mentor_client):
    """MNT-002 stays unimplemented: asking a question already reports the provider."""
    assert mentor_client.get("/api/v1/mentor/availability").status_code == 404
