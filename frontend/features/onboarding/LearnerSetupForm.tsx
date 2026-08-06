"use client";

import { useActionState, useId, useState } from "react";

import { Notice } from "@/components/Notice";
import styles from "@/features/onboarding/LearnerSetupForm.module.css";
import { saveLearnerSetup } from "@/features/onboarding/actions";
import { INITIAL_SETUP_STATE, type SetupState } from "@/features/onboarding/submission";
import type { LearningProgram } from "@/types/curriculum";
import type { LearnerProfile } from "@/types/learner";
import {
  MAXIMUM_SESSION_MINUTES,
  MINIMUM_SESSION_MINUTES,
  TOPIC_SEQUENCING_CHOICES,
  TOPIC_SEQUENCING_DESCRIPTIONS,
  TOPIC_SEQUENCING_LABELS,
  datesMayChange,
  type ExaminationSchedule,
  type StudyGoal,
} from "@/types/study-goal";

interface LearnerSetupFormProps {
  profile: LearnerProfile | null;
  programs: LearningProgram[];
  schedules: ExaminationSchedule[];
  goal: StudyGoal | null;
}

/** The date span a schedule publishes, written the way a learner reads it. */
function describeWindow(schedule: ExaminationSchedule): string {
  if (!schedule.examination_window) {
    return "sitting days not published yet";
  }
  const { starts_on, ends_on } = schedule.examination_window;
  return starts_on === ends_on ? starts_on : `${starts_on} to ${ends_on}`;
}

/**
 * The learner setup form.
 *
 * A client component only so it can show the result of the last submission
 * beside the field responsible. It calls no API itself: the submission goes to a
 * server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript -- the form posts natively and
 * the page re-renders with the same state -- so setup does not depend on a
 * hydrated bundle.
 */
export function LearnerSetupForm({ profile, programs, schedules, goal }: LearnerSetupFormProps) {
  const [state, submit, pending] = useActionState<SetupState, FormData>(
    saveLearnerSetup,
    INITIAL_SETUP_STATE,
  );
  const [target, setTarget] = useState<"examination" | "target_date">(
    goal?.examination || schedules.length > 0 ? "examination" : "target_date",
  );

  const nameId = useId();
  const timezoneId = useId();
  const programId = useId();
  const scheduleId = useId();
  const dateId = useId();
  const sessionId = useId();
  const sequencingId = useId();
  const messageId = useId();

  if (programs.length === 0) {
    return (
      <Notice title="No learning programs yet" tone="attention">
        <p>
          The curriculum has not been loaded into this environment, so there is nothing to study
          toward. Run the curriculum seed described in the project README, then reload this page.
        </p>
      </Notice>
    );
  }

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
        <legend className={styles.legend}>About you</legend>

        <div className={styles.field}>
          <label htmlFor={nameId}>Your name</label>
          <input
            aria-describedby={state.field === "display_name" ? describedBy : undefined}
            defaultValue={profile?.display_name ?? ""}
            id={nameId}
            maxLength={200}
            name="display_name"
            type="text"
          />
          <p className={styles.hint}>Optional. Leave it empty to remove a name you saved before.</p>
        </div>

        <div className={styles.field}>
          <label htmlFor={timezoneId}>Timezone</label>
          <input
            aria-describedby={state.field === "timezone" ? describedBy : undefined}
            defaultValue={profile?.timezone ?? ""}
            id={timezoneId}
            name="timezone"
            placeholder="Asia/Kolkata"
            type="text"
          />
          <p className={styles.hint}>
            An IANA timezone name. Your study dates are read in this zone, so a wrong one moves them
            by a day at the boundary. Leave it empty to keep the installation default.
          </p>
        </div>
      </fieldset>

      <fieldset className={styles.group}>
        <legend className={styles.legend}>What you are studying</legend>

        <div className={styles.field}>
          <label htmlFor={programId}>Learning program</label>
          <select
            aria-describedby={state.field === "learning_program_id" ? describedBy : undefined}
            defaultValue={goal?.learning_program.id ?? programs[0]?.id}
            id={programId}
            name="learning_program_id"
          >
            {programs.map((program) => (
              <option key={program.id} value={program.id}>
                {program.name}
              </option>
            ))}
          </select>
          <p className={styles.hint}>
            Your goal is bound to this program&rsquo;s active curriculum version.
          </p>
        </div>
      </fieldset>

      <fieldset className={styles.group}>
        <legend className={styles.legend}>What you are working toward</legend>

        <div className={styles.choice}>
          <label>
            <input
              checked={target === "examination"}
              name="goal_target"
              onChange={() => setTarget("examination")}
              type="radio"
              value="examination"
            />
            A published examination
          </label>
          <label>
            <input
              checked={target === "target_date"}
              name="goal_target"
              onChange={() => setTarget("target_date")}
              type="radio"
              value="target_date"
            />
            My own completion date
          </label>
        </div>

        {target === "examination" ? (
          <div className={styles.field}>
            <label htmlFor={scheduleId}>Examination</label>
            {schedules.length === 0 ? (
              <p className={styles.hint} role="status">
                No examination schedule has been loaded for this program. Run the examination
                schedule seed, or work toward your own completion date instead.
              </p>
            ) : (
              <>
                <select
                  aria-describedby={
                    state.field === "examination_schedule_id" ? describedBy : undefined
                  }
                  defaultValue={goal?.examination?.id ?? schedules[0]?.id}
                  id={scheduleId}
                  name="examination_schedule_id"
                >
                  {schedules.map((schedule) => (
                    <option key={schedule.id} value={schedule.id}>
                      {schedule.name} — {describeWindow(schedule)}
                    </option>
                  ))}
                </select>
                <ul className={styles.schedules}>
                  {schedules.map((schedule) => (
                    <li key={schedule.id}>
                      <strong>{schedule.name}</strong>: {describeWindow(schedule)}
                      {datesMayChange(schedule) ? (
                        <span className={styles.provisional}>
                          {" "}
                          Provisional — {schedule.organising_body ?? "the organising body"} may
                          still change these dates.
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
                <p className={styles.hint}>
                  LearnFlow plans against the whole span of published sitting days. The examining
                  body has not announced which of them your paper falls on.
                </p>
              </>
            )}
          </div>
        ) : (
          <div className={styles.field}>
            <label htmlFor={dateId}>Target completion date</label>
            <input
              aria-describedby={state.field === "target_date" ? describedBy : undefined}
              defaultValue={goal?.target_date ?? ""}
              id={dateId}
              name="target_date"
              type="date"
            />
            <p className={styles.hint}>
              For a learner following no published examination. Do not use it to guess a paper date
              inside an examination window.
            </p>
          </div>
        )}
      </fieldset>

      {/*
       * Preferences ride on the goal write above rather than on a form of their
       * own, because GOAL-001 and GOAL-004 carry them. Both controls are shown
       * together and submitted together, which is why the API replaces the group
       * rather than merging into it: a box the learner cleared means "no
       * preference", and that has to reach the API to take effect.
       */}
      <fieldset className={styles.group}>
        <legend className={styles.legend}>How you want to study</legend>
        <p className={styles.hint}>
          What a study plan should take into account when one is built. Nothing is planned yet, and
          leaving either of these empty is a fine answer &mdash; LearnFlow will choose for itself
          rather than assume.
        </p>

        <div className={styles.field}>
          <label htmlFor={sessionId}>Preferred session length</label>
          <input
            aria-describedby={
              state.field === "preferred_session_minutes" ? describedBy : undefined
            }
            defaultValue={goal?.planning_preferences.preferred_session_minutes ?? ""}
            id={sessionId}
            max={MAXIMUM_SESSION_MINUTES}
            min={MINIMUM_SESSION_MINUTES}
            name="preferred_session_minutes"
            step={5}
            type="number"
          />
          <p className={styles.hint}>
            How long one block of study should be, in minutes, between{" "}
            {MINIMUM_SESSION_MINUTES} and {MAXIMUM_SESSION_MINUTES}. It says how long a block runs,
            not when in the day it starts. Leave it empty for no preference.
          </p>
        </div>

        <div className={styles.field}>
          <label htmlFor={sequencingId}>Topic order</label>
          <select
            aria-describedby={state.field === "topic_sequencing" ? describedBy : undefined}
            defaultValue={goal?.planning_preferences.topic_sequencing ?? ""}
            id={sequencingId}
            name="topic_sequencing"
          >
            <option value="">No preference</option>
            {TOPIC_SEQUENCING_CHOICES.map((choice) => (
              <option key={choice} value={choice}>
                {TOPIC_SEQUENCING_LABELS[choice]}
              </option>
            ))}
          </select>
          <ul className={styles.schedules}>
            {TOPIC_SEQUENCING_CHOICES.map((choice) => (
              <li key={choice}>
                <strong>{TOPIC_SEQUENCING_LABELS[choice]}</strong>:{" "}
                {TOPIC_SEQUENCING_DESCRIPTIONS[choice]}
              </li>
            ))}
          </ul>
        </div>
      </fieldset>

      {goal ? <input name="study_goal_id" type="hidden" value={goal.id} /> : null}

      <button className={styles.submit} disabled={pending} type="submit">
        {pending ? "Saving…" : goal ? "Update my setup" : "Save my setup"}
      </button>
    </form>
  );
}
