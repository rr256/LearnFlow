/**
 * Date presentation for the home screen.
 *
 * Plain functions, so they are testable without a running server.
 *
 * Dates are printed exactly as the API sent them, in ISO `YYYY-MM-DD`. Nothing
 * here converts one into a `Date`: a date-only string parses as UTC midnight, so
 * rendering it in a locale behind UTC would move a published sitting day back by
 * a day -- the same boundary error the learner's timezone exists to prevent
 * (docs/adr/ADR-016-learner-onboarding-api-contracts.md).
 */

import type { ExaminationPeriodType } from "@/types/study-goal";

/**
 * The learner-facing label for each period type the API documents.
 *
 * `results` reads as an announcement rather than a span, because that period is
 * a single day.
 */
const PERIOD_LABELS: Record<ExaminationPeriodType, string> = {
  registration: "Registration",
  late_registration: "Late registration",
  examination: "Examination",
  results: "Results announced",
};

/**
 * One dated span, written the way a learner reads it.
 *
 * A period whose start and end are the same day is a single-day event, so it is
 * shown as one date rather than as a span from a day to itself.
 */
export function describeDateSpan(startsOn: string, endsOn: string): string {
  return startsOn === endsOn ? startsOn : `${startsOn} to ${endsOn}`;
}

/**
 * The label for a period type.
 *
 * An unrecognised type is shown readably rather than hidden: the stored set is
 * closed today, and a period LearnFlow cannot name is still a date the learner
 * needs to see.
 */
export function describePeriodType(periodType: string): string {
  return PERIOD_LABELS[periodType as ExaminationPeriodType] ?? periodType.replace(/_/g, " ");
}
