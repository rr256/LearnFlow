"""The Ollama adapter behind `AIProvider`.

**The only file in LearnFlow that makes an outbound request.** Everything vendor-
specific lives here: the URL, the JSON shape, the system prompt, and the mapping
from a transport failure to a named port error. Application code sees the port
and never learns which model answered
([dependency rules](../../../../docs/architecture/dependency-rules.md)).

**It talks to Ollama on this machine** — the provider
[ADR-004](../../../../docs/adr/ADR-004-ollama-local-ai-provider.md) selected —
so in this build the learner's passages reach `localhost` and stop there. No API
key exists anywhere in this file, in configuration, or in the environment,
because a local provider authenticates nothing. That is not an oversight to be
corrected later: a cloud adapter would be a **separate class beside this one**,
added by an explicit decision under ADR-004's own mitigation, and it would bring
its own credential handling with it.

**It uses the standard library.** `urllib.request` is enough for one POST with a
timeout, so this adds **no dependency** to `requirements.txt` — no vendor SDK, no
HTTP client, and nothing that pulls a transitive tree in behind it. A dependency
is a Stop Gate 1 decision, and the cheapest way to respect that gate was not to
need one.

**One attempt, then an honest failure.** There is no retry. A local model that
timed out will usually time out again, and retrying would double a learner's wait
to arrive at the same message; a connection refused means Ollama is not running,
which a second attempt one millisecond later will not change. The three failures
are told apart so the screen can say *start Ollama*, *pull the model*, or *it
took too long* rather than *something went wrong*.

**No learner text ever reaches a log or an error message.** The passages and the
question are written into the request body and nowhere else. Every exception
raised here carries a fixed sentence about the provider — never the prompt, never
a passage, never the reply, and never the response body, which on a failure can
echo the request back. This is `docs/api/conventions.md`'s rule, applied where it
matters most.
"""

import json
import urllib.error
import urllib.request
from typing import Final

from app.application.ports.ai_provider import (
    AIProviderModelMissingError,
    AIProviderTimedOutError,
    AIProviderUnavailableError,
    AIProviderUnusableReplyError,
    GroundedAnswerRequest,
)

SYSTEM_PROMPT: Final = (
    "You are LearnFlow's study mentor. Answer the learner's question using ONLY "
    "the numbered passages below, which are extracts from the learner's own study "
    "notes.\n"
    "\n"
    "Rules:\n"
    "- Use only what the passages state. Do not add facts from your own knowledge, "
    "even if you are confident they are correct.\n"
    "- If the passages do not answer the question, say plainly that the learner's "
    "notes do not cover it. Do not answer anyway.\n"
    "- If the passages partly answer it, answer that part and say which part is "
    "missing.\n"
    "- Do not invent a citation, a source name, a note title, or a reference. "
    "LearnFlow shows the learner which passages these are.\n"
    "- Write plain prose for a learner revising this topic. No markdown, no "
    "headings, and no bullet list unless the answer is genuinely a list.\n"
    "- Be brief. A few sentences is usually enough."
)
"""What the model is told before it sees the question.

**The instruction is a request, not a guarantee.** A model can ignore it, which
is why the real protection is structural: it is handed the passages and nothing
else, so anything it adds beyond them is visibly its own and the learner has the
passages in front of them to check against. The rule against inventing citations
matters for the same reason — LearnFlow assembles the citation list from what it
sent, so a source name in the prose would be the one thing on the screen that
nothing verified.
"""

_GENERATE_PATH: Final = "/api/generate"
_JSON: Final = "application/json"
_MODEL_MISSING_MARKERS: Final = ("not found", "no such model", "pull the model")


def build_prompt(request: GroundedAnswerRequest) -> str:
    """The user prompt for one grounded question.

    Passages are numbered so the model can refer to them while reasoning, and
    **the numbers are deliberately not a citation scheme**: LearnFlow does not ask
    the model to cite them and does not read a number back out of the reply. The
    citation list on the screen is the passages themselves, in this order.

    Nothing but the request's own fields reaches this string — no identifier, no
    title, and no learner data of any other kind, because `GroundedAnswerRequest`
    holds none.
    """
    passages = "\n\n".join(
        f"Passage {number}:\n{text}" for number, text in enumerate(request.passages, start=1)
    )
    return (
        f"Topic: {request.topic_name} (subject: {request.subject_name})\n"
        f"\n"
        f"{passages}\n"
        f"\n"
        f"Question: {request.question}"
    )


class OllamaAIProvider:
    """Asks a locally running Ollama instance for a grounded answer.

    Args:
        base_url: Where Ollama listens, validated as an `http`/`https` URL by
            configuration before it reaches here.
        model: The chat model to ask, which must already be pulled.
        timeout_seconds: How long one attempt may take. Generous by default,
            because a local model on modest hardware is slow rather than broken.
    """

    def __init__(self, *, base_url: str, model: str, timeout_seconds: float) -> None:
        """Bind the adapter to one Ollama instance and one model."""
        self._endpoint = f"{base_url.rstrip('/')}{_GENERATE_PATH}"
        self._model = model
        self._timeout = timeout_seconds

    def generate_answer(self, request: GroundedAnswerRequest) -> str:
        """Ask Ollama the question, grounded in the passages.

        `stream` is false because the answer is rendered in one piece by a server
        component; streaming would need a transport the frontend does not have and
        would buy nothing on a screen that shows the whole answer at once.

        Raises:
            AIProviderUnavailableError: Ollama could not be reached.
            AIProviderModelMissingError: The model is not installed.
            AIProviderTimedOutError: No reply arrived within the timeout.
            AIProviderUnusableReplyError: The reply was empty or unreadable.
        """
        payload = json.dumps(
            {
                "model": self._model,
                "system": SYSTEM_PROMPT,
                "prompt": build_prompt(request),
                "stream": False,
            }
        ).encode("utf-8")

        post = urllib.request.Request(  # noqa: S310 - scheme validated in configuration
            self._endpoint,
            data=payload,
            headers={"Content-Type": _JSON, "Accept": _JSON},
            method="POST",
        )

        try:
            with urllib.request.urlopen(post, timeout=self._timeout) as reply:  # noqa: S310
                body = reply.read()
        except urllib.error.HTTPError as error:
            # A subclass of URLError, so it must be caught first.
            raise _from_http_status(error) from None
        except urllib.error.URLError as error:
            # Refused connections, unknown hosts, and timeouts all arrive here,
            # the last wrapped rather than raised directly.
            raise _transport_failure(error.reason) from None
        except TimeoutError:
            raise AIProviderTimedOutError("The AI provider did not answer in time.") from None

        return _answer_from(body)


def _answer_from(body: bytes) -> str:
    """The prose out of one Ollama reply.

    A reply that is not JSON, that is JSON of the wrong shape, or that carries an
    empty completion are all one thing to a learner — the provider answered with
    nothing usable — so they share an outcome. **The body is never quoted into
    the error**: it echoes the prompt back on some failures, and the prompt holds
    the learner's notes.
    """
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError, UnicodeDecodeError:
        raise AIProviderUnusableReplyError("The AI provider's reply could not be read.") from None

    prose = parsed.get("response") if isinstance(parsed, dict) else None
    if not isinstance(prose, str) or not prose.strip():
        raise AIProviderUnusableReplyError("The AI provider returned an empty answer.")
    return prose.strip()


def _from_http_status(error: urllib.error.HTTPError) -> Exception:
    """Which failure an HTTP status means.

    Ollama answers `404` for a model it does not have. The body says which model,
    and is read **only** to look for a fixed marker phrase — never stored, logged,
    or included in the raised message.
    """
    if error.code == 404:
        detail = _peek(error)
        if any(marker in detail for marker in _MODEL_MISSING_MARKERS):
            return AIProviderModelMissingError(
                "The AI provider does not have the configured model installed."
            )
    return AIProviderUnavailableError("The AI provider could not answer this request.")


def _peek(error: urllib.error.HTTPError) -> str:
    """The error body, lowercased, for marker matching only.

    An unreadable body is an empty string rather than a second failure: this is
    used to refine a message, so it must never become a way for the adapter to
    raise something unexpected.
    """
    try:
        return error.read().decode("utf-8", errors="replace").lower()
    except OSError:
        return ""


def _transport_failure(reason: object) -> Exception:
    """Which failure a `URLError` means, from the reason it wrapped.

    A timeout reaches here wrapped rather than raised, so it is recognised by
    type. Everything else — a refused connection, an unknown host, a DNS
    failure — means the provider is not there.

    **The reason is inspected and never quoted.** It can carry an operating
    system message, and a message this build has not read is not one it can
    promise is free of learner text.
    """
    if isinstance(reason, TimeoutError):
        return AIProviderTimedOutError("The AI provider did not answer in time.")
    return AIProviderUnavailableError("The AI provider could not be reached.")
