"use client";

import { useActionState, useId } from "react";

import styles from "@/features/practice/QuestionStatusControl.module.css";
import { saveQuestionStatus } from "@/features/practice/actions";
import {
  INITIAL_QUESTION_STATUS_STATE,
  type QuestionStatusState,
} from "@/features/practice/submission";
import { QUESTION_STATUS_LABELS, type QuestionStatus } from "@/types/practice";

interface QuestionStatusControlProps {
  questionId: string;
  /** Named in the button's accessible label, so several stay distinguishable. */
  prompt: string;
  /** The question's stored status, as the API sent it. */
  status: string;
}

/** True when the API would accept this status as a target, so it can be offered. */
function isOffered(status: string): status is QuestionStatus {
  return status === "ready" || status === "retired";
}

/**
 * Where a learner sets a practice question aside, or brings it back.
 *
 * **Nothing here deletes, and nothing here edits.** Setting a question aside
 * means no new quiz asks it; a quiz already assembled goes on asking it, because
 * attempts are marked against it and a result must stay true to what was
 * answered. It is reversible from this same control — the position ADR-022 took
 * for a superseded plan and ADR-032 for archived material.
 *
 * A client component only so it can show the result of the last submission
 * beside the question it acted on. It calls no API itself: the submission goes to
 * a server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript — the form posts natively and the
 * page re-renders. The status travels in a hidden field rather than on the
 * button, so a scriptless submission carries it exactly as a hydrated one does.
 */
export function QuestionStatusControl({
  questionId,
  prompt,
  status,
}: QuestionStatusControlProps) {
  const [state, submit, pending] = useActionState<QuestionStatusState, FormData>(
    saveQuestionStatus,
    INITIAL_QUESTION_STATUS_STATE,
  );
  const messageId = useId();

  if (!isOffered(status)) {
    return <p className={styles.unmovable}>Status: {status}</p>;
  }

  const target: QuestionStatus = status === "retired" ? "ready" : "retired";

  return (
    <div className={styles.control}>
      <form action={submit}>
        <input type="hidden" name="question_id" value={questionId} />
        <input type="hidden" name="status" value={target} />

        <button
          aria-describedby={state.status === "idle" ? undefined : messageId}
          disabled={pending}
          type="submit"
        >
          {/*
            The visible words stay part of the accessible name rather than being
            replaced by an `aria-label`, so speaking the label a learner can see
            still activates the button. The prompt is appended for a screen
            reader, because a list holding several would otherwise present the
            same name on every one of them.
          */}
          {QUESTION_STATUS_LABELS[target]}
          <span className={styles.forScreenReaders}> — {prompt}</span>
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
