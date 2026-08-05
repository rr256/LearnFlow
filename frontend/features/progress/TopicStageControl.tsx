"use client";

import { useActionState, useId } from "react";

import styles from "@/features/progress/TopicStageControl.module.css";
import { saveTopicStage } from "@/features/progress/actions";
import { INITIAL_STAGE_STATE, type StageState } from "@/features/progress/submission";
import {
  LEARNING_STAGES,
  LEARNING_STAGE_LABELS,
  LEARNING_STAGE_NEXT_ACTIONS,
  type LearningStage,
} from "@/types/progress";

interface TopicStageControlProps {
  topicId: string;
  /** Named in the control's accessible label, so each one is distinguishable. */
  topicName: string;
  /** The stored stage, or null when the learner has recorded nothing. */
  learningStage: LearningStage | null;
}

/**
 * Where a learner records how far along they are with one topic.
 *
 * A client component only so it can show the result of the last submission
 * beside the control that produced it. It calls no API itself: the submission
 * goes to a server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript -- the form posts natively and
 * the page re-renders -- so recording progress does not depend on a hydrated
 * bundle. That is also why the submit button is always present rather than
 * relying on an `onChange` handler.
 *
 * The stage a learner has not set is shown as *Not explored*, which is the
 * neutral starting state rather than a stored value. Every stage is paired with
 * a next action, so the control suggests something to do rather than grading the
 * learner (FR-005).
 */
export function TopicStageControl({ topicId, topicName, learningStage }: TopicStageControlProps) {
  const [state, submit, pending] = useActionState<StageState, FormData>(
    saveTopicStage,
    INITIAL_STAGE_STATE,
  );
  const selectId = useId();
  const messageId = useId();

  const current: LearningStage = learningStage ?? "not_explored";

  return (
    <form action={submit} className={styles.control}>
      <input type="hidden" name="topic_id" value={topicId} />

      <label className={styles.label} htmlFor={selectId}>
        Learning stage for {topicName}
      </label>
      <div className={styles.row}>
        <select
          aria-describedby={state.status === "idle" ? undefined : messageId}
          className={styles.select}
          defaultValue={current}
          id={selectId}
          name="learning_stage"
        >
          {LEARNING_STAGES.map((stage) => (
            <option key={stage} value={stage}>
              {LEARNING_STAGE_LABELS[stage]}
            </option>
          ))}
        </select>
        <button className={styles.save} disabled={pending} type="submit">
          {pending ? "Saving…" : "Save"}
        </button>
      </div>

      {/*
        The next action is the point of the stage. Showing it beside the control
        keeps the five labels from reading as a score, which is what FR-005 and
        the terminology guidance both ask for.
      */}
      {learningStage ? (
        <p className={styles.nextAction}>{LEARNING_STAGE_NEXT_ACTIONS[current]}</p>
      ) : null}

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
