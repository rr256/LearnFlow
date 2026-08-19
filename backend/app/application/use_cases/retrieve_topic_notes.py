"""Finding passages in a learner's own notes for a topic they chose.

Serves RES-013, the first **retrieval** in LearnFlow and the second half of the
foundation [ADR-037](../../../../docs/adr/ADR-037-learner-written-resource-notes.md)
laid. It advances
[FR-008](../../../../docs/requirements/functional.md#fr-008-grounded-mentor-assistance)
by one criterion and **meets none of the rest**: there is no mentor here.

**It retrieves and does not answer.** Nothing asks a model anything, generates
prose, summarises, paraphrases, or explains. What comes back is the learner's own
words beside the material they came from. A learner reading a result is reading
themselves, never LearnFlow.

**A passage is an exact substring of the stored note.** It is cut here, from
the body the repository returned, rather than rendered by the database:
`ts_headline` would be shorter to transfer but its parser drops text it reads as
an HTML tag, so `vector<int>` came back mangled. Cutting on word boundaries
keeps every literal character -- angle brackets, operators, punctuation -- and
inserts nothing, so a passage carries no word the learner did not write.

**It is local, deterministic, and reads only the database.** The search is
PostgreSQL's own full-text search. There is no embedding provider, no vector
store, no AI provider, no external API, no URL fetch, and no background job — and
this use case binds **no provider at all**, which a test asserts, so adding one
would be a visible decision rather than a quiet one (NFR-001).

**It runs only when the learner asks.** Nothing here is triggered by rendering a
page, saving a note, or opening a plan; a search happens because a learner chose
a topic and submitted. That is what keeps the privacy statement a description of
what LearnFlow does rather than of what it might do.

**Nothing is ranked as a learner's performance.** Relevance decides the order
passages arrive in and nothing else: the figure is discarded by the adapter and
never reaches a response, because a number beside a learner's own writing reads
as a mark on it.

**It writes nothing at all.** No note, no resource, no learning stage, no plan,
no plan item, no revision, no quiz, and no record that a search happened — there
is no search history, because storing what a learner looked for is a second
feature with its own privacy question.
"""

import re
import uuid

from app.application.dto.note_retrieval import (
    LEAD_IN_WORDS,
    MAX_PASSAGE_WORDS,
    MAX_PASSAGES,
    NoteMatch,
    TopicNotePassage,
    TopicNoteSearchOutcome,
    TopicNoteSearchResult,
)
from app.application.ports.learner_repository import LearnerRepository
from app.application.ports.note_search_repository import NoteSearchRepository
from app.application.ports.resource_repository import ResourceRepository
from app.application.use_cases.local_learner import resolve_local_learner


class TopicNoteRetrievalError(Exception):
    """Base class for the refusals this use case makes."""


class LearnerNotSetUpError(TopicNoteRetrievalError):
    """No learner is stored, so there are no notes to search."""


class UnknownTopicError(TopicNoteRetrievalError):
    """A topic identifier naming nothing stored."""


class RetrieveTopicNotes:
    """Finds passages in the learner's notes for one curriculum topic.

    It binds three repositories and **no provider**: learners, to resolve who is
    asking; resources, to name the topic being asked about; and the note search.
    There is nothing here through which a learner's text could leave the process.
    """

    def __init__(
        self,
        *,
        learners: LearnerRepository,
        resources: ResourceRepository,
        notes: NoteSearchRepository,
    ) -> None:
        """Bind the use case to its ports."""
        self._learners = learners
        self._resources = resources
        self._notes = notes

    def search(self, topic_id: uuid.UUID) -> TopicNoteSearchResult:
        """Passages from the learner's own notes that mention this topic.

        **Only the learner's own material is searched**, and only where they have
        said it covers this topic: a note is considered when it is `active`, its
        resource is `registered` and owned by them, and that resource is linked
        to the topic asked about. Archived material drops out exactly as it does
        from the curriculum, revision, and plan screens, so putting something
        aside means one thing everywhere.

        An empty answer says **why** — see `TopicNoteSearchOutcome` — because
        "link some material", "write a note", and "try another topic" are
        different next steps and a bare "nothing found" hides which one applies.

        This reads and writes nothing. Asking twice returns the same answer and
        leaves no trace that either happened.

        Raises:
            LearnerNotSetUpError: No learner is stored yet.
            UnknownTopicError: The topic identifier names nothing stored.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError("No learner is stored, so there are no notes to search.")

        topic = next(iter(self._resources.list_topics([topic_id])), None)
        if topic is None:
            raise UnknownTopicError(f"No topic is stored with identifier {topic_id}.")

        def answer(
            outcome: TopicNoteSearchOutcome,
            passages: tuple[TopicNotePassage, ...] = (),
        ) -> TopicNoteSearchResult:
            return TopicNoteSearchResult(
                topic_id=topic.id,
                topic_name=topic.name,
                subject_name=topic.subject_name,
                outcome=outcome,
                passages=passages,
            )

        # Asked in this order so an empty answer can say which step ran out.
        # Each is a boolean, never a count: how much material a learner has is
        # not something this endpoint reports.
        if not self._notes.has_linked_material(learner_id=learner.id, topic_id=topic.id):
            return answer(TopicNoteSearchOutcome.NO_LINKED_MATERIAL)
        if not self._notes.has_active_notes(learner_id=learner.id, topic_id=topic.id):
            return answer(TopicNoteSearchOutcome.NO_ACTIVE_NOTES)

        terms = search_terms_for(topic.name)
        matches = self._notes.search_matches(
            learner_id=learner.id,
            topic_id=topic.id,
            query_terms=terms,
            limit=MAX_PASSAGES,
        )
        if not matches:
            return answer(TopicNoteSearchOutcome.NO_MATCHING_PASSAGE)
        return answer(
            TopicNoteSearchOutcome.FOUND,
            tuple(_passage_from(match, terms) for match in matches),
        )


def search_terms_for(topic_name: str) -> str:
    """The search terms a topic's name contributes, as PostgreSQL will read them.

    **The topic is the query.** A learner types nothing: they choose a topic, and
    its name becomes the terms. That is why no free-text box exists — a typed
    query is a different feature, with its own question about what gets logged.

    The words are joined with `or` rather than left implicitly `and`, because
    `websearch_to_tsquery` reads adjacent words as *all must appear*: a topic
    called *CPU scheduling* would then miss a note that only ever says
    "scheduler". Any word may match, and relevance ordering puts the passages
    matching more of them first — recall from the `or`, precision from the order.

    Punctuation is dropped rather than escaped. `websearch_to_tsquery` treats
    `or`, `-`, and quotation marks as operators, so a topic name containing them
    would otherwise change the query's shape; stripping to words and digits keeps
    a topic's name from ever being read as syntax.

    Stemming is PostgreSQL's, from the `english` configuration, so "scheduling"
    and "scheduler" reach the same lexeme.
    """
    words = re.findall(r"[\w]+", topic_name.lower(), flags=re.UNICODE)
    meaningful = [word for word in words if word not in _OPERATOR_WORDS]
    return " or ".join(meaningful)


_OPERATOR_WORDS = frozenset({"or", "and", "not"})
"""Words `websearch_to_tsquery` reads as operators rather than as terms.

Removed from a topic's name so that a topic called *Search and Sorting* asks for
its two real words rather than carrying a stray conjunction into the query.
"""


def _passage_from(match: NoteMatch, query_terms: str) -> TopicNotePassage:
    """One passage, cut from the note the search matched."""
    return TopicNotePassage(
        note_id=match.note_id,
        note_title=match.note_title,
        resource_id=match.resource_id,
        resource_title=match.resource_title,
        resource_type=match.resource_type,
        topic_id=match.topic_id,
        topic_name=match.topic_name,
        subject_name=match.subject_name,
        passage=extract_passage(match.body, query_terms),
    )


def extract_passage(body: str, query_terms: str) -> str:
    """One contiguous stretch of a note, **character for character**.

    The result is always an **exact substring** of `body`. Nothing is inserted,
    replaced, escaped, joined, or elided, so `vector<int>`, `a < b`, tabs, and
    every other literal survive exactly as the learner typed them. A short note
    comes back whole.

    The window is cut on **word boundaries** around the first word that looks
    like one of the query terms, with `LEAD_IN_WORDS` of run-up so it does not
    begin mid-thought.

    **Locating the match here is an approximation, and only ever chooses where to
    cut.** Whether a note matched at all was decided by PostgreSQL, with real
    stemming; this repeats that cheaply with `_looks_like`, because character
    offsets are not something a `tsvector` can give back. When the approximation
    finds nothing — a genuinely stemmed match this cannot see — the passage is
    the **start of the note**, which is honest and still exact. It never changes
    *which* notes came back, only which part of one is shown.
    """
    words = list(re.finditer(r"[\w]+", body, flags=re.UNICODE))
    if not words:
        return body.strip()

    terms = [term for term in _terms_of(query_terms) if term]
    first = next(
        (index for index, word in enumerate(words) if _looks_like(word.group(0), terms)),
        0,
    )

    start_word = max(0, first - LEAD_IN_WORDS)
    end_word = min(len(words) - 1, start_word + MAX_PASSAGE_WORDS - 1)

    # Up to the start of the word *after* the last one kept, rather than to the
    # end of that word: a window ending at `matters` would otherwise drop the
    # full stop after it. Trailing whitespace is removed, and nothing else.
    start = words[start_word].start()
    end = len(body) if end_word + 1 == len(words) else words[end_word + 1].start()
    return body[start:end].rstrip()


def _terms_of(query_terms: str) -> list[str]:
    """The words of a query, with the `or` joins `search_terms_for` added removed."""
    return [
        word for word in re.findall(r"[\w]+", query_terms.lower()) if word not in _OPERATOR_WORDS
    ]


def _looks_like(word: str, terms: list[str]) -> bool:
    """Whether one word of a note plausibly matched one of the query terms.

    A cheap stand-in for Snowball stemming: two words count as the same when they
    **share at least `_STEM_PREFIX` leading characters**, which is what lets a
    topic word "scheduling" find "schedulers" — neither is a prefix of the other,
    so a containment test would miss it, and that is the case this exists for.
    A word shorter than that must match outright, so "ip" does not sweep up
    "ipv6".

    It is deliberately generous and deliberately powerless: it cannot add a note
    to the results or remove one, because that was settled by PostgreSQL before
    this ran. All it decides is where a passage is cut.
    """
    lowered = word.lower()
    for term in terms:
        if lowered == term:
            return True
        shared = 0
        for left, right in zip(lowered, term, strict=False):
            if left != right:
                break
            shared += 1
        if shared >= _STEM_PREFIX:
            return True
    return False


_STEM_PREFIX = 4
"""How many leading characters two words must share to be treated as one.

Four is long enough that "data" does not meet "deadlock", and short enough for
"schedul(ing|ers|e)" to meet each other. It affects only where a passage is cut,
never which notes came back.
"""
