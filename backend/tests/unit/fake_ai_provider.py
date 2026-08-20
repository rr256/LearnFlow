"""An in-memory stand-in for the AI provider port.

**No test in LearnFlow reaches a real provider.** This is the only thing the
grounded-answer use case is ever bound to under test, so the suite makes no
outbound request, needs no Ollama running, and cannot be made to pass or fail by
a model's mood. The real adapter is covered separately, against a stubbed
transport, in `test_ollama_ai_provider.py`.

It **records every request it is given**, which is what makes the feature's
central promise testable: with no passages retrieved, `requests` must stay empty.
An assertion that a call did not happen needs somewhere the call would have been
recorded, and this is it.
"""

from app.application.ports.ai_provider import AIProviderError, GroundedAnswerRequest


class FakeAIProvider:
    """Answers with a fixed string, or raises, and remembers what it was asked.

    Args:
        answer: What `generate_answer` returns when it does not raise.
        fails_with: Raised instead of answering, to exercise a failure branch.
            The request is still recorded first, because a provider that was
            asked and then failed **was** asked.
    """

    def __init__(
        self,
        *,
        answer: str = "Round robin gives each process a fixed quantum.",
        fails_with: AIProviderError | None = None,
    ) -> None:
        """Start with nothing asked."""
        self.answer = answer
        self.fails_with = fails_with
        self.requests: list[GroundedAnswerRequest] = []

    @property
    def was_asked(self) -> bool:
        """Whether the provider was reached at all.

        Named as a boolean rather than a count for the reason the note-search port
        gives: what is being asserted is *whether* an outbound call happened, and
        a figure would invite a test to accept "only one".
        """
        return bool(self.requests)

    def generate_answer(self, request: GroundedAnswerRequest) -> str:
        """Record the request, then answer or raise."""
        self.requests.append(request)
        if self.fails_with is not None:
            raise self.fails_with
        return self.answer
