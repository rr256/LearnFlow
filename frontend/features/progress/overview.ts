/**
 * Selecting the facts the progress overview states, out of records that already
 * exist.
 *
 * Plain functions, so they are testable without a running server, and selection
 * only: nothing here plans, schedules, re-orders, or decides anything that is
 * stored. What order topics go in, which day work falls on, whether a review is
 * due, and whether a week reaches a date are all backend rules
 * (docs/development/coding-standards.md#ui-responsibilities), and this file would
 * be the wrong place to disagree with them.
 *
 * **Nothing here counts.** No total, no percentage, no ratio, no streak, and no
 * tally of what the learner has completed, skipped, postponed, or reviewed.
 * docs/domain/terminology.md permits a *plan coverage count* — a fact about a
 * plan, such as `item_count` — and forbids everything else by name: "nothing
 * counts skips", "nothing counts postponements", and "no revision count appears
 * in the interface at all". The overview therefore renders the counts the API
 * already reports and derives none of its own. The list lengths below decide
 * whether a panel has anything to show; none of them reaches the screen.
 *
 * Dates stay ISO `YYYY-MM-DD` strings and are never parsed into a `Date`, for the
 * reason `features/home/dates.ts` records.
 */

import type { Revision } from "@/types/revision";
import type { PlanItem, PlanItemStatus, StudyPlan } from "@/types/study-plan";
import {
  PLAN_ITEM_SETTLED_LABELS,
  PLAN_TYPE_LABELS,
  isPlanType,
  isSettledStatus,
} from "@/types/study-plan";

/** One item the learner has settled, with the plan it was settled on. */
export interface MarkedItem {
  item: PlanItem;
  /** The heading of the plan holding it, as a learner reads it. */
  planLabel: string;
}

/** The items sharing one settled status, under the words that describe it. */
export interface MarkedGroup {
  status: PlanItemStatus;
  /** What the learner reads for this status, from the shared label table. */
  label: string;
  items: MarkedItem[];
}

/**
 * The order the groups appear in.
 *
 * Presentation, in the same sense that Monday comes first in a week: it is held
 * here rather than stored, and it ranks nothing. A completed item is not worth
 * more than a skipped one — the three are different statements about different
 * sessions, and the plan treats a skipped and a postponed topic identically.
 */
const MARKED_STATUSES: readonly PlanItemStatus[] = ["completed", "skipped", "postponed"];

/**
 * The work the learner has said something about, across the plans given.
 *
 * Every item the learner has marked keeps its own line, including two items
 * naming the same topic on different plans: PLN-004 moves the named item alone,
 * so a topic settled on the week and still `planned` on the roadmap is two
 * different records and collapsing them would report a mark nobody made.
 *
 * A status this build does not recognise is left out rather than guessed at,
 * which is what `describeSettledStatus` does with the same set.
 *
 * @param plans The plans to read, nulls allowed so a caller can pass whichever
 *   of a goal's active plans exist.
 */
export function selectMarkedWork(plans: readonly (StudyPlan | null)[]): MarkedGroup[] {
  const marked = new Map<string, MarkedItem[]>();

  for (const plan of plans) {
    if (!plan) {
      continue;
    }
    const planLabel = describePlanType(plan.plan_type);
    for (const item of plan.items) {
      if (!isSettledStatus(item.status)) {
        continue;
      }
      const existing = marked.get(item.status);
      if (existing) {
        existing.push({ item, planLabel });
      } else {
        marked.set(item.status, [{ item, planLabel }]);
      }
    }
  }

  return MARKED_STATUSES.map((status) => ({
    status,
    label: PLAN_ITEM_SETTLED_LABELS[status] ?? status,
    items: marked.get(status) ?? [],
  })).filter((group) => group.items.length > 0);
}

/**
 * The heading a learner reads for a plan of this type.
 *
 * A type this build does not recognise is shown as the API sent it rather than
 * hidden, so a backend that writes a `monthly` or `daily` plan still renders
 * something true here.
 */
export function describePlanType(planType: string): string {
  return isPlanType(planType) ? PLAN_TYPE_LABELS[planType] : planType;
}

/**
 * The reviews owed now.
 *
 * `is_due` is **read, not derived**: what counts as due is a domain rule the
 * backend owns, and a screen deciding for itself could disagree with the record
 * it is rendering. Unlike an overdue plan item, a revision dated today is due.
 */
export function selectDueReviews(revisions: readonly Revision[]): Revision[] {
  return revisions.filter((revision) => revision.is_due);
}
