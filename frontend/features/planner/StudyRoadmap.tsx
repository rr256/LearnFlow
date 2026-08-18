import styles from "@/features/planner/StudyRoadmap.module.css";
import { PlanItemStatusControl } from "@/features/planner/PlanItemStatusControl";
import { describeEstimate, describeSettledStatus, itemClassName } from "@/features/planner/plan";
import { TopicResources } from "@/features/resources/TopicResources";
import { resourcesFor } from "@/features/resources/by-topic";
import type { LearningResource } from "@/types/resource";
import type { StudyPlan } from "@/types/study-plan";

interface StudyRoadmapProps {
  /** The roadmap, or null when no plan has been generated yet. */
  plan: StudyPlan | null;
  /**
   * The learner's catalogued material, keyed by the topics it covers, or null
   * when it could not be read. Null renders the roadmap without it, which costs
   * the reader the material rather than the plan they came for.
   */
  resources?: Map<string, LearningResource[]> | null;
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
 * further down is later, not worse, and nothing counts how many are done.
 *
 * Each item carries the control that says what became of it, as the week's items
 * do: a plan item is a plan item, and a learner working ahead of their week — or
 * setting a topic aside before it reaches one — should not have to wait for it to
 * appear there. Moving one moves that item alone: the same topic on the week's
 * plan is a separate item and stays as it was.
 *
 * **The material beside an item is the learner's own, and nothing suggests any.**
 * It is what they linked to that topic in their catalogue, listed read-only in the
 * API's order; material they have put aside is left out. A topic appearing on both
 * this panel and the week shows the same material twice because it is the same
 * topic read twice, not because anything is emphasised.
 */
export function StudyRoadmap({ plan, resources = null }: StudyRoadmapProps) {
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
            <li className={itemClassName(item, styles)} key={item.id}>
              <p className={styles.topic}>
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
              {/*
                The learner's own material for this item's topic, read-only:
                adding it and putting it aside live on the catalogue screen.
                Nothing is suggested -- this is what they linked, and a topic
                with nothing linked renders nothing at all.
              */}
              {resources && item.topic ? (
                <TopicResources
                  resources={resourcesFor(resources, item.topic.id)}
                  topicName={item.topic.name}
                />
              ) : null}
              <PlanItemStatusControl
                planItemId={item.id}
                status={item.status}
                topicName={item.topic ? item.topic.name : "this item"}
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
