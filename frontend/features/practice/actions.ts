"use server";

/**
 * The write paths for checkpoint practice: writing a question, setting one
 * aside, assembling a quiz, and submitting an attempt.
 *
 * A server action runs on the Next.js server, so the browser still makes no
 * request to the backend: the form posts to this process, which calls the API
 * with the same server-side `API_BASE_URL` every view uses. The API therefore
 * needs no CORS allow-list and no API address reaches a client bundle, which is
 * the position ADR-015 takes and this feature inherits rather than renegotiates.
 *
 * They hold no practice rule. How many options a question may offer, which
 * questions a quiz asks, in what order, and whether an answer is correct are all
 * decided by the backend; these map a form onto one or two API calls and map the
 * answer back into something a control can show.
 *
 * **Nothing here marks an answer, counts one, or totals anything.**
 *
 * **This module exports async functions and nothing else.** A `"use server"`
 * file may export only async functions, and a constant exported from one fails
 * at runtime with a `500` that neither `tsc` nor `next build` reports. The state
 * shapes and their initial values therefore live in `submission.ts`.
 */

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  readAttemptSubmission,
  readQuestionStatusSubmission,
  readQuestionSubmission,
  readQuizTopics,
  type AnswerFormState,
  type QuestionFormState,
  type QuestionStatusState,
  type StartQuizState,
} from "@/features/practice/submission";
import {
  ApiError,
  assembleCheckpointQuiz,
  startQuizAttempt,
  submitQuizAttempt,
  updatePracticeQuestionStatus,
  writePracticeQuestion,
} from "@/lib/api-client";

/** What a learner reads when a form asked for something that cannot be sent. */
const UNUSABLE_QUESTION_FORM =
  "Write the question, give it at least two options, mark which one is expected, and choose a topic it covers.";

/**
 * QZ-008 -- record one practice question the learner has written.
 *
 * The confirmation quotes the question rather than saying "saved", so a learner
 * writing several in a row can see which one landed.
 */
export async function writeQuestionAction(
  _previous: QuestionFormState,
  form: FormData,
): Promise<QuestionFormState> {
  const submission = readQuestionSubmission(form);
  if (!submission) {
    return { status: "error", message: UNUSABLE_QUESTION_FORM };
  }

  try {
    const question = await writePracticeQuestion(submission);
    revalidatePath("/practice");
    return {
      status: "saved",
      message: `Added “${question.prompt}” to your practice questions.`,
    };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", message: error.message };
    }
    throw error;
  }
}

/**
 * QZ-010 -- set one practice question aside, or bring it back.
 *
 * **Nothing is deleted.** Setting a question aside means no new quiz asks it,
 * and it is reversible from the same control — which is why the list still shows
 * what has been set aside. A quiz already assembled keeps asking it, because
 * attempts are marked against it.
 *
 * Only the named question moves: no quiz, no attempt, no learning stage, no
 * plan, no plan item, and no revision.
 */
export async function saveQuestionStatus(
  _previous: QuestionStatusState,
  form: FormData,
): Promise<QuestionStatusState> {
  const submission = readQuestionStatusSubmission(form);
  if (!submission) {
    return { status: "error", message: "That is not something a question can be set to." };
  }

  try {
    await updatePracticeQuestionStatus(submission.questionId, submission.status);
    revalidatePath("/practice");
    return {
      status: "saved",
      message:
        submission.status === "retired"
          ? "Set aside. It stays in your questions and you can use it again."
          : "Back in use. New quizzes will ask it again.",
    };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", message: error.message };
    }
    throw error;
  }
}

/**
 * QZ-001 -- assemble a quiz from the learner's questions, then open it.
 *
 * On success this **redirects** to the quiz rather than returning it, so the
 * flow works with no JavaScript: the form posts, the server assembles, and the
 * browser follows a normal redirect to the page where the learner answers.
 *
 * `redirect` throws to unwind, so it is called outside the `try` — catching it
 * would turn a successful redirect into an error message.
 */
export async function startQuizAction(
  _previous: StartQuizState,
  form: FormData,
): Promise<StartQuizState> {
  const topicIds = readQuizTopics(form);
  if (!topicIds) {
    return { status: "error", message: "Choose at least one topic to practise." };
  }

  let quizId: string;
  try {
    quizId = (await assembleCheckpointQuiz(topicIds)).id;
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", message: error.message };
    }
    throw error;
  }

  revalidatePath("/practice");
  redirect(`/practice/quizzes/${quizId}`);
}

/**
 * QZ-003 and QZ-005 -- begin an attempt and submit its answers together.
 *
 * Two calls rather than one because the contract has two, and one form post
 * because a learner answers a quiz once: starting an attempt when the answers
 * are already in hand keeps the whole thing to a single submission that works
 * with no JavaScript.
 *
 * **A question the learner left alone is absent from the submission** and is
 * recorded as unanswered, never as wrong. Submitting with nothing answered is
 * allowed.
 *
 * On success this redirects to the result. Nothing else moves: no learning
 * stage, no plan, no plan item, and no revision — a checkpoint says what
 * happened in one attempt, not that a topic is understood.
 */
export async function submitAnswersAction(
  _previous: AnswerFormState,
  form: FormData,
): Promise<AnswerFormState> {
  const submission = readAttemptSubmission(form);
  if (!submission) {
    return { status: "error", message: "That answer sheet could not be read. Reload and retry." };
  }

  let attemptId: string;
  try {
    const attempt = await startQuizAttempt(submission.quizId);
    attemptId = (await submitQuizAttempt(attempt.id, submission.answers)).id;
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", message: error.message };
    }
    throw error;
  }

  revalidatePath("/practice");
  redirect(`/practice/attempts/${attemptId}`);
}
