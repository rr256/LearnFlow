import Link from "next/link";

import styles from "@/features/home/PlanningPreferences.module.css";
import { describeSessionLength, describeTopicSequencing } from "@/features/onboarding/preferences";
import type { StudyGoal } from "@/types/study-goal";

interface PlanningPreferencesProps {
  /** The goal whose preferences are shown. Null before the learner has a goal. */
  goal: StudyGoal | null;
}

/**
 * The planning preferences the learner has saved, read-only.
 *
 * It reports what is stored and links to learner setup to change it; nothing here
 * writes. The preferences come off the goal, which GOAL-002 already returned, so
 * this panel costs the home screen no extra request.
 *
 * A preference the learner has not set is absent rather than shown as a default,
 * because the two mean different things: an unset preference leaves the choice to
 * the planner, and showing a guessed value would report a decision nobody made.
 */
export function PlanningPreferences({ goal }: PlanningPreferencesProps) {
  const preferences = goal?.planning_preferences ?? null;
  const sessionLength = describeSessionLength(preferences?.preferred_session_minutes ?? null);
  const topicOrder = describeTopicSequencing(preferences?.topic_sequencing ?? null);
  const shown = [
    ...(sessionLength ? [{ term: "Session length", value: sessionLength }] : []),
    ...(topicOrder ? [{ term: "Topic order", value: topicOrder }] : []),
  ];

  return (
    <section aria-labelledby="your-preferences" className={styles.panel}>
      <h2 id="your-preferences">How you want to study</h2>
      {shown.length === 0 ? (
        <p className={styles.empty}>
          {goal ? (
            <>
              No planning preferences are saved yet.{" "}
              <Link href="/setup">Tell LearnFlow how you like to study</Link>, or leave this to
              LearnFlow to decide when a plan is built.
            </>
          ) : (
            <>
              Planning preferences belong to a study goal.{" "}
              <Link href="/setup">Choose what you are working toward</Link> first.
            </>
          )}
        </p>
      ) : (
        <>
          <dl className={styles.preferences}>
            {shown.map((entry) => (
              <div key={entry.term}>
                <dt>{entry.term}</dt>
                <dd>{entry.value}</dd>
              </div>
            ))}
          </dl>
          <p className={styles.pending}>
            Saved for a study plan. No plan is generated yet, so nothing acts on these.
          </p>
        </>
      )}
    </section>
  );
}
