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
import {
  MAXIMUM_SESSION_MINUTES,
  MINIMUM_SESSION_MINUTES,
  isTopicSequencing,
  type NewStudyGoal,
  type PlanningPreferences,
  type StudyGoalUpdate,
} from "@/types/study-goal";

/** How the learner chose to describe their horizon. */
export type GoalTarget = "examination" | "target_date";

/** What one submission of the setup form asks for. */
export interface SetupSubmission {
  profile: LearnerProfileUpdate;
  learningProgramId: string;
  examinationScheduleId: string | null;
  targetDate: string | null;
  /**
   * The whole preference group, which the goal write replaces.
   *
   * The form shows every preference at once, so what it submits is the complete
   * set: a control the learner cleared is sent as null rather than left out, and
   * the stored value is replaced rather than merged with.
   */
  planningPreferences: PlanningPreferences;
  /** The goal to update, or null to create one. */
  studyGoalId: string | null;
}

/** A field the form can report a problem against. */
export type SetupField =
  | "display_name"
  | "timezone"
  | "learning_program_id"
  | "examination_schedule_id"
  | "target_date"
  | "preferred_session_minutes"
  | "topic_sequencing";

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

  const preferences = readPlanningPreferences(form);
  if ("problem" in preferences) {
    return preferences;
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
      planningPreferences: preferences.preferences,
      studyGoalId: trimmed(form.get("study_goal_id")) || null,
    },
  };
}

/**
 * Read the preference controls into the group the goal write replaces.
 *
 * A control left blank is sent as null, which unsets it. The form shows both, so
 * a blank one is a learner saying "no preference" rather than a learner who did
 * not reach the field.
 *
 * The bounds are checked here as well as by the API, so a mistyped number is
 * reported beside the box rather than after a round trip. The backend remains the
 * only place they are enforced.
 */
function readPlanningPreferences(
  form: FormData,
): { preferences: PlanningPreferences } | { problem: SubmissionProblem } {
  const entered = trimmed(form.get("preferred_session_minutes"));
  let preferredSessionMinutes: number | null = null;
  if (entered) {
    const minutes = Number(entered);
    if (!Number.isInteger(minutes)) {
      return {
        problem: {
          field: "preferred_session_minutes",
          message: "Enter a session length as a whole number of minutes, or leave it empty.",
        },
      };
    }
    if (minutes < MINIMUM_SESSION_MINUTES || minutes > MAXIMUM_SESSION_MINUTES) {
      return {
        problem: {
          field: "preferred_session_minutes",
          message: `A session length must be between ${MINIMUM_SESSION_MINUTES} and ${MAXIMUM_SESSION_MINUTES} minutes, or empty.`,
        },
      };
    }
    preferredSessionMinutes = minutes;
  }

  const sequencing = trimmed(form.get("topic_sequencing"));
  if (sequencing && !isTopicSequencing(sequencing)) {
    return {
      problem: {
        field: "topic_sequencing",
        message: "Choose one of the topic orders offered, or leave it unset.",
      },
    };
  }

  return {
    preferences: {
      preferred_session_minutes: preferredSessionMinutes,
      topic_sequencing: sequencing || null,
    },
  };
}

/** The GOAL-001 body one submission implies. */
export function toNewStudyGoal(submission: SetupSubmission): NewStudyGoal {
  return {
    learning_program_id: submission.learningProgramId,
    examination_schedule_id: submission.examinationScheduleId,
    target_date: submission.targetDate,
    planning_preferences: submission.planningPreferences,
  };
}

/** The GOAL-004 body one submission implies. */
export function toStudyGoalUpdate(submission: SetupSubmission): StudyGoalUpdate {
  return {
    examination_schedule_id: submission.examinationScheduleId,
    target_date: submission.targetDate,
    // Sent every time, because the form carries the whole group: a preference the
    // learner cleared has to reach the API as null to be unset.
    planning_preferences: submission.planningPreferences,
  };
}
