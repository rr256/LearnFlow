"use client";

import { useActionState, useId } from "react";

import styles from "@/features/revision/ScheduleRevisionsForm.module.css";
import { scheduleRevisionsAction } from "@/features/revision/actions";
import { INITIAL_SCHEDULE_STATE, type ScheduleState } from "@/features/revision/submission";

/**
 * The button that asks for reviews to be scheduled from finished work.
 *
 * **The learner asks; nothing schedules on its own.** Completing a plan item
 * creates no review, so a list never rearranges itself under a learner working
 * through it — which is ADR-021's promise for a plan item, kept here for a
 * review.
 *
 * A client component only so it can report what the last run did. It calls no
 * API itself: the submission goes to a server action, so the browser still never
 * reaches the backend, and the form posts natively without JavaScript.
 *
 * The hint says what pressing it does *before* it is pressed, including that
 * asking twice is safe — a learner who cannot tell whether a button duplicates
 * their reviews will not press it.
 */
export function ScheduleRevisionsForm() {
  const [state, submit, pending] = useActionState<ScheduleState, FormData>(
    scheduleRevisionsAction,
    INITIAL_SCHEDULE_STATE,
  );
  const messageId = useId();

  return (
    <form action={submit} className={styles.form}>
      <p className={styles.hint}>
        Bring finished topics back for review. Each returns a set number of days after you
        finished it, from the learning stage you recorded — or from LearnFlow&apos;s own interval
        where you have recorded none. Asking twice adds nothing: a topic that already has a review
        waiting is left alone.
      </p>

      <button
        aria-describedby={state.status === "idle" ? undefined : messageId}
        disabled={pending}
        type="submit"
      >
        Schedule reviews
      </button>

      {state.status === "idle" ? null : (
        <p
          className={state.status === "error" ? styles.failed : styles.saved}
          id={messageId}
          role={state.status === "error" ? "alert" : "status"}
        >
          {state.message}
        </p>
      )}
    </form>
  );
}
