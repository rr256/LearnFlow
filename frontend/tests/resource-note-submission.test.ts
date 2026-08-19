import { describe, expect, it } from "vitest";

import {
  readEditNoteSubmission,
  readNoteStatusSubmission,
  readWriteNoteSubmission,
} from "@/features/resources/note-submission";

function form(entries: Array<[string, string]>): FormData {
  const data = new FormData();
  for (const [name, value] of entries) {
    data.append(name, value);
  }
  return data;
}

describe("readWriteNoteSubmission", () => {
  it("reads the material, a title, and the learner's text", () => {
    const submission = readWriteNoteSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "Deadlock conditions"],
        ["body", "Mutual exclusion, hold and wait."],
      ]),
    );

    expect(submission).toEqual({
      resourceId: "resource-1",
      note: { title: "Deadlock conditions", body: "Mutual exclusion, hold and wait." },
    });
  });

  it("keeps the learner's line breaks and indentation exactly", () => {
    // The one field in the product that must not be normalised: a pasted code
    // block or a transcribed passage loses its shape if the inside is touched.
    const pasted = "Step one:\n\n    indented\n\nStep two.";

    const submission = readWriteNoteSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "Steps"],
        ["body", `\n\n${pasted}\n  `],
      ]),
    );

    expect(submission?.note.body).toBe(pasted);
  });

  it("keeps pasted markup as the characters it is", () => {
    const submission = readWriteNoteSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "Tricky"],
        ["body", "<script>alert(1)</script> **not bold**"],
      ]),
    );

    expect(submission?.note.body).toBe("<script>alert(1)</script> **not bold**");
  });

  it("refuses a note with no text in it", () => {
    expect(
      readWriteNoteSubmission(
        form([
          ["resource_id", "resource-1"],
          ["title", "A title"],
          ["body", "   \n\t "],
        ]),
      ),
    ).toBeNull();
  });

  it("refuses a note with no title", () => {
    expect(
      readWriteNoteSubmission(
        form([
          ["resource_id", "resource-1"],
          ["title", "  "],
          ["body", "Some text."],
        ]),
      ),
    ).toBeNull();
  });

  it("refuses a form that names no material", () => {
    expect(
      readWriteNoteSubmission(form([["title", "A title"], ["body", "Some text."]])),
    ).toBeNull();
  });

  it("does not judge how long a note may be", () => {
    // The backend is the only authority on the bound, so a long note is sent and
    // refused there rather than silently dropped here.
    const submission = readWriteNoteSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "Long"],
        ["body", "x".repeat(50_000)],
      ]),
    );

    expect(submission?.note.body).toHaveLength(50_000);
  });
});

describe("readEditNoteSubmission", () => {
  it("reads the note and both of its fields", () => {
    const submission = readEditNoteSubmission(
      form([
        ["note_id", "note-1"],
        ["title", "Deadlock conditions"],
        ["body", "Corrected text."],
      ]),
    );

    expect(submission).toEqual({
      noteId: "note-1",
      changes: { title: "Deadlock conditions", body: "Corrected text." },
    });
  });

  it("never carries a status, so a correction cannot put a note aside", () => {
    const submission = readEditNoteSubmission(
      form([
        ["note_id", "note-1"],
        ["title", "A title"],
        ["body", "Some text."],
        ["status", "archived"],
      ]),
    );

    expect(submission?.changes).not.toHaveProperty("status");
  });

  it("refuses a form that names no note", () => {
    expect(
      readEditNoteSubmission(form([["title", "A title"], ["body", "Some text."]])),
    ).toBeNull();
  });

  it("refuses a correction that would empty the note", () => {
    expect(
      readEditNoteSubmission(
        form([
          ["note_id", "note-1"],
          ["title", "A title"],
          ["body", ""],
        ]),
      ),
    ).toBeNull();
  });
});

describe("readNoteStatusSubmission", () => {
  it("reads the note and the status the hidden field carries", () => {
    const submission = readNoteStatusSubmission(
      form([
        ["note_id", "note-1"],
        ["status", "archived"],
      ]),
    );

    expect(submission).toEqual({ noteId: "note-1", status: "archived" });
  });

  it("reads the status that brings a note back", () => {
    const submission = readNoteStatusSubmission(
      form([
        ["note_id", "note-1"],
        ["status", "active"],
      ]),
    );

    expect(submission).toEqual({ noteId: "note-1", status: "active" });
  });

  it("refuses a status a note cannot be set to", () => {
    expect(
      readNoteStatusSubmission(
        form([
          ["note_id", "note-1"],
          ["status", "indexed"],
        ]),
      ),
    ).toBeNull();
  });

  it("refuses a form that names no note", () => {
    expect(readNoteStatusSubmission(form([["status", "archived"]]))).toBeNull();
  });
});
