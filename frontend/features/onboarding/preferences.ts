/**
 * Writing a saved planning preference the way a learner reads it.
 *
 * Plain functions, so both the setup screen and the home screen can be tested
 * without a running server. They hold no business rule: which orders exist and
 * what a session length may be are decided by the backend, which is the only
 * place they can be enforced (docs/development/coding-standards.md).
 *
 * The reading half of the setup form lives in `submission.ts` rather than here,
 * because preferences ride on the goal write that form already makes.
 *
 * A preference the learner has not set returns null, and a caller leaves it out
 * rather than printing a default. Reporting a guessed value back would tell the
 * learner they had made a decision they have not made.
 *
 * A value this build does not recognise is also null rather than shown raw, the
 * rule the stage and weekday joins already follow: an order added to the contract
 * later is left out instead of printed as an identifier.
 */

import {
  TOPIC_SEQUENCING_LABELS,
  isTopicSequencing,
  type PlanningPreferences,
} from "@/types/study-goal";

/**
 * The preferred session length, or null when the learner has not set one.
 *
 * Minutes are reported as minutes. Converting them to hours would be arithmetic
 * over a planning input, which belongs to the planner rather than to a label —
 * the same rule weekly availability follows.
 */
export function describeSessionLength(minutes: number | null): string | null {
  if (minutes === null) {
    return null;
  }
  return minutes === 1 ? "1 minute" : `${minutes} minutes`;
}

/** The topic order's label, or null when unset or unrecognised. */
export function describeTopicSequencing(sequencing: string | null): string | null {
  if (sequencing === null || !isTopicSequencing(sequencing)) {
    return null;
  }
  return TOPIC_SEQUENCING_LABELS[sequencing];
}

/** Whether the learner has set any preference this build can show. */
export function hasPlanningPreferences(preferences: PlanningPreferences | null): boolean {
  if (preferences === null) {
    return false;
  }
  return (
    describeSessionLength(preferences.preferred_session_minutes) !== null ||
    describeTopicSequencing(preferences.topic_sequencing) !== null
  );
}
