import { describe, expect, it } from "vitest";

import {
  datedWorkEndsInsideMonth,
  isWithinMonth,
  learnerMonth,
  monthBounds,
  monthLabel,
  selectMonthlyWork,
} from "@/features/planner/month";
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

function topic(id: string): PlanItem["topic"] {
  return {
    id,
    code: null,
    name: `Topic ${id}`,
    subject_id: "subject-1",
    subject_name: "Operating Systems",
  };
}

function plan(overrides: Partial<StudyPlan> = {}): StudyPlan {
  return {
    id: "plan-1",
    learner_id: "learner-1",
    study_goal_id: "goal-1",
    plan_type: "weekly",
    period_start: "2026-08-09",
    period_end: "2026-08-15",
    status: "active",
    generation_reason: "The first 3 of 60 topics on your roadmap.",
    item_count: 0,
    items: [],
    ...overrides,
  };
}

describe("learnerMonth", () => {
  /*
   * The instant is passed in rather than read from the clock, so these assert
   * exact months rather than that the code agrees with itself -- the same reason
   * the backend reads its clock through a port.
   */
  it("gives the learner's own month, not the server's", () => {
    // 18:30 UTC on the last day of August is already September in Asia/Kolkata,
    // so the learner's month has turned over while the process's has not.
    const monthBoundary = new Date("2026-08-31T18:30:00Z");

    expect(learnerMonth(monthBoundary, "Asia/Kolkata")).toBe("2026-09");
    expect(learnerMonth(monthBoundary, "UTC")).toBe("2026-08");
  });

  it("gives the previous month for a learner west of the server", () => {
    const earlyMorning = new Date("2026-09-01T02:00:00Z");

    expect(learnerMonth(earlyMorning, "America/New_York")).toBe("2026-08");
    expect(learnerMonth(earlyMorning, "UTC")).toBe("2026-09");
  });

  it("pads a single-digit month, so the result sorts as an ISO month", () => {
    expect(learnerMonth(new Date("2026-01-05T00:30:00Z"), "UTC")).toBe("2026-01");
  });

  it("falls back to UTC for a zone that cannot be read, rather than failing", () => {
    // The same fallback the backend's `_today_for` applies, inherited through
    // `learnerToday`: a month a day out at its boundary is recoverable, and a
    // screen that refuses to render is not.
    const instant = new Date("2026-08-31T18:30:00Z");

    expect(learnerMonth(instant, "Not/AZone")).toBe("2026-08");
    expect(learnerMonth(instant, "")).toBe("2026-08");
  });
});

describe("monthBounds", () => {
  it("runs from the first to the last day of a 31-day month", () => {
    expect(monthBounds("2026-08")).toEqual({ startsOn: "2026-08-01", endsOn: "2026-08-31" });
  });

  it("runs to the 30th of a 30-day month", () => {
    expect(monthBounds("2026-09")).toEqual({ startsOn: "2026-09-01", endsOn: "2026-09-30" });
  });

  it("ends February on the 28th in a common year", () => {
    expect(monthBounds("2026-02").endsOn).toBe("2026-02-28");
  });

  it("ends February on the 29th in a leap year", () => {
    expect(monthBounds("2028-02").endsOn).toBe("2028-02-29");
  });

  it("applies the full Gregorian rule to a century that is not a leap year", () => {
    /* Divisible by four but not by four hundred, so 2100 is a common year. A
     * boundary that is wrong once a century is still wrong. */
    expect(monthBounds("2100-02").endsOn).toBe("2100-02-28");
  });

  it("applies the full Gregorian rule to a century that is a leap year", () => {
    expect(monthBounds("2000-02").endsOn).toBe("2000-02-29");
  });

  it("pads a single-digit day, so the bound sorts as an ISO date", () => {
    expect(monthBounds("2026-01")).toEqual({ startsOn: "2026-01-01", endsOn: "2026-01-31" });
  });
});

describe("monthLabel", () => {
  it("names the month a learner is reading", () => {
    expect(monthLabel("2026-08")).toBe("August 2026");
    expect(monthLabel("2026-01")).toBe("January 2026");
    expect(monthLabel("2026-12")).toBe("December 2026");
  });

  it("returns a month it cannot name unchanged rather than rendering undefined", () => {
    expect(monthLabel("2026-13")).toBe("2026-13");
  });
});

describe("isWithinMonth", () => {
  it("includes both boundaries of the month", () => {
    expect(isWithinMonth("2026-08-01", "2026-08")).toBe(true);
    expect(isWithinMonth("2026-08-31", "2026-08")).toBe(true);
  });

  it("excludes the days either side of it", () => {
    expect(isWithinMonth("2026-07-31", "2026-08")).toBe(false);
    expect(isWithinMonth("2026-09-01", "2026-08")).toBe(false);
  });

  it("excludes an undated item, which belongs to no month", () => {
    expect(isWithinMonth(null, "2026-08")).toBe(false);
  });
});

describe("selectMonthlyWork", () => {
  const month = "2026-08";

  it("groups the month's dated work by day, earliest first", () => {
    const work = selectMonthlyWork(
      plan({
        items: [
          item({ id: "second", scheduled_for: "2026-08-10" }),
          item({ id: "first", scheduled_for: "2026-08-09" }),
        ],
      }),
      null,
      month,
    );

    expect(work.days.map((day) => day.on)).toEqual(["2026-08-09", "2026-08-10"]);
    expect(work.days[0]?.items.map((entry) => entry.id)).toEqual(["first"]);
  });

  it("leaves out dated work belonging to another month", () => {
    /* A weekly plan can straddle a month boundary. The days beyond this month
     * are that month's work, and showing them here would misdate the view. */
    const work = selectMonthlyWork(
      plan({
        items: [
          item({ id: "august", scheduled_for: "2026-08-31" }),
          item({ id: "september", scheduled_for: "2026-09-01" }),
          item({ id: "july", scheduled_for: "2026-07-31" }),
        ],
      }),
      null,
      month,
    );

    expect(work.days.map((day) => day.on)).toEqual(["2026-08-31"]);
  });

  it.each(["completed", "skipped", "postponed"])(
    "keeps a %s item on its day rather than hiding it",
    (status) => {
      /* The plan is the record of what the month held, on this screen as on
       * every other panel (ADR-021, ADR-024, ADR-025). */
      const work = selectMonthlyWork(
        plan({ items: [item({ id: "settled", scheduled_for: "2026-08-09", status })] }),
        null,
        month,
      );

      expect(work.days[0]?.items.map((entry) => entry.id)).toEqual(["settled"]);
    },
  );

  it("lists the roadmap topics the week has not dated, in roadmap order", () => {
    const work = selectMonthlyWork(
      plan({ items: [item({ topic: topic("t1"), scheduled_for: "2026-08-09" })] }),
      plan({
        plan_type: "roadmap",
        items: [
          item({ id: "r1", topic: topic("t1"), priority: 1 }),
          item({ id: "r2", topic: topic("t2"), priority: 2 }),
          item({ id: "r3", topic: topic("t3"), priority: 3 }),
        ],
      }),
      month,
    );

    expect(work.ahead.map((entry) => entry.id)).toEqual(["r2", "r3"]);
  });

  it("leaves out a roadmap topic the week dated in a later month", () => {
    /* The plan has decided when that topic happens, so listing it as undated
     * would say it had not. */
    const work = selectMonthlyWork(
      plan({ items: [item({ topic: topic("t2"), scheduled_for: "2026-09-02" })] }),
      plan({
        plan_type: "roadmap",
        items: [item({ id: "r1", topic: topic("t1") }), item({ id: "r2", topic: topic("t2") })],
      }),
      month,
    );

    expect(work.ahead.map((entry) => entry.id)).toEqual(["r1"]);
  });

  it("keeps a roadmap item naming no topic, which cannot be matched against a dated one", () => {
    const work = selectMonthlyWork(
      plan({ items: [item({ topic: topic("t1"), scheduled_for: "2026-08-09" })] }),
      plan({ plan_type: "roadmap", items: [item({ id: "orphan", topic: null })] }),
      month,
    );

    expect(work.ahead.map((entry) => entry.id)).toEqual(["orphan"]);
  });

  it("dates nothing from a roadmap, whose items name no day", () => {
    const work = selectMonthlyWork(
      plan({ plan_type: "roadmap", items: [item()] }),
      plan({ plan_type: "roadmap", items: [item({ id: "r1" })] }),
      month,
    );

    expect(work.days).toEqual([]);
  });

  it("returns nothing when neither plan exists", () => {
    expect(selectMonthlyWork(null, null, month)).toEqual({ days: [], ahead: [] });
  });
});

describe("datedWorkEndsInsideMonth", () => {
  it("is true when the plan's last dated day falls before the month ends", () => {
    expect(datedWorkEndsInsideMonth(plan({ period_end: "2026-08-15" }), "2026-08")).toBe(true);
  });

  it("is false when the plan's dated work reaches the end of the month", () => {
    expect(datedWorkEndsInsideMonth(plan({ period_end: "2026-08-31" }), "2026-08")).toBe(false);
  });

  it("is false when the plan's dated work runs past the month", () => {
    expect(datedWorkEndsInsideMonth(plan({ period_end: "2026-09-04" }), "2026-08")).toBe(false);
  });

  it("is false for a plan with no end date, whose dated work cannot be said to run out", () => {
    expect(datedWorkEndsInsideMonth(plan({ period_end: null }), "2026-08")).toBe(false);
  });

  it("is false when there is no weekly plan at all", () => {
    expect(datedWorkEndsInsideMonth(null, "2026-08")).toBe(false);
  });
});
