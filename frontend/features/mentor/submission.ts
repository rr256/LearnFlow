/**
 * Reading one asked question off a form, and the shape an answer comes back in.
 *
 * Separate from `actions.ts` because a `"use server"` module may export **only**
 * async functions: a constant exported from one fails at runtime with a `500`
 * that neither `tsc` nor `next build` reports. The state shapes and their
 * initial values therefore live here, as they do for every other feature.
 *
 * **Nothing here is stored.** The state exists for the length of one render — it
 * holds the last answer so the screen can show it, and there is no history, no
 * transcript, and no previous question to go back to.
 */

import type { StudyAnswer } from "@/types/study-answer";

/**
 * What the mentor screen knows after a submission.
 *
 * `answer` carries the whole MNT-001 result, including the passages and the
 * outcome — so an empty answer and a provider failure are both this shape rather
 * than an error. `error` is only for a request that was refused outright.
 */
export interface StudyQuestionState {
  /** The last answer, or null before anything has been asked. */
  answer: StudyAnswer | null;
  /** Why a request could not be made at all. Never a provider failure. */
  error: string | null;
  /**
   * The topic last chosen, so the picker keeps it after a submission.
   *
   * Kept even when the request was refused: a learner who mistyped a question
   * should not have to find their topic again.
   */
  topicId: string | null;
  /** The question last typed, kept for the same reason. */
  question: string;
}

export const INITIAL_STUDY_QUESTION_STATE: StudyQuestionState = {
  answer: null,
  error: null,
  topicId: null,
  question: "",
};

/** What one submitted form holds. */
export interface StudyQuestionSubmission {
  topicId: string;
  question: string;
}

/**
 * Read a question and its topic off the submitted form.
 *
 * Trimmed only at the ends. What a learner wrote inside their question is theirs
 * and is sent character for character, the same respect for their text that
 * keeps a passage an exact substring.
 *
 * The emptiness checks here are a courtesy that saves a round trip; the backend
 * refuses a blank or over-long question whatever a browser allowed, which is
 * where the rule actually lives.
 */
export function readStudyQuestionSubmission(
  form: FormData,
): StudyQuestionSubmission | { error: string } {
  const topicId = readField(form, "topic_id");
  const question = readField(form, "question");

  if (!topicId) {
    return { error: "Choose a topic to ask about." };
  }
  if (!question) {
    return { error: "Type a question to ask." };
  }
  return { topicId, question };
}

/** One trimmed text field, or an empty string when it is absent or not text. */
function readField(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}
