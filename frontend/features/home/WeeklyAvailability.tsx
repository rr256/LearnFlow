import Link from "next/link";

import styles from "@/features/home/WeeklyAvailability.module.css";
import { describeMinutes, weekInOrder } from "@/features/onboarding/availability";
import { WEEKDAY_LABELS, isWeekday, type StudyGoal } from "@/types/study-goal";

interface WeeklyAvailabilityProps {
  /** The goal whose week is shown. Null before the learner has set a goal. */
  goal: StudyGoal | null;
}

/**
 * The weekly study time the learner has saved, read-only.
 *
 * It reports what is stored and links to learner setup to change it; nothing here
 * writes. The week comes off the goal, which GOAL-002 already returned, so this
 * panel costs the home screen no extra request.
 *
 * Days the learner has not set are absent rather than shown as zero, because the
 * two mean different things: an absent day is one they have not thought about, and
 * a zero is one they deliberately keep free.
 *
 * No total is shown. Availability is a planning input, and adding the days up is
 * planning work that arrives with the planner.
 */
export function WeeklyAvailability({ goal }: WeeklyAvailabilityProps) {
  const week = weekInOrder(goal?.availability ?? null);

  return (
    <section aria-labelledby="your-week" className={styles.panel}>
      <h2 id="your-week">Your study week</h2>
      {week.length === 0 ? (
        <p className={styles.empty}>
          {goal ? (
            <>
              No study time is saved yet.{" "}
              <Link href="/setup">Tell LearnFlow when you can study</Link>, so a plan has something
              real to work with.
            </>
          ) : (
            <>
              Weekly availability belongs to a study goal.{" "}
              <Link href="/setup">Choose what you are working toward</Link> first.
            </>
          )}
        </p>
      ) : (
        <dl className={styles.week}>
          {week.map((slot) => (
            <div key={slot.day_of_week}>
              <dt>
                {isWeekday(slot.day_of_week)
                  ? WEEKDAY_LABELS[slot.day_of_week]
                  : slot.day_of_week}
              </dt>
              <dd>{describeMinutes(slot.available_minutes)}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
