import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  INITIAL_REMOVE_STATE,
  RemoveControl,
  type RemoveState,
} from "@/features/resources/RemoveControl";

afterEach(cleanup);

function renderControl(
  action: (previous: RemoveState, form: FormData) => Promise<RemoveState> = vi.fn(
    async () => ({ message: null }),
  ),
) {
  const rendered = render(
    <RemoveControl
      action={action}
      consequence="The file and its contents are deleted from this computer."
      fieldName="file_id"
      fieldValue="file-1"
      kind="PDF"
      label="Chapter 3.pdf"
    />,
  );
  return { ...rendered, action };
}

describe("RemoveControl", () => {
  it("starts closed, so the destructive option is not the first thing on the line", () => {
    const { container } = renderControl();

    expect(container.querySelector("details")?.hasAttribute("open")).toBe(false);
  });

  it("takes two deliberate actions rather than one", () => {
    // Opening the disclosure IS the confirmation step. A `window.confirm` was
    // rejected: it does not exist without JavaScript and cannot be styled.
    const { container } = renderControl();

    expect(container.querySelector("summary")?.textContent).toBe("Remove this PDF");
    expect(
      screen.getByRole("button", { name: /yes, remove this pdf permanently/i }),
    ).toBeDefined();
  });

  it("names what is being removed", () => {
    const { container } = renderControl();

    expect(container.textContent).toContain("Chapter 3.pdf");
  });

  it("says what is lost and that it cannot be undone", () => {
    const { container } = renderControl();

    expect(container.textContent).toMatch(/permanent/i);
    expect(container.textContent).toMatch(/cannot be undone/i);
    expect(container.textContent).toMatch(/keeps no copy/i);
  });

  it("points at the reversible alternative", () => {
    const { container } = renderControl();

    expect(container.textContent).toMatch(/set it aside instead/i);
    expect(container.textContent).toMatch(/reversible/i);
  });

  it("carries the identifier the action reads", () => {
    const { container } = renderControl();

    const hidden = container.querySelector<HTMLInputElement>('input[name="file_id"]');
    expect(hidden?.value).toBe("file-1");
    expect(hidden?.type).toBe("hidden");
  });

  it("posts natively rather than through a script", () => {
    // Asserts the markup, which is all this layer can see. Whether the button is
    // *reachable* with scripting disabled depends on how React streams the page,
    // which only the standalone run can measure -- see ADR-041.
    const { container } = renderControl();

    const form = container.querySelector("form");
    expect(form).not.toBeNull();
    expect(form?.getAttribute("method")).not.toBe("get");
  });

  it("does not remove anything until the button is pressed", () => {
    const { container, action } = renderControl();

    fireEvent.click(container.querySelector("summary")!);

    expect(action).not.toHaveBeenCalled();
  });

  it("reports progress and disables the button while removing", async () => {
    // Held open deliberately -- a mock that resolves at once closes the pending
    // window before it can be observed -- but **resolved before the test ends**.
    // A never-resolving action stays in React's queue and blocks state updates
    // in later tests in this file, which is a leak rather than a fixture.
    let release: (state: { message: string | null }) => void = () => {};
    const pending = new Promise<{ message: string | null }>((resolve) => {
      release = resolve;
    });
    const { container } = renderControl(vi.fn(() => pending));

    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Removing…" })).toHaveProperty("disabled", true);
    });

    await act(async () => {
      release({ message: null });
    });
  });

  it("shows a refusal rather than failing silently", async () => {
    // Rendered inline rather than through the helper: the helper's default
    // parameter fixes the mock's return type to `{ message: null }`, and a
    // refusal needs a string.
    const { container } = render(
      <RemoveControl
        action={vi.fn(async () => ({
          message: "This material is put aside, so it cannot be changed.",
        }))}
        consequence="The file and its contents are deleted from this computer."
        fieldName="file_id"
        fieldValue="file-1"
        kind="PDF"
        label="Chapter 3.pdf"
      />,
    );

    // `act` flushes the action's resolution into the render. The message is read
    // from `textContent` rather than by role: it lives inside a `<details>` that
    // is closed until the learner opens it, and a closed disclosure is outside
    // the accessibility tree.
    await act(async () => {
      fireEvent.submit(container.querySelector("form")!);
    });

    expect(container.textContent).toMatch(/put aside/i);
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
  });

  it("adapts its wording to what is being removed", () => {
    cleanup();
    render(
      <RemoveControl
        action={vi.fn(async () => ({ message: null }))}
        consequence="The note and everything written in it are deleted."
        fieldName="note_id"
        fieldValue="note-1"
        kind="note"
        label="Round robin"
      />,
    );

    expect(screen.getByText("Remove this note")).toBeDefined();
    expect(
      screen.getByRole("button", { name: /yes, remove this note permanently/i }),
    ).toBeDefined();
  });

  it("starts with nothing reported", () => {
    expect(INITIAL_REMOVE_STATE).toEqual({ message: null });
  });
});
