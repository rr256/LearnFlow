"""The port an AI provider is reached through.

This is the **first outbound port in LearnFlow that is not a database read**, and
the first through which a learner's own words can leave the process. Everything
about its shape is chosen to keep that boundary visible.

**It carries text and nothing else.** `GroundedAnswerRequest` holds a question,
the topic it was asked about, and the passages retrieved from the learner's own
notes -- all `str`. There is deliberately no note identifier, no resource
identifier, no learner identifier, no plan, no progress, and no whole note on it,
because a structure that cannot hold an identifier cannot leak one. What may be
sent is decided by this dataclass rather than by the adapter that serialises it,
and a test asserts the shape.

**It answers a question and nothing else.** There is one method. The provider is
never asked to plan, to mark, to rank, to recommend, or to decide anything about
a learner: it turns a question and some passages into prose, and the caller
decides what to do with the result.

**The provider selected today is Ollama, running locally**
([ADR-004](../../../../docs/adr/ADR-004-ollama-local-ai-provider.md)), so in the
build that exists nothing leaves the machine at all. The port exists so that is a
statement about the composition root rather than about the whole codebase --
which is what makes a future cloud adapter an explicit, reviewable decision under
ADR-004's own mitigation rather than a quiet edit.

**Failures are named, not generic.** Three of them are told apart because they
ask the learner to do three different things: start the provider, install the
model, or wait and try again. A caller that could not tell them apart would have
to say "something went wrong", which helps nobody. See `AIProviderError`.

**Nothing here retries, caches, logs, or stores.** A retry is the adapter's
business at most, and this build performs none
([ADR-039](../../../../docs/adr/ADR-039-source-grounded-study-answers.md)).
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GroundedAnswerRequest:
    """Everything that may be sent to an AI provider, and nothing more.

    **This is the privacy boundary, expressed as a type.** The fields here are
    the complete list of what leaves the application layer; anything absent
    cannot be transmitted, because the adapter is given this object and never the
    retrieval result it was built from.

    Note the omissions, which are deliberate: no `note_id`, no `resource_id`, no
    `topic_id`, no `learner_id`, no note title, no resource title, no timestamps,
    and no whole note body. A citation is assembled by LearnFlow from what it
    retrieved, so the model never needs to name a source and is never given the
    means to.

    Attributes:
        question: What the learner typed, verbatim.
        topic_name: The curriculum topic they asked it about, so the model knows
            the subject area a bare question sits in.
        subject_name: The subject that topic belongs to, for the same reason.
        passages: The learner's own words, exactly as retrieved -- each an exact
            substring of a stored note. These are the **only** grounds an answer
            may use, and an empty tuple is impossible here: a request is never
            built without them (`AnswerTopicQuestion`).
    """

    question: str
    topic_name: str
    subject_name: str
    passages: tuple[str, ...]


class AIProviderError(Exception):
    """Base class for every way asking a provider can fail.

    A caller that catches this catches all of them; a caller that wants to tell a
    learner what to do next catches the subclasses, which exist because "start
    Ollama", "pull the model", and "it took too long" are three different next
    steps.

    **No message raised from here ever carries note text or a question.** The
    provider was sent the learner's words, so an error path is exactly where they
    would otherwise resurface -- in a log, a stack trace, or an HTTP body. See
    docs/api/conventions.md.
    """


class AIProviderUnavailableError(AIProviderError):
    """The provider could not be reached at all.

    Ollama is not running, or is not listening where configuration says it is.
    """


class AIProviderModelMissingError(AIProviderError):
    """The provider is running but does not have the configured model.

    Distinct from unavailability because the learner's next step is to pull the
    model rather than to start anything.
    """


class AIProviderTimedOutError(AIProviderError):
    """The provider accepted the request and did not answer in time.

    Expected on modest hardware rather than exceptional, which is why the timeout
    is configurable and why this build does **not** retry: a local model that ran
    out of time will usually run out of time again, and a retry would double the
    wait to reach the same message.
    """


class AIProviderUnusableReplyError(AIProviderError):
    """The provider answered, and the answer was not usable.

    An empty completion, or a reply this build cannot read. Told apart from a
    transport failure because nothing is wrong with the connection: retrying
    would ask the same model the same question.
    """


class AIProvider(Protocol):
    """Generates prose from a question and the passages supporting it."""

    def generate_answer(self, request: GroundedAnswerRequest) -> str:
        """Answer the question using only the passages in the request.

        The instruction to stay within the passages is the adapter's to give,
        because it is expressed in whatever form the vendor's API takes. What is
        guaranteed here is narrower and more important: the provider is given
        nothing else to draw on from LearnFlow, so any claim beyond the passages
        came from the model's own training rather than from the learner's data.

        Returns:
            The answer as plain text. Never markup: the presentation layer
            renders it as text, exactly as it renders a passage.

        Raises:
            AIProviderUnavailableError: The provider could not be reached.
            AIProviderModelMissingError: The configured model is not installed.
            AIProviderTimedOutError: No answer arrived within the timeout.
            AIProviderUnusableReplyError: The reply was empty or unreadable.
        """
        ...
