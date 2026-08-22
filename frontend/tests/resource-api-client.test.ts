import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, listResources, registerResource, updateResource } from "@/lib/api-client";

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

const resource = {
  id: "11111111-1111-4111-8111-111111111111",
  owner_learner_id: "44444444-4444-4444-8444-444444444444",
  resource_type: "note",
  title: "Process scheduling notes",
  source_label: "Blue binder, chapter 3",
  external_reference: null,
  status: "registered",
  topics: [
    {
      id: "22222222-2222-4222-8222-222222222222",
      code: null,
      name: "CPU scheduling",
      subject_id: "33333333-3333-4333-8333-333333333333",
      subject_name: "Operating Systems",
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listResources", () => {
  it("reads the collection envelope", async () => {
    respondWith({ data: [resource], pagination: { limit: 100, offset: 0, total: 1 } });

    const resources = await listResources();

    expect(resources).toHaveLength(1);
    expect(resources[0]?.topics[0]?.name).toBe("CPU scheduling");
  });

  it("asks for the documented path", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listResources();

    expect(requestUrl()).toContain("/api/v1/resources?");
    expect(requestInit().method ?? "GET").toBe("GET");
  });

  it("narrows to one topic when asked", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listResources({ topicId: "22222222-2222-4222-8222-222222222222" });

    expect(requestUrl()).toContain("topic_id=22222222-2222-4222-8222-222222222222");
  });

  it("narrows to one status when asked", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listResources({ status: "archived" });

    expect(requestUrl()).toContain("status=archived");
  });

  it("asks for no status by default, so the caller sees both groups", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listResources();

    expect(requestUrl()).not.toContain("status=");
  });

  it("rejects a body that is not the documented collection", async () => {
    respondWith({ data: resource });

    await expect(listResources()).rejects.toBeInstanceOf(ApiError);
  });

  it("reports an unreachable API rather than resolving to nothing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );

    await expect(listResources()).rejects.toMatchObject({ code: "api_unreachable" });
  });
});

describe("registerResource", () => {
  it("posts what the learner catalogued", async () => {
    respondWith({ data: resource }, 201);

    await registerResource({
      resource_type: "note",
      title: "Process scheduling notes",
      source_label: "Blue binder, chapter 3",
      external_reference: null,
      topic_ids: ["22222222-2222-4222-8222-222222222222"],
    });

    expect(requestUrl()).toContain("/api/v1/resources");
    expect(requestInit().method).toBe("POST");
    expect(JSON.parse(requestInit().body as string)).toEqual({
      resource_type: "note",
      title: "Process scheduling notes",
      source_label: "Blue binder, chapter 3",
      external_reference: null,
      topic_ids: ["22222222-2222-4222-8222-222222222222"],
    });
  });

  it("sends no status: everything is registered, and putting aside is a later step", async () => {
    respondWith({ data: resource }, 201);

    await registerResource({
      resource_type: "note",
      title: "Notes",
      source_label: "Shelf",
      external_reference: null,
      topic_ids: [],
    });

    expect(JSON.parse(requestInit().body as string)).not.toHaveProperty("status");
  });

  it("keeps the API's error code so a caller can branch on the rule", async () => {
    respondWith(
      {
        error: {
          code: "validation_error",
          message: "A link must be a full http:// or https:// web address.",
          details: [
            {
              field: "body.external_reference",
              message: "A link must be a full http:// or https:// web address.",
              type: "unsupported_reference_scheme",
            },
          ],
        },
      },
      422,
    );

    await expect(
      registerResource({
        resource_type: "pdf",
        title: "Local notes",
        source_label: null,
        external_reference: "D:\\GATE\\notes.pdf",
        topic_ids: [],
      }),
    ).rejects.toMatchObject({ code: "validation_error", status: 422 });
  });
});

describe("updateResource", () => {
  it("patches only what it was given", async () => {
    respondWith({ data: { ...resource, status: "archived" } });

    await updateResource(resource.id, { status: "archived" });

    expect(requestUrl()).toContain(`/api/v1/resources/${resource.id}`);
    expect(requestInit().method).toBe("PATCH");
    expect(JSON.parse(requestInit().body as string)).toEqual({ status: "archived" });
  });

  it("replaces the whole topic set when topics are supplied", async () => {
    respondWith({ data: resource });

    await updateResource(resource.id, { topic_ids: [] });

    expect(JSON.parse(requestInit().body as string)).toEqual({ topic_ids: [] });
  });

  it("reports a resource that is not the learner's as not found", async () => {
    respondWith(
      { error: { code: "not_found", message: "No learning resource is stored.", details: [] } },
      404,
    );

    await expect(updateResource(resource.id, { status: "archived" })).rejects.toMatchObject({
      isNotFound: true,
    });
  });
});

describe("deleteResource", () => {
  it("sends DELETE to the documented path", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));

    const { deleteResource } = await import("@/lib/api-client");
    await deleteResource("resource-1");

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/resources/resource-1");
    expect(init.method).toBe("DELETE");
  });

  it("reads no body, because a 204 has none", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));

    const { deleteResource } = await import("@/lib/api-client");
    await expect(deleteResource("resource-1")).resolves.toBeUndefined();
  });

  it("reports material that is already gone", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ error: { code: "not_found", message: "No such material.", details: [] } }),
            { status: 404 },
          ),
      ),
    );

    const { deleteResource } = await import("@/lib/api-client");
    await expect(deleteResource("resource-1")).rejects.toMatchObject({ isNotFound: true });
  });
});
