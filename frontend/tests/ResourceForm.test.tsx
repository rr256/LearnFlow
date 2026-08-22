import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The form imports the server actions, which pull in `next/cache`. A component
// test exercises the markup and the values it starts with, not the write path;
// what each action sends is covered by tests/resource-submission.test.ts and by
// the standalone run with JavaScript disabled.
vi.mock("@/features/resources/actions", () => ({
  registerResourceAction: vi.fn(),
  saveResourceEdit: vi.fn(),
  saveResourceStatus: vi.fn(),
  // The catalogue now renders each resource's notes, which reach the note
  // actions. Their own parsing is covered by tests/resource-note-submission.test.ts.
  writeResourceNoteAction: vi.fn(),
  saveResourceNoteEdit: vi.fn(),
  saveResourceNoteStatus: vi.fn(),
  removeResourceAction: vi.fn(),
  removeResourceNoteAction: vi.fn(),
}));

const { ResourceForm } = await import("@/features/resources/ResourceForm");
const { ResourceCatalogue } = await import("@/features/resources/ResourceCatalogue");

import type { SubjectTopicOptions } from "@/features/resources/topic-options";
import type { LearningResource } from "@/types/resource";

afterEach(cleanup);

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
    id: "resource-1",
    owner_learner_id: "learner-1",
    resource_type: "pyq",
    title: "Scheduling PYQs 2015–2025",
    source_label: "Blue binder, chapter 3",
    external_reference: "https://example.test/pyq.pdf",
    status: "registered",
    topics: [
      {
        id: "topic-2",
        code: null,
        name: "Deadlock",
        subject_id: "subject-1",
        subject_name: "Operating Systems",
      },
    ],
    ...overrides,
  };
}

describe("ResourceForm, registering", () => {
  it("starts empty, under its own heading", () => {
    render(<ResourceForm topicGroups={topicGroups} />);

    expect(screen.getByRole("heading", { name: "Add study material" })).toBeDefined();
    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe("");
    expect(screen.getByRole("button", { name: "Add to my material" })).toBeDefined();
  });

  it("names no resource, so nothing can be edited by accident", () => {
    const { container } = render(<ResourceForm topicGroups={topicGroups} />);

    expect(container.querySelector('input[name="resource_id"]')).toBeNull();
  });
});

describe("ResourceForm, editing", () => {
  it("starts from what is stored", () => {
    render(<ResourceForm resource={resource()} topicGroups={topicGroups} />);

    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe(
      "Scheduling PYQs 2015–2025",
    );
    expect((screen.getByLabelText("Kind of material") as HTMLSelectElement).value).toBe("pyq");
    expect(
      (screen.getByLabelText("Where it is, in your own words") as HTMLInputElement).value,
    ).toBe("Blue binder, chapter 3");
    expect((screen.getByLabelText("Link") as HTMLInputElement).value).toBe(
      "https://example.test/pyq.pdf",
    );
  });

  it("starts with the topics the material already covers selected", () => {
    render(<ResourceForm resource={resource()} topicGroups={topicGroups} />);

    const picker = screen.getByLabelText("Topics it covers") as HTMLSelectElement;
    const selected = [...picker.selectedOptions].map((option) => option.value);

    expect(selected).toEqual(["topic-2"]);
  });

  it("leaves a field the learner has not filled in empty rather than inventing one", () => {
    render(
      <ResourceForm
        resource={resource({ source_label: null, external_reference: null })}
        topicGroups={topicGroups}
      />,
    );

    expect(
      (screen.getByLabelText("Where it is, in your own words") as HTMLInputElement).value,
    ).toBe("");
    expect((screen.getByLabelText("Link") as HTMLInputElement).value).toBe("");
  });

  it("names the resource it will change", () => {
    const { container } = render(
      <ResourceForm resource={resource()} topicGroups={topicGroups} />,
    );

    const hidden = container.querySelector('input[name="resource_id"]') as HTMLInputElement;
    expect(hidden.value).toBe("resource-1");
  });

  it("offers to save rather than to add", () => {
    render(<ResourceForm resource={resource()} topicGroups={topicGroups} />);

    expect(screen.getByRole("button", { name: "Save changes" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Add to my material" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Add study material" })).toBeNull();
  });

  it("keeps a stored kind this build does not offer, so editing cannot change it silently", () => {
    render(
      <ResourceForm resource={resource({ resource_type: "podcast" })} topicGroups={topicGroups} />,
    );

    expect((screen.getByLabelText("Kind of material") as HTMLSelectElement).value).toBe("podcast");
  });

  it("offers no way to archive, so a correction stays separate from putting material aside", () => {
    const { container } = render(
      <ResourceForm resource={resource()} topicGroups={topicGroups} />,
    );

    expect(container.querySelector('[name="status"]')).toBeNull();
  });

  it("carries every field the edit needs on one form", () => {
    const { container } = render(
      <ResourceForm resource={resource()} topicGroups={topicGroups} />,
    );

    const form = container.querySelector("form") as HTMLFormElement;
    const named = [...form.querySelectorAll("[name]")].map((field) =>
      field.getAttribute("name"),
    );

    expect(named).toEqual([
      "resource_id",
      "title",
      "resource_type",
      "source_label",
      "external_reference",
      "topic_ids",
    ]);
    // That the form posts natively -- `method="POST"` with a multipart
    // encoding, which is what makes editing work without JavaScript -- is
    // asserted against the production standalone server instead. React only
    // renders those attributes for a real server action, and this test mocks
    // them.
  });

  it("says the picker is unavailable without claiming a failure", () => {
    render(<ResourceForm resource={resource()} topicGroups={[]} />);

    expect(screen.getByText(/No topics are available to choose from yet/)).toBeDefined();
    expect(screen.getByText(/save your other changes/)).toBeDefined();
  });
});

describe("ResourceCatalogue, the edit path", () => {
  it("offers an edit form for material in the catalogue", () => {
    render(<ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />);

    expect(
      screen.getByText("Edit details — Scheduling PYQs 2015–2025"),
    ).toBeDefined();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDefined();
  });

  it("prefills that form from the material it belongs to", () => {
    render(<ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />);

    expect((screen.getByLabelText("Title") as HTMLInputElement).value).toBe(
      "Scheduling PYQs 2015–2025",
    );
  });

  it("offers no edit form for material put aside", () => {
    render(
      <ResourceCatalogue resources={[resource({ status: "archived" })]} topicGroups={topicGroups} />,
    );

    expect(screen.queryByText(/^Edit details/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    expect(screen.getByRole("button", { name: /Put back in the catalogue/ })).toBeDefined();
  });

  it("says how to change material that has been put aside", () => {
    render(
      <ResourceCatalogue resources={[resource({ status: "archived" })]} topicGroups={topicGroups} />,
    );

    expect(screen.getByText(/put a piece back to\s+change its details/)).toBeDefined();
  });

  it("edits one piece of material without offering to edit another", () => {
    render(
      <ResourceCatalogue
        resources={[
          resource({ id: "resource-1", title: "In use" }),
          resource({ id: "resource-2", title: "Set down", status: "archived" }),
        ]}
        topicGroups={topicGroups}
      />,
    );

    expect(screen.getAllByRole("button", { name: "Save changes" })).toHaveLength(1);
    expect(screen.getByText("Edit details — In use")).toBeDefined();
    expect(screen.queryByText("Edit details — Set down")).toBeNull();
  });

  it("keeps the edit form behind a disclosure that needs no JavaScript", () => {
    const { container } = render(
      <ResourceCatalogue resources={[resource()]} topicGroups={topicGroups} />,
    );

    const disclosure = container.querySelector("details");
    expect(disclosure).not.toBeNull();
    expect(disclosure?.querySelector("summary")).not.toBeNull();
    expect(disclosure?.querySelector("form")).not.toBeNull();
  });
});
