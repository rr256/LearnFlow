"use server";

/**
 * The write path for manual topic progress.
 *
 * A server action runs on the Next.js server, so the browser still makes no
 * request to the backend: the form posts to this process, which calls the API
 * with the same server-side `API_BASE_URL` the curriculum views use. The API
 * therefore needs no CORS allow-list and no API address reaches a client bundle,
 * which is the position ADR-015 takes and this feature inherits rather than
 * renegotiates.
 *
 * It holds no business rule. Which stages exist, whether a topic accepts one,
 * and whether a learner exists to own the record are decided by the backend;
 * this maps the form onto one API call and maps the answer back into something
 * the control can show.
 *
 * **This module exports one async function and nothing else.** A `"use server"`
 * file may export only async functions, and a constant exported from one fails
 * at runtime with a `500` that neither `tsc` nor `next build` reports. The state
 * shape and its initial value therefore live in `submission.ts`.
 */

import { revalidatePath } from "next/cache";

import { readStageSubmission, type StageState } from "@/features/progress/submission";
import { ApiError, recordTopicStage } from "@/lib/api-client";
import { LEARNING_STAGE_LABELS, isLearningStage } from "@/types/progress";

/**
 * Record the learner's stage for one topic.
 *
 * A conflict means the learner profile does not exist yet, so the message says
 * what to do about it rather than repeating the backend's wording -- setup is a
 * screen away, and "no learner profile exists" is not an instruction.
 */
export async function saveTopicStage(_previous: StageState, form: FormData): Promise<StageState> {
  const read = readStageSubmission(form);
  if ("problem" in read) {
    return { status: "error", message: read.problem };
  }
  const { submission } = read;

  let saved;
  try {
    saved = await recordTopicStage(submission.topicId, submission.learningStage);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    if (error.isUnreachable) {
      return {
        status: "error",
        message:
          "The LearnFlow API could not be reached, so nothing was saved. Check that the backend is running, then try again.",
      };
    }
    if (error.isConflict) {
      return {
        status: "error",
        message: "Complete your learner setup first, then record your progress here.",
      };
    }
    return { status: "error", message: error.message };
  }

  // The curriculum page reads the saved stages, so it has to be re-rendered for
  // the change to survive a navigation back to it.
  revalidatePath("/curriculum", "layout");

  const stage = saved.learning_stage;
  const label = isLearningStage(stage) ? LEARNING_STAGE_LABELS[stage] : stage;
  return { status: "saved", message: `Saved as ${label}.` };
}
