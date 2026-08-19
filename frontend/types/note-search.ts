/**
 * Topic-note retrieval types, derived from the RES-013 response contract in
 * docs/api/endpoints.md#resource-and-ingestion-endpoints.
 *
 * A learner chooses a topic and sees passages from **their own** notes. This is
 * retrieval and nothing more: no answer is generated, nothing is summarised, and
 * no AI model is involved anywhere.
 *
 * `passage` is **plain text and is rendered as plain text**. Nothing here parses
 * it as HTML or Markdown, and nothing passes it to `dangerouslySetInnerHTML` —
 * React escapes it, and CSS `white-space: pre-wrap` preserves the learner's own
 * line breaks.
 *
 * **No relevance figure exists in this contract.** Relevance decided the order
 * the API returned and nothing else, so nothing here can render a number beside
 * a learner's own writing
 * (docs/development/coding-standards.md#ui-responsibilities).
 */

import type { DataEnvelope } from "@/types/api";

/**
 * Why a search returned what it did.
 *
 * Three empty answers are kept apart because they ask the learner to do three
 * different things.
 */
export const SEARCH_OUTCOMES = [
  "found",
  "no_linked_material",
  "no_active_notes",
  "no_matching_passage",
] as const;

export type SearchOutcome = (typeof SEARCH_OUTCOMES)[number];

/** True when the API sent an outcome this build knows what to say about. */
export function isKnownOutcome(value: string): value is SearchOutcome {
  return (SEARCH_OUTCOMES as readonly string[]).includes(value);
}

/** One passage from one of the learner's notes. */
export interface NotePassage {
  note_id: string;
  note_title: string;
  resource_id: string;
  resource_title: string;
  resource_type: string;
  topic_id: string;
  topic_name: string;
  subject_name: string;
  /** The learner's own text, as an extract. Never markup. */
  passage: string;
}

/** What one search answered with. */
export interface TopicNoteSearch {
  topic_id: string;
  topic_name: string;
  subject_name: string;
  outcome: SearchOutcome | string;
  passages: NotePassage[];
}

export type TopicNoteSearchResponse = DataEnvelope<TopicNoteSearch>;
