import { describe, expect, it } from "vitest";

import {
  INITIAL_RESOURCE_FILE_FORM_STATE,
  readResourceFileStatusSubmission,
  readResourceFileSubmission,
} from "@/features/resources/file-submission";
import { MAX_FILE_BYTES, readablePages, readableSize } from "@/types/resource-file";

const RESOURCE = "11111111-1111-4111-8111-111111111111";

function form(fields: Record<string, string>, file?: File): FormData {
  const data = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    data.set(name, value);
  }
  if (file) {
    data.set("file", file, file.name);
  }
  return data;
}

function pdf(name = "chapter.pdf", bytes = 1024): File {
  return new File([new Uint8Array(bytes)], name, { type: "application/pdf" });
}

describe("readResourceFileSubmission", () => {
  it("reads the chosen file and the resource it belongs to", () => {
    const submitted = readResourceFileSubmission(form({ resource_id: RESOURCE }, pdf()));

    expect(submitted).toMatchObject({ resourceId: RESOURCE });
    expect((submitted as { file: File }).file.name).toBe("chapter.pdf");
  });

  it("asks for a file when none was chosen", () => {
    // A browser submits an empty file input as a zero-byte, unnamed part, so
    // "nothing chosen" is recognised by size and name rather than by absence.
    const empty = new File([], "", { type: "application/octet-stream" });

    expect(readResourceFileSubmission(form({ resource_id: RESOURCE }, empty))).toEqual({
      error: "Choose a PDF to add.",
    });
  });

  it("refuses something that is not named as a PDF", () => {
    const submitted = readResourceFileSubmission(
      form({ resource_id: RESOURCE }, pdf("notes.txt")),
    );

    expect(submitted).toEqual({ error: "Only PDF files can be added here." });
  });

  it("refuses a file past the size limit, naming both sizes", () => {
    const submitted = readResourceFileSubmission(
      form({ resource_id: RESOURCE }, pdf("huge.pdf", MAX_FILE_BYTES + 1)),
    );

    expect((submitted as { error: string }).error).toContain("25.0 MB");
  });

  it("accepts a file exactly at the limit", () => {
    const submitted = readResourceFileSubmission(
      form({ resource_id: RESOURCE }, pdf("big.pdf", MAX_FILE_BYTES)),
    );

    expect(submitted).toMatchObject({ resourceId: RESOURCE });
  });

  it("refuses a submission that names no resource", () => {
    expect(readResourceFileSubmission(form({}, pdf()))).toMatchObject({
      error: expect.stringContaining("could not be identified"),
    });
  });

  it("never repeats the filename in a refusal", () => {
    const secret = "my-private-thesis-draft.docx";

    const submitted = readResourceFileSubmission(form({ resource_id: RESOURCE }, pdf(secret)));

    expect((submitted as { error: string }).error).not.toContain(secret);
  });
});

describe("readResourceFileStatusSubmission", () => {
  it("reads the file and the status it should move to", () => {
    expect(
      readResourceFileStatusSubmission(form({ file_id: "file-1", status: "archived" })),
    ).toEqual({ fileId: "file-1", status: "archived" });
  });

  it("refuses a submission missing either field", () => {
    expect(readResourceFileStatusSubmission(form({ status: "archived" }))).toMatchObject({
      error: expect.stringContaining("could not be identified"),
    });
    expect(readResourceFileStatusSubmission(form({ file_id: "file-1" }))).toMatchObject({
      error: expect.stringContaining("could not be identified"),
    });
  });
});

describe("the initial state", () => {
  it("holds nothing before anything has been uploaded", () => {
    expect(INITIAL_RESOURCE_FILE_FORM_STATE).toEqual({ stored: null, error: null });
  });
});

describe("readable descriptions of a document", () => {
  it("reads a size in units a learner checks against a limit", () => {
    expect(readableSize(25 * 1024 * 1024)).toBe("25.0 MB");
    expect(readableSize(1024 * 800)).toBe("800 KB");
    expect(readableSize(512)).toBe("512 bytes");
  });

  it("says one page rather than 1 pages", () => {
    expect(readablePages(1)).toBe("1 page");
    expect(readablePages(12)).toBe("12 pages");
  });
});
