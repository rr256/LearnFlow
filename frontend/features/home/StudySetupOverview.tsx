import Link from "next/link";

import { Notice } from "@/components/Notice";
import { ExaminationDates } from "@/features/home/ExaminationDates";
import styles from "@/features/home/StudySetupOverview.module.css";
import type { LearnerProfile } from "@/types/learner";
import type { ExaminationSchedule, StudyGoal } from "@/types/study-goal";

interface StudySetupOverviewProps {
  profile: LearnerProfile | null;
  goal: StudyGoal | null;
  /**
   * The published schedule the goal aims at, when EXM-001 returned it.
   *
   * A goal response carries the examination window but not the dated periods, so
   * the registration and results dates come from the schedule rather than the
   * goal. Null when the goal aims at no examination, or when the cycle was not
   * among the schedules published for its program.
   */
  schedule: ExaminationSchedule | null;
}

/**
 * What the learner has already saved: their profile, their study goal, and the
 * examination the goal aims at.
 *
 * This is a read-only view of learner setup. It shows what is stored and links
 * to `/setup` to change it; nothing here writes.
 *
 * It deliberately does not reuse `features/onboarding/StudyGoalSummary`. That
 * component belongs to the first-time flow and its empty state points at the
 * form beneath it, which this screen does not have.
 *
 * Dates are left to `ExaminationDates`, so the goal panel names the cycle
 * without repeating its window -- and the provisional status is stated once,
 * beside every date it qualifies.
 */
export function StudySetupOverview({ profile, goal, schedule }: StudySetupOverviewProps) {
  if (!profile && !goal) {
    return (
      <Notice title="Nothing is set up yet">
        <p>
          LearnFlow does not know who you are or what you are working toward.{" "}
          <Link href="/setup">Set up your study goal</Link> to choose a learning program and a
          horizon to plan against.
        </p>
      </Notice>
    );
  }

  const examination = goal?.examination ?? null;

  return (
    <>
      <section aria-labelledby="your-details" className={styles.panel}>
        <h2 id="your-details">Your details</h2>
        {profile ? (
          <dl className={styles.details}>
            <div>
              <dt>Name</dt>
              <dd>{profile.display_name ?? "Not set"}</dd>
            </div>
            <div>
              <dt>Timezone</dt>
              <dd>{profile.timezone}</dd>
            </div>
          </dl>
        ) : (
          <p className={styles.empty}>
            No profile is saved yet. <Link href="/setup">Add your name and timezone</Link> so your
            study dates are read in the right zone.
          </p>
        )}
      </section>

      <section aria-labelledby="your-goal" className={styles.panel}>
        <h2 id="your-goal">Your study goal</h2>
        {goal ? (
          <dl className={styles.details}>
            <div>
              <dt>Learning program</dt>
              <dd>{goal.learning_program.name}</dd>
            </div>
            <div>
              <dt>Curriculum version</dt>
              <dd>{goal.curriculum_version.version_label}</dd>
            </div>
            <div>
              <dt>Goal status</dt>
              <dd>{goal.status}</dd>
            </div>
            {examination ? (
              <div>
                <dt>Working toward</dt>
                <dd>{examination.name}</dd>
              </div>
            ) : null}
            {goal.target_date ? (
              <div>
                <dt>Target completion date</dt>
                <dd>{goal.target_date}</dd>
              </div>
            ) : null}
          </dl>
        ) : (
          <p className={styles.empty}>
            No study goal is saved yet. <Link href="/setup">Choose what you are working toward</Link>
            , so LearnFlow has a horizon to plan against.
          </p>
        )}
      </section>

      {examination ? (
        <ExaminationDates examination={examination} periods={schedule?.periods ?? null} />
      ) : null}
    </>
  );
}
