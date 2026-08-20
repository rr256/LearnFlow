"use server";

/**
 * Asking one question, from the Next.js server.
 *
 * A server action runs on the Next.js server, so the browser still makes no
 * request to the backend: the form posts to this process, which calls the API
 * with the same server-side `API_BASE_URL` every view uses. The API therefore
 * needs no CORS allow-list and no API address reaches a client bundle, which is
 * the position ADR-015 takes and this feature inherits rather than renegotiates.
 *
 * **It is an action rather than a `GET` deliberately**, which departs from
 * `/resources/search` next door. A search carries a topic identifier; this
 * carries a learner's own question, and a question in the address would land in
 * server logs and browser history. The backend chose `POST` for that reason, and
 * a `GET` form here would undo it.
 *
 * **It revalidates nothing**, because nothing was written. No question, no
 * answer, and no record that either happened — so no other screen has anything
 * to re-read.
 *
 * It holds no rule about answering. Whether there is anything to answer from,
 * whether the model is asked at all, and what may be sent are all decided by the
 * backend; this maps a form onto one API call and maps the answer back.
 *
 * **This module exports async functions and nothing else.** A `"use server"`
 * file may export only async functions, and a constant exported from one fails
 * at runtime with a `500` that neither `tsc` nor `next build` reports. The state
 * shapes and their initial values therefore live in `submission.ts`.
 */

import {
  readStudyQuestionSubmission,
  type StudyQuestionState,
} from "@/features/mentor/submission";
import { ApiError, askStudyQuestion } from "@/lib/api-client";

/**
 * MNT-001 — ask a question about one topic and return what came back.
 *
 * **A provider failure is not an error here.** The backend reports an
 * unreachable, slow, or unusable provider as an outcome on a `200`, with the
 * retrieved passages intact, so it arrives as an answer this screen can explain
 * rather than as something that threw. Only a refused request becomes `error`.
 *
 * The topic and question are carried back in the state so the form keeps what
 * the learner chose and typed, whichever way the request went.
 */
export async function askStudyQuestionAction(
  _previous: StudyQuestionState,
  form: FormData,
): Promise<StudyQuestionState> {
  const submitted = readStudyQuestionSubmission(form);
  const topicId = "error" in submitted ? readTopicId(form) : submitted.topicId;
  const question = "error" in submitted ? readQuestion(form) : submitted.question;

  if ("error" in submitted) {
    return { answer: null, error: submitted.error, topicId, question };
  }

  try {
    const answer = await askStudyQuestion(submitted.topicId, submitted.question);
    return { answer, error: null, topicId, question };
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return { answer: null, error: messageFor(error), topicId, question };
  }
}

/** The topic as submitted, so a refused request does not lose the learner's choice. */
function readTopicId(form: FormData): string | null {
  const value = form.get("topic_id");
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/** The question as submitted, kept for the same reason. */
function readQuestion(form: FormData): string {
  const value = form.get("question");
  return typeof value === "string" ? value : "";
}

/**
 * What to tell the learner about a refused request.
 *
 * The API's own message is used where it has one, because it names the rule that
 * was broken. **No note text or question is ever in it** — the backend keeps both
 * out of every error it writes, which is the rule that matters most where the
 * data is a learner's own study material.
 */
function messageFor(error: ApiError): string {
  if (error.isUnreachable) {
    return "LearnFlow could not reach its own backend, so nothing was asked.";
  }
  if (error.isConflict) {
    return "Finish setting up your study goal before asking a question.";
  }
  if (error.isNotFound) {
    return "That topic is not in the curriculum any more. Choose another one.";
  }
  return error.message;
}
