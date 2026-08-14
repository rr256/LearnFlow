import { describe, expect, it } from "vitest";

import { readRevisionSubmission } from "@/features/revision/submission";
import { REVISION_STATUS_CHANGES, isSettledRevision } from "@/types/revision";

function form(entries: Record<string, string>): FormData {
  const data = new FormData();
  for (const [name, value] of Object.entries(entries)) {
    data.set(name, value);
  }
  return data;
}

describe("readRevisionSubmission", () => {
  it.each(REVISION_STATUS_CHANGES)("reads the %s a form carries", (status) => {
    const submission = readRevisionSubmission(form({ revision_id: "r-1", status }));

    expect(submission).toEqual({ revisionId: "r-1", status });
  });

  it("reads the status from a hidden field rather than a button", () => {
    /* So a scriptless submission carries it exactly as a hydrated one does. */
    const submission = readRevisionSubmission(
      form({ revision_id: "r-1", status: "completed" }),
    );

    expect(submission?.status).toBe("completed");
  });

  it("trims surrounding whitespace", () => {
    const submission = readRevisionSubmission(
      form({ revision_id: "  r-1  ", status: "  skipped  " }),
    );

    expect(submission).toEqual({ revisionId: "r-1", status: "skipped" });
  });

  it("refuses a form naming no revision", () => {
    expect(readRevisionSubmission(form({ status: "completed" }))).toBeNull();
  });

  it("refuses a form naming no status", () => {
    expect(readRevisionSubmission(form({ revision_id: "r-1" }))).toBeNull();
  });

  it("refuses a status this build does not offer", () => {
    expect(readRevisionSubmission(form({ revision_id: "r-1", status: "invented" }))).toBeNull();
  });

  it("refuses `scheduled`, which needs a date nothing collects", () => {
    expect(readRevisionSubmission(form({ revision_id: "r-1", status: "scheduled" }))).toBeNull();
  });

  it("refuses an empty form", () => {
    expect(readRevisionSubmission(new FormData())).toBeNull();
  });
});

describe("isSettledRevision", () => {
  it.each(["completed", "skipped", "postponed"])("treats %s as answered", (status) => {
    expect(isSettledRevision(status)).toBe(true);
  });

  it.each(["due", "scheduled"])("treats %s as still open", (status) => {
    expect(isSettledRevision(status)).toBe(false);
  });

  it("treats a status this build does not recognise as still open", () => {
    /* The safe reading of "nobody has said anything about this". */
    expect(isSettledRevision("invented")).toBe(false);
  });
});
