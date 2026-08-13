import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// Both panels render the status control, which imports the server action and
// pulls in `next/cache`. A component test exercises the markup, not the write
// path; the action's own parsing is covered by tests/plan-submission.test.ts.
vi.mock("@/features/planner/actions", () => ({ savePlanItemStatus: vi.fn() }));

const { PlanWeek } = await import("@/features/planner/PlanWeek");
const { StudyRoadmap } = await import("@/features/planner/StudyRoadmap");

import type { PlanItem, StudyPlan } from "@/types/study-plan";

afterEach(cleanup);

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
    plan_type: "roadmap",
    period_start: "2026-08-06",
    period_end: "2027-02-06",
    status: "active",
    generation_reason: "60 topics from your curriculum, in syllabus order.",
    item_count: 1,
    items: [item()],
    ...overrides,
  };
}

describe("StudyRoadmap", () => {
  it("shows the plan's own reason for existing", () => {
    render(<StudyRoadmap plan={plan()} />);

    expect(screen.getByText(/60 topics from your curriculum/)).toBeDefined();
  });

  it("shows each item's reason, which is what FR-003 asks a recommendation to carry", () => {
    render(<StudyRoadmap plan={plan()} />);

    expect(screen.getByText(/Topic 1 of 60 in syllabus order/)).toBeDefined();
  });

  it("names the topic and its subject", () => {
    render(<StudyRoadmap plan={plan()} />);

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    // The subject appears twice: beside the topic, and inside the item's own
    // reason, which is prose the backend wrote.
    expect(screen.getAllByText(/Operating Systems/).length).toBeGreaterThan(0);
  });

  it("renders the items in the order the plan put them in", () => {
    render(
      <StudyRoadmap
        plan={plan({
          item_count: 2,
          items: [
            item({ id: "first", topic: { ...item().topic!, name: "First topic" } }),
            item({ id: "second", priority: 2, topic: { ...item().topic!, name: "Second topic" } }),
          ],
        })}
      />,
    );

    const rendered = screen.getAllByRole("listitem").map((node) => node.textContent ?? "");
    expect(rendered[0]).toContain("First topic");
    expect(rendered[1]).toContain("Second topic");
  });

  it("renders nothing at all when no plan has been generated", () => {
    const { container } = render(<StudyRoadmap plan={null} />);

    expect(container.firstChild).toBeNull();
  });

  it("says so when a plan holds no topics", () => {
    render(<StudyRoadmap plan={plan({ item_count: 0, items: [] })} />);

    expect(screen.getByText(/holds no topics/)).toBeDefined();
  });

  it("reports no total of its own", () => {
    /*
     * Turning a plan into an hours figure would be a second opinion about the
     * learner's time, formed here rather than by the planner that has the
     * trade-offs in view.
     */
    render(<StudyRoadmap plan={plan()} />);

    expect(screen.queryByText(/total/i)).toBeNull();
  });
});

describe("PlanWeek", () => {
  const week = plan({
    plan_type: "weekly",
    period_end: "2026-08-12",
    generation_reason: "The first 2 of 60 topics on your roadmap.",
    item_count: 2,
    items: [
      item({ id: "monday", scheduled_for: "2026-08-10" }),
      item({
        id: "saturday",
        priority: 2,
        scheduled_for: "2026-08-15",
        estimated_minutes: 30,
        topic: { ...item().topic!, name: "Page replacement" },
      }),
    ],
  });

  it("groups the work under the day it falls on", () => {
    render(<PlanWeek plan={week} />);

    expect(screen.getByRole("heading", { name: "2026-08-10" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "2026-08-15" })).toBeDefined();
  });

  it("shows how long each session is expected to take", () => {
    render(<PlanWeek plan={week} />);

    expect(screen.getByText(/1 hr/)).toBeDefined();
    expect(screen.getByText(/30 min/)).toBeDefined();
  });

  it("names the action in words rather than by colour alone", () => {
    render(<PlanWeek plan={week} />);

    expect(screen.getAllByText("Study").length).toBe(2);
  });

  it("shows each item's reason, which is what FR-003 asks a recommendation to carry", () => {
    render(<PlanWeek plan={week} />);

    expect(
      screen.getAllByText(/Topic 1 of 60 in syllabus order, from Operating Systems\./).length,
    ).toBe(2);
  });

  it("omits the reason paragraph when an item carries none", () => {
    // The plan's own reason is cleared too, so the assertion can only be
    // satisfied by the item's reason being absent rather than by the panel's.
    render(
      <PlanWeek
        plan={plan({
          plan_type: "weekly",
          generation_reason: null,
          items: [item({ scheduled_for: "2026-08-10", recommendation_reason: null })],
        })}
      />,
    );

    expect(screen.queryByText(/syllabus order/)).toBeNull();
  });

  it("renders nothing when no week was generated", () => {
    const { container } = render(<PlanWeek plan={null} />);

    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when the plan holds no dated work", () => {
    const { container } = render(<PlanWeek plan={plan({ items: [item()] })} />);

    expect(container.firstChild).toBeNull();
  });
});

/**
 * The gap this file previously had: `PlanWeek` rendered a dated item without the
 * reason the plan gave for it, and no test noticed. Asserting the property over
 * both panels at once means a third panel, or a rewrite of either, cannot drop a
 * reason silently.
 */
describe("every panel that shows an item shows its reason", () => {
  const reasoned = plan({
    item_count: 1,
    items: [item({ scheduled_for: "2026-08-10", recommendation_reason: "Because it is next." })],
  });

  it.each([
    ["StudyRoadmap", StudyRoadmap],
    ["PlanWeek", PlanWeek],
  ])("%s renders the item's recommendation_reason", (_name, Panel) => {
    render(<Panel plan={reasoned} />);

    expect(screen.getByText("Because it is next.")).toBeDefined();
  });
});

/**
 * A plan item is a plan item, whichever panel it appears on, so the completion
 * behaviour is asserted over both at once. Asserting it on one would let a
 * rewrite of the other drop the control silently -- which is exactly how the
 * missing reason on `PlanWeek` reached CI.
 */
describe("every panel that shows an item lets the learner say what became of it", () => {
  const panels: [string, typeof StudyRoadmap][] = [
    ["StudyRoadmap", StudyRoadmap],
    ["PlanWeek", PlanWeek],
  ];

  function withStatus(status: string) {
    return plan({
      item_count: 1,
      items: [item({ scheduled_for: "2026-08-10", status })],
    });
  }

  it.each(panels)("%s offers a control naming the topic on a planned item", (_name, Panel) => {
    render(<Panel plan={withStatus("planned")} />);

    expect(screen.getByRole("button", { name: /Mark completed.*CPU scheduling/ })).toBeDefined();
  });

  it.each(panels)("%s offers a way to skip a planned item", (_name, Panel) => {
    /* FR-004's first criterion: a learner may say a planned task is not
     * happening, not only that it is done. */
    render(<Panel plan={withStatus("planned")} />);

    expect(screen.getByRole("button", { name: /Skip this item.*CPU scheduling/ })).toBeDefined();
  });

  it.each(panels)("%s says in words that an item is completed", (_name, Panel) => {
    /* Never colour alone: the meaning has to survive a monochrome screen. */
    render(<Panel plan={withStatus("completed")} />);

    expect(screen.getByText("Marked completed")).toBeDefined();
  });

  it.each(panels)("%s offers a way to undo a completed item", (_name, Panel) => {
    /* A learner who marked the wrong line must not be stuck with it. */
    render(<Panel plan={withStatus("completed")} />);

    expect(
      screen.getByRole("button", { name: /Return to planned.*CPU scheduling/ }),
    ).toBeDefined();
  });

  it.each(panels)("%s keeps a completed item in place rather than hiding it", (_name, Panel) => {
    /* The plan is a record of what it held. Hiding finished work would leave a
     * roadmap short of a topic and a day looking undone. */
    render(<Panel plan={withStatus("completed")} />);

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.getByText(/Topic 1 of 60 in syllabus order/)).toBeDefined();
  });

  it.each(panels)("%s says in words that an item is skipped", (_name, Panel) => {
    /* Never colour alone: the meaning has to survive a monochrome screen. */
    render(<Panel plan={withStatus("skipped")} />);

    expect(screen.getByText("Marked skipped")).toBeDefined();
  });

  it.each(panels)("%s offers a way to take a skip back", (_name, Panel) => {
    /* Nothing in LearnFlow treats a statement about work as a verdict, so
     * skipping is no more one-way than completing is. */
    render(<Panel plan={withStatus("skipped")} />);

    expect(screen.getByRole("button", { name: /Return to planned.*CPU scheduling/ })).toBeDefined();
    expect(screen.getByRole("button", { name: /Mark completed.*CPU scheduling/ })).toBeDefined();
  });

  it.each(panels)("%s keeps a skipped item in place rather than hiding it", (_name, Panel) => {
    /* Hiding a skip would hide a decision the learner may want to take back, and
     * would leave the plan reading as though the item had never been there. */
    render(<Panel plan={withStatus("skipped")} />);

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.getByText(/Topic 1 of 60 in syllabus order/)).toBeDefined();
  });

  it.each(panels)("%s offers a way to postpone a planned item", (_name, Panel) => {
    /* FR-004's first criterion in full: a learner may say a planned task is not
     * happening yet, not only that it is done or that it is not happening. */
    render(<Panel plan={withStatus("planned")} />);

    expect(
      screen.getByRole("button", { name: /Postpone this item.*CPU scheduling/ }),
    ).toBeDefined();
  });

  it.each(panels)("%s says in words that an item is postponed", (_name, Panel) => {
    /* Never colour alone: the meaning has to survive a monochrome screen. */
    render(<Panel plan={withStatus("postponed")} />);

    expect(screen.getByText("Marked postponed")).toBeDefined();
  });

  it.each(panels)("%s offers a way to take a postponement back", (_name, Panel) => {
    /* Nothing in LearnFlow treats a statement about work as a verdict, so
     * postponing is no more one-way than completing is. */
    render(<Panel plan={withStatus("postponed")} />);

    expect(screen.getByRole("button", { name: /Return to planned.*CPU scheduling/ })).toBeDefined();
    expect(screen.getByRole("button", { name: /Mark completed.*CPU scheduling/ })).toBeDefined();
    expect(screen.getByRole("button", { name: /Skip this item.*CPU scheduling/ })).toBeDefined();
  });

  it.each(panels)("%s keeps a postponed item in place rather than hiding it", (_name, Panel) => {
    /* The plan is a record of what was planned, and the day it named is not
     * rewritten by postponing it. */
    render(<Panel plan={withStatus("postponed")} />);

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.getByText(/Topic 1 of 60 in syllabus order/)).toBeDefined();
  });

  it.each(panels)("%s offers the three statuses an item is not already in", (_name, Panel) => {
    /* Every status the column holds is now one a learner may ask for, so the
     * control offers the other three rather than a single next step. */
    render(<Panel plan={withStatus("planned")} />);

    expect(screen.getAllByRole("button")).toHaveLength(3);
  });

  it.each(panels)("%s shows no control for a status the API will not accept", (_name, Panel) => {
    /* Reached only by a status a later backend adds and this build has not been
     * taught; a button offering it would be one that always fails. */
    render(<Panel plan={withStatus("invented")} />);

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/Status: invented/)).toBeDefined();
  });

  it.each(panels)("%s counts nothing about what is done", (_name, Panel) => {
    /* ADR-020: nothing totals a day, a week, or a plan. Counting completions
     * would be the same second opinion in a new form. */
    render(
      <Panel
        plan={plan({
          item_count: 2,
          items: [
            item({ id: "a", scheduled_for: "2026-08-10", status: "completed" }),
            item({ id: "b", scheduled_for: "2026-08-10", priority: 2 }),
          ],
        })}
      />,
    );

    expect(screen.queryByText(/1 of 2 completed/i)).toBeNull();
    expect(screen.queryByText(/\d+%/)).toBeNull();
  });
});
