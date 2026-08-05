/**
 * Topic-progress types, derived from the PRG-002 and PRG-004 response contract
 * in docs/api/endpoints.md#progress-and-study-activity-endpoints.
 *
 * Nothing here describes a database table, and no stage is calculated in the
 * frontend: a learner sets a stage and the backend stores it
 * (docs/architecture/dependency-rules.md).
 */

import type { CollectionEnvelope, DataEnvelope } from "@/types/api";

/**
 * The five learner-visible stages, in the form the API puts on the wire.
 *
 * The order is the progression a learner moves along, not a ranking. Nothing in
 * this application compares two stages, and a learner may move to any of them
 * from any of them.
 */
export const LEARNING_STAGES = [
  "not_explored",
  "building_foundation",
  "developing_confidence",
  "practice_ready",
  "strong_understanding",
] as const;

export type LearningStage = (typeof LEARNING_STAGES)[number];

/**
 * The label a learner reads for each stage, from docs/domain/terminology.md.
 *
 * The wire value and the label are deliberately separate representations: a
 * copy-edit here must not become a database migration, and a `snake_case`
 * identifier is not something to show a learner.
 */
export const LEARNING_STAGE_LABELS: Record<LearningStage, string> = {
  not_explored: "Not explored",
  building_foundation: "Building foundation",
  developing_confidence: "Developing confidence",
  practice_ready: "Practice-ready",
  strong_understanding: "Strong understanding",
};

/**
 * The next action each stage suggests.
 *
 * Every stage is paired with something constructive to do, which is what
 * FR-005 asks for: the interface presents an encouraging next action rather
 * than a negative label. None of these is a judgement of the learner.
 */
export const LEARNING_STAGE_NEXT_ACTIONS: Record<LearningStage, string> = {
  not_explored: "Start with the concepts when you reach this topic.",
  building_foundation: "Focus on the concepts and the basic study material.",
  developing_confidence: "Work through focused practice on the parts that are still unclear.",
  practice_ready: "Practise more topic-focused questions.",
  strong_understanding: "Keep this one fresh with scheduled revision.",
};

/** True when a string is one of the five stages the API accepts. */
export function isLearningStage(value: string): value is LearningStage {
  return (LEARNING_STAGES as readonly string[]).includes(value);
}

/** The topic a progress record describes, as PRG-002 and PRG-004 return it. */
export interface TopicProgressTopic {
  id: string;
  code: string | null;
  name: string;
  is_trackable: boolean;
  subject_id: string;
  curriculum_version_id: string;
}

/** One recorded stage, with the topic it belongs to. */
export interface TopicProgress {
  id: string;
  learner_id: string;
  learning_stage: LearningStage | string;
  /** `learner` for a stage the learner set themselves. */
  stage_source: string;
  topic: TopicProgressTopic;
}

export type TopicProgressCollectionResponse = CollectionEnvelope<TopicProgress>;
export type TopicProgressResponse = DataEnvelope<TopicProgress>;
