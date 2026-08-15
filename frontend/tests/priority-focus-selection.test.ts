import { describe, expect, it } from "vitest";

import { selectPriorityFocus } from "@/features/progress/priority-focus";
import type { PriorityGroup, PriorityKind } from "@/features/progress/priority-focus";
import type { Revision } from "@/types/revision";
import type { PlanFeasibility, PlanItem, StudyPlan } from "@/types/study-plan";

const TODAY = "2026-08-15";

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
    scheduled_for: "2026-08-13",
    estimated_minutes: 60,
    priority: 1,
    status: "planned",
    recommendation_reason: "Topic 1 of 60 in syllabus order, from Operating Systems.",
    completed_at: null,
    ...overrides,
  };
}

function week(items: PlanItem[]): StudyPlan {
  return {
    id: "plan-week",
    learner_id: "learner-1",
    study_goal_id: "goal-1",
    plan_type: "weekly",
    period_start: "2026-08-11",
    period_end: "2026-08-17",
    status: "active",
    generation_reason: "The first 3 of 60 topics on your roadmap.",
    item_count: items.length,
    items,
  };
}

function revision(overrides: Partial<Revision> = {}): Revision {
  return {
    id: `revision-${Math.random()}`,
    topic: {
      id: "topic-2",
      code: null,
      name: "Deadlock",
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

function feasibility(overrides: Partial<PlanFeasibility> = {}): PlanFeasibility {
  return {
    study_goal_id: "goal-1",
    assessed_on: TODAY,
    verdict: "sufficient",
    reason: "Your saved study week offers 30 hr before 2027-02-06, and 55 topics need 55 hr.",
    unknown_reason: null,
    horizon_ends_on: "2027-02-06",
    remaining_topic_count: 55,
    session_minutes: 60,
    session_minutes_chosen_by_planner: true,
    study_days: 176,
    available_minutes: 1800,
    required_minutes: 3300,
    shortfall_minutes: 0,
    coverable_topic_count: 55,
    ...overrides,
  };
}

/** The group of one kind, or undefined when nothing put it on screen. */
function group(groups: PriorityGroup[], kind: PriorityKind): PriorityGroup | undefined {
  return groups.find((candidate) => candidate.kind === kind);
}

describe("selectPriorityFocus", () => {
  it("names work whose day has passed with nothing said about it", () => {
    const outstanding = item({ id: "item-overdue", scheduled_for: "2026-08-13" });

    const focus = selectPriorityFocus(week([outstanding]), TODAY, [], null);

    const work = group(focus.groups, "outstanding_work");
    expect(work?.entries).toHaveLength(1);
    expect(work?.entries[0]?.title).toBe("CPU scheduling");
    expect(work?.entries[0]?.context).toBe("Operating Systems");
    expect(work?.entries[0]?.fact).toContain("2026-08-13");
    expect(work?.entries[0]?.fact).toContain("that day has passed");
  });

  it("carries the sentence the plan wrote for the item rather than one of its own", () => {
    /* The reason is frozen when the plan is generated (ADR-020). A screen
     * composing its own could disagree with the record it is explaining. */
    const outstanding = item({ recommendation_reason: "You recorded Building foundation here." });

    const focus = selectPriorityFocus(week([outstanding]), TODAY, [], null);

    expect(group(focus.groups, "outstanding_work")?.entries[0]?.reason).toBe(
      "You recorded Building foundation here.",
    );
  });

  it("leaves out work the learner has already settled", () => {
    /* Completed, skipped, and postponed are all statements the learner already
     * made. Showing one back as needing attention would ask them again, which is
     * why adaptation will not re-mark a settled item either. */
    const settled = ["completed", "skipped", "postponed"].map((status, index) =>
      item({ id: `item-${status}`, scheduled_for: `2026-08-1${index}`, status }),
    );

    const focus = selectPriorityFocus(week(settled), TODAY, [], null);

    expect(group(focus.groups, "outstanding_work")).toBeUndefined();
  });

  it("does not treat today's work, or a day still to come, as needing attention", () => {
    const items = [
      item({ id: "item-today", scheduled_for: TODAY }),
      item({ id: "item-ahead", scheduled_for: "2026-08-17" }),
    ];

    const focus = selectPriorityFocus(week(items), TODAY, [], null);

    expect(group(focus.groups, "outstanding_work")).toBeUndefined();
  });

  it("treats an item in a status this build does not recognise as outstanding", () => {
    /* The same call `selectDailyWork` makes: an unknown status has not been
     * settled as far as this build can tell, and hiding it would drop work
     * silently. */
    const unknown = item({ id: "item-unknown", status: "deferred_indefinitely" });

    const focus = selectPriorityFocus(week([unknown]), TODAY, [], null);

    expect(group(focus.groups, "outstanding_work")?.entries).toHaveLength(1);
  });

  it("names the reviews the backend reports as due, and no others", () => {
    const revisions = [
      revision({ id: "rev-due", is_due: true }),
      revision({ id: "rev-later", is_due: false, due_on: "2026-09-01" }),
    ];

    const focus = selectPriorityFocus(null, TODAY, revisions, null);

    const reviews = group(focus.groups, "review_due");
    expect(reviews?.entries).toHaveLength(1);
    expect(reviews?.entries[0]?.id).toBe("rev-due");
    expect(reviews?.entries[0]?.fact).toContain("2026-08-14");
    expect(reviews?.entries[0]?.reason).toContain("7 days after finished study");
  });

  it("reads is_due rather than comparing the date itself", () => {
    /* What counts as due is a domain rule, and unlike an overdue plan item a
     * revision dated today is due. A revision the backend says is due is due even
     * when its date is still ahead. */
    const focus = selectPriorityFocus(
      null,
      TODAY,
      [revision({ id: "rev-ahead", due_on: "2026-12-01", is_due: true })],
      null,
    );

    expect(group(focus.groups, "review_due")?.entries[0]?.id).toBe("rev-ahead");
  });

  it("raises a saved week that does not reach the date, with the backend's sentence", () => {
    const reading = feasibility({
      verdict: "insufficient",
      shortfall_minutes: 1500,
      coverable_topic_count: 30,
      reason: "Your saved week offers 30 hr, and the work that is left needs 55 hr.",
    });

    const focus = selectPriorityFocus(null, TODAY, [], reading);

    const time = group(focus.groups, "time_to_date");
    expect(time?.entries).toHaveLength(1);
    expect(time?.entries[0]?.fact).toContain("does not cover the work left before your date");
    expect(time?.entries[0]?.reason).toBe(reading.reason);
    expect(time?.actionHref).toBe("/plan");
  });

  it("raises an unanswerable time question, naming which input is missing", () => {
    const noDate = selectPriorityFocus(
      null,
      TODAY,
      [],
      feasibility({ verdict: "unknown", unknown_reason: "no_horizon" }),
    );
    const noWeek = selectPriorityFocus(
      null,
      TODAY,
      [],
      feasibility({ verdict: "unknown", unknown_reason: "no_availability_saved" }),
    );

    expect(group(noDate.groups, "time_to_date")?.entries[0]?.fact).toContain("no target date");
    expect(group(noWeek.groups, "time_to_date")?.entries[0]?.fact).toContain("No study week");
    /* Two different gaps ask the learner for two different things, and both are
     * settled in setup rather than by re-planning. */
    expect(group(noDate.groups, "time_to_date")?.actionHref).toBe("/setup");
    expect(group(noWeek.groups, "time_to_date")?.actionHref).toBe("/setup");
  });

  it("says nothing about a week that reaches the date", () => {
    const focus = selectPriorityFocus(null, TODAY, [], feasibility({ verdict: "sufficient" }));

    expect(group(focus.groups, "time_to_date")).toBeUndefined();
  });

  it("says nothing about a verdict this build does not recognise", () => {
    /* Claiming a priority from a value that cannot be interpreted would put a
     * demand in front of a learner that no rule made. */
    const focus = selectPriorityFocus(null, TODAY, [], feasibility({ verdict: "probably_fine" }));

    expect(group(focus.groups, "time_to_date")).toBeUndefined();
  });

  it("makes no claim either way when there is no feasibility reading", () => {
    /* Unreachable on a screen today: a failed PLN-006 read is an `ApiError` the
     * page reports in full. Tolerated here because the prop is typed that way,
     * and it contributes no entry rather than a claim in either direction. */
    const focus = selectPriorityFocus(null, TODAY, [], null);

    expect(group(focus.groups, "time_to_date")).toBeUndefined();
  });

  it("keeps the groups in a fixed order and drops the empty ones", () => {
    /* Presentation, not a ranking: the order is fixed only so the panel reads the
     * same way twice, and a group with nothing in it disappears entirely rather
     * than appearing empty. */
    const focus = selectPriorityFocus(
      week([item({ id: "item-overdue" })]),
      TODAY,
      [revision()],
      feasibility({ verdict: "insufficient" }),
    );

    expect(focus.groups.map((entry) => entry.kind)).toEqual([
      "outstanding_work",
      "review_due",
      "time_to_date",
    ]);
  });

  it("returns nothing at all when no record needs attention", () => {
    const focus = selectPriorityFocus(
      week([item({ id: "item-today", scheduled_for: TODAY })]),
      TODAY,
      [revision({ is_due: false })],
      feasibility({ verdict: "sufficient" }),
    );

    expect(focus.groups).toHaveLength(0);
  });

  it("keeps each outstanding item on its own line, earliest day first", () => {
    /* Two items naming one topic on two days are two records, and PLN-004 moves
     * the named item alone — collapsing them would report a mark nobody made. */
    const items = [
      item({ id: "item-later", scheduled_for: "2026-08-14" }),
      item({ id: "item-earlier", scheduled_for: "2026-08-12" }),
    ];

    const focus = selectPriorityFocus(week(items), TODAY, [], null);

    expect(group(focus.groups, "outstanding_work")?.entries.map((entry) => entry.id)).toEqual([
      "item-earlier",
      "item-later",
    ]);
  });

  it("names a topic the curriculum no longer stores rather than dropping it", () => {
    const focus = selectPriorityFocus(
      week([item({ id: "item-gone", topic: null })]),
      TODAY,
      [revision({ id: "rev-gone", topic: null })],
      null,
    );

    expect(group(focus.groups, "outstanding_work")?.entries[0]?.title).toBe(
      "A topic that is no longer stored",
    );
    expect(group(focus.groups, "outstanding_work")?.entries[0]?.context).toBeNull();
    expect(group(focus.groups, "review_due")?.entries[0]?.title).toBe(
      "A topic that is no longer stored",
    );
  });

  it("ignores an undated plan, because nothing about it can have passed", () => {
    /* A roadmap orders topics and dates none of them. Reading one here would
     * claim a day the plan never named. */
    const roadmap: StudyPlan = {
      ...week([item({ id: "item-roadmap", scheduled_for: null })]),
      id: "plan-roadmap",
      plan_type: "roadmap",
      period_start: null,
      period_end: null,
    };

    const focus = selectPriorityFocus(roadmap, TODAY, [], null);

    expect(group(focus.groups, "outstanding_work")).toBeUndefined();
  });

  it("never reports a figure of its own", () => {
    /* The module computes list lengths to decide whether a group has anything to
     * show; none of them is returned. Nothing here totals, tallies, or scores. */
    const focus = selectPriorityFocus(
      week([item({ id: "item-a" }), item({ id: "item-b", scheduled_for: "2026-08-12" })]),
      TODAY,
      [revision(), revision()],
      feasibility({ verdict: "insufficient" }),
    );

    for (const candidate of focus.groups) {
      const shape = JSON.stringify(candidate);
      expect(shape).not.toContain('"count"');
      expect(shape).not.toContain('"total"');
      for (const entry of candidate.entries) {
        expect(Object.keys(entry).sort()).toEqual(["context", "fact", "id", "reason", "title"]);
      }
    }
  });
});
