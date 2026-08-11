"use client";

import { useActionState, useId } from "react";

import styles from "@/features/planner/PlanItemStatusControl.module.css";
import { savePlanItemStatus } from "@/features/planner/actions";
import { INITIAL_PLAN_ITEM_STATE, type PlanItemState } from "@/features/planner/submission";
import {
  PLAN_ITEM_STATUS_CHANGES,
  PLAN_ITEM_STATUS_CHANGE_LABELS,
  type PlanItemStatusChange,
} from "@/types/study-plan";

interface PlanItemStatusControlProps {
  planItemId: string;
  /** Named in each button's accessible label, so they stay distinguishable. */
  topicName: string;
  /** The item's stored status, as the API sent it. */
  status: string;
}

/** True when the API would accept this status as a target, so it can be offered. */
function isOffered(status: string): status is PlanItemStatusChange {
  return (PLAN_ITEM_STATUS_CHANGES as readonly string[]).includes(status);
}

/**
 * Where a learner says what became of one plan item's work.
 *
 * It offers the two statuses the item is not already in, so completing,
 * skipping, and putting an item back are the same control rather than three.
 * Nothing here is one-way: PLN-004 accepts a move between any two of the three,
 * and a mis-tap on a list of sixty items should not be permanent.
 *
 * A client component only so it can show the result of the last submission
 * beside the item it acted on. It calls no API itself: each submission goes to a
 * server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript -- each form posts natively and
 * the page re-renders -- so moving an item does not depend on a hydrated bundle.
 * The status travels in a hidden field rather than on the button, so a scriptless
 * submission carries it exactly as a hydrated one does.
 *
 * **Skipping is a statement about this item, not about the topic.** The wording
 * says so, and the message after a skip says the topic is planned again — a
 * learner reading "skipped" alone could reasonably think they had dropped it for
 * good.
 *
 * An item in a status the API will not take as a target -- `postponed`, which
 * only ever sits on a superseded plan -- is shown as the API sent it, with no
 * control, rather than being presented as something a learner can move.
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

  if (!isOffered(status)) {
    return <p className={styles.unmovable}>Status: {status}</p>;
  }

  const targets = PLAN_ITEM_STATUS_CHANGES.filter((target) => target !== status);

  return (
    <div className={styles.control}>
      <div className={styles.actions}>
        {targets.map((target) => (
          <form action={submit} key={target}>
            <input type="hidden" name="plan_item_id" value={planItemId} />
            <input type="hidden" name="status" value={target} />

            <button
              aria-describedby={state.status === "idle" ? undefined : messageId}
              className={styles[target] ?? ""}
              disabled={pending}
              type="submit"
            >
              {/*
                The visible words stay part of the accessible name rather than
                being replaced by an `aria-label`, so speaking the label a learner
                can see still activates the button. The topic is appended for a
                screen reader, because a week holding several items would
                otherwise present the same two names on every one of them.

                Every label names the state it moves the item *to*, using the
                vocabulary docs/domain/terminology.md settles, so a learner
                returning to the page a week later reads what the button will do
                rather than an "undo" whose subject has been forgotten.
              */}
              {PLAN_ITEM_STATUS_CHANGE_LABELS[target]}
              <span className={styles.forScreenReaders}> — {topicName}</span>
            </button>
          </form>
        ))}
      </div>

      {state.status === "idle" ? null : (
        <p
          className={state.status === "error" ? styles.failed : styles.saved}
          id={messageId}
          role={state.status === "error" ? "alert" : "status"}
        >
          {state.message}
        </p>
      )}
    </div>
  );
}
