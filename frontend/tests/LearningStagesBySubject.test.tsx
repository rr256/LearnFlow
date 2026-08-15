import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LearningStagesBySubject } from "@/features/progress/LearningStagesBySubject";
import type { SubjectStages } from "@/features/progress/subject-stages";

afterEach(cleanup);

const CURRICULUM_HREF = "/curriculum/programs/program-1";

function groups(): SubjectStages[] {
  return [
    {
      id: "subject-os",
      name: "Operating Systems",
      code: "CS-OS",
      topics: [
        { id: "topic-1", name: "CPU scheduling", code: "OS-2", stageLabel: "Practice-ready" },
        { id: "topic-2", name: "Deadlock", code: null, stageLabel: "Building foundation" },
      ],
    },
    {
      id: "subject-db",
      name: "Databases",
      code: "CS-DB",
      topics: [{ id: "topic-3", name: "Normalisation", code: null, stageLabel: "Not explored" }],
    },
  ];
}

function panel(overrides: Partial<Parameters<typeof LearningStagesBySubject>[0]> = {}) {
  return (
    <LearningStagesBySubject
      curriculumHref={CURRICULUM_HREF}
      groups={groups()}
      {...overrides}
    />
  );
}

/** The list one subject's recorded topics sit in, found through its heading. */
function subjectListing(subjectName: string): HTMLElement {
  const listing = screen.getByRole("heading", { name: new RegExp(subjectName) }).closest("li");
  if (!listing) {
    throw new Error(`No subject listing was rendered for ${subjectName}.`);
  }
  return listing;
}

describe("LearningStagesBySubject", () => {
  it("groups the recorded topics under a heading for each subject", () => {
    render(panel());

    expect(
      screen.getByRole("heading", { name: "Learning stages you have recorded" }),
    ).toBeDefined();
    expect(screen.getByRole("heading", { name: /Operating Systems/ })).toBeDefined();
    expect(screen.getByRole("heading", { name: /Databases/ })).toBeDefined();
    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.getByText("Normalisation")).toBeDefined();
  });

  it("names each stage with the label a learner reads", () => {
    render(panel());

    /* Scoped to the subject each topic sits under, because the lead sentence
     * also names *Not explored* -- the neutral state a topic with no record
     * reads as, which the panel explains rather than lists. */
    const operatingSystems = subjectListing("Operating Systems");
    expect(within(operatingSystems).getByText("Practice-ready")).toBeDefined();
    expect(within(operatingSystems).getByText("Building foundation")).toBeDefined();
    expect(within(subjectListing("Databases")).getByText("Not explored")).toBeDefined();
  });

  it("renders the subjects and topics in the order it was given them", () => {
    /* That order is the curriculum's own, decided by `selectStagesBySubject`
     * from CUR-003. Re-ordering here would put a curriculum rule in a
     * component. */
    render(panel());

    const headings = screen
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent ?? "");

    expect(headings[0]).toContain("Operating Systems");
    expect(headings[1]).toContain("Databases");
  });

  it("offers no control of any kind", () => {
    /* Read-only by decision: recording a stage stays beside the topic in the
     * curriculum view, so this screen cannot become a second place one is
     * written. */
    render(panel());

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(document.querySelector("form")).toBeNull();
    expect(document.querySelector("select")).toBeNull();
    expect(document.querySelector("input")).toBeNull();
  });

  it("counts nothing", () => {
    /* No topic count beside a subject, no percentage of a subject recorded, no
     * rate, and no bar — every one of them a measurement of the learner rather
     * than a description of a plan
     * (docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores). */
    render(panel());

    const rendered = document.body.textContent ?? "";
    expect(rendered).not.toMatch(/\d+%/);
    expect(rendered).not.toMatch(/\d+\s*(of|\/)\s*\d+/);
    expect(rendered).not.toMatch(/\d+\s*topics?\b/i);
    expect(rendered.toLowerCase()).not.toContain("streak");
    expect(rendered.toLowerCase()).not.toContain("completion rate");
    expect(document.querySelector("progress")).toBeNull();
    expect(document.querySelector("meter")).toBeNull();
  });

  it("describes topics, never the learner", () => {
    render(panel());

    const rendered = (document.body.textContent ?? "").toLowerCase();
    for (const wording of [
      "weak topic",
      "weak area",
      "weakness",
      "mastered",
      "failed",
      "you are behind",
      "falling behind",
      "strongest",
      "weakest",
    ]) {
      expect(rendered).not.toContain(wording);
    }
  });

  it("says a learner has recorded nothing, and where they would", () => {
    render(panel({ groups: [] }));

    expect(screen.getByText(/have not recorded a learning stage for any topic yet/)).toBeDefined();
    expect(screen.getByRole("link", { name: "Browse your curriculum" })).toBeDefined();
  });

  it("tells an unreadable panel apart from a learner who has recorded nothing", () => {
    /* The two mean different things, and reporting the first as the second
     * would tell a learner their study history is empty when it is not. */
    render(panel({ groups: null }));

    expect(screen.getByText(/could not be read just now/)).toBeDefined();
    expect(screen.queryByText(/have not recorded a learning stage/)).toBeNull();
    expect(screen.getByText(/Everything else on this page is unaffected/)).toBeDefined();
  });

  it("links to the curriculum, where a stage is recorded and changed", () => {
    render(panel());

    const link = screen.getByRole("link", { name: /Record or change a stage/ });
    expect(link.getAttribute("href")).toBe(CURRICULUM_HREF);
  });

  it("keeps a record whose topic the curriculum no longer holds", () => {
    render(
      panel({
        groups: [
          {
            id: "unplaced",
            name: "Topics no longer in your curriculum",
            code: null,
            topics: [{ id: "topic-gone", name: "A retired topic", code: null, stageLabel: "Practice-ready" }],
          },
        ],
      }),
    );

    expect(
      screen.getByRole("heading", { name: "Topics no longer in your curriculum" }),
    ).toBeDefined();
    expect(screen.getByText("A retired topic")).toBeDefined();
  });
});
