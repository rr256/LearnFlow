/**
 * Source-grounded study answer types, derived from the MNT-001 response contract
 * in docs/api/endpoints.md#mentor-endpoints.
 *
 * A learner asks a question about one curriculum topic and gets an answer built
 * from passages in **their own** notes, with those passages shown beneath it.
 *
 * **`answer` and `passage` are both plain text and are rendered as plain text.**
 * Nothing here parses either as HTML or Markdown, and nothing passes either to
 * `dangerouslySetInnerHTML` — React escapes them, and CSS `white-space: pre-wrap`
 * preserves the line breaks. A model's output is treated with exactly the same
 * suspicion as any other text arriving over the network, which matters more here
 * than on the retrieval screen: a passage came from the learner, while an answer
 * came from a model.
 *
 * **The citations are not parsed out of the answer.** `passages` is what the
 * backend retrieved and sent, recorded before the model was asked. Nothing on
 * this side reads a source name out of the prose, so an answer cannot cite a
 * note that was never consulted.
 *
 * **No figure exists in this contract** — no score, no confidence, no relevance,
 * and no count (docs/development/coding-standards.md#ui-responsibilities).
 */

import type { DataEnvelope } from "@/types/api";
import type { NotePassage } from "@/types/note-search";

/**
 * Why a question was answered the way it was.
 *
 * Seven outcomes, in three groups that ask the learner to do different things.
 * The three **ungrounded** ones mean the model was never asked at all; the three
 * **provider** ones mean it was asked and could not answer, and the passages are
 * still there to read.
 */
export const ANSWER_OUTCOMES = [
  "answered",
  "no_linked_material",
  "no_active_notes",
  "no_matching_passage",
  "provider_unavailable",
  "provider_timed_out",
  "provider_unusable_reply",
] as const;

export type AnswerOutcome = (typeof ANSWER_OUTCOMES)[number];

/** True when the API sent an outcome this build knows what to say about. */
export function isKnownAnswerOutcome(value: string): value is AnswerOutcome {
  return (ANSWER_OUTCOMES as readonly string[]).includes(value);
}

/**
 * The outcomes reached **without asking the model anything**.
 *
 * Named because the screen says so explicitly: a learner seeing no answer should
 * know LearnFlow declined to invent one, not that something failed.
 */
export const UNGROUNDED_OUTCOMES: readonly AnswerOutcome[] = [
  "no_linked_material",
  "no_active_notes",
  "no_matching_passage",
];

/** True when no model was asked, because nothing of the learner's supported an answer. */
export function isUngrounded(outcome: string): boolean {
  return (UNGROUNDED_OUTCOMES as readonly string[]).includes(outcome);
}

/** What one question was answered with. */
export interface StudyAnswer {
  topic_id: string;
  topic_name: string;
  subject_name: string;
  /** The question, echoed back as it was asked. */
  question: string;
  outcome: AnswerOutcome | string;
  /** The answer as plain text, or null when there is none. Never markup. */
  answer: string | null;
  /** The passages the answer was grounded in — the citations. */
  passages: NotePassage[];
}

export type StudyAnswerResponse = DataEnvelope<StudyAnswer>;

/**
 * How long a question may be, mirroring `MAX_QUESTION_LENGTH` on the backend.
 *
 * A courtesy on the form, not the rule: the backend refuses an over-long
 * question whatever a browser allowed.
 */
export const MAX_QUESTION_LENGTH = 1000;
