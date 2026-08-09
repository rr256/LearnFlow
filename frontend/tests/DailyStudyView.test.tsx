import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The view renders the status control, which imports the server action and pulls
// in `next/cache`. A component test exercises the markup, not the write path;
// the action's own parsing is covered by tests/plan-submission.test.ts.
vi.mock("@/features/planner/actions", () => ({ savePlanItemStatus: vi.fn() }));

const { DailyStudyView } = await import("@/features/planner/DailyStudyView");

import type { PlanItem, StudyPlan } from "@/types/study-plan";

afterEach(cleanup);

const TODAY = "2026-08-09";

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
    scheduled_for: TODAY,
    estimated_minutes: 60,
    priority: 1,
    status: "planned",
    recommendation_reason: "Topic 1 of 60 in syllabus order, from Operating Systems.",
    completed_at: null,
    ...overrides,
  };
}

function week(overrides: Partial<StudyPlan> = {}): StudyPlan {
  return {
    id: "plan-1",
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

describe("DailyStudyView", () => {
  it("shows the learner's own date rather than the server's", () => {
    render(<DailyStudyView plan={week()} today={TODAY} />);

    expect(screen.getByText(TODAY)).toBeDefined();
  });

  it("names the topic, its subject, and how long the session is expected to take", () => {
    render(<DailyStudyView plan={week()} today={TODAY} />);

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.getByText(/Operating Systems · 1 hr/)).toBeDefined();
  });

  it("shows each item's reason, which is what FR-003 asks a recommendation to carry", () => {
    render(<DailyStudyView plan={week()} today={TODAY} />);

    expect(screen.getByText(/Topic 1 of 60 in syllabus order/)).toBeDefined();
  });

  it("names the action in words rather than by colour alone", () => {
    render(<DailyStudyView plan={week()} today={TODAY} />);

    expect(screen.getByText("Study")).toBeDefined();
  });

  it("offers the completion control beside today's work", () => {
    render(<DailyStudyView plan={week()} today={TODAY} />);

    expect(screen.getByRole("button", { name: /Mark completed.*CPU scheduling/ })).toBeDefined();
  });

  it("lets a learner undo a completion, and keeps the item in place", () => {
    render(
      <DailyStudyView plan={week({ items: [item({ status: "completed" })] })} today={TODAY} />,
    );

    expect(screen.getByText("Marked completed")).toBeDefined();
    expect(screen.getByRole("button", { name: /Return to planned.*CPU scheduling/ })).toBeDefined();
    expect(screen.getByText("CPU scheduling")).toBeDefined();
  });

  it("shows no control for a status PLN-004 will not accept", () => {
    render(<DailyStudyView plan={week({ items: [item({ status: "postponed" })] })} today={TODAY} />);

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/Status: postponed/)).toBeDefined();
  });

  it("leaves out work the plan placed on a day still to come", () => {
    render(
      <DailyStudyView
        plan={week({ items: [item({ scheduled_for: "2026-08-12", topic: null })] })}
        today={TODAY}
      />,
    );

    expect(screen.queryByText("A topic that is no longer stored")).toBeNull();
  });

  it("counts nothing about what is done", () => {
    /* ADR-020 and ADR-021: nothing totals a day, a week, or a plan, and a
     * completion count is the same second opinion in a new form. */
    render(
      <DailyStudyView
        plan={week({
          item_count: 2,
          items: [
            item({ id: "a", status: "completed" }),
            item({ id: "b", priority: 2 }),
          ],
        })}
        today={TODAY}
      />,
    );

    expect(screen.queryByText(/1 of 2/i)).toBeNull();
    expect(screen.queryByText(/\d+%/)).toBeNull();
    expect(screen.queryByText(/total/i)).toBeNull();
  });
});

describe("DailyStudyView and work whose day has passed", () => {
  const missed = week({
    item_count: 2,
    items: [
      item({ id: "friday", scheduled_for: "2026-08-07" }),
      item({ id: "today", priority: 2 }),
    ],
  });

  it("shows it under its own heading rather than mixed into today", () => {
    render(<DailyStudyView plan={missed} today={TODAY} />);

    expect(screen.getByRole("heading", { name: "Today" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "From earlier days" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "2026-08-07" })).toBeDefined();
  });

  it("says plainly that nothing has moved it, and that adapting is the learner's to ask for", () => {
    render(<DailyStudyView plan={missed} today={TODAY} />);

    expect(screen.getByText(/Nothing has moved them/)).toBeDefined();
    expect(screen.getByRole("link", { name: "update your plan" })).toBeDefined();
  });

  it("still lets the learner complete it where it stands", () => {
    render(<DailyStudyView plan={missed} today={TODAY} />);

    expect(screen.getAllByRole("button", { name: /Mark completed/ })).toHaveLength(2);
  });

  it("describes the item, never the learner", () => {
    /* docs/domain/terminology.md: a day passing is a fact about a date, not a
     * verdict on a person. */
    const { container } = render(<DailyStudyView plan={missed} today={TODAY} />);
    const copy = container.textContent ?? "";

    expect(copy).not.toMatch(/behind/i);
    expect(copy).not.toMatch(/you missed/i);
    expect(copy).not.toMatch(/failed/i);
    expect(copy).not.toMatch(/weak/i);
  });

  it("shows no earlier-days section when nothing is outstanding", () => {
    render(<DailyStudyView plan={week()} today={TODAY} />);

    expect(screen.queryByRole("heading", { name: "From earlier days" })).toBeNull();
  });
});

describe("DailyStudyView on a day with no work", () => {
  it("says the plan places nothing on today, without inventing a reason", () => {
    render(<DailyStudyView plan={week({ item_count: 0, items: [] })} today={TODAY} />);

    expect(screen.getByText(/Nothing is planned for today/)).toBeDefined();
  });

  it("says so when the week the plan covers has run out", () => {
    render(
      <DailyStudyView
        plan={week({ period_end: "2026-08-08", item_count: 0, items: [] })}
        today={TODAY}
      />,
    );

    expect(screen.getByText(/ran to 2026-08-08 and has passed/)).toBeDefined();
  });

  it("still shows work whose day has passed on an empty day", () => {
    render(
      <DailyStudyView
        plan={week({ items: [item({ scheduled_for: "2026-08-07" })] })}
        today={TODAY}
      />,
    );

    expect(screen.getByText(/Nothing is planned for today/)).toBeDefined();
    expect(screen.getByRole("heading", { name: "From earlier days" })).toBeDefined();
  });
});
