"""Contract tests for the checkpoint-practice endpoints (QZ-001 to QZ-010).

These run over the real application factory and the real use cases, with only the
repositories replaced, so they exercise routing, validation, response mapping,
and error mapping over the code the running backend uses. The database
counterpart is tests/integration/test_checkpoint_practice_api.py.

Two rules are asserted here as well as in the use-case tests, because they are
properties of the **HTTP contract** rather than of the rule behind it:

- **QZ-002 never sends an expected answer**, so a quiz open in a browser cannot
  be read for its answers.
- **No response carries a score**, a total, a count of correct answers, or a
  percentage, which is what docs/domain/terminology.md forbids and ADR-033
  records.
"""

import uuid

QUESTIONS = "/api/v1/practice-questions"
QUIZZES = "/api/v1/checkpoint-quizzes"
ATTEMPTS = "/api/v1/quiz-attempts"

SCORE_FIELDS = {
    "score",
    "max_score",
    "marks",
    "max_marks",
    "awarded_marks",
    "correct_count",
    "incorrect_count",
    "percent",
    "accuracy_percent",
    "total_correct",
}


def field_names(payload) -> set[str]:
    """Every key appearing anywhere in a JSON payload."""
    if isinstance(payload, dict):
        return set(payload) | {name for value in payload.values() for name in field_names(value)}
    if isinstance(payload, list):
        return {name for item in payload for name in field_names(item)}
    return set()


def write(client, practising, **fields):
    body = {
        "prompt": "How many bits address 1 KiB?",
        "options": ["8", "10", "16", "1024"],
        "correct_option_index": 1,
        "explanation": "1 KiB is 2^10 bytes, so ten bits address it.",
        "topic_ids": [str(practising.topic.id)],
    }
    body.update(fields)
    return client.post(QUESTIONS, json=body)


def assemble(client, practising, topic_ids=None):
    ids = topic_ids or [str(practising.topic.id)]
    return client.post(f"{QUIZZES}/generate", json={"topic_ids": ids})


def taking(client, practising, prompts=("How many bits address 1 KiB?",)):
    """Write the questions named, assemble a quiz, and begin an attempt."""
    for prompt in prompts:
        write(client, practising, prompt=prompt)
    quiz = assemble(client, practising).json()["data"]
    attempt = client.post(f"{QUIZZES}/{quiz['id']}/attempts").json()["data"]
    return quiz, attempt


# -- writing questions --------------------------------------------------------


def test_writing_returns_the_stored_question(practice_client, practising):
    response = write(practice_client, practising)

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["prompt"] == "How many bits address 1 KiB?"
    assert data["status"] == "ready"
    assert data["source_type"] == "curated"


def test_option_keys_are_assigned_by_position(practice_client, practising):
    data = write(practice_client, practising).json()["data"]

    assert [option["key"] for option in data["options"]] == ["a", "b", "c", "d"]
    assert data["expected_option_key"] == "b"


def test_a_written_question_names_the_topics_it_covers(practice_client, practising):
    data = write(practice_client, practising).json()["data"]

    assert [topic["name"] for topic in data["topics"]] == ["CPU scheduling"]
    assert data["topics"][0]["subject_name"] == "Operating Systems"


def test_a_question_may_cover_a_topic_that_only_groups_subtopics(practice_client, practising):
    response = write(practice_client, practising, topic_ids=[str(practising.heading.id)])

    assert response.status_code == 201


def test_a_question_covering_no_topic_is_refused(practice_client, practising):
    response = write(practice_client, practising, topic_ids=[])

    assert response.status_code == 422


def test_a_question_offering_one_option_is_refused(practice_client, practising):
    response = write(practice_client, practising, options=["10"], correct_option_index=0)

    assert response.status_code == 422


def test_two_options_saying_the_same_thing_are_refused(practice_client, practising):
    response = write(practice_client, practising, options=["10", "10"])

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "duplicate_option"


def test_an_expected_answer_naming_no_option_is_refused(practice_client, practising):
    response = write(practice_client, practising, options=["8", "10"], correct_option_index=3)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.correct_option_index"


def test_an_unknown_topic_is_refused(practice_client, practising):
    response = write(practice_client, practising, topic_ids=[str(uuid.uuid4())])

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "unknown_topic"


def test_an_unknown_field_is_rejected_rather_than_ignored(practice_client, practising):
    response = write(practice_client, practising, difficulty="hard")

    assert response.status_code == 422


# -- listing questions --------------------------------------------------------


def test_questions_are_listed_newest_first(practice_client, practising):
    write(practice_client, practising, prompt="First")
    write(practice_client, practising, prompt="Second")

    body = practice_client.get(QUESTIONS).json()

    assert [question["prompt"] for question in body["data"]] == ["Second", "First"]
    assert body["pagination"]["total"] == 2


def test_a_topic_filter_narrows_the_list(practice_client, practising):
    write(practice_client, practising, prompt="Scheduling")
    write(
        practice_client,
        practising,
        prompt="Paging",
        topic_ids=[str(practising.other_topic.id)],
    )

    response = practice_client.get(QUESTIONS, params={"topic_id": str(practising.other_topic.id)})
    body = response.json()

    assert [question["prompt"] for question in body["data"]] == ["Paging"]


def test_an_unknown_status_filter_is_refused(practice_client):
    response = practice_client.get(QUESTIONS, params={"status": "draft"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "unknown_question_status"


# -- retiring a question ------------------------------------------------------


def test_a_question_can_be_retired_and_brought_back(practice_client, practising):
    question_id = write(practice_client, practising).json()["data"]["id"]

    retired = practice_client.patch(f"{QUESTIONS}/{question_id}", json={"status": "retired"})
    restored = practice_client.patch(f"{QUESTIONS}/{question_id}", json={"status": "ready"})

    assert retired.json()["data"]["status"] == "retired"
    assert restored.json()["data"]["status"] == "ready"


def test_a_partly_supplied_correction_is_refused(practice_client, practising):
    """The content travels as one group: a prompt alone could not be interpreted."""
    question_id = write(practice_client, practising).json()["data"]["id"]

    response = practice_client.patch(f"{QUESTIONS}/{question_id}", json={"prompt": "Different"})

    assert response.status_code == 422


# -- correcting a question ----------------------------------------------------


def a_correction(practising, **fields):
    """A whole replacement content group, overridable field by field."""
    body = {
        "prompt": "How many bits address 1 MiB?",
        "options": ["10", "20", "16"],
        "correct_option_index": 1,
        "explanation": "1 MiB is 2^20 bytes.",
        "topic_ids": [str(practising.topic.id)],
    }
    body.update(fields)
    return body


def test_a_question_no_quiz_has_asked_can_be_corrected(practice_client, practising):
    question_id = write(practice_client, practising).json()["data"]["id"]

    response = practice_client.patch(f"{QUESTIONS}/{question_id}", json=a_correction(practising))

    assert response.status_code == 200
    corrected = response.json()["data"]
    assert corrected["prompt"] == "How many bits address 1 MiB?"
    assert [option["text"] for option in corrected["options"]] == ["10", "20", "16"]
    assert corrected["expected_option_key"] == "b"
    assert corrected["id"] == question_id


def test_a_correction_replaces_the_topics_the_question_covers(practice_client, practising):
    question_id = write(practice_client, practising).json()["data"]["id"]

    response = practice_client.patch(
        f"{QUESTIONS}/{question_id}",
        json=a_correction(practising, topic_ids=[str(practising.other_topic.id)]),
    )

    assert [topic["id"] for topic in response.json()["data"]["topics"]] == [
        str(practising.other_topic.id)
    ]


def test_a_correction_leaving_out_an_explanation_clears_it(practice_client, practising):
    question_id = write(practice_client, practising).json()["data"]["id"]
    body = a_correction(practising)
    del body["explanation"]

    response = practice_client.patch(f"{QUESTIONS}/{question_id}", json=body)

    assert response.json()["data"]["explanation"] is None


def test_a_question_a_quiz_has_asked_cannot_be_corrected(practice_client, practising):
    """A past result was marked against the wording as it then stood."""
    question_id = write(practice_client, practising).json()["data"]["id"]
    assemble(practice_client, practising)

    response = practice_client.patch(f"{QUESTIONS}/{question_id}", json=a_correction(practising))

    assert response.status_code == 409


def test_a_question_a_quiz_has_asked_can_still_be_set_aside(practice_client, practising):
    question_id = write(practice_client, practising).json()["data"]["id"]
    assemble(practice_client, practising)

    response = practice_client.patch(f"{QUESTIONS}/{question_id}", json={"status": "retired"})

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "retired"


def test_a_question_set_aside_cannot_be_corrected_as_it_stands(practice_client, practising):
    question_id = write(practice_client, practising).json()["data"]["id"]
    practice_client.patch(f"{QUESTIONS}/{question_id}", json={"status": "retired"})

    response = practice_client.patch(f"{QUESTIONS}/{question_id}", json=a_correction(practising))

    assert response.status_code == 409


def test_an_empty_update_is_refused(practice_client, practising):
    question_id = write(practice_client, practising).json()["data"]["id"]

    response = practice_client.patch(f"{QUESTIONS}/{question_id}", json={})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "empty_update"


def test_a_question_that_is_not_stored_is_reported_as_missing(practice_client):
    response = practice_client.patch(f"{QUESTIONS}/{uuid.uuid4()}", json={"status": "retired"})

    assert response.status_code == 404


# -- assembling a quiz --------------------------------------------------------


def test_a_quiz_asks_every_ready_question_for_the_chosen_topics(practice_client, practising):
    write(practice_client, practising, prompt="First")
    write(practice_client, practising, prompt="Second")

    response = assemble(practice_client, practising)

    assert response.status_code == 201
    assert [question["prompt"] for question in response.json()["data"]["questions"]] == [
        "First",
        "Second",
    ]


def test_a_quiz_names_the_topics_it_covers(practice_client, practising):
    write(practice_client, practising)

    data = assemble(practice_client, practising).json()["data"]

    assert [topic["name"] for topic in data["topics"]] == ["CPU scheduling"]


def test_a_quiz_for_topics_with_no_questions_is_refused(practice_client, practising):
    response = assemble(practice_client, practising)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "no_questions_for_topics"


def test_a_quiz_covering_no_topic_is_refused(practice_client):
    response = practice_client.post(f"{QUIZZES}/generate", json={"topic_ids": []})

    assert response.status_code == 422


# -- reading a quiz -----------------------------------------------------------


def test_a_quiz_being_taken_never_sends_the_expected_answer(practice_client, practising):
    """The rule QZ-002 exists for: an open quiz cannot be read for its answers."""
    write(practice_client, practising)
    quiz_id = assemble(practice_client, practising).json()["data"]["id"]

    body = practice_client.get(f"{QUIZZES}/{quiz_id}").json()

    assert "expected_option_key" not in field_names(body)
    assert "explanation" not in field_names(body)
    assert "2^10" not in practice_client.get(f"{QUIZZES}/{quiz_id}").text


def test_a_quiz_being_taken_still_sends_its_options(practice_client, practising):
    write(practice_client, practising)
    quiz_id = assemble(practice_client, practising).json()["data"]["id"]

    data = practice_client.get(f"{QUIZZES}/{quiz_id}").json()["data"]

    assert [option["key"] for option in data["questions"][0]["options"]] == ["a", "b", "c", "d"]


def test_a_quiz_that_is_not_stored_is_reported_as_missing(practice_client):
    response = practice_client.get(f"{QUIZZES}/{uuid.uuid4()}")

    assert response.status_code == 404


# -- attempts -----------------------------------------------------------------


def test_starting_an_attempt_returns_it_created(practice_client, practising):
    write(practice_client, practising)
    quiz_id = assemble(practice_client, practising).json()["data"]["id"]

    response = practice_client.post(f"{QUIZZES}/{quiz_id}/attempts")

    assert response.status_code == 201
    assert response.json()["data"]["status"] == "in_progress"


def test_asking_twice_returns_the_attempt_already_open(practice_client, practising):
    write(practice_client, practising)
    quiz_id = assemble(practice_client, practising).json()["data"]["id"]
    first = practice_client.post(f"{QUIZZES}/{quiz_id}/attempts").json()["data"]["id"]

    response = practice_client.post(f"{QUIZZES}/{quiz_id}/attempts")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == first


def test_submitting_marks_each_question(practice_client, practising):
    quiz, attempt = taking(practice_client, practising)
    question_id = quiz["questions"][0]["question_id"]

    response = practice_client.post(
        f"{ATTEMPTS}/{attempt['id']}/submit",
        json={"answers": [{"question_id": question_id, "option_key": "b"}]},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "evaluated"
    assert data["outcomes"][0]["is_correct"] is True


def test_a_marked_result_shows_the_expected_answer_and_the_explanation(practice_client, practising):
    quiz, attempt = taking(practice_client, practising)
    question_id = quiz["questions"][0]["question_id"]

    data = practice_client.post(
        f"{ATTEMPTS}/{attempt['id']}/submit",
        json={"answers": [{"question_id": question_id, "option_key": "a"}]},
    ).json()["data"]

    assert data["outcomes"][0]["is_correct"] is False
    assert data["outcomes"][0]["expected_option_key"] == "b"
    assert "2^10" in data["outcomes"][0]["explanation"]


def test_an_unanswered_question_is_not_a_wrong_one(practice_client, practising):
    _, attempt = taking(practice_client, practising, prompts=("First", "Second"))

    data = practice_client.post(f"{ATTEMPTS}/{attempt['id']}/submit", json={"answers": []}).json()[
        "data"
    ]

    assert [outcome["is_correct"] for outcome in data["outcomes"]] == [None, None]
    assert [outcome["chosen_option_key"] for outcome in data["outcomes"]] == [None, None]


def test_submitting_twice_is_refused(practice_client, practising):
    _, attempt = taking(practice_client, practising)
    practice_client.post(f"{ATTEMPTS}/{attempt['id']}/submit", json={"answers": []})

    response = practice_client.post(f"{ATTEMPTS}/{attempt['id']}/submit", json={"answers": []})

    assert response.status_code == 409


def test_an_answer_naming_a_question_the_quiz_does_not_ask_is_refused(practice_client, practising):
    _, attempt = taking(practice_client, practising)

    response = practice_client.post(
        f"{ATTEMPTS}/{attempt['id']}/submit",
        json={"answers": [{"question_id": str(uuid.uuid4()), "option_key": "a"}]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "unknown_question"


def test_an_option_the_question_does_not_offer_is_refused(practice_client, practising):
    quiz, attempt = taking(practice_client, practising)

    response = practice_client.post(
        f"{ATTEMPTS}/{attempt['id']}/submit",
        json={"answers": [{"question_id": quiz["questions"][0]["question_id"], "option_key": "z"}]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "unknown_option"


def test_an_attempt_in_progress_reveals_no_answers(practice_client, practising):
    _, attempt = taking(practice_client, practising)

    body = practice_client.get(f"{ATTEMPTS}/{attempt['id']}").json()

    assert body["data"]["outcomes"][0]["expected_option_key"] is None
    assert body["data"]["outcomes"][0]["explanation"] is None


def test_attempts_are_listed_with_the_pagination_block(practice_client, practising):
    taking(practice_client, practising)

    body = practice_client.get(ATTEMPTS).json()

    assert body["pagination"]["total"] == 1
    assert body["data"][0]["quiz_title"] == "Practice: CPU scheduling"


def test_an_attempt_that_is_not_stored_is_reported_as_missing(practice_client):
    response = practice_client.get(f"{ATTEMPTS}/{uuid.uuid4()}")

    assert response.status_code == 404


# -- nothing rates the learner ------------------------------------------------


def test_no_response_carries_a_score(practice_client, practising):
    """docs/domain/terminology.md forbids a number that rates the learner."""
    quiz, attempt = taking(practice_client, practising, prompts=("First", "Second"))
    marked = practice_client.post(
        f"{ATTEMPTS}/{attempt['id']}/submit",
        json={"answers": [{"question_id": quiz["questions"][0]["question_id"], "option_key": "b"}]},
    ).json()

    for body in (
        marked,
        practice_client.get(ATTEMPTS).json(),
        practice_client.get(f"{ATTEMPTS}/{attempt['id']}").json(),
        practice_client.get(f"{QUIZZES}/{quiz['id']}").json(),
        practice_client.get(QUESTIONS).json(),
    ):
        assert not field_names(body) & SCORE_FIELDS
