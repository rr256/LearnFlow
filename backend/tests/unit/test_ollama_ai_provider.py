"""What the Ollama adapter sends, and how it reports each way of failing.

**No test here opens a socket.** `urlopen` is replaced throughout, so the suite
runs with nothing installed and nothing listening — which is also what proves the
adapter is reached through one function that can be stubbed, rather than scattered
across the module.

The failure tests exist because the three of them mean three different next steps
for a learner: start Ollama, pull the model, or wait. A test that only checked
"it raised something" would let those collapse.
"""

import io
import json
import urllib.error
import urllib.request

import pytest

from app.application.ports.ai_provider import (
    AIProviderModelMissingError,
    AIProviderTimedOutError,
    AIProviderUnavailableError,
    AIProviderUnusableReplyError,
    GroundedAnswerRequest,
)
from app.infrastructure.providers.ollama_ai_provider import (
    SYSTEM_PROMPT,
    OllamaAIProvider,
    build_prompt,
)

QUESTION = "How does round robin choose the next process?"
PASSAGE = "Round robin gives each process a quantum, then moves it to the back."

request = GroundedAnswerRequest(
    question=QUESTION,
    topic_name="CPU scheduling",
    subject_name="Operating Systems",
    passages=(PASSAGE,),
)


def provider(**overrides) -> OllamaAIProvider:
    """An adapter pointed at a host nothing is listening on."""
    settings = {
        "base_url": "http://127.0.0.1:11434",
        "model": "llama3.1:8b",
        "timeout_seconds": 60.0,
    }
    return OllamaAIProvider(**{**settings, **overrides})


class Reply:
    """A stand-in for the response object `urlopen` yields."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> Reply:
        return self

    def __exit__(self, *_: object) -> bool:
        return False


def answering(monkeypatch, body: object, *, sent: list | None = None):
    """Replace `urlopen` with one that answers, recording what it was given."""
    payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def fake_urlopen(post, timeout=None):
        if sent is not None:
            sent.append((post, timeout))
        return Reply(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def failing(monkeypatch, error: BaseException):
    """Replace `urlopen` with one that raises."""

    def fake_urlopen(post, timeout=None):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


@pytest.fixture
def http_error():
    """Builds HTTP failures with readable bodies, and closes them afterwards.

    **The closing is load-bearing.** `urllib.error.HTTPError` extends
    `tempfile._TemporaryFileWrapper` through `urllib.response.addbase`, so one
    left unclosed raises from its finalizer whenever the collector next runs —
    which `-W error` then reports against whatever test happened to be running at
    that moment, somewhere else in the suite entirely. Closing them here keeps a
    failure attributable to the test that caused it.
    """
    created: list[urllib.error.HTTPError] = []

    def build(code: int, body: str) -> urllib.error.HTTPError:
        error = urllib.error.HTTPError(
            "http://127.0.0.1:11434/api/generate",
            code,
            "error",
            {},  # type: ignore[arg-type]
            io.BytesIO(body.encode("utf-8")),
        )
        created.append(error)
        return error

    yield build

    for error in created:
        error.close()


# -- what is sent -------------------------------------------------------------


def test_the_request_names_the_model_and_asks_for_one_whole_answer(monkeypatch):
    sent: list = []
    answering(monkeypatch, {"response": "It runs each in turn."}, sent=sent)

    provider().generate_answer(request)

    body = json.loads(sent[0][0].data)
    assert body["model"] == "llama3.1:8b"
    assert body["stream"] is False
    assert body["system"] == SYSTEM_PROMPT


def test_the_prompt_carries_the_question_and_the_passages(monkeypatch):
    sent: list = []
    answering(monkeypatch, {"response": "ok"}, sent=sent)

    provider().generate_answer(request)

    prompt = json.loads(sent[0][0].data)["prompt"]
    assert QUESTION in prompt
    assert PASSAGE in prompt
    assert "CPU scheduling" in prompt


def test_the_configured_timeout_reaches_urlopen(monkeypatch):
    sent: list = []
    answering(monkeypatch, {"response": "ok"}, sent=sent)

    provider(timeout_seconds=12.5).generate_answer(request)

    assert sent[0][1] == 12.5


def test_the_endpoint_is_built_without_a_doubled_slash():
    # Pydantic's `AnyHttpUrl` renders a trailing slash, so the adapter has to
    # tolerate one rather than produce `//api/generate`.
    assert provider(base_url="http://127.0.0.1:11434/")._endpoint.endswith("/api/generate")
    assert "//api" not in provider(base_url="http://127.0.0.1:11434/")._endpoint


def test_a_passage_survives_into_the_prompt_character_for_character():
    prompt = build_prompt(
        GroundedAnswerRequest(
            question="What is stored?",
            topic_name="Data structures",
            subject_name="Programming",
            passages=("Use vector<int> when a < b matters.",),
        )
    )

    assert "vector<int>" in prompt
    assert "a < b" in prompt


def test_the_prompt_is_built_from_the_request_fields_and_nothing_else():
    """Every word of the prompt traces to a request field or to fixed scaffolding.

    Asserted by removing the request's own values and the labels this module
    writes, and requiring that what remains holds no content — so a field added
    to the prompt later fails here rather than travelling unnoticed.
    """
    prompt = build_prompt(request)

    remaining = prompt
    for value in (QUESTION, PASSAGE, "CPU scheduling", "Operating Systems"):
        remaining = remaining.replace(value, "")
    for label in ("Topic:", "(subject:", ")", "Passage 1:", "Question:"):
        remaining = remaining.replace(label, "")

    assert remaining.strip() == ""


# -- reading the reply --------------------------------------------------------


def test_the_answer_comes_back_trimmed(monkeypatch):
    answering(monkeypatch, {"response": "  It runs each in turn.\n"})

    assert provider().generate_answer(request) == "It runs each in turn."


def test_an_empty_completion_is_unusable(monkeypatch):
    answering(monkeypatch, {"response": "   "})

    with pytest.raises(AIProviderUnusableReplyError):
        provider().generate_answer(request)


def test_a_missing_response_field_is_unusable(monkeypatch):
    answering(monkeypatch, {"done": True})

    with pytest.raises(AIProviderUnusableReplyError):
        provider().generate_answer(request)


def test_a_reply_that_is_not_json_is_unusable(monkeypatch):
    answering(monkeypatch, b"<html>gateway</html>")

    with pytest.raises(AIProviderUnusableReplyError):
        provider().generate_answer(request)


def test_a_json_reply_that_is_not_an_object_is_unusable(monkeypatch):
    answering(monkeypatch, ["not", "an", "object"])

    with pytest.raises(AIProviderUnusableReplyError):
        provider().generate_answer(request)


# -- how each failure is reported --------------------------------------------


def test_a_refused_connection_means_the_provider_is_unavailable(monkeypatch):
    failing(monkeypatch, urllib.error.URLError(ConnectionRefusedError("refused")))

    with pytest.raises(AIProviderUnavailableError):
        provider().generate_answer(request)


def test_a_timeout_raised_directly_is_reported_as_a_timeout(monkeypatch):
    failing(monkeypatch, TimeoutError("timed out"))

    with pytest.raises(AIProviderTimedOutError):
        provider().generate_answer(request)


def test_a_timeout_wrapped_in_a_url_error_is_reported_as_a_timeout(monkeypatch):
    # How `urlopen` actually surfaces a socket timeout on most platforms.
    failing(monkeypatch, urllib.error.URLError(TimeoutError("timed out")))

    with pytest.raises(AIProviderTimedOutError):
        provider().generate_answer(request)


def test_a_model_that_is_not_installed_is_told_apart_from_an_unreachable_provider(
    monkeypatch, http_error
):
    failing(monkeypatch, http_error(404, '{"error":"model \'llama3.1:8b\' not found"}'))

    with pytest.raises(AIProviderModelMissingError):
        provider().generate_answer(request)


def test_a_404_that_is_not_about_a_model_is_reported_as_unavailable(monkeypatch, http_error):
    failing(monkeypatch, http_error(404, "no such route"))

    with pytest.raises(AIProviderUnavailableError):
        provider().generate_answer(request)


def test_a_server_error_is_reported_as_unavailable(monkeypatch, http_error):
    failing(monkeypatch, http_error(500, "internal"))

    with pytest.raises(AIProviderUnavailableError):
        provider().generate_answer(request)


def test_an_unreadable_error_body_does_not_become_a_second_failure(monkeypatch, http_error):
    broken = http_error(404, "")
    monkeypatch.setattr(broken, "read", _raises_os_error)
    failing(monkeypatch, broken)

    with pytest.raises(AIProviderUnavailableError):
        provider().generate_answer(request)


def _raises_os_error() -> bytes:
    raise OSError("closed")


# -- no learner text escapes --------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.URLError(ConnectionRefusedError("refused")),
        urllib.error.URLError(TimeoutError("timed out")),
        TimeoutError("timed out"),
    ],
)
def test_no_failure_message_carries_the_question_or_a_passage(monkeypatch, failure):
    """The rule that matters most where the data is a learner's own study material."""
    failing(monkeypatch, failure)

    with pytest.raises(Exception) as raised:
        provider().generate_answer(request)

    message = str(raised.value)
    assert QUESTION not in message
    assert PASSAGE not in message


def test_a_failure_body_echoing_the_prompt_is_never_quoted_back(monkeypatch, http_error):
    # Some gateways echo the request. The body is read for a marker and never
    # carried into the message.
    failing(monkeypatch, http_error(400, json.dumps({"error": f"bad prompt: {PASSAGE}"})))

    with pytest.raises(AIProviderUnavailableError) as raised:
        provider().generate_answer(request)

    assert PASSAGE not in str(raised.value)


def test_an_unusable_reply_is_not_quoted_into_the_error(monkeypatch):
    answering(monkeypatch, json.dumps({"response": "", "echo": PASSAGE}).encode("utf-8"))

    with pytest.raises(AIProviderUnusableReplyError) as raised:
        provider().generate_answer(request)

    assert PASSAGE not in str(raised.value)


def test_a_failure_chains_no_cause_that_could_carry_the_request(monkeypatch):
    """`raise ... from None` at every site, so a traceback carries no prompt."""
    failing(monkeypatch, urllib.error.URLError(ConnectionRefusedError("refused")))

    with pytest.raises(AIProviderUnavailableError) as raised:
        provider().generate_answer(request)

    assert raised.value.__cause__ is None


# -- what the system prompt asks for -----------------------------------------


def test_the_system_prompt_forbids_answering_beyond_the_passages():
    lowered = SYSTEM_PROMPT.lower()

    assert "only" in lowered
    assert "do not" in lowered


def test_the_system_prompt_forbids_inventing_a_citation():
    # LearnFlow assembles the citation list; a source named in the prose would be
    # the one thing on the screen that nothing verified.
    assert "do not invent a citation" in SYSTEM_PROMPT.lower()
