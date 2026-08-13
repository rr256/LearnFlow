import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MonthlyPlanView } from "@/features/planner/MonthlyPlanView";
import type { PlanItem, StudyPlan } from "@/types/study-plan";

afterEach(cleanup);

const MONTH = "2026-08";

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
    scheduled_for: "2026-08-09",
    estimated_minutes: 60,
    priority: 1,
    status: "planned",
    recommendation_reason: "Topic 1 of 60 in syllabus order, from Operating Systems.",
    completed_at: null,
    ...overrides,
  };
}

function topic(id: string, name: string): PlanItem["topic"] {
  return {
    id,
    code: null,
    name,
    subject_id: "subject-1",
    subject_name: "Operating Systems",
  };
}

function week(overrides: Partial<StudyPlan> = {}): StudyPlan {
  return {
    id: "plan-week",
    learner_id: "learner-1",
    study_goal_id: "goal-1",
    plan_type: "weekly",
    period_start: "2026-08-09",
    period_end: "2026-08-15",
    status: "active",
    generation_reason: "The first 3 of 60 topics on your roadmap.",
    item_count: 1,
    items: [item()],
    ...overrides,
  };
}

function roadmap(overrides: Partial<StudyPlan> = {}): StudyPlan {
  return {
    id: "plan-roadmap",
    learner_id: "learner-1",
    study_goal_id: "goal-1",
    plan_type: "roadmap",
    period_start: "2026-08-09",
    period_end: "2027-02-06",
    status: "active",
    generation_reason: "60 topics in syllabus order, to 2027-02-06.",
    item_count: 2,
    items: [
      item({ id: "ahead-1", topic: topic("topic-2", "Deadlock"), scheduled_for: null, priority: 2 }),
      item({ id: "ahead-2", topic: topic("topic-3", "Paging"), scheduled_for: null, priority: 3 }),
    ],
    ...overrides,
  };
}

describe("MonthlyPlanView", () => {
  it("names the month the learner is in, from their own timezone", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.getByRole("heading", { name: "August 2026" })).toBeDefined();
  });

  it("heads each dated day the plan placed work on", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.getByRole("heading", { name: "2026-08-09" })).toBeDefined();
  });

  it("names the topic, its subject, and how long the session is expected to take", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.getAllByText(/Operating Systems · 1 hr/).length).toBeGreaterThan(0);
  });

  it("shows each item's reason, which is what FR-003 asks a recommendation to carry", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.getAllByText(/Topic 1 of 60 in syllabus order/).length).toBeGreaterThan(0);
  });

  it("names the action in words rather than by colour alone", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.getAllByText("Study").length).toBeGreaterThan(0);
  });

  it("lists the roadmap topics the dated week has not reached, in the order it chose", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.getByRole("heading", { name: "Next in your roadmap" })).toBeDefined();
    expect(screen.getByText("Deadlock")).toBeDefined();
    expect(screen.getByText("Paging")).toBeDefined();
  });

  it("says the rest of the month has no dates yet, rather than leaving it to be inferred", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.getByText(/dates work as far as 2026-08-15/)).toBeDefined();
  });

  it("says what the learner is working toward", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.getByText(/working toward 2027-02-06/)).toBeDefined();
  });

  it("says when the month is the one being worked toward", () => {
    render(
      <MonthlyPlanView
        month={MONTH}
        roadmap={roadmap({ period_end: "2026-08-24" })}
        week={week()}
      />,
    );

    expect(screen.getByText(/This is the month you are working toward/)).toBeDefined();
  });

  it.each([
    ["completed", "Marked completed"],
    ["skipped", "Marked skipped"],
    ["postponed", "Marked postponed"],
  ])("keeps a %s item in place and says so in words", (status, label) => {
    render(
      <MonthlyPlanView
        month={MONTH}
        roadmap={roadmap()}
        week={week({ items: [item({ status })] })}
      />,
    );

    expect(screen.getByText(label)).toBeDefined();
    expect(screen.getByText("CPU scheduling")).toBeDefined();
  });

  it("offers no control that would change a plan item", () => {
    /* This screen is read-only by decision (ADR-026). Marking work stays on
     * `/plan/today` and `/plan`, so a month cannot become a fourth place a
     * status is written. */
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.queryByRole("button")).toBeNull();
  });

  it("offers no generate and no adapt control", () => {
    /* Rebuilding a plan stays where the learner asks for it (ADR-022). */
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.queryByRole("button", { name: /Generate/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Update your plan/i })).toBeNull();
  });

  it("counts nothing about the month", () => {
    /* Nothing totals a day, a week, a month, or a plan, and no number here
     * describes the learner (docs/domain/terminology.md). */
    render(
      <MonthlyPlanView
        month={MONTH}
        roadmap={roadmap()}
        week={week({
          item_count: 2,
          items: [item({ id: "a", status: "completed" }), item({ id: "b", priority: 2 })],
        })}
      />,
    );

    expect(screen.queryByText(/1 of 2/i)).toBeNull();
    expect(screen.queryByText(/\d+%/)).toBeNull();
    expect(screen.queryByText(/total/i)).toBeNull();
    expect(screen.queryByText(/streak/i)).toBeNull();
  });

  it("describes items and the plan, never the learner", () => {
    render(
      <MonthlyPlanView
        month={MONTH}
        roadmap={roadmap()}
        week={week({ items: [item({ scheduled_for: "2026-08-02" })] })}
      />,
    );

    const page = document.body.textContent ?? "";
    for (const wording of ["behind", "you failed", "fell behind", "missed target", "you are late"]) {
      expect(page.toLowerCase()).not.toContain(wording);
    }
  });

  it("leaves out dated work belonging to another month", () => {
    render(
      <MonthlyPlanView
        month={MONTH}
        roadmap={roadmap({ items: [] })}
        week={week({ items: [item({ scheduled_for: "2026-09-01", topic: null })] })}
      />,
    );

    expect(screen.queryByText("A topic that is no longer stored")).toBeNull();
  });

  it("explains a month the plan placed no dated work in", () => {
    render(
      <MonthlyPlanView month="2026-11" roadmap={roadmap()} week={week()} />,
    );

    expect(screen.getByText(/no work on a day in November 2026/)).toBeDefined();
    expect(screen.getByRole("link", { name: "update your plan" })).toBeDefined();
  });

  it("explains a goal with no roadmap yet", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={null} week={week()} />);

    expect(screen.getByText(/no roadmap, so there is no order to work through yet/)).toBeDefined();
    expect(screen.getByRole("link", { name: "Generate a plan" })).toBeDefined();
  });

  it("explains a roadmap the dated week reaches the end of", () => {
    render(
      <MonthlyPlanView
        month={MONTH}
        roadmap={roadmap({ items: [item({ id: "only", scheduled_for: null })] })}
        week={week()}
      />,
    );

    expect(screen.getByText(/reaches all of them/)).toBeDefined();
  });

  it("points a learner at the screen where work is marked", () => {
    render(<MonthlyPlanView month={MONTH} roadmap={roadmap()} week={week()} />);

    expect(screen.getByRole("link", { name: "today's study view" })).toBeDefined();
  });
});
