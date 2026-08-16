/**
 * Joining a learner's catalogued material onto the topics they are reading about.
 *
 * RES-002 returns each resource with the topics it covers; the curriculum view
 * and the revision list both need the reverse — the material covering one topic.
 * Turning one into the other is the client's job, and it is plain functions here
 * so it is testable without a running server, which is why
 * `features/progress/stages.ts` is separate for the same reason.
 *
 * **Nothing here is a business rule.** No material is recommended, ranked,
 * scored, or filtered by suitability: the material for a topic is the material
 * the learner linked to it, in the order the API returned. That order is the
 * backend's, and re-sorting it in the browser would put a decision here that
 * belongs there (docs/development/coding-standards.md#ui-responsibilities).
 */

import type { LearningResource } from "@/types/resource";

/** Material that is in the catalogue rather than put aside. */
export function isInCatalogue(resource: LearningResource): boolean {
  return resource.status === "registered";
}

/**
 * Index a learner's material by each topic it covers.
 *
 * A resource covering three topics appears under all three: it is one record
 * read three ways, not three records.
 *
 * Archived material is left out. A learner who put something aside has said they
 * are not using it, and showing it beside a topic anyway would make putting it
 * aside meaningless — while the catalogue screen still lists it, so nothing is
 * hidden from the place it can be brought back.
 */
export function resourcesByTopicId(
  resources: LearningResource[],
): Map<string, LearningResource[]> {
  const index = new Map<string, LearningResource[]>();
  for (const resource of resources) {
    if (!isInCatalogue(resource)) {
      continue;
    }
    for (const topic of resource.topics) {
      index.set(topic.id, [...(index.get(topic.id) ?? []), resource]);
    }
  }
  return index;
}

/**
 * The material covering one topic, or an empty list when the learner has linked
 * none.
 *
 * An empty list is the honest answer for a topic nothing covers. Nothing is
 * suggested in its place: LearnFlow has no material of its own to offer, and
 * inventing a recommendation would be a claim it cannot support.
 */
export function resourcesFor(
  index: Map<string, LearningResource[]>,
  topicId: string,
): LearningResource[] {
  return index.get(topicId) ?? [];
}
