/**
 * Joining recorded stages onto the curriculum a learner is browsing.
 *
 * PRG-002 returns only the topics a learner has recorded something against, and
 * CUR-003 returns every topic. Putting the two together is the client's job, and
 * it is plain functions here so it is testable without a running server -- the
 * same reason `features/home/dates.ts` is separate.
 *
 * This is not a business rule. Nothing here decides what a stage means, ranks
 * one against another, or computes a stage from anything; it looks one up.
 */

import { isLearningStage, type LearningStage, type TopicProgress } from "@/types/progress";

/** Index the learner's recorded stages by the topic each belongs to. */
export function stagesByTopicId(records: TopicProgress[]): Map<string, LearningStage> {
  const index = new Map<string, LearningStage>();
  for (const record of records) {
    // A stage the client does not recognise is skipped rather than shown raw.
    // The API's catalogue could gain a value before this build knows the label
    // for it, and `not_explored` is a truthful fallback where a `snake_case`
    // identifier on screen would not be.
    if (isLearningStage(record.learning_stage)) {
      index.set(record.topic.id, record.learning_stage);
    }
  }
  return index;
}

/**
 * The stage recorded for one topic, or null when the learner has recorded none.
 *
 * Null is the neutral starting state, which the control shows as *Not
 * explored*. It is deliberately distinct from a stored `not_explored`, which
 * means the learner said so on purpose.
 */
export function stageFor(
  index: Map<string, LearningStage>,
  topicId: string,
): LearningStage | null {
  return index.get(topicId) ?? null;
}
