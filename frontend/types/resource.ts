/**
 * Learning-resource types, derived from the RES-001 to RES-004 response contract
 * in docs/api/endpoints.md#resource-and-ingestion-endpoints.
 *
 * Nothing here recommends anything. Which material suits a topic, which is worth
 * reading first, and what a learner should study next are not decided here or
 * anywhere in the frontend: a topic's material is the material the learner linked
 * to it, listed in the order the API returned
 * (docs/development/coding-standards.md#ui-responsibilities).
 *
 * `external_reference` is always an `http` or `https` address — the backend
 * refuses any other scheme — so no location on the learner's own machine reaches
 * a page. Material that is not on the web is described by `source_label`, in the
 * learner's own words.
 */

import type { CollectionEnvelope, DataEnvelope } from "@/types/api";

/** The kinds of study material this build catalogues. */
export const RESOURCE_TYPES = [
  "pdf",
  "note",
  "pyq",
  "formula_sheet",
  "video_reference",
] as const;

export type ResourceType = (typeof RESOURCE_TYPES)[number];

/**
 * What a learner reads for each kind.
 *
 * *PYQ* keeps its own name: docs/domain/terminology.md makes it canonical
 * vocabulary, and a previous-year question is exactly what a GATE learner calls
 * it.
 */
export const RESOURCE_TYPE_LABELS: Record<ResourceType, string> = {
  pdf: "PDF",
  note: "Notes",
  pyq: "PYQs",
  formula_sheet: "Formula sheet",
  video_reference: "Video",
};

/** The statuses a resource can be in. */
export const RESOURCE_STATUSES = ["registered", "archived"] as const;

export type ResourceStatus = (typeof RESOURCE_STATUSES)[number];

/**
 * What each status control says, naming the state it moves the resource *to*.
 *
 * Nothing deletes: putting material aside is reversible, so both directions are
 * offered and neither is final.
 */
export const RESOURCE_STATUS_LABELS: Record<ResourceStatus, string> = {
  registered: "Put back in the catalogue",
  archived: "Put aside",
};

/** True when the API sent a type this build knows a label for. */
export function isResourceType(value: string): value is ResourceType {
  return (RESOURCE_TYPES as readonly string[]).includes(value);
}

/**
 * What a learner reads for one kind, falling back to what the API sent.
 *
 * A type this build does not recognise is shown as it arrived rather than
 * hidden, so a backend that grows a sixth still renders something true.
 */
export function resourceTypeLabel(resourceType: string): string {
  return isResourceType(resourceType) ? RESOURCE_TYPE_LABELS[resourceType] : resourceType;
}

/** A curriculum topic a resource covers. */
export interface ResourceTopic {
  id: string;
  code: string | null;
  name: string;
  subject_id: string;
  subject_name: string;
}

/** One piece of study material a learner has catalogued. */
export interface LearningResource {
  id: string;
  /** Null is reserved for curated or shared content, which nothing writes. */
  owner_learner_id: string | null;
  resource_type: ResourceType | string;
  title: string;
  /** Where the material is, in the learner's own words. */
  source_label: string | null;
  /** An http or https address; no local path can reach this field. */
  external_reference: string | null;
  status: ResourceStatus | string;
  topics: ResourceTopic[];
}

/** What RES-001 is asked to register. */
export interface NewLearningResource {
  resource_type: string;
  title: string;
  source_label: string | null;
  external_reference: string | null;
  topic_ids: string[];
}

/**
 * What RES-004 is asked to change.
 *
 * A field left out is not touched; an explicit null clears one that can be
 * cleared. `topic_ids` replaces the whole link set.
 */
export interface LearningResourceUpdate {
  title?: string;
  resource_type?: string;
  source_label?: string | null;
  external_reference?: string | null;
  status?: string;
  topic_ids?: string[];
}

export type LearningResourceCollectionResponse = CollectionEnvelope<LearningResource>;
export type LearningResourceResponse = DataEnvelope<LearningResource>;
