/**
 * Presenting a generated study plan the way a learner reads it.
 *
 * Plain functions, so they are testable without a running server, and
 * presentation only: nothing here decides what is in a plan, what order it goes
 * in, or how long a session is. Those are backend rules
 * (docs/development/coding-standards.md#ui-responsibilities), and this file
 * would be the wrong place to disagree with them.
 *
 * Dates are printed as the API's own ISO strings rather than parsed into a
 * `Date`, for the reason `features/home/dates.ts` records: `new Date("2027-02-06")`
 * is parsed as UTC midnight and can move a day backwards for a learner west of
 * Greenwich, which on a plan would be the wrong day's work.
 */

import type { PlanItem, PlanItemStatus, StudyPlan } from "@/types/study-plan";
import {
  PLAN_ITEM_ACTION_LABELS,
  PLAN_ITEM_SETTLED_LABELS,
  isSettledStatus,
} from "@/types/study-plan";

/** One day of a weekly plan, with the work placed on it. */
export interface PlannedDay {
  /** The ISO date, as the API sent it. */
  on: string;
  items: PlanItem[];
}

/**
 * Group a dated plan's items by the day they fall on, earliest first.
 *
 * Items with no date are left out: a roadmap item is deliberately undated, and
 * putting it under a heading would claim a day nothing chose.
 */
export function groupByDay(plan: StudyPlan | null): PlannedDay[] {
  if (!plan) {
    return [];
  }
  const days = new Map<string, PlanItem[]>();
  for (const item of plan.items) {
    if (!item.scheduled_for) {
      continue;
    }
    const existing = days.get(item.scheduled_for);
    if (existing) {
      existing.push(item);
    } else {
      days.set(item.scheduled_for, [item]);
    }
  }
  return [...days.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([on, items]) => ({ on, items }));
}

/**
 * How long an item is expected to take, for a learner to read.
 *
 * Reported as the plan stored it. Nothing here totals a day or a week: that is
 * planning arithmetic, and the plan is what performs it.
 */
export function describeEstimate(minutes: number | null): string {
  if (minutes === null) {
    return "No estimate";
  }
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  const hourPart = `${hours} hr`;
  return remainder === 0 ? hourPart : `${hourPart} ${remainder} min`;
}

/**
 * The label for an item's action.
 *
 * An action this build does not recognise is shown as the API sent it rather
 * than hidden, so a backend that grows a fifth action still renders something
 * true.
 */
export function describeAction(action: string): string {
  return action in PLAN_ITEM_ACTION_LABELS
    ? PLAN_ITEM_ACTION_LABELS[action as keyof typeof PLAN_ITEM_ACTION_LABELS]
    : action;
}

/**
 * The plan of a given type among those given, or null.
 *
 * The active plans of one goal are a roadmap and, when the learner's week had
 * room for one, a plan for that week.
 */
export function planOfType(plans: StudyPlan[], planType: string): StudyPlan | null {
  return plans.find((plan) => plan.plan_type === planType) ?? null;
}

/**
 * The classes the panels give one item, marked once the learner has settled it.
 *
 * `styles` is a CSS Module, whose generated type is an index signature rather
 * than a named shape, so each class is read by key and falls back to nothing.
 * A missing class is a stylesheet that no longer defines it, which should leave
 * the item unstyled rather than render the word `undefined` into an attribute.
 *
 * All three settled statuses are marked, because a learner writes all three. The
 * mark never carries the meaning on its own: `describeSettledStatus` puts it in
 * words beside the item (docs/development/coding-standards.md).
 */
export function itemClassName(item: PlanItem, styles: Readonly<Record<string, string>>): string {
  const base = styles.item ?? "";
  if (!isSettledStatus(item.status)) {
    return base;
  }
  return `${base} ${styles[item.status] ?? ""}`.trim();
}

/**
 * What a panel says beside an item the learner has settled, or null.
 *
 * A settled item keeps its place on every panel rather than moving or
 * disappearing: the plan is the record of what was planned, and hiding a line
 * would leave a roadmap short of a topic and a day looking undone. So each panel
 * says what became of it instead.
 *
 * Null for `planned`, which needs no announcement, and for any status this build
 * does not recognise, which is shown by the control rather than labelled here.
 */
export function describeSettledStatus(status: string): string | null {
  return PLAN_ITEM_SETTLED_LABELS[status as PlanItemStatus] ?? null;
}
