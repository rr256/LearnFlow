/**
 * Reading the checkpoint-practice forms into the requests they make.
 *
 * Kept apart from the server actions so they can be tested as ordinary
 * functions. They hold no practice rule: how many options a question may offer,
 * whether two options say the same thing, which topics exist, which questions a
 * quiz asks, and whether an answer is correct are all decided by the backend,
 * which is the only place they can be enforced
 * (docs/development/coding-standards.md). What is checked here is that a form
 * produced something worth sending at all.
 *
 * **Nothing here marks an answer.** A form carries what the learner chose; the
 * comparison with the expected option happens in
 * `backend/app/domain/checkpoint_marking.py` and nowhere else.
 */

import { QUESTION_STATUSES, type QuestionStatus } from "@/types/practice";

/**
 * How many option fields the question form offers.
 *
 * Four, which is what a GATE multiple-choice question conventionally has. The
 * backend accepts between two and six; a learner needing fewer leaves the last
 * fields blank, and blanks are dropped before the request is sent.
 */
export const OPTION_FIELD_COUNT = 4;

/**
 * What the question form shows after a submission.
 *
 * The message says what happened; the status only decides how it is announced.
 */
export interface QuestionFormState {
  status: "idle" | "saved" | "error";
  message: string;
}

/**
 * The state before anything has been submitted.
 *
 * It lives here rather than beside the action because a `"use server"` module
 * may export only async functions -- a constant exported from one fails at
 * runtime, which neither the type checker nor the production build reports.
 */
export const INITIAL_QUESTION_FORM_STATE: QuestionFormState = { status: "idle", message: "" };

/** What the control beside one question shows after a submission. */
export interface QuestionStatusState {
  status: "idle" | "saved" | "error";
  message: string;
}

export const INITIAL_QUESTION_STATUS_STATE: QuestionStatusState = { status: "idle", message: "" };

/** What the "start a quiz" form shows when it could not start one. */
export interface StartQuizState {
  status: "idle" | "error";
  message: string;
}

export const INITIAL_START_QUIZ_STATE: StartQuizState = { status: "idle", message: "" };

/** What the answer form shows when a submission could not be sent. */
export interface AnswerFormState {
  status: "idle" | "error";
  message: string;
}

export const INITIAL_ANSWER_FORM_STATE: AnswerFormState = { status: "idle", message: "" };

function trimmed(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value.trim() : "";
}

/** What the question form asks for, ready to send to QZ-008. */
export interface QuestionSubmission {
  prompt: string;
  options: string[];
  correct_option_index: number;
  explanation: string | null;
  topic_ids: string[];
}

/**
 * Read the question form, or null when it asks for nothing sendable.
 *
 * Blank option fields are dropped, so a learner writing a two-option question
 * leaves the last two empty rather than being shown a different form. The chosen
 * answer is re-indexed against the options that survived, so dropping a blank
 * cannot silently move which option is marked correct.
 *
 * Everything else is the backend's to judge: two options saying the same thing,
 * a topic that does not exist, and an answer naming no option are all refused
 * there, and the refusal is shown to the learner rather than pre-empted here.
 */
export function readQuestionSubmission(form: FormData): QuestionSubmission | null {
  const prompt = trimmed(form.get("prompt"));
  const chosen = trimmed(form.get("correct_option"));
  const topicIds = form.getAll("topic_ids").filter((id): id is string => typeof id === "string");

  const offered: { index: number; text: string }[] = [];
  for (let index = 0; index < OPTION_FIELD_COUNT; index += 1) {
    const text = trimmed(form.get(`option_${index}`));
    if (text) {
      offered.push({ index, text });
    }
  }

  const correct = offered.findIndex((option) => String(option.index) === chosen);
  if (!prompt || offered.length < 2 || correct === -1 || topicIds.length === 0) {
    return null;
  }

  const explanation = trimmed(form.get("explanation"));
  return {
    prompt,
    options: offered.map((option) => option.text),
    correct_option_index: correct,
    explanation: explanation || null,
    topic_ids: topicIds,
  };
}

/** What the correction form asks for, ready to send to QZ-010. */
export interface QuestionCorrectionSubmission extends QuestionSubmission {
  questionId: string;
}

/**
 * Read the correction form, or null when it asks for nothing sendable.
 *
 * The same reading as a newly written question, plus the question it corrects.
 * The content travels as one group, so a correction sends every field the write
 * form sends — an explanation left blank clears the stored one, which is what
 * QZ-010 documents and ADR-019 fixed for a preference group.
 *
 * Whether the question may still be corrected is **not** decided here: a quiz
 * having already asked it is a backend fact this screen cannot see, and the
 * refusal it returns is shown to the learner rather than guessed at.
 */
export function readQuestionCorrection(form: FormData): QuestionCorrectionSubmission | null {
  const questionId = trimmed(form.get("question_id"));
  const submission = readQuestionSubmission(form);
  if (!questionId || !submission) {
    return null;
  }
  return { questionId, ...submission };
}

/** What the status control asks for, ready to send to QZ-010. */
export interface QuestionStatusSubmission {
  questionId: string;
  status: QuestionStatus;
}

/** Read the status control, or null when it named something unsendable. */
export function readQuestionStatusSubmission(form: FormData): QuestionStatusSubmission | null {
  const questionId = trimmed(form.get("question_id"));
  const status = trimmed(form.get("status"));
  if (!questionId || !QUESTION_STATUSES.includes(status as QuestionStatus)) {
    return null;
  }
  return { questionId, status: status as QuestionStatus };
}

/** Read the topics a quiz should cover, or null when none were chosen. */
export function readQuizTopics(form: FormData): string[] | null {
  const topicIds = form.getAll("topic_ids").filter((id): id is string => typeof id === "string");
  return topicIds.length > 0 ? topicIds : null;
}

/** One answer, as the answer form carries it. */
export interface AnswerSubmissionFields {
  question_id: string;
  option_key: string;
}

/** What the answer form asks for, ready to send to QZ-003 and QZ-005. */
export interface AttemptSubmission {
  quizId: string;
  answers: AnswerSubmissionFields[];
}

/**
 * Read the answer form, or null when it does not name the quiz.
 *
 * **An unanswered question is simply absent.** A radio group nobody chose from
 * posts nothing, so the question is left out of the submission and the backend
 * records it as unanswered rather than as wrong. Submitting with nothing
 * answered is therefore allowed, and is not the same as submitting nothing.
 *
 * Answers are named `answer_<question id>`, so the form needs no hidden index
 * and cannot pair an option with the wrong question.
 */
export function readAttemptSubmission(form: FormData): AttemptSubmission | null {
  const quizId = trimmed(form.get("quiz_id"));
  if (!quizId) {
    return null;
  }

  const answers: AnswerSubmissionFields[] = [];
  for (const [field, value] of form.entries()) {
    if (!field.startsWith("answer_") || typeof value !== "string" || !value) {
      continue;
    }
    answers.push({ question_id: field.slice("answer_".length), option_key: value });
  }
  return { quizId, answers };
}
