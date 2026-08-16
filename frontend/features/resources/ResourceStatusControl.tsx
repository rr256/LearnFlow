"use client";

import { useActionState, useId } from "react";

import styles from "@/features/resources/ResourceStatusControl.module.css";
import { saveResourceStatus } from "@/features/resources/actions";
import {
  INITIAL_RESOURCE_STATUS_STATE,
  type ResourceStatusState,
} from "@/features/resources/submission";
import { RESOURCE_STATUS_LABELS, type ResourceStatus } from "@/types/resource";

interface ResourceStatusControlProps {
  resourceId: string;
  /** Named in the button's accessible label, so several stay distinguishable. */
  title: string;
  /** The resource's stored status, as the API sent it. */
  status: string;
}

/** True when the API would accept this status as a target, so it can be offered. */
function isOffered(status: string): status is ResourceStatus {
  return status === "registered" || status === "archived";
}

/**
 * Where a learner puts material aside, or brings it back.
 *
 * **Nothing here deletes.** Putting material aside is a statement that the
 * learner is not using it now, and it is reversible from this same control —
 * which is why the catalogue goes on listing it. That is the position ADR-022
 * took for a superseded plan and ADR-024 for a skipped item: a record is kept and
 * the learner's statement about it can be taken back.
 *
 * A client component only so it can show the result of the last submission
 * beside the material it acted on. It calls no API itself: the submission goes to
 * a server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript — the form posts natively and the
 * page re-renders — so putting material aside does not depend on a hydrated
 * bundle. The status travels in a hidden field rather than on the button, so a
 * scriptless submission carries it exactly as a hydrated one does.
 */
export function ResourceStatusControl({
  resourceId,
  title,
  status,
}: ResourceStatusControlProps) {
  const [state, submit, pending] = useActionState<ResourceStatusState, FormData>(
    saveResourceStatus,
    INITIAL_RESOURCE_STATUS_STATE,
  );
  const messageId = useId();

  if (!isOffered(status)) {
    return <p className={styles.unmovable}>Status: {status}</p>;
  }

  const target: ResourceStatus = status === "archived" ? "registered" : "archived";

  return (
    <div className={styles.control}>
      <form action={submit}>
        <input type="hidden" name="resource_id" value={resourceId} />
        <input type="hidden" name="status" value={target} />

        <button
          aria-describedby={state.status === "idle" ? undefined : messageId}
          className={styles[target] ?? ""}
          disabled={pending}
          type="submit"
        >
          {/*
            The visible words stay part of the accessible name rather than being
            replaced by an `aria-label`, so speaking the label a learner can see
            still activates the button. The title is appended for a screen
            reader, because a list holding several would otherwise present the
            same name on every one of them.
          */}
          {RESOURCE_STATUS_LABELS[target]}
          <span className={styles.forScreenReaders}> — {title}</span>
        </button>
      </form>

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
