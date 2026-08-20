import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The note list renders the form and status control, which import the server
// actions and pull in `next/cache`. A component test exercises the markup, not
// the write path; the actions' own parsing is covered by
// tests/resource-note-submission.test.ts.
vi.mock("@/features/resources/actions", () => ({
  saveResourceStatus: vi.fn(),
  registerResourceAction: vi.fn(),
  saveResourceEdit: vi.fn(),
  writeResourceNoteAction: vi.fn(),
  saveResourceNoteEdit: vi.fn(),
  saveResourceNoteStatus: vi.fn(),
}));

const { ResourceNotes } = await import("@/features/resources/ResourceNotes");

import type { ResourceNote } from "@/types/resource-note";

afterEach(cleanup);

/**
 * The paragraph a note's text is displayed in.
 *
 * Queried by exact `textContent` rather than through `getByText`, for two
 * reasons: a note is also prefilled into the correction form's textarea, so the
 * text legitimately appears twice, and `getByText` collapses whitespace, which
 * is exactly what these tests exist to prove is preserved.
 */
function displayedBody(container: HTMLElement, text: string): HTMLParagraphElement | undefined {
  return Array.from(container.querySelectorAll("p")).find(
    (paragraph) => paragraph.textContent === text,
  );
}

function note(overrides: Partial<ResourceNote> = {}): ResourceNote {
  return {
    id: `note-${Math.random()}`,
    resource_id: "resource-1",
    title: "Deadlock conditions",
    body: "Mutual exclusion, hold and wait, no pre-emption, circular wait.",
    status: "active",
    ...overrides,
  };
}

describe("ResourceNotes", () => {
  it("shows the learner's own text", () => {
    const { container } = render(
      <ResourceNotes notes={[note()]} resourceId="resource-1" writable />,
    );

    expect(screen.getByText("Deadlock conditions")).toBeDefined();
    expect(
      displayedBody(container, "Mutual exclusion, hold and wait, no pre-emption, circular wait."),
    ).toBeDefined();
  });

  it("renders pasted markup as text rather than as elements", () => {
    // The main safety property of the feature. React escapes an interpolated
    // string, and nothing here calls `dangerouslySetInnerHTML`, so a pasted tag
    // is something the learner reads rather than something the browser runs.
    const pasted = '<script>alert("x")</script><b>bold?</b>';

    const { container } = render(
      <ResourceNotes notes={[note({ body: pasted })]} resourceId="resource-1" writable />,
    );

    expect(displayedBody(container, pasted)).toBeDefined();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
  });

  it("keeps a note's line breaks in the text rather than inserting markup", () => {
    const pasted = "Step one:\n\n    indented\n\nStep two.";

    const { container } = render(
      <ResourceNotes notes={[note({ body: pasted })]} resourceId="resource-1" writable />,
    );

    // The characters survive exactly; `white-space: pre-wrap` in the stylesheet
    // is what displays them, so no `<br>` is manufactured from the learner's
    // text.
    expect(displayedBody(container, pasted)).toBeDefined();
    expect(container.querySelector("br")).toBeNull();
  });

  it("keeps each note closed so a long one does not fill the catalogue", () => {
    const { container } = render(
      <ResourceNotes notes={[note(), note({ title: "Second" })]} resourceId="resource-1" writable />,
    );

    for (const disclosure of container.querySelectorAll("details")) {
      expect(disclosure.hasAttribute("open")).toBe(false);
    }
  });

  it("separates notes the learner has put aside from the ones they are using", () => {
    render(
      <ResourceNotes
        notes={[note({ title: "In use" }), note({ title: "Set down", status: "archived" })]}
        resourceId="resource-1"
        writable
      />,
    );

    expect(screen.getByText("Notes you have put aside")).toBeDefined();
    expect(screen.getByText("In use")).toBeDefined();
    expect(screen.getByText("Set down")).toBeDefined();
  });

  it("says nothing about how many notes there are", () => {
    const { container } = render(
      <ResourceNotes
        notes={[note(), note({ title: "Second" }), note({ title: "Third" })]}
        resourceId="resource-1"
        writable
      />,
    );

    // No count, no ranking, no score: docs/domain/terminology.md's line between a
    // plan's own coverage and a measurement of the learner, applied to a
    // learner's own writing.
    expect(container.textContent).not.toMatch(/\b3\b/);
    expect(container.textContent).not.toMatch(/notes?\s*\(\d/i);
  });

  it("invites a first note when there are none", () => {
    render(<ResourceNotes notes={[]} resourceId="resource-1" writable />);

    expect(screen.getByText(/Nothing written yet/)).toBeDefined();
  });

  it("says the text stays on this computer", () => {
    // NFR-001 asks for the data-sharing position to be clear before it matters.
    const { container } = render(<ResourceNotes notes={[]} resourceId="resource-1" writable />);

    expect(container.textContent).toMatch(/stored on this computer/i);
  });

  it("offers no control on material the learner has put aside", () => {
    const { container } = render(
      <ResourceNotes notes={[note()]} resourceId="resource-1" writable={false} />,
    );

    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector("button")).toBeNull();
    expect(container.querySelector("textarea")).toBeNull();
  });

  it("still shows the notes of material the learner has put aside", () => {
    // Putting material aside stops it being written to; it hides nothing.
    render(
      <ResourceNotes
        notes={[note({ body: "Still here." })]}
        resourceId="resource-1"
        writable={false}
      />,
    );

    expect(screen.getByText("Still here.")).toBeDefined();
  });

  it("offers no way to delete a note", () => {
    const { container } = render(
      <ResourceNotes notes={[note()]} resourceId="resource-1" writable />,
    );

    expect(container.textContent).not.toMatch(/delete|remove|erase/i);
  });

  it("offers no search control of its own", () => {
    // Searching lives at /resources/search, where the learner asks for it. This
    // area writes and reads one resource's notes and nothing more.
    //
    // The wording changed with ADR-038: the copy now *names* the topic search,
    // because a privacy statement that quietly stopped being true would be worse
    // than none. What must stay absent is a control here, not the word.
    const { container } = render(
      <ResourceNotes notes={[note()]} resourceId="resource-1" writable />,
    );

    expect(container.querySelector('input[type="search"]')).toBeNull();
    expect(container.textContent).not.toMatch(/ask (a|the) (question|mentor)/i);
  });

  it("says who reads a note and when, rather than that nothing does", () => {
    // ADR-038 narrowed ADR-037's promise: the topic search reads notes, locally
    // and only when asked. ADR-039 added the second reader. The form says so.
    const { container } = render(<ResourceNotes notes={[]} resourceId="resource-1" writable />);

    expect(container.textContent).toMatch(/never sent anywhere/i);
    expect(container.textContent).toMatch(/only when you ask/i);
    expect(container.textContent).not.toMatch(/nothing reads it/i);
  });

  it("names the AI model as a reader rather than promising none ever sees a note", () => {
    // MNT-001 made the older promise false. The copy states the second reader,
    // that it runs here, and that it is given passages rather than a whole note.
    const { container } = render(<ResourceNotes notes={[]} resourceId="resource-1" writable />);

    expect(container.textContent).toMatch(/AI model/i);
    expect(container.textContent).toMatch(/on this machine/i);
    expect(container.textContent).toMatch(/never a whole note/i);
    expect(container.textContent).not.toMatch(/no AI model ever sees/i);
  });
});
