"use client";

import { useActionState, useId } from "react";

import { Notice } from "@/components/Notice";
import styles from "@/features/onboarding/AvailabilityForm.module.css";
import { saveAvailability } from "@/features/onboarding/actions";
import {
  INITIAL_AVAILABILITY_STATE,
  MINUTES_IN_A_DAY,
  minutesByDay,
  minutesFieldName,
  type AvailabilityState,
} from "@/features/onboarding/availability";
import { WEEKDAYS, WEEKDAY_LABELS, type StudyGoal } from "@/types/study-goal";

interface AvailabilityFormProps {
  /** The goal the week belongs to. Null before the learner has set one. */
  goal: StudyGoal | null;
}

/**
 * The weekly availability form.
 *
 * One box per day. A number is the study time available that day; `0` says the
 * day is deliberately kept free; an empty box says the day is not set at all.
 * Adding, editing, and removing a day are therefore the same submission --
 * GOAL-005 replaces the whole week, so what the form shows is what is saved.
 *
 * A client component only so it can show the result of the last submission
 * beside the day responsible. It calls no API itself: the submission goes to a
 * server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript -- the form posts natively and the
 * page re-renders with the same state -- so saving a week does not depend on a
 * hydrated bundle.
 *
 * No weekly total is shown. Availability is a planning input, and adding the days
 * up is planning work that arrives with the planner.
 */
export function AvailabilityForm({ goal }: AvailabilityFormProps) {
  const [state, submit, pending] = useActionState<AvailabilityState, FormData>(
    saveAvailability,
    INITIAL_AVAILABILITY_STATE,
  );
  const messageId = useId();
  const dayFieldId = useId();

  if (!goal) {
    return (
      <Notice title="Set your study goal first">
        <p>
          Weekly availability belongs to a study goal, so LearnFlow needs to know what you are
          working toward before it can record when you can study. Save your goal above, then set
          your week here.
        </p>
      </Notice>
    );
  }

  const stored = minutesByDay(goal.availability);
  const describedBy = state.status === "error" ? messageId : undefined;

  return (
    <form action={submit} className={styles.form}>
      {state.status !== "idle" ? (
        <div
          className={state.status === "error" ? styles.error : styles.saved}
          id={messageId}
          role={state.status === "error" ? "alert" : "status"}
        >
          {state.message}
        </div>
      ) : null}

      <fieldset className={styles.group}>
        <legend className={styles.legend}>When you can study</legend>
        <p className={styles.hint}>
          Enter the minutes you can realistically give each day. Leave a day empty to leave it
          unset, or enter <code>0</code> to say you keep it free. This is a planning input, not a
          promise — LearnFlow does not judge it.
        </p>

        <ol className={styles.days}>
          {WEEKDAYS.map((day) => (
            <li className={styles.day} key={day}>
              <label htmlFor={`${dayFieldId}-${day}`}>{WEEKDAY_LABELS[day]}</label>
              <input
                aria-describedby={state.day === day ? describedBy : undefined}
                defaultValue={stored[day] ?? ""}
                id={`${dayFieldId}-${day}`}
                inputMode="numeric"
                max={MINUTES_IN_A_DAY}
                min={0}
                name={minutesFieldName(day)}
                step={1}
                type="number"
              />
              <span className={styles.unit}>minutes</span>
            </li>
          ))}
        </ol>
      </fieldset>

      <input name="study_goal_id" type="hidden" value={goal.id} />

      <button className={styles.submit} disabled={pending} type="submit">
        {pending ? "Saving…" : "Save my week"}
      </button>
    </form>
  );
}
