import { describe, expect, it } from "vitest";

import {
  readEditSubmission,
  readRegisterSubmission,
  readResourceStatusSubmission,
} from "@/features/resources/submission";

function form(entries: Array<[string, string]>): FormData {
  const data = new FormData();
  for (const [name, value] of entries) {
    data.append(name, value);
  }
  return data;
}

describe("readRegisterSubmission", () => {
  it("reads a title, a kind, and where the material is", () => {
    const submission = readRegisterSubmission(
      form([
        ["title", "Process scheduling notes"],
        ["resource_type", "note"],
        ["source_label", "Blue binder"],
      ]),
    );

    expect(submission).toEqual({
      resource_type: "note",
      title: "Process scheduling notes",
      source_label: "Blue binder",
      external_reference: null,
      topic_ids: [],
    });
  });

  it("reads every topic a multiple selection carries", () => {
    const submission = readRegisterSubmission(
      form([
        ["title", "Notes"],
        ["resource_type", "note"],
        ["source_label", "Shelf"],
        ["topic_ids", "topic-1"],
        ["topic_ids", "topic-2"],
      ]),
    );

    expect(submission?.topic_ids).toEqual(["topic-1", "topic-2"]);
  });

  it("accepts material with no topic chosen yet", () => {
    const submission = readRegisterSubmission(
      form([
        ["title", "Notes"],
        ["resource_type", "note"],
        ["source_label", "Shelf"],
      ]),
    );

    expect(submission?.topic_ids).toEqual([]);
  });

  it("sends a blank label as absent rather than as an empty string", () => {
    const submission = readRegisterSubmission(
      form([
        ["title", "Notes"],
        ["resource_type", "note"],
        ["source_label", "   "],
        ["external_reference", "https://example.test/notes"],
      ]),
    );

    expect(submission?.source_label).toBeNull();
    expect(submission?.external_reference).toBe("https://example.test/notes");
  });

  it("trims what the learner typed", () => {
    const submission = readRegisterSubmission(
      form([
        ["title", "  Notes  "],
        ["resource_type", "note"],
        ["source_label", "  Shelf  "],
      ]),
    );

    expect(submission?.title).toBe("Notes");
    expect(submission?.source_label).toBe("Shelf");
  });

  it("refuses a form with no title", () => {
    expect(
      readRegisterSubmission(
        form([
          ["title", "  "],
          ["resource_type", "note"],
          ["source_label", "Shelf"],
        ]),
      ),
    ).toBeNull();
  });

  it("refuses a form naming neither a label nor a link", () => {
    expect(
      readRegisterSubmission(
        form([
          ["title", "Notes"],
          ["resource_type", "note"],
        ]),
      ),
    ).toBeNull();
  });

  it("refuses a kind of material this build does not offer", () => {
    expect(
      readRegisterSubmission(
        form([
          ["title", "Scan"],
          ["resource_type", "attachment"],
          ["source_label", "Shelf"],
        ]),
      ),
    ).toBeNull();
  });

  it("sends a link the backend will judge rather than judging it here", () => {
    const submission = readRegisterSubmission(
      form([
        ["title", "Local notes"],
        ["resource_type", "pdf"],
        ["external_reference", "D:\\GATE\\notes.pdf"],
      ]),
    );

    // Refusing a local path is the backend's rule, and it is the only place it
    // can be enforced. The form sends what was typed and reports the refusal.
    expect(submission?.external_reference).toBe("D:\\GATE\\notes.pdf");
  });
});

describe("readEditSubmission", () => {
  const edit = (entries: Array<[string, string]>) =>
    readEditSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "Scheduling PYQs"],
        ["resource_type", "pyq"],
        ["source_label", "Blue binder"],
        ["external_reference", "https://example.test/pyq.pdf"],
        ...entries,
      ]),
    );

  it("names the resource and carries every field", () => {
    const submission = edit([["topic_ids", "topic-1"]]);

    expect(submission).toEqual({
      resourceId: "resource-1",
      changes: {
        resource_type: "pyq",
        title: "Scheduling PYQs",
        source_label: "Blue binder",
        external_reference: "https://example.test/pyq.pdf",
        topic_ids: ["topic-1"],
      },
    });
  });

  it("sends every topic the picker carried, so the stored set matches the form", () => {
    const submission = edit([
      ["topic_ids", "topic-1"],
      ["topic_ids", "topic-2"],
    ]);

    expect(submission?.changes.topic_ids).toEqual(["topic-1", "topic-2"]);
  });

  it("sends an empty topic list when the learner selected none, which unlinks them", () => {
    const submission = edit([]);

    expect(submission?.changes.topic_ids).toEqual([]);
  });

  it("sends a cleared field as null, which is how RES-004 spells a clearance", () => {
    const submission = readEditSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "Scheduling PYQs"],
        ["resource_type", "pyq"],
        ["source_label", ""],
        ["external_reference", "https://example.test/pyq.pdf"],
      ]),
    );

    expect(submission?.changes.source_label).toBeNull();
  });

  it("refuses an edit that would leave the material saying where it is nowhere", () => {
    const submission = readEditSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "Scheduling PYQs"],
        ["resource_type", "pyq"],
        ["source_label", ""],
        ["external_reference", ""],
      ]),
    );

    expect(submission).toBeNull();
  });

  it("refuses an edit with no title", () => {
    const submission = readEditSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "   "],
        ["resource_type", "pyq"],
        ["source_label", "Blue binder"],
      ]),
    );

    expect(submission).toBeNull();
  });

  it("refuses a kind of material this build does not offer", () => {
    const submission = readEditSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "Scan"],
        ["resource_type", "attachment"],
        ["source_label", "Blue binder"],
      ]),
    );

    expect(submission).toBeNull();
  });

  it("refuses a form naming no resource, so nothing is edited by guesswork", () => {
    const submission = readEditSubmission(
      form([
        ["title", "Scheduling PYQs"],
        ["resource_type", "pyq"],
        ["source_label", "Blue binder"],
      ]),
    );

    expect(submission).toBeNull();
  });

  it("carries no status, so an edit cannot put material aside", () => {
    const submission = edit([["status", "archived"]]);

    expect(submission?.changes).not.toHaveProperty("status");
  });

  it("sends a link the backend will judge rather than judging it here", () => {
    const submission = readEditSubmission(
      form([
        ["resource_id", "resource-1"],
        ["title", "Local notes"],
        ["resource_type", "pdf"],
        ["source_label", ""],
        ["external_reference", "D:\\GATE\\notes.pdf"],
      ]),
    );

    expect(submission?.changes.external_reference).toBe("D:\\GATE\\notes.pdf");
  });
});

describe("readResourceStatusSubmission", () => {
  it("reads the resource and the status a form carries", () => {
    const submission = readResourceStatusSubmission(
      form([
        ["resource_id", "resource-1"],
        ["status", "archived"],
      ]),
    );

    expect(submission).toEqual({ resourceId: "resource-1", status: "archived" });
  });

  it("reads putting material back as well as putting it aside", () => {
    const submission = readResourceStatusSubmission(
      form([
        ["resource_id", "resource-1"],
        ["status", "registered"],
      ]),
    );

    expect(submission?.status).toBe("registered");
  });

  it("refuses a status this build does not offer", () => {
    expect(
      readResourceStatusSubmission(
        form([
          ["resource_id", "resource-1"],
          ["status", "ready"],
        ]),
      ),
    ).toBeNull();
  });

  it("refuses a form naming no resource", () => {
    expect(readResourceStatusSubmission(form([["status", "archived"]]))).toBeNull();
  });
});
