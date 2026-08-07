import styles from "@/features/planner/StudyRoadmap.module.css";
import { describeEstimate } from "@/features/planner/plan";
import type { StudyPlan } from "@/types/study-plan";

interface StudyRoadmapProps {
  /** The roadmap, or null when no plan has been generated yet. */
  plan: StudyPlan | null;
}

/**
 * The order the plan works through the curriculum, with the reason for each item.
 *
 * Read-only, and it reorders nothing: the items arrive in plan order, and
 * ordering is a curriculum and planning rule that belongs to the backend
 * (docs/development/coding-standards.md#ui-responsibilities).
 *
 * Every item shows why it is where it is, which is what FR-003 asks a
 * recommendation to carry. The sentence was written when the plan was generated,
 * so a plan set aside months ago still explains itself in the terms that produced
 * it rather than in today's.
 *
 * Nothing here is a score. `priority` is a position in a list, and a topic
 * further down is later, not worse.
 */
export function StudyRoadmap({ plan }: StudyRoadmapProps) {
  if (!plan) {
    return null;
  }

  return (
    <section aria-labelledby="your-roadmap" className={styles.panel}>
      <h2 id="your-roadmap">Your roadmap</h2>
      <p className={styles.summary}>
        {plan.item_count} topics
        {plan.period_start && plan.period_end
          ? `, from ${plan.period_start} to ${plan.period_end}`
          : ""}
        .
      </p>
      {plan.generation_reason ? (
        <p className={styles.reason}>{plan.generation_reason}</p>
      ) : null}
      {plan.items.length === 0 ? (
        <p className={styles.empty}>
          This plan holds no topics. That happens when the curriculum it was built from has none
          that progress can be recorded against.
        </p>
      ) : (
        <ol className={styles.items}>
          {plan.items.map((item) => (
            <li className={styles.item} key={item.id}>
              <p className={styles.topic}>
                {item.topic ? item.topic.name : "A topic that is no longer stored"}
              </p>
              <p className={styles.meta}>
                {item.topic ? `${item.topic.subject_name} · ` : ""}
                {describeEstimate(item.estimated_minutes)}
              </p>
              {item.recommendation_reason ? (
                <p className={styles.why}>{item.recommendation_reason}</p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
