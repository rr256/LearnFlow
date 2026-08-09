"use client";

import { useActionState, useId } from "react";

import styles from "@/features/planner/AdaptPlanForm.module.css";
import { adaptPlan } from "@/features/planner/actions";
import { INITIAL_ADAPT_STATE, type AdaptState } from "@/features/planner/submission";

interface AdaptPlanFormProps {
  studyGoalId: string;
}

/**
 * Where a learner asks for their plan to be rebuilt around where they are.
 *
 * A client component only so it can show the result of the last submission
 * beside the button that produced it. It calls no API itself: the submission
 * goes to a server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript -- the form posts natively and
 * the page re-renders -- so adapting a plan does not depend on a hydrated
 * bundle.
 *
 * **The learner asks; nothing adapts on its own.** Marking an item completed
 * re-plans nothing, and saving a new study week re-plans nothing. That is the
 * promise PLN-004 made and this control keeps: the plan moves when the learner
 * decides it should, not underneath them.
 *
 * The hint says what adapting will do before it is pressed — what is dropped,
 * what is carried forward, and that the old plan is kept — because a learner
 * working from a plan needs to know what a rebuild costs them.
 */
export function AdaptPlanForm({ studyGoalId }: AdaptPlanFormProps) {
  const [state, submit, pending] = useActionState<AdaptState, FormData>(
    adaptPlan,
    INITIAL_ADAPT_STATE,
  );
  const messageId = useId();

  return (
    <form action={submit} className={styles.form}>
      <input type="hidden" name="study_goal_id" value={studyGoalId} />
      <button
        aria-describedby={state.status === "idle" ? undefined : messageId}
        className={styles.adapt}
        disabled={pending}
        type="submit"
      >
        {pending ? "Rebuilding around your progress…" : "Update my plan"}
      </button>
      <p className={styles.hint}>
        Rebuilds your plan from where you are: topics you have completed are not planned again, and
        work whose day has passed is carried forward. Your previous plan is kept, not deleted.
      </p>
      {state.status === "idle" ? null : (
        <p
          className={state.status === "error" ? styles.error : styles.adapted}
          id={messageId}
          role={state.status === "error" ? "alert" : "status"}
        >
          {state.message}
        </p>
      )}
    </form>
  );
}
