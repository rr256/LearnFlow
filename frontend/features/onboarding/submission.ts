/**
 * Reading the setup form into the two requests it makes.
 *
 * Kept apart from the server action so it can be tested as an ordinary
 * function. It holds no business rule: whether a goal aims at enough, whether a
 * timezone is real, and whether an active goal already exists are all decided by
 * the backend, which is the only place they can be enforced
 * (docs/development/coding-standards.md).
 *
 * What it does own is the difference between "the learner left this blank" and
 * "the learner cleared it" -- an HTML form sends an empty string for both, and
 * the API contract distinguishes absent from null.
 */

import type { LearnerProfileUpdate } from "@/types/learner";
import type { NewStudyGoal, StudyGoalUpdate } from "@/types/study-goal";

/** How the learner chose to describe their horizon. */
export type GoalTarget = "examination" | "target_date";

/** What one submission of the setup form asks for. */
export interface SetupSubmission {
  profile: LearnerProfileUpdate;
  learningProgramId: string;
  examinationScheduleId: string | null;
  targetDate: string | null;
  /** The goal to update, or null to create one. */
  studyGoalId: string | null;
}

/** A field the form can report a problem against. */
export type SetupField =
  | "display_name"
  | "timezone"
  | "learning_program_id"
  | "examination_schedule_id"
  | "target_date";

/** A reason the submission could not be built, tied to the field at fault. */
export interface SubmissionProblem {
  field: SetupField;
  message: string;
}

/** What the form shows after a submission. */
export interface SetupState {
  status: "idle" | "saved" | "error";
  message: string;
  /** The field to mark, when the failure belongs to one. */
  field: SetupField | null;
}

/**
 * The state before anything has been submitted.
 *
 * It lives here rather than beside the action because a `"use server"` module
 * may export only async functions -- a constant exported from one fails at
 * runtime, which neither the type checker nor the production build reports.
 */
export const INITIAL_SETUP_STATE: SetupState = { status: "idle", message: "", field: null };

function trimmed(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value.trim() : "";
}

/**
 * Read one submission of the setup form.
 *
 * @returns The submission, or the first problem that stops it being built.
 */
export function readSetupSubmission(
  form: FormData,
): { submission: SetupSubmission } | { problem: SubmissionProblem } {
  const learningProgramId = trimmed(form.get("learning_program_id"));
  if (!learningProgramId) {
    return {
      problem: {
        field: "learning_program_id",
        message: "Choose the learning program you are studying.",
      },
    };
  }

  const target = trimmed(form.get("goal_target")) as GoalTarget;
  const examinationScheduleId = trimmed(form.get("examination_schedule_id"));
  const targetDate = trimmed(form.get("target_date"));

  if (target === "examination" && !examinationScheduleId) {
    return {
      problem: {
        field: "examination_schedule_id",
        message: "Choose the examination you are preparing for.",
      },
    };
  }
  if (target === "target_date" && !targetDate) {
    return {
      problem: {
        field: "target_date",
        message: "Choose the date you are working toward.",
      },
    };
  }

  const displayName = trimmed(form.get("display_name"));
  const timezone = trimmed(form.get("timezone"));

  return {
    submission: {
      // An empty name is sent as null, which removes a stored one. Absence
      // would leave it, and a learner who cleared the box meant to clear it.
      profile: {
        display_name: displayName || null,
        ...(timezone ? { timezone } : {}),
      },
      learningProgramId,
      // Only one horizon is submitted at a time, so the other is cleared
      // rather than left behind from a previous choice.
      examinationScheduleId: target === "examination" ? examinationScheduleId : null,
      targetDate: target === "target_date" ? targetDate : null,
      studyGoalId: trimmed(form.get("study_goal_id")) || null,
    },
  };
}

/** The GOAL-001 body one submission implies. */
export function toNewStudyGoal(submission: SetupSubmission): NewStudyGoal {
  return {
    learning_program_id: submission.learningProgramId,
    examination_schedule_id: submission.examinationScheduleId,
    target_date: submission.targetDate,
  };
}

/** The GOAL-004 body one submission implies. */
export function toStudyGoalUpdate(submission: SetupSubmission): StudyGoalUpdate {
  return {
    examination_schedule_id: submission.examinationScheduleId,
    target_date: submission.targetDate,
  };
}
