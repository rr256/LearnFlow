import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  listResourceNotes,
  updateResourceNote,
  writeResourceNote,
} from "@/lib/api-client";

function respondWith(body: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

function requestUrl(): string {
  return vi.mocked(fetch).mock.calls[0]?.[0] as string;
}

function requestInit(): RequestInit {
  return vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
}

const RESOURCE_ID = "11111111-1111-4111-8111-111111111111";
const NOTE_ID = "22222222-2222-4222-8222-222222222222";

const note = {
  id: NOTE_ID,
  resource_id: RESOURCE_ID,
  title: "Deadlock conditions",
  body: "Mutual exclusion, hold and wait.",
  status: "active",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listResourceNotes", () => {
  it("reads the collection envelope", async () => {
    respondWith({ data: [note], pagination: { limit: 100, offset: 0, total: 1 } });

    const notes = await listResourceNotes(RESOURCE_ID);

    expect(notes).toHaveLength(1);
    expect(notes[0]?.title).toBe("Deadlock conditions");
  });

  it("asks for the documented path, scoped to the resource", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listResourceNotes(RESOURCE_ID);

    expect(requestUrl()).toContain(`/api/v1/resources/${RESOURCE_ID}/notes?`);
    expect(requestInit().method ?? "GET").toBe("GET");
  });

  it("assumes no status, so the caller asks for the one it wants", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listResourceNotes(RESOURCE_ID);
    const unfiltered = requestUrl();

    expect(unfiltered).not.toContain("status=");
  });

  it("passes a status filter through when one is asked for", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listResourceNotes(RESOURCE_ID, { status: "active" });

    expect(requestUrl()).toContain("status=active");
  });

  it("reports a resource that is not the learner's as missing", async () => {
    respondWith({ error: { code: "not_found", message: "No such resource.", details: [] } }, 404);

    await expect(listResourceNotes(RESOURCE_ID)).rejects.toBeInstanceOf(ApiError);
  });
});

describe("writeResourceNote", () => {
  it("posts the note to the resource that holds it", async () => {
    respondWith({ data: note }, 201);

    const written = await writeResourceNote(RESOURCE_ID, {
      title: "Deadlock conditions",
      body: "Mutual exclusion, hold and wait.",
    });

    expect(written.id).toBe(NOTE_ID);
    expect(requestUrl()).toContain(`/api/v1/resources/${RESOURCE_ID}/notes`);
    expect(requestInit().method).toBe("POST");
  });

  it("sends the learner's text unchanged, line breaks and all", async () => {
    respondWith({ data: note }, 201);
    const pasted = "Step one:\n\n    indented\n\nStep two.";

    await writeResourceNote(RESOURCE_ID, { title: "Steps", body: pasted });

    expect(JSON.parse(requestInit().body as string)).toEqual({
      title: "Steps",
      body: pasted,
    });
  });

  it("sends no learner identifier and no status", async () => {
    respondWith({ data: note }, 201);

    await writeResourceNote(RESOURCE_ID, { title: "A title", body: "Some text." });
    const sent = JSON.parse(requestInit().body as string);

    expect(sent).not.toHaveProperty("learner_id");
    expect(sent).not.toHaveProperty("status");
  });

  it("reports material that is put aside as a conflict", async () => {
    respondWith(
      { error: { code: "conflict", message: "This material is put aside.", details: [] } },
      409,
    );

    await expect(
      writeResourceNote(RESOURCE_ID, { title: "A title", body: "Some text." }),
    ).rejects.toMatchObject({ isConflict: true });
  });

  it("reports a malformed answer rather than returning one", async () => {
    respondWith({ data: "not a note" }, 201);

    await expect(
      writeResourceNote(RESOURCE_ID, { title: "A title", body: "Some text." }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});

describe("updateResourceNote", () => {
  it("patches the note by its own identifier", async () => {
    respondWith({ data: { ...note, body: "Corrected." } });

    const corrected = await updateResourceNote(NOTE_ID, { body: "Corrected." });

    expect(corrected.body).toBe("Corrected.");
    expect(requestUrl()).toContain(`/api/v1/resource-notes/${NOTE_ID}`);
    expect(requestInit().method).toBe("PATCH");
  });

  it("sends only the fields it was given", async () => {
    respondWith({ data: { ...note, status: "archived" } });

    await updateResourceNote(NOTE_ID, { status: "archived" });

    expect(JSON.parse(requestInit().body as string)).toEqual({ status: "archived" });
  });

  it("reports a note that is not the learner's as missing", async () => {
    respondWith({ error: { code: "not_found", message: "No such note.", details: [] } }, 404);

    await expect(updateResourceNote(NOTE_ID, { body: "Mine now." })).rejects.toMatchObject({
      isNotFound: true,
    });
  });
});
