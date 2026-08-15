import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PriorityFocus } from "@/features/progress/PriorityFocus";
import type { PriorityFocus as PriorityFocusReading } from "@/features/progress/priority-focus";

afterEach(cleanup);

function reading(overrides: Partial<PriorityFocusReading> = {}): PriorityFocusReading {
  return {
    groups: [
      {
        kind: "outstanding_work",
        heading: "Work whose day has passed",
        actionHref: "/plan/today",
        actionLabel: "Say what became of it on today's screen",
        entries: [
          {
            id: "item-1",
            title: "CPU scheduling",
            context: "Operating Systems",
            fact: "Your plan placed this on 2026-08-13, and that day has passed with nothing said about it.",
            reason: "Topic 1 of 60 in syllabus order, from Operating Systems.",
          },
        ],
      },
      {
        kind: "review_due",
        heading: "Topics ready to come back",
        actionHref: "/revisions",
        actionLabel: "Mark these on your reviews screen",
        entries: [
          {
            id: "rev-1",
            title: "Deadlock",
            context: "Operating Systems",
            fact: "LearnFlow has had this ready to review since 2026-08-14.",
            reason: "LearnFlow brings a topic back 7 days after finished study.",
          },
        ],
      },
      {
        kind: "time_to_date",
        heading: "The time you have saved",
        actionHref: "/plan",
        actionLabel: "See the figures and update your plan",
        entries: [
          {
            id: "goal-1",
            title: "The study time you saved and the date you are working toward",
            context: null,
            fact: "The study time you have saved does not cover the work left before your date.",
            reason: "Your saved week offers 30 hr, and the work that is left needs 55 hr.",
          },
        ],
      },
    ],
    ...overrides,
  };
}

function panel(overrides: Partial<Parameters<typeof PriorityFocus>[0]> = {}) {
  return <PriorityFocus focus={reading()} hasWeek {...overrides} />;
}

/** The listing one group sits in, found through its heading. */
function groupListing(heading: string): HTMLElement {
  const listing = screen.getByRole("heading", { name: heading }).closest("li");
  if (!listing) {
    throw new Error(`No group listing was rendered for ${heading}.`);
  }
  return listing;
}

describe("PriorityFocus", () => {
  it("gathers each kind of attention under its own heading", () => {
    render(panel());

    expect(screen.getByRole("heading", { name: "What could use your attention" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Work whose day has passed" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Topics ready to come back" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "The time you have saved" })).toBeDefined();
  });

  it("explains why each entry is here, in the words of the record behind it", () => {
    render(panel());

    const work = groupListing("Work whose day has passed");
    expect(within(work).getByText("CPU scheduling")).toBeDefined();
    expect(within(work).getByText(/that day has passed/)).toBeDefined();
    expect(within(work).getByText(/Topic 1 of 60 in syllabus order/)).toBeDefined();

    const reviews = groupListing("Topics ready to come back");
    expect(within(reviews).getByText(/ready to review since 2026-08-14/)).toBeDefined();
    expect(within(reviews).getByText(/7 days after finished study/)).toBeDefined();
  });

  it("names where each kind is acted on and links there", () => {
    /* ADR-029's rule for this screen: every panel names where its action lives
     * rather than acquiring a control of its own. */
    render(panel());

    expect(
      within(groupListing("Work whose day has passed")).getByRole("link", {
        name: "Say what became of it on today's screen",
      }),
    ).toBeDefined();
    expect(
      within(groupListing("Topics ready to come back")).getByRole("link", {
        name: "Mark these on your reviews screen",
      }),
    ).toBeDefined();
    expect(
      within(groupListing("The time you have saved")).getByRole("link", {
        name: "See the figures and update your plan",
      }),
    ).toBeDefined();
  });

  it("offers no control of any kind", () => {
    /* `/progress` writes nothing at all. Marking work stays on today's screen and
     * the plan screen, and rebuilding a plan stays where the learner asks for it. */
    render(panel());

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(document.querySelector("form")).toBeNull();
    expect(document.querySelector("select")).toBeNull();
    expect(document.querySelector("input")).toBeNull();
  });

  it("counts nothing", () => {
    /* No tally of how many things need attention, no percentage, no fraction, no
     * streak, and no bar — each a measurement of the learner rather than a
     * description of a plan
     * (docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores). */
    render(panel());

    const rendered = document.body.textContent ?? "";
    expect(rendered).not.toMatch(/\d+%/);
    expect(rendered).not.toMatch(/\d+\s*(of|\/)\s*\d+\s*(items?|topics?|reviews?)/i);
    expect(rendered).not.toMatch(/\d+\s*(items?|reviews?)\s+(need|are|waiting)/i);
    expect(rendered.toLowerCase()).not.toContain("streak");
    expect(rendered.toLowerCase()).not.toContain("completion rate");
    expect(document.querySelector("progress")).toBeNull();
    expect(document.querySelector("meter")).toBeNull();
  });

  it("ranks nothing", () => {
    /* No entry is numbered, no group is called the most important, and there is
     * no top-anything. Nothing in LearnFlow ranks two topics against each other. */
    render(panel());

    const rendered = (document.body.textContent ?? "").toLowerCase();
    for (const wording of [
      "most important",
      "highest priority",
      "top priority",
      "urgent",
      "rank",
      "score",
      "first priority",
    ]) {
      expect(rendered).not.toContain(wording);
    }
    expect(rendered).toContain("not in any order of importance");
  });

  it("describes records, never the learner", () => {
    render(panel());

    const rendered = (document.body.textContent ?? "").toLowerCase();
    for (const wording of [
      "weak topic",
      "weak area",
      "weakness",
      "weakest",
      "mastered",
      "failed",
      "you are behind",
      "falling behind",
      "at risk",
      "procrastinat",
      "you gave up",
    ]) {
      expect(rendered).not.toContain(wording);
    }
  });

  it("says nothing is waiting, and names what would appear here", () => {
    render(panel({ focus: reading({ groups: [] }) }));

    expect(screen.getByText(/Nothing is waiting on you right now/)).toBeDefined();
    expect(screen.getByText(/would each appear here/)).toBeDefined();
  });

  it("explains an empty panel differently when no week is dated", () => {
    /* With no weekly plan there is no day for anything to have passed on, so the
     * panel says that rather than implying the learner is up to date. */
    render(panel({ focus: reading({ groups: [] }), hasWeek: false }));

    expect(screen.getByText(/no plan for a week/)).toBeDefined();
    expect(screen.getByRole("link", { name: "Generate or update your plan" })).toBeDefined();
  });

  it("leaves the subject out when there is none to name", () => {
    render(
      panel({
        focus: reading({
          groups: [
            {
              kind: "review_due",
              heading: "Topics ready to come back",
              actionHref: "/revisions",
              actionLabel: "Mark these on your reviews screen",
              entries: [
                {
                  id: "rev-gone",
                  title: "A topic that is no longer stored",
                  context: null,
                  fact: "LearnFlow has had this ready to review since 2026-08-14.",
                  reason: null,
                },
              ],
            },
          ],
        }),
      }),
    );

    expect(screen.getByText("A topic that is no longer stored")).toBeDefined();
    expect(screen.queryByText("Operating Systems")).toBeNull();
  });
});
