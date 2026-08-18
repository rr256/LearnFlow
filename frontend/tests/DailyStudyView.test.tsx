import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The view renders the status control, which imports the server action and pulls
// in `next/cache`. A component test exercises the markup, not the write path;
// the action's own parsing is covered by tests/plan-submission.test.ts.
vi.mock("@/features/planner/actions", () => ({ savePlanItemStatus: vi.fn() }));

const { DailyStudyView } = await import("@/features/planner/DailyStudyView");

import { resourcesByTopicId } from "@/features/resources/by-topic";

import type { LearningResource } from "@/types/resource";
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

  it("offers the skip control beside today's work", () => {
    /* A learner deciding today's session is not happening says so here, on the
     * screen they are working from. */
    render(<DailyStudyView plan={week()} today={TODAY} />);

    expect(screen.getByRole("button", { name: /Skip this item.*CPU scheduling/ })).toBeDefined();
  });

  it("lets a learner take a skip back, and keeps the item in place", () => {
    render(<DailyStudyView plan={week({ items: [item({ status: "skipped" })] })} today={TODAY} />);

    expect(screen.getByText("Marked skipped")).toBeDefined();
    expect(screen.getByRole("button", { name: /Return to planned.*CPU scheduling/ })).toBeDefined();
    expect(screen.getByText("CPU scheduling")).toBeDefined();
  });

  it("lets a learner undo a completion, and keeps the item in place", () => {
    render(
      <DailyStudyView plan={week({ items: [item({ status: "completed" })] })} today={TODAY} />,
    );

    expect(screen.getByText("Marked completed")).toBeDefined();
    expect(screen.getByRole("button", { name: /Return to planned.*CPU scheduling/ })).toBeDefined();
    expect(screen.getByText("CPU scheduling")).toBeDefined();
  });

  it("offers the postpone control beside today's work", () => {
    /* A learner deciding today's session is not happening yet says so here, on
     * the screen they are working from. */
    render(<DailyStudyView plan={week()} today={TODAY} />);

    expect(
      screen.getByRole("button", { name: /Postpone this item.*CPU scheduling/ }),
    ).toBeDefined();
  });

  it("lets a learner take a postponement back, and keeps the item in place", () => {
    render(
      <DailyStudyView plan={week({ items: [item({ status: "postponed" })] })} today={TODAY} />,
    );

    expect(screen.getByText("Marked postponed")).toBeDefined();
    expect(screen.getByRole("button", { name: /Return to planned.*CPU scheduling/ })).toBeDefined();
    expect(screen.getByText("CPU scheduling")).toBeDefined();
  });

  it("shows no control for a status PLN-004 will not accept", () => {
    render(<DailyStudyView plan={week({ items: [item({ status: "invented" })] })} today={TODAY} />);

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/Status: invented/)).toBeDefined();
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

  it("leaves out work whose day passed once the learner has skipped it", () => {
    /* They have already said it is not going to fill that day. Showing it back
     * under 'From earlier days' would ask a question they answered. */
    render(
      <DailyStudyView
        plan={week({
          item_count: 2,
          items: [
            item({ id: "friday", scheduled_for: "2026-08-07", status: "skipped" }),
            item({ id: "today", priority: 2 }),
          ],
        })}
        today={TODAY}
      />,
    );

    expect(screen.queryByRole("heading", { name: "From earlier days" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "2026-08-07" })).toBeNull();
  });

  it("leaves out work whose day passed once the learner has postponed it", () => {
    /* The display half of the settled rule: adaptation will not write over their
     * statement, so this screen must not present it as still outstanding. */
    render(
      <DailyStudyView
        plan={week({
          item_count: 2,
          items: [
            item({ id: "friday", scheduled_for: "2026-08-07", status: "postponed" }),
            item({ id: "today", priority: 2 }),
          ],
        })}
        today={TODAY}
      />,
    );

    expect(screen.queryByRole("heading", { name: "From earlier days" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "2026-08-07" })).toBeNull();
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

describe("the daily study view showing the learner's own material", () => {
  const TOPIC = {
    id: "topic-1",
    code: null,
    name: "CPU scheduling",
    subject_id: "subject-1",
    subject_name: "Operating Systems",
  };

  function resource(overrides: Partial<LearningResource> = {}): LearningResource {
    return {
      id: `resource-${Math.random()}`,
      owner_learner_id: "learner-1",
      resource_type: "note",
      title: "Kanodia OS notes",
      source_label: "Blue binder, chapter 3",
      external_reference: null,
      status: "registered",
      topics: [TOPIC],
      ...overrides,
    };
  }

  it("lists the material for today's work", () => {
    render(
      <DailyStudyView
        plan={week()}
        resources={resourcesByTopicId([resource()])}
        today={TODAY}
      />,
    );

    expect(screen.getByRole("list", { name: "Your material for CPU scheduling" })).toBeDefined();
    expect(screen.getByText(/Blue binder, chapter 3/)).toBeDefined();
  });

  it("lists it beside work whose day has passed too", () => {
    /* The same item reads the same wherever a learner meets it, which is why
     * both panels render through one component. */
    render(
      <DailyStudyView
        plan={week({ items: [item({ scheduled_for: "2026-08-07" })] })}
        resources={resourcesByTopicId([resource()])}
        today={TODAY}
      />,
    );

    expect(screen.getByRole("heading", { name: "From earlier days" })).toBeDefined();
    expect(screen.getByRole("list", { name: "Your material for CPU scheduling" })).toBeDefined();
  });

  it("shows nothing for a topic with nothing linked", () => {
    /* ADR-032: LearnFlow holds no material and recommends none, so a topic with
     * nothing linked renders nothing rather than an invented suggestion. */
    render(<DailyStudyView plan={week()} resources={new Map()} today={TODAY} />);

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.queryByText("Your material")).toBeNull();
  });

  it("shows the day's work when the catalogue could not be read", () => {
    render(<DailyStudyView plan={week()} resources={null} today={TODAY} />);

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.queryByText("Your material")).toBeNull();
  });

  it("leaves out material the learner put aside", () => {
    render(
      <DailyStudyView
        plan={week()}
        resources={resourcesByTopicId([
          resource({ title: "Put aside notes", status: "archived" }),
          resource({ title: "Current notes" }),
        ])}
        today={TODAY}
      />,
    );

    expect(screen.getByText("Current notes")).toBeDefined();
    expect(screen.queryByText("Put aside notes")).toBeNull();
  });

  it("adds no control for material", () => {
    /* Registering, correcting, and putting material aside live on the catalogue
     * screen alone; the status control stays the only button on an item. */
    render(
      <DailyStudyView
        plan={week()}
        resources={resourcesByTopicId([resource()])}
        today={TODAY}
      />,
    );

    for (const button of screen.queryAllByRole("button")) {
      expect(button.textContent).not.toMatch(/material|resource|archive/i);
    }
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("counts nothing about the material", () => {
    render(
      <DailyStudyView
        plan={week()}
        resources={resourcesByTopicId([resource(), resource({ title: "Second note" })])}
        today={TODAY}
      />,
    );

    expect(screen.queryByText(/2 resources/i)).toBeNull();
    expect(screen.queryByText(/\d+%/)).toBeNull();
  });
});
