import { describe, expect, it } from "vitest";

import {
  describePlanType,
  selectDueReviews,
  selectMarkedWork,
} from "@/features/progress/overview";
import type { Revision } from "@/types/revision";
import type { PlanItem, StudyPlan } from "@/types/study-plan";

function item(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: `item-${Math.random()}`,
    topic: {
      id: "topic-1",
      code: null,
      name: "CPU scheduling",
      subject_id: "subject-1",
      subject_name: "Operating Systems",
    },
    action_type: "study",
    scheduled_for: "2026-08-14",
    estimated_minutes: 60,
    priority: 1,
    status: "planned",
    recommendation_reason: "Topic 1 of 60 in syllabus order, from Operating Systems.",
    completed_at: null,
    ...overrides,
  };
}

function plan(overrides: Partial<StudyPlan> = {}): StudyPlan {
  return {
    id: "plan-week",
    learner_id: "learner-1",
    study_goal_id: "goal-1",
    plan_type: "weekly",
    period_start: "2026-08-14",
    period_end: "2026-08-20",
    status: "active",
    generation_reason: "The first 3 of 60 topics on your roadmap.",
    item_count: 1,
    items: [item()],
    ...overrides,
  };
}

function revision(overrides: Partial<Revision> = {}): Revision {
  return {
    id: `revision-${Math.random()}`,
    topic: {
      id: "topic-1",
      code: null,
      name: "CPU scheduling",
      subject_id: "subject-1",
      subject_name: "Operating Systems",
    },
    due_on: "2026-08-14",
    scheduled_for: null,
    status: "due",
    trigger_type: "completed_plan_item",
    recommendation_reason: "LearnFlow brings a topic back 7 days after finished study.",
    completed_at: null,
    is_due: true,
    ...overrides,
  };
}

describe("selectMarkedWork", () => {
  it("groups the items the learner has settled under the words for each status", () => {
    const groups = selectMarkedWork([
      plan({
        items: [
          item({ id: "a", status: "completed" }),
          item({ id: "b", status: "skipped" }),
          item({ id: "c", status: "postponed" }),
        ],
      }),
    ]);

    expect(groups.map((group) => group.status)).toEqual(["completed", "skipped", "postponed"]);
    expect(groups.map((group) => group.label)).toEqual([
      "Marked completed",
      "Marked skipped",
      "Marked postponed",
    ]);
  });

  it("leaves out a group nothing was marked in, rather than showing it empty", () => {
    const groups = selectMarkedWork([plan({ items: [item({ status: "skipped" })] })]);

    expect(groups.map((group) => group.status)).toEqual(["skipped"]);
  });

  it("leaves out items nobody has said anything about", () => {
    /* `planned` is the one unsettled status: nothing has been said about it, so
     * it belongs under what the plan holds rather than under what the learner
     * has stated. */
    expect(selectMarkedWork([plan({ items: [item({ status: "planned" })] })])).toEqual([]);
  });

  it("leaves out a status this build does not recognise", () => {
    /* The same handling `describeSettledStatus` gives one: it is not marked
     * rather than guessed at. */
    expect(selectMarkedWork([plan({ items: [item({ status: "abandoned" })] })])).toEqual([]);
  });

  it("keeps two items naming the same topic on different plans apart", () => {
    /* PLN-004 moves the named item alone, so a topic marked on the week and
     * still planned on the roadmap is two records. Collapsing them would report
     * a mark the learner never made. */
    const groups = selectMarkedWork([
      plan({ items: [item({ id: "on-week", status: "completed" })] }),
      plan({
        id: "plan-roadmap",
        plan_type: "roadmap",
        items: [item({ id: "on-roadmap", status: "completed", scheduled_for: null })],
      }),
    ]);

    expect(groups[0]?.items.map((marked) => marked.item.id)).toEqual(["on-week", "on-roadmap"]);
    expect(groups[0]?.items.map((marked) => marked.planLabel)).toEqual([
      "Your week",
      "Your roadmap",
    ]);
  });

  it("accepts a goal whose plans do not all exist", () => {
    expect(selectMarkedWork([null, null])).toEqual([]);
    expect(selectMarkedWork([null, plan({ items: [item({ status: "completed" })] })])).toHaveLength(
      1,
    );
  });
});

describe("describePlanType", () => {
  it("names the plan the way the learner reads it elsewhere", () => {
    expect(describePlanType("roadmap")).toBe("Your roadmap");
    expect(describePlanType("weekly")).toBe("Your week");
  });

  it("shows a type this build does not recognise as the API sent it", () => {
    expect(describePlanType("quarterly")).toBe("quarterly");
  });
});

describe("selectDueReviews", () => {
  it("keeps the reviews the backend says are owed now", () => {
    const due = revision({ id: "due" });
    const later = revision({ id: "later", due_on: "2026-09-01", is_due: false });

    expect(selectDueReviews([due, later]).map((each) => each.id)).toEqual(["due"]);
  });

  it("reads `is_due` rather than comparing dates itself", () => {
    /* What counts as due is a domain rule the backend owns. A review dated in
     * the past that the learner has settled is not due, and this must take the
     * backend's word for it rather than deciding from `due_on`. */
    const settled = revision({ id: "settled", due_on: "2020-01-01", status: "skipped", is_due: false });

    expect(selectDueReviews([settled])).toEqual([]);
  });

  it("preserves the order the backend returned", () => {
    /* REV-001 returns earliest due date first, fixed by the backend so a page
     * cannot be reordered after it has been sliced. */
    const first = revision({ id: "first", due_on: "2026-08-10" });
    const second = revision({ id: "second", due_on: "2026-08-14" });

    expect(selectDueReviews([first, second]).map((each) => each.id)).toEqual(["first", "second"]);
  });
});
