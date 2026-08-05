"use server";

/**
 * The write path for learner setup.
 *
 * A server action runs on the Next.js server, so the browser still makes no
 * request to the backend: the form posts to this process, which calls the API
 * with the same server-side `API_BASE_URL` the curriculum views use. The API
 * therefore needs no CORS allow-list and no API address reaches a client bundle,
 * which is the position ADR-015 takes and this feature inherits rather than
 * renegotiates.
 *
 * It holds no business rule. Whether a goal aims at enough, whether a timezone
 * is real, and whether an active goal already exists are decided by the backend;
 * this maps the form onto two API calls and maps the answer back into something
 * the form can show.
 *
 * **This module exports one async function and nothing else.** A `"use server"`
 * file may export only async functions, and a constant exported from one fails
 * at runtime with a `500` that neither `tsc` nor `next build` reports. The
 * state shape and its initial value therefore live in `submission.ts`.
 */

import { revalidatePath } from "next/cache";

import {
  readSetupSubmission,
  toNewStudyGoal,
  toStudyGoalUpdate,
  type SetupField,
  type SetupState,
} from "@/features/onboarding/submission";
import { ApiError, createStudyGoal, updateLearnerProfile, updateStudyGoal } from "@/lib/api-client";

/** Map an API `details` field path onto the form control that produced it. */
function toSetupField(path: string): SetupField | null {
  const name = path.replace(/^body\./, "");
  const known: SetupField[] = [
    "display_name",
    "timezone",
    "learning_program_id",
    "examination_schedule_id",
    "target_date",
  ];
  return known.includes(name as SetupField) ? (name as SetupField) : null;
}

function toState(error: ApiError): SetupState {
  if (error.isUnreachable) {
    return {
      status: "error",
      message:
        "The LearnFlow API could not be reached, so nothing was saved. Check that the backend is running, then try again.",
      field: null,
    };
  }
  const detail = error.details.find((entry) => toSetupField(entry.field) !== null);
  return {
    status: "error",
    message: error.message,
    field: detail ? toSetupField(detail.field) : null,
  };
}

/**
 * Save the learner's profile and study goal.
 *
 * The profile is written first, because a goal needs a learner to own it: the
 * backend refuses GOAL-001 with a conflict until one exists, and LRN-002 is what
 * creates it.
 *
 * The two writes are separate requests, so a goal that fails leaves an updated
 * profile behind. That is reported rather than hidden -- the message says the
 * profile was saved and the goal was not, and re-submitting the form retries
 * only what is still missing.
 */
export async function saveLearnerSetup(
  _previous: SetupState,
  form: FormData,
): Promise<SetupState> {
  const read = readSetupSubmission(form);
  if ("problem" in read) {
    return { status: "error", message: read.problem.message, field: read.problem.field };
  }
  const { submission } = read;

  let profileSaved = false;
  try {
    await updateLearnerProfile(submission.profile);
    profileSaved = true;

    if (submission.studyGoalId) {
      await updateStudyGoal(submission.studyGoalId, toStudyGoalUpdate(submission));
    } else {
      await createStudyGoal(toNewStudyGoal(submission));
    }
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    const state = toState(error);
    if (profileSaved) {
      // Say what did happen. "Something went wrong" would leave the learner
      // unsure whether to re-enter their name.
      revalidatePath("/setup");
      return {
        ...state,
        message: `Your profile was saved, but the study goal was not: ${state.message}`,
      };
    }
    return state;
  }

  revalidatePath("/setup");
  return {
    status: "saved",
    message: "Your setup is saved. You can change it here at any time.",
    field: null,
  };
}
