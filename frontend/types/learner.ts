/**
 * Learner profile types, derived from the LRN-001 and LRN-002 response contract
 * in docs/api/endpoints.md#learner-setup-and-goal-endpoints.
 *
 * Nothing here describes a database table, and no type carries a learner
 * identifier inbound: the backend resolves the effective learner itself, so the
 * frontend never chooses whose profile it is reading or writing.
 */

import type { DataEnvelope } from "@/types/api";

/** The local learner's identity and preferences. */
export interface LearnerProfile {
  id: string;
  display_name: string | null;
  /** IANA timezone name, such as `Asia/Kolkata`. */
  timezone: string;
}

/**
 * A partial update to the profile.
 *
 * A field left out is not changed. `display_name: null` removes the stored name,
 * which absence deliberately cannot express.
 */
export interface LearnerProfileUpdate {
  display_name?: string | null;
  timezone?: string;
}

/** `data` is null before setup has created a learner, which is not an error. */
export type LearnerProfileResponse = DataEnvelope<LearnerProfile | null>;
