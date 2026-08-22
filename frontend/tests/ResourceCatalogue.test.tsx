import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The catalogue renders the status control, which imports the server action and
// pulls in `next/cache`. A component test exercises the markup, not the write
// path; the action's own parsing is covered by tests/resource-submission.test.ts.
vi.mock("@/features/resources/actions", () => ({
  saveResourceStatus: vi.fn(),
  registerResourceAction: vi.fn(),
  saveResourceEdit: vi.fn(),
  // The catalogue now renders each resource's notes, which reach the note
  // actions. Their own parsing is covered by tests/resource-note-submission.test.ts.
  writeResourceNoteAction: vi.fn(),
  saveResourceNoteEdit: vi.fn(),
  saveResourceNoteStatus: vi.fn(),
  // RES-005 removes the whole resource; the catalogue renders its control.
  removeResourceAction: vi.fn(),
  removeResourceNoteAction: vi.fn(),
}));

const { ResourceCatalogue } = await import("@/features/resources/ResourceCatalogue");

import type { SubjectTopicOptions } from "@/features/resources/topic-options";

import type { LearningResource } from "@/types/resource";

afterEach(cleanup);

/** The paragraph carrying the resource's title, as opposed to the removal warning. */
function titleLine(): HTMLElement | null {
  return (
    screen
      .getAllByText("Process scheduling notes")
      .map((node) => node.closest("p"))
      .find((node) => node?.className?.includes("title")) ??
    screen.getAllByText("Process scheduling notes")[0]?.closest("p") ??
    null
  );
}

/** One stored PDF, enough for the removal warning to count. */
function storedFile() {
  return {
    id: `file-${Math.random().toString(16).slice(2)}`,
    resource_id: "resource-1",
    original_filename: "chapter.pdf",
    byte_size: 1024,
    page_count: 3,
    content_type: "application/pdf",
    checksum: "a".repeat(64),
    status: "active",
    created_at: null,
    updated_at: null,
  };
}

/** One note kept against the material. */
function keptNote() {
  return {
    id: `note-${Math.random().toString(16).slice(2)}`,
    resource_id: "resource-1",
    title: "Round robin",
    body: "Quantum first.",
    status: "active",
  };
}

const topicGroups: SubjectTopicOptions[] = [
  {
    subjectId: "subject-1",
    subjectName: "Operating Systems",
    topics: [
      { id: "topic-1", label: "CPU scheduling" },
      { id: "topic-2", label: "Deadlock" },
    ],
  },
];

function resource(overrides: Partial<LearningResource> = {}): LearningResource {
  return {
    id: `resource-${Math.random()}`,
    owner_learner_id: "learner-1",
    resource_type: "note",
    title: "Process scheduling notes",
    source_label: "Blue binder, chapter 3",
    external_reference: null,
    status: "registered",
    topics: [
      {
        id: "topic-1",
        code: null,
        name: "CPU scheduling",
        subject_id: "subject-1",
        subject_name: "Operating Systems",
      },
    ],
    ...overrides,
  };
}

describe("ResourceCatalogue", () => {
  it("lists material the learner has catalogued", () => {
    render(<ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />);

    expect(screen.getByRole("heading", { name: "Your material" })).toBeDefined();
    // The title also appears inside the removal warning, which names what
    // is being removed, so this reads the title line rather than the text.
    expect(screen.getAllByText("Process scheduling notes").length).toBeGreaterThan(0);
  });

  it("names the kind of material in words rather than by colour alone", () => {
    render(<ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />);

    // Read off the title line rather than by text alone: the edit form's own
    // kind picker renders every label as an option too, and the removal warning
    // names the title as well.
    const line = titleLine();
    expect(line?.textContent).toContain("Notes");
  });

  it("shows a kind this build does not recognise as the API sent it", () => {
    render(
      <ResourceCatalogue
        resources={[resource({ resource_type: "podcast" })]}
        topicGroups={topicGroups}
      />,
    );

    const line = titleLine();
    expect(line?.textContent).toContain("podcast");
  });

  it("shows where offline material is, in the learner's own words", () => {
    render(<ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />);

    expect(screen.getByText("Blue binder, chapter 3")).toBeDefined();
  });

  it("links material that is on the web", () => {
    render(
      <ResourceCatalogue
        resources={[resource({ external_reference: "https://example.test/os.pdf" })]}
        topicGroups={topicGroups}
      />,
    );

    const link = screen.getByRole("link", { name: "https://example.test/os.pdf" });
    expect(link.getAttribute("href")).toBe("https://example.test/os.pdf");
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("names the topics each piece covers", () => {
    render(<ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />);

    expect(screen.getByText(/Covers: CPU scheduling/)).toBeDefined();
  });

  it("says plainly when material covers no topic yet", () => {
    render(<ResourceCatalogue resources={[resource({ topics: [] })]} topicGroups={topicGroups} />);

    expect(screen.getByText(/No topics chosen yet/)).toBeDefined();
  });

  it("offers to put material aside, and to remove it permanently", () => {
    // RES-005 reversed this module's former guard that no removal was offered.
    // Putting aside stays first; removing sits last, behind a disclosure.
    render(<ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />);

    expect(screen.getByRole("button", { name: /Put aside/ })).toBeDefined();
    expect(
      screen.getByRole("button", { name: /Yes, remove this material and everything in it/ }),
    ).toBeDefined();
  });

  it("keeps the removal control closed, so it takes two deliberate actions", () => {
    const { container } = render(
      <ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />,
    );

    const disclosure = [...container.querySelectorAll("details")].find((element) =>
      element.querySelector("summary")?.textContent?.startsWith("Remove this"),
    );
    expect(disclosure).toBeDefined();
    expect(disclosure?.hasAttribute("open")).toBe(false);
  });

  it("says the removal is permanent, what it takes, and what to do instead", () => {
    // A fixed identifier, because the helper above randomises one and the
    // owned-record maps are keyed by it.
    const material = resource({ id: "resource-fixed" });
    const { container } = render(
      <ResourceCatalogue
        resources={[material]}
        topicGroups={topicGroups}
        filesByResource={{ "resource-fixed": [storedFile(), storedFile()] }}
        notesByResource={{ "resource-fixed": [keptNote()] }}
      />,
    );

    const text = container.textContent ?? "";
    expect(text).toMatch(/is permanent/);
    expect(text).toMatch(/2 stored PDFs and 1 note/);
    expect(text).toMatch(/keeps no copy/);
    expect(text).toMatch(/cannot be undone/);
    expect(text).toMatch(/put it aside instead/);
  });

  it("names no figure when the material holds nothing", () => {
    const { container } = render(
      <ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />,
    );

    expect(container.textContent).toContain(
      "The material and the topics it covers are removed from your catalogue.",
    );
  });

  it("offers removal for material that is put aside too", () => {
    // Requiring an archive first would turn the shelf into a deletion queue.
    render(
      <ResourceCatalogue resources={[resource({ status: "archived" })]} topicGroups={topicGroups} />,
    );

    expect(
      screen.getByRole("button", { name: /Yes, remove this material and everything in it/ }),
    ).toBeDefined();
  });

  it("keeps material that was put aside, under its own heading, with a way back", () => {
    render(<ResourceCatalogue resources={[resource({ status: "archived" })]} topicGroups={topicGroups} />);

    expect(screen.getByRole("heading", { name: "Put aside" })).toBeDefined();
    expect(screen.getByRole("button", { name: /Put back in the catalogue/ })).toBeDefined();
  });

  it("separates material in the catalogue from material put aside", () => {
    render(
      <ResourceCatalogue
        resources={[
          resource({ title: "In use" }),
          resource({ title: "Set down", status: "archived" }),
        ]}
        topicGroups={topicGroups}
      />,
    );

    expect(screen.getByRole("heading", { name: "Your material" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Put aside" })).toBeDefined();
    // Each title appears twice now: on its line, and inside the removal warning
    // that names what is being removed.
    expect(screen.getAllByText("In use").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Set down").length).toBeGreaterThan(0);
  });

  it("says how to start when nothing is catalogued", () => {
    render(<ResourceCatalogue resources={[]} topicGroups={topicGroups} />);

    expect(screen.getByText(/Nothing here yet/)).toBeDefined();
  });

  it("distinguishes an empty catalogue from one whose material is all put aside", () => {
    render(<ResourceCatalogue resources={[resource({ status: "archived" })]} topicGroups={topicGroups} />);

    expect(screen.getByText(/Everything you have added is put aside/)).toBeDefined();
    expect(screen.queryByText(/Nothing here yet/)).toBeNull();
  });

  it("counts nothing at all", () => {
    render(
      <ResourceCatalogue
        resources={[resource({ title: "One" }), resource({ title: "Two" })]}
        topicGroups={topicGroups}
      />,
    );

    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\b2 (resources|pieces|items)\b/i);
    expect(text).not.toMatch(/%/);
    expect(document.querySelector("progress")).toBeNull();
    expect(document.querySelector("meter")).toBeNull();
  });

  it("says nothing about the learner, only about the material", () => {
    render(<ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />);

    const text = (document.body.textContent ?? "").toLowerCase();
    for (const forbidden of ["behind", "weak", "mastered", "failed", "streak"]) {
      expect(text).not.toContain(forbidden);
    }
  });
});
