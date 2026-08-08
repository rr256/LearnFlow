"use client";

import { useActionState, useId } from "react";

import styles from "@/features/planner/PlanItemStatusControl.module.css";
import { savePlanItemStatus } from "@/features/planner/actions";
import { INITIAL_PLAN_ITEM_STATE, type PlanItemState } from "@/features/planner/submission";

interface PlanItemStatusControlProps {
  planItemId: string;
  /** Named in the button's accessible label, so each one is distinguishable. */
  topicName: string;
  /** The item's stored status, as the API sent it. */
  status: string;
}

/**
 * Where a learner marks one plan item completed, or returns it to planned.
 *
 * A client component only so it can show the result of the last submission
 * beside the item it acted on. It calls no API itself: the submission goes to a
 * server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript -- the form posts natively and
 * the page re-renders -- so completing an item does not depend on a hydrated
 * bundle.
 *
 * **Completing is reversible.** A learner who marked the wrong line gets a
 * control that returns it to planned, not a dead end. Completing an item says its
 * planned work happened; it is not a claim about the topic, and nothing here
 * reads as a verdict on the learner.
 *
 * An item in a status this build does not offer -- `skipped` or `postponed`,
 * which the API does not yet accept -- is shown as the API sent it, with no
 * control, rather than being quietly presented as something a learner can move.
 */
export function PlanItemStatusControl({
  planItemId,
  topicName,
  status,
}: PlanItemStatusControlProps) {
  const [state, submit, pending] = useActionState<PlanItemState, FormData>(
    savePlanItemStatus,
    INITIAL_PLAN_ITEM_STATE,
  );
  const messageId = useId();

  if (status !== "planned" && status !== "completed") {
    return <p className={styles.unmovable}>Status: {status}</p>;
  }

  const done = status === "completed";
  const next = done ? "planned" : "completed";

  return (
    <form action={submit} className={styles.control}>
      <input type="hidden" name="plan_item_id" value={planItemId} />
      <input type="hidden" name="status" value={next} />

      <button
        aria-describedby={state.status === "idle" ? undefined : messageId}
        className={done ? styles.undo : styles.complete}
        disabled={pending}
        type="submit"
      >
        {/*
          The visible words stay part of the accessible name rather than being
          replaced by an `aria-label`, so speaking the label a learner can see
          still activates the button. The topic is appended for a screen reader,
          because a week holding several items would otherwise present the same
          name on every one of them.

          Both labels name the state they move the item *to*, using the
          vocabulary docs/domain/terminology.md settles, so a learner returning to
          the page a week later reads what the button will do rather than an
          "undo" whose subject has been forgotten.
        */}
        {done ? "Return to planned" : "Mark completed"}
        <span className={styles.forScreenReaders}> — {topicName}</span>
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
