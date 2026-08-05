/**
 * Reading the topic-stage form into the request it makes.
 *
 * Kept apart from the server action so it can be tested as an ordinary
 * function. It holds no business rule: which stages exist, whether a topic
 * accepts one, and whether a learner exists to own the record are all decided by
 * the backend, which is the only place they can be enforced
 * (docs/development/coding-standards.md). What it checks here is that the form
 * produced something worth sending at all.
 */

import { isLearningStage, type LearningStage } from "@/types/progress";

/** What one submission of a topic-stage form asks for. */
export interface StageSubmission {
  topicId: string;
  learningStage: LearningStage;
}

/** What the control shows after a submission. */
export interface StageState {
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
export const INITIAL_STAGE_STATE: StageState = { status: "idle", message: "" };

function trimmed(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value.trim() : "";
}

/**
 * Read one submission of a topic-stage form.
 *
 * @returns The submission, or the reason it could not be built.
 */
export function readStageSubmission(
  form: FormData,
): { submission: StageSubmission } | { problem: string } {
  const topicId = trimmed(form.get("topic_id"));
  if (!topicId) {
    return { problem: "That form did not say which topic it was for." };
  }

  const learningStage = trimmed(form.get("learning_stage"));
  if (!isLearningStage(learningStage)) {
    return { problem: "Choose one of the listed stages." };
  }

  return { submission: { topicId, learningStage } };
}
