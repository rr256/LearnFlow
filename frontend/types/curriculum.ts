/**
 * Curriculum types, derived from the CUR-001 to CUR-003 response contract in
 * docs/api/endpoints.md#curriculum-endpoints.
 *
 * Nothing here describes a database table. Subjects, topics, and subtopics
 * arrive from the backend as data; no GATE CSE content is expressed in this
 * repository's frontend code (FR-001).
 */

import type { CollectionEnvelope, DataEnvelope } from "@/types/api";

/** Lifecycle of a curriculum version. A draft or retired version is readable. */
export type CurriculumVersionStatus = "draft" | "active" | "retired";

/** A curriculum version, named well enough to request its tree. */
export interface CurriculumVersion {
  id: string;
  learning_program_id: string;
  version_label: string;
  status: CurriculumVersionStatus | string;
  source_reference: string | null;
  published_at: string | null;
}

/** A learning program and the curriculum version currently active for it. */
export interface LearningProgram {
  id: string;
  code: string;
  name: string;
  description: string | null;
  /** Null while the program has only draft or retired versions. */
  active_curriculum_version: CurriculumVersion | null;
}

/** A topic, with any subtopics nested beneath it to whatever depth is used. */
export interface Topic {
  id: string;
  code: string | null;
  name: string;
  description: string | null;
  position: number;
  /** False for a topic that only groups subtopics. */
  is_trackable: boolean;
  subtopics: Topic[];
}

/** A subject and its root topics, in the order the syllabus teaches them. */
export interface Subject {
  id: string;
  code: string;
  name: string;
  description: string | null;
  position: number;
  topics: Topic[];
}

/** A prerequisite or sequencing edge between two topics of one version. */
export interface TopicRelationship {
  source_topic_id: string;
  target_topic_id: string;
  relationship_type: string;
}

/**
 * One curriculum version's full hierarchy.
 *
 * Relationships sit beside the tree rather than inside it, because an edge
 * relates two topics and nesting it under one would assert which end owns it.
 */
export interface CurriculumTree {
  curriculum_version: CurriculumVersion;
  subjects: Subject[];
  topic_relationships: TopicRelationship[];
}

export type LearningProgramCollectionResponse = CollectionEnvelope<LearningProgram>;
export type LearningProgramResponse = DataEnvelope<LearningProgram>;
export type CurriculumTreeResponse = DataEnvelope<CurriculumTree>;
