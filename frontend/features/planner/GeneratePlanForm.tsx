"use client";

import { useActionState, useId } from "react";

import styles from "@/features/planner/GeneratePlanForm.module.css";
import { createStudyPlan } from "@/features/planner/actions";
import { INITIAL_PLAN_STATE, type PlanState } from "@/features/planner/submission";

interface GeneratePlanFormProps {
  studyGoalId: string;
  /** Whether a plan already exists, which changes what the button offers to do. */
  hasPlan: boolean;
}

/**
 * Where a learner asks for a plan to be generated.
 *
 * A client component only so it can show the result of the last submission
 * beside the button that produced it. It calls no API itself: the submission
 * goes to a server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript -- the form posts natively and
 * the page re-renders -- so generating a plan does not depend on a hydrated
 * bundle.
 *
 * The button says plainly what rebuilding does, because a learner who has been
 * working from a plan needs to know the old one is kept rather than discarded.
 */
export function GeneratePlanForm({ studyGoalId, hasPlan }: GeneratePlanFormProps) {
  const [state, submit, pending] = useActionState<PlanState, FormData>(
    createStudyPlan,
    INITIAL_PLAN_STATE,
  );
  const messageId = useId();

  return (
    <form action={submit} className={styles.form}>
      <input type="hidden" name="study_goal_id" value={studyGoalId} />
      <button
        aria-describedby={state.status === "idle" ? undefined : messageId}
        className={styles.generate}
        disabled={pending}
        type="submit"
      >
        {pending
          ? "Building your plan…"
          : hasPlan
            ? "Rebuild my plan"
            : "Create my study plan"}
      </button>
      <p className={styles.hint}>
        {hasPlan
          ? "Rebuilding uses your setup as it stands now. Your previous plan is kept, not deleted."
          : "Built from your curriculum, your goal, your study week, and how you said you want to study."}
      </p>
      {state.status === "idle" ? null : (
        <p
          className={state.status === "error" ? styles.error : styles.saved}
          id={messageId}
          role={state.status === "error" ? "alert" : "status"}
        >
          {state.message}
        </p>
      )}
    </form>
  );
}
