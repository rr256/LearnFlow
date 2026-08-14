"use client";

import { useActionState, useId } from "react";

import styles from "@/features/revision/RevisionStatusControl.module.css";
import { saveRevisionStatus } from "@/features/revision/actions";
import { INITIAL_REVISION_STATE, type RevisionState } from "@/features/revision/submission";
import {
  REVISION_STATUS_CHANGES,
  REVISION_STATUS_CHANGE_LABELS,
  type RevisionStatusChange,
} from "@/types/revision";

interface RevisionStatusControlProps {
  revisionId: string;
  /** Named in each button's accessible label, so they stay distinguishable. */
  topicName: string;
  /** The revision's stored status, as the API sent it. */
  status: string;
}

/** True when the API would accept this status as a target, so it can be offered. */
function isOffered(status: string): status is RevisionStatusChange {
  return (REVISION_STATUS_CHANGES as readonly string[]).includes(status);
}

/**
 * Where a learner says what became of one review.
 *
 * It offers the three statuses the revision is not already in, so marking one
 * reviewed, skipping it, postponing it, and putting it back are the same control
 * rather than four. Nothing here is one-way: REV-003 accepts a move between any
 * two of the four, and a mis-tap should not be permanent.
 *
 * This deliberately mirrors `PlanItemStatusControl`. A learner who has learned
 * how to mark a plan item should not have to learn a second vocabulary for a
 * review, so the shape, the reversibility, and the hidden-field submission are
 * the same. The labels differ because the subject does: a review is *reviewed*,
 * not *completed*.
 *
 * A client component only so it can show the result of the last submission
 * beside the revision it acted on. It calls no API itself: each submission goes
 * to a server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript -- each form posts natively and
 * the page re-renders -- so moving a revision does not depend on a hydrated
 * bundle. The status travels in a hidden field rather than on the button, so a
 * scriptless submission carries it exactly as a hydrated one does.
 *
 * A revision in a status the API will not take as a target -- `scheduled`, which
 * nothing writes -- is shown as the API sent it, with no control, rather than
 * being presented as something a learner can move.
 */
export function RevisionStatusControl({
  revisionId,
  topicName,
  status,
}: RevisionStatusControlProps) {
  const [state, submit, pending] = useActionState<RevisionState, FormData>(
    saveRevisionStatus,
    INITIAL_REVISION_STATE,
  );
  const messageId = useId();

  if (!isOffered(status)) {
    return <p className={styles.unmovable}>Status: {status}</p>;
  }

  const targets = REVISION_STATUS_CHANGES.filter((target) => target !== status);

  return (
    <div className={styles.control}>
      <div className={styles.actions}>
        {targets.map((target) => (
          <form action={submit} key={target}>
            <input type="hidden" name="revision_id" value={revisionId} />
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
                screen reader, because a list holding several reviews would
                otherwise present the same names on every one of them.
              */}
              {REVISION_STATUS_CHANGE_LABELS[target]}
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
