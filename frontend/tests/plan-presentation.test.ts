import { describe, expect, it } from "vitest";

import {
  describeAction,
  describeEstimate,
  describeSettledStatus,
  groupByDay,
  itemClassName,
  planOfType,
} from "@/features/planner/plan";
import { PLAN_ITEM_SETTLED_STATUSES, isSettledStatus } from "@/types/study-plan";
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
    scheduled_for: null,
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
    id: "plan-1",
    learner_id: "learner-1",
    study_goal_id: "goal-1",
    plan_type: "weekly",
    period_start: "2026-08-06",
    period_end: "2026-08-12",
    status: "active",
    generation_reason: "The first 3 topics of your roadmap.",
    item_count: 0,
    items: [],
    ...overrides,
  };
}

describe("groupByDay", () => {
  it("groups a dated plan's items by day, earliest first", () => {
    const days = groupByDay(
      plan({
        items: [
          item({ id: "b", scheduled_for: "2026-08-08" }),
          item({ id: "a", scheduled_for: "2026-08-06" }),
          item({ id: "c", scheduled_for: "2026-08-06" }),
        ],
      }),
    );

    expect(days.map((day) => day.on)).toEqual(["2026-08-06", "2026-08-08"]);
    expect(days[0]?.items.map((entry) => entry.id)).toEqual(["a", "c"]);
  });

  it("keeps the order the plan put the items in within a day", () => {
    const days = groupByDay(
      plan({
        items: [
          item({ id: "first", priority: 1, scheduled_for: "2026-08-06" }),
          item({ id: "second", priority: 2, scheduled_for: "2026-08-06" }),
        ],
      }),
    );

    expect(days[0]?.items.map((entry) => entry.id)).toEqual(["first", "second"]);
  });

  it("leaves out an undated item rather than claiming a day for it", () => {
    const days = groupByDay(plan({ items: [item({ scheduled_for: null })] }));

    expect(days).toEqual([]);
  });

  it("returns nothing for a plan that does not exist", () => {
    expect(groupByDay(null)).toEqual([]);
  });
});

describe("describeEstimate", () => {
  it("reports minutes under an hour as minutes", () => {
    expect(describeEstimate(45)).toBe("45 min");
  });

  it("reports a whole number of hours without a remainder", () => {
    expect(describeEstimate(120)).toBe("2 hr");
  });

  it("reports hours and minutes together", () => {
    expect(describeEstimate(90)).toBe("1 hr 30 min");
  });

  it("says so when a plan carries no estimate", () => {
    expect(describeEstimate(null)).toBe("No estimate");
  });
});

describe("describeAction", () => {
  it("labels each documented action", () => {
    expect(describeAction("study")).toBe("Study");
    expect(describeAction("review_mistakes")).toBe("Review mistakes");
  });

  it("shows an action this build does not know rather than hiding it", () => {
    expect(describeAction("watch_a_lecture")).toBe("watch_a_lecture");
  });
});

describe("planOfType", () => {
  it("finds the plan of the type asked for", () => {
    const roadmap = plan({ id: "roadmap", plan_type: "roadmap" });
    const weekly = plan({ id: "weekly", plan_type: "weekly" });

    expect(planOfType([roadmap, weekly], "weekly")?.id).toBe("weekly");
  });

  it("returns null when no plan of that type was generated", () => {
    expect(planOfType([plan({ plan_type: "roadmap" })], "weekly")).toBeNull();
  });
});

describe("itemClassName", () => {
  const styles = {
    item: "item",
    completed: "completed",
    skipped: "skipped",
    postponed: "postponed",
  };

  it("marks a completed item without dropping its base class", () => {
    expect(itemClassName(item({ status: "completed" }), styles)).toBe("item completed");
  });

  it("marks a skipped item without dropping its base class", () => {
    expect(itemClassName(item({ status: "skipped" }), styles)).toBe("item skipped");
  });

  it("marks a postponed item without dropping its base class", () => {
    expect(itemClassName(item({ status: "postponed" }), styles)).toBe("item postponed");
  });

  it("leaves a planned item unmarked", () => {
    expect(itemClassName(item(), styles)).toBe("item");
  });

  it("leaves a status this build does not recognise unmarked", () => {
    expect(itemClassName(item({ status: "invented" }), styles)).toBe("item");
  });
});

describe("describeSettledStatus", () => {
  it("names the three statuses a learner writes", () => {
    expect(describeSettledStatus("completed")).toBe("Marked completed");
    expect(describeSettledStatus("skipped")).toBe("Marked skipped");
    expect(describeSettledStatus("postponed")).toBe("Marked postponed");
  });

  it("says nothing about an item nobody has settled", () => {
    expect(describeSettledStatus("planned")).toBeNull();
  });

  it("says nothing about a status this build does not recognise", () => {
    /* The control reports it verbatim; a label here would invent wording for a
     * state the product cannot reach. */
    expect(describeSettledStatus("invented")).toBeNull();
  });

  it("never describes the learner", () => {
    /* docs/domain/terminology.md: a status is a fact about an item. */
    for (const status of ["completed", "skipped", "planned", "postponed"]) {
      expect(describeSettledStatus(status) ?? "").not.toMatch(/\byou\b|\byour\b|behind/i);
    }
  });
});

describe("isSettledStatus", () => {
  it("mirrors the backend's SETTLED_STATUSES exactly", () => {
    /* The one frontend copy of the set `select_overdue` reads. It decides a
     * heading and a mark, never a stored value; the backend rule stays
     * authoritative (ADR-023). */
    expect(PLAN_ITEM_SETTLED_STATUSES).toEqual(["completed", "skipped", "postponed"]);
  });

  it("treats a planned item as the only unsettled one", () => {
    expect(isSettledStatus("planned")).toBe(false);
  });

  it("treats a status this build does not recognise as unsettled", () => {
    /* A backend that grows a fifth status must not have it silently dropped from
     * *From earlier days*, which is where an unsettled item belongs. */
    expect(isSettledStatus("invented")).toBe(false);
  });
});
