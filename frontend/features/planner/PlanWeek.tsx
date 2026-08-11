import styles from "@/features/planner/PlanWeek.module.css";
import { PlanItemStatusControl } from "@/features/planner/PlanItemStatusControl";
import {
  describeAction,
  describeEstimate,
  describeSettledStatus,
  groupByDay,
  itemClassName,
} from "@/features/planner/plan";
import type { StudyPlan } from "@/types/study-plan";

interface PlanWeekProps {
  /** The dated plan for the coming week, or null when none was generated. */
  plan: StudyPlan | null;
}

/**
 * The work the plan places on each of the coming days.
 *
 * Read-only, and it reorders nothing: the items arrive in plan order and are
 * grouped by the day the backend chose. A day with no work is absent rather than
 * shown empty — the learner either kept it free or has not set it, and neither is
 * a day this screen should fill.
 *
 * Every item shows the reason the plan gives for it, as the roadmap does. FR-003
 * asks a learner to be able to see why an item is recommended, and the week is
 * the panel they act on daily — a dated item without its reason would be an
 * instruction rather than a recommendation.
 *
 * No day is totalled and no week is added up, and nothing counts how much of a
 * day is done. Turning a plan into a figure would be a second opinion about the
 * learner's time or their progress, formed here rather than by the planner that
 * has the trade-offs in view.
 *
 * Each item carries the control that says what became of it — completed, skipped,
 * or back to planned — which is the panel a learner acts on daily. A settled item
 * stays where it is rather than moving or disappearing: the plan says what the day
 * held, and hiding what was finished would leave the day looking undone, while
 * hiding what was skipped would hide a decision the learner may want to take back.
 */
export function PlanWeek({ plan }: PlanWeekProps) {
  const days = groupByDay(plan);

  if (!plan || days.length === 0) {
    return null;
  }

  return (
    <section aria-labelledby="your-week" className={styles.panel}>
      <h2 id="your-week">Your week</h2>
      {plan.generation_reason ? (
        <p className={styles.reason}>{plan.generation_reason}</p>
      ) : null}
      <ol className={styles.days}>
        {days.map((day) => (
          <li key={day.on}>
            {/*
             * Printed as the API sent it. Parsing a date-only string into a
             * `Date` reads it as UTC midnight, which west of Greenwich would
             * show the previous day's heading over the day's work.
             */}
            <h3 className={styles.date}>{day.on}</h3>
            <ul className={styles.items}>
              {day.items.map((item) => (
                <li className={itemClassName(item, styles)} key={item.id}>
                  <p className={styles.topic}>
                    <span className={styles.action}>{describeAction(item.action_type)}</span>{" "}
                    {item.topic ? item.topic.name : "A topic that is no longer stored"}
                  </p>
                  <p className={styles.meta}>
                    {item.topic ? `${item.topic.subject_name} · ` : ""}
                    {describeEstimate(item.estimated_minutes)}
                  </p>
                  {describeSettledStatus(item.status) ? (
                    <p className={styles.settledLabel}>{describeSettledStatus(item.status)}</p>
                  ) : null}
                  {item.recommendation_reason ? (
                    <p className={styles.why}>{item.recommendation_reason}</p>
                  ) : null}
                  <PlanItemStatusControl
                    planItemId={item.id}
                    status={item.status}
                    topicName={item.topic ? item.topic.name : "this item"}
                  />
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </section>
  );
}
