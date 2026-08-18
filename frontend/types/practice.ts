/**
 * Checkpoint-practice types, derived from the QZ-001 to QZ-010 response contract
 * in docs/api/endpoints.md#checkpoint-quiz-endpoints.
 *
 * **Nothing here carries a score.** There is no total, no mark, no count of
 * correct answers, and no percentage — a result is a list of per-question
 * outcomes, which is what docs/domain/terminology.md requires and ADR-033
 * records. A screen renders the fields it was given and derives none, so no
 * component may add one up either.
 *
 * **Nothing here recommends or ranks.** Which question is worth answering first,
 * which topic to practise, and how a learner is doing are decided nowhere in the
 * frontend: a quiz asks every question the learner wrote for the topics they
 * chose, in the order the API returned
 * (docs/development/coding-standards.md#ui-responsibilities).
 *
 * A quiz being taken carries no expected answer and no explanation — the API has
 * nowhere to put them — so `QuizQuestion` below has no field for either.
 */

import type { CollectionEnvelope, DataEnvelope } from "@/types/api";

/** The statuses a practice question can be in. */
export const QUESTION_STATUSES = ["ready", "retired"] as const;

export type QuestionStatus = (typeof QUESTION_STATUSES)[number];

/**
 * What each status control says, naming the state it moves the question *to*.
 *
 * Nothing deletes: setting a question aside is reversible, so both directions
 * are offered and neither is final.
 */
export const QUESTION_STATUS_LABELS: Record<QuestionStatus, string> = {
  ready: "Use it again",
  retired: "Set aside",
};

/** How a question's current state reads where it is listed. */
export const QUESTION_STATE_LABELS: Record<QuestionStatus, string> = {
  ready: "In use",
  retired: "Set aside",
};

/** A curriculum topic a question, quiz, or attempt covers. */
export interface PracticeTopic {
  id: string;
  code: string | null;
  name: string;
  subject_id: string;
  subject_name: string;
}

/** One option a question offers. Keys are assigned by the backend, by position. */
export interface AnswerOption {
  key: string;
  text: string;
}

/** One practice question as its author reads it, with its expected answer. */
export interface PracticeQuestion {
  id: string;
  author_learner_id: string | null;
  question_type: string;
  source_type: string;
  prompt: string;
  options: AnswerOption[];
  expected_option_key: string;
  explanation: string | null;
  status: string;
  written_at: string;
  topics: PracticeTopic[];
}

/**
 * One question as a quiz asks it.
 *
 * No expected answer and no explanation, deliberately: QZ-002 does not send
 * them, so a quiz open in a browser cannot be read for its answers.
 */
export interface QuizQuestion {
  position: number;
  question_id: string;
  prompt: string;
  options: AnswerOption[];
}

/** One assembled checkpoint quiz. */
export interface CheckpointQuiz {
  id: string;
  learner_id: string | null;
  title: string;
  source_type: string;
  status: string;
  topics: PracticeTopic[];
  questions: QuizQuestion[];
}

/**
 * What became of one question in one attempt.
 *
 * `expected_option_key` and `explanation` are null until the attempt has been
 * marked. `is_correct` is null for a question left unanswered — **an unanswered
 * question is not a wrong one** — which is why the three states are kept apart
 * rather than collapsed into a boolean.
 */
export interface AttemptOutcome {
  position: number;
  question_id: string;
  prompt: string;
  options: AnswerOption[];
  chosen_option_key: string | null;
  expected_option_key: string | null;
  explanation: string | null;
  is_correct: boolean | null;
}

/** One attempt, with what became of each question. */
export interface QuizAttempt {
  id: string;
  learner_id: string;
  checkpoint_quiz_id: string;
  quiz_title: string;
  status: string;
  started_at: string | null;
  submitted_at: string | null;
  evaluated_at: string | null;
  topics: PracticeTopic[];
  outcomes: AttemptOutcome[];
}

/** What QZ-008 asks for when a learner writes a question. */
export interface NewPracticeQuestion {
  prompt: string;
  options: string[];
  correct_option_index: number;
  explanation?: string | null;
  topic_ids: string[];
}

/** One answer in a submission. A question left alone is simply omitted. */
export interface SubmittedAnswer {
  question_id: string;
  option_key: string;
}

export type PracticeQuestionResponse = DataEnvelope<PracticeQuestion>;
export type PracticeQuestionCollectionResponse = CollectionEnvelope<PracticeQuestion>;
export type CheckpointQuizResponse = DataEnvelope<CheckpointQuiz>;
export type QuizAttemptResponse = DataEnvelope<QuizAttempt>;
export type QuizAttemptCollectionResponse = CollectionEnvelope<QuizAttempt>;

/**
 * How one outcome reads, in words rather than as a mark.
 *
 * The three states an outcome can be in, named so no caller has to decide what
 * `null` means. Nothing here is a score, and nothing is coloured by severity.
 */
export function outcomeLabel(outcome: AttemptOutcome): string {
  if (outcome.is_correct === null) {
    return "You did not answer this one";
  }
  return outcome.is_correct ? "You chose the expected answer" : "Not the expected answer";
}

/** The wording of one option, or its key when the option has since gone. */
export function optionText(options: AnswerOption[], key: string | null): string | null {
  if (key === null) {
    return null;
  }
  return options.find((option) => option.key === key)?.text ?? key;
}
