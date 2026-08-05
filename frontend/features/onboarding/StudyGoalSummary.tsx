import { Notice } from "@/components/Notice";
import styles from "@/features/onboarding/StudyGoalSummary.module.css";
import { datesMayChange, type StudyGoal } from "@/types/study-goal";

interface StudyGoalSummaryProps {
  goal: StudyGoal | null;
}

/**
 * The goal the learner has already set, if any.
 *
 * The examination is reported as a window, with the source it came from, the day
 * that source was read, and whether it is still provisional. All four travel
 * together: a date shown without its status reads as settled fact, and one shown
 * without its source cannot be checked when the examining body revises it.
 */
export function StudyGoalSummary({ goal }: StudyGoalSummaryProps) {
  if (!goal) {
    return (
      <Notice title="No study goal yet">
        <p>
          Fill in the form below to choose your learning program and what you are working toward.
          You can change it at any time.
        </p>
      </Notice>
    );
  }

  const examination = goal.examination;
  const window = examination?.examination_window ?? null;

  return (
    <section aria-labelledby="current-goal" className={styles.summary}>
      <h2 id="current-goal">Your current setup</h2>
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
          <dt>Status</dt>
          <dd>{goal.status}</dd>
        </div>
        {examination ? (
          <div>
            <dt>Examination window</dt>
            <dd>
              {window ? `${window.starts_on} to ${window.ends_on}` : "Sitting days not published"}
              {datesMayChange(examination) ? (
                <span className={styles.provisional}>
                  {" "}
                  Provisional — {examination.organising_body ?? "the organising body"} may still
                  change these dates.
                </span>
              ) : null}
            </dd>
          </div>
        ) : null}
        {goal.target_date ? (
          <div>
            <dt>Target completion date</dt>
            <dd>{goal.target_date}</dd>
          </div>
        ) : null}
      </dl>
      {examination ? (
        <p className={styles.source}>
          Dates from{" "}
          <a href={examination.source_reference} rel="noreferrer noopener" target="_blank">
            {examination.organising_body ?? examination.name}
          </a>
          , read on {examination.source_checked_on}.
        </p>
      ) : null}
    </section>
  );
}
