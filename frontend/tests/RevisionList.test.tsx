import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The list renders the status control, which imports the server action and pulls
// in `next/cache`. A component test exercises the markup, not the write path;
// the action's own parsing is covered by tests/revision-submission.test.ts.
vi.mock("@/features/revision/actions", () => ({ saveRevisionStatus: vi.fn() }));

const { RevisionList } = await import("@/features/revision/RevisionList");

import type { Revision } from "@/types/revision";

afterEach(cleanup);

function revision(overrides: Partial<Revision> = {}): Revision {
  return {
    id: `revision-${Math.random()}`,
    topic: {
      id: "topic-1",
      code: null,
      name: "CPU scheduling",
      subject_id: "subject-1",
      subject_name: "Operating Systems",
    },
    due_on: "2026-08-20",
    scheduled_for: null,
    status: "due",
    trigger_type: "completed_plan_item",
    recommendation_reason:
      "Operating Systems · CPU scheduling. You completed planned work on this on 2026-08-13, " +
      "and LearnFlow brings a topic back after 7 days when no learning stage is recorded.",
    completed_at: null,
    is_due: true,
    ...overrides,
  };
}

describe("RevisionList", () => {
  it("shows a review that is ready under its own heading", () => {
    render(<RevisionList revisions={[revision()]} />);

    expect(screen.getByRole("heading", { name: "Ready to review" })).toBeDefined();
    expect(screen.getByText("CPU scheduling")).toBeDefined();
  });

  it("names the topic, its subject, and the day it fell due", () => {
    render(<RevisionList revisions={[revision()]} />);

    expect(screen.getByText(/Operating Systems · Due 2026-08-20/)).toBeDefined();
  });

  it("shows the reason the schedule gave, which FR-006 asks a recommendation to carry", () => {
    render(<RevisionList revisions={[revision()]} />);

    expect(screen.getByText(/brings a topic back after 7 days/)).toBeDefined();
  });

  it("names what brought the topic back in words rather than by colour alone", () => {
    render(<RevisionList revisions={[revision()]} />);

    expect(screen.getByText("After finished study")).toBeDefined();
  });

  it("distinguishes a review that follows an earlier review", () => {
    render(<RevisionList revisions={[revision({ trigger_type: "completed_revision" })]} />);

    expect(screen.getByText("After your last review")).toBeDefined();
  });

  it("shows a trigger this build does not recognise as the API sent it", () => {
    render(<RevisionList revisions={[revision({ trigger_type: "low_evidence" })]} />);

    expect(screen.getByText("low_evidence")).toBeDefined();
  });

  it("offers the three statuses a ready review is not already in", () => {
    render(<RevisionList revisions={[revision()]} />);

    expect(screen.getByRole("button", { name: /Mark reviewed.*CPU scheduling/ })).toBeDefined();
    expect(screen.getByRole("button", { name: /Skip this review/ })).toBeDefined();
    expect(screen.getByRole("button", { name: /Postpone this review/ })).toBeDefined();
    expect(screen.queryByRole("button", { name: /Put back as due/ })).toBeNull();
  });

  it.each([
    ["completed", "Marked reviewed"],
    ["skipped", "Marked skipped"],
    ["postponed", "Marked postponed"],
  ])("keeps a %s review in place and says so in words", (status, label) => {
    render(<RevisionList revisions={[revision({ status, is_due: false })]} />);

    expect(screen.getByText(label)).toBeDefined();
    expect(screen.getByText("CPU scheduling")).toBeDefined();
  });

  it("lets a learner take back any answer they gave", () => {
    render(<RevisionList revisions={[revision({ status: "completed", is_due: false })]} />);

    expect(screen.getByRole("button", { name: /Put back as due/ })).toBeDefined();
  });

  it("shows no control for a status REV-003 will not accept", () => {
    /* `scheduled` is in the column but nothing writes it, and it needs a date
     * nothing collects, so it is reported rather than offered. */
    render(<RevisionList revisions={[revision({ status: "scheduled", is_due: false })]} />);

    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/Status: scheduled/)).toBeDefined();
  });

  it("separates reviews still to come from those that are ready", () => {
    render(
      <RevisionList
        revisions={[
          revision({ id: "now", is_due: true }),
          revision({ id: "later", due_on: "2026-09-01", is_due: false }),
        ]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Ready to review" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Later, and already answered" })).toBeDefined();
  });

  it("takes whether a review is due from the API rather than from its date", () => {
    /* `select_due` owns the rule; a screen deciding for itself could disagree
     * with the record it is rendering. */
    render(<RevisionList revisions={[revision({ due_on: "2020-01-01", is_due: false })]} />);

    expect(screen.getByRole("heading", { name: "Later, and already answered" })).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Ready to review" })).toBeDefined();
  });

  it("explains an empty screen for a learner with no reviews at all", () => {
    render(<RevisionList revisions={[]} />);

    expect(screen.getByText(/No reviews are scheduled yet/)).toBeDefined();
    expect(screen.getByRole("link", { name: "mark some study completed" })).toBeDefined();
  });

  it("explains a learner who is simply up to date", () => {
    render(<RevisionList revisions={[revision({ is_due: false })]} />);

    expect(screen.getByText(/Nothing is ready to review today/)).toBeDefined();
  });

  it("names a topic that is no longer stored rather than failing", () => {
    render(<RevisionList revisions={[revision({ topic: null })]} />);

    expect(screen.getByText("A topic that is no longer stored")).toBeDefined();
  });

  it("counts nothing about reviews", () => {
    /* No "3 due", no streak, no percentage — the line terminology.md draws. */
    render(
      <RevisionList
        revisions={[
          revision({ id: "a", status: "completed", is_due: false }),
          revision({ id: "b" }),
        ]}
      />,
    );

    expect(screen.queryByText(/1 of 2/i)).toBeNull();
    expect(screen.queryByText(/\d+%/)).toBeNull();
    expect(screen.queryByText(/streak/i)).toBeNull();
  });

  it("describes reviews and topics, never the learner", () => {
    render(<RevisionList revisions={[revision({ due_on: "2020-01-01" })]} />);

    const page = (document.body.textContent ?? "").toLowerCase();
    for (const wording of [
      "you are behind",
      "you forgot",
      "overdue",
      "you failed",
      "you have neglected",
    ]) {
      expect(page).not.toContain(wording);
    }
  });

  it("never says a review is a failure notice", () => {
    render(<RevisionList revisions={[revision()]} />);

    const page = (document.body.textContent ?? "").toLowerCase();
    expect(page).not.toContain("weak");
    expect(page).not.toContain("mastered");
  });
});
