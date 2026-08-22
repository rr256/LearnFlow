import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  deleteResourceFile,
  fetchResourceFileContent,
  listResourceFiles,
  updateResourceFile,
  uploadResourceFile,
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

const RESOURCE = "11111111-1111-4111-8111-111111111111";
const FILE = "22222222-2222-4222-8222-222222222222";

const stored = {
  id: FILE,
  resource_id: RESOURCE,
  original_filename: "Chapter 3.pdf",
  byte_size: 90210,
  page_count: 12,
  content_type: "application/pdf",
  checksum: "a".repeat(64),
  status: "active",
  created_at: null,
  updated_at: null,
};

function pdf(name = "Chapter 3.pdf"): File {
  return new File([new Uint8Array(64)], name, { type: "application/pdf" });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("uploadResourceFile", () => {
  it("posts the file as multipart to the documented path", async () => {
    respondWith({ data: stored });

    await uploadResourceFile(RESOURCE, pdf());

    expect(requestUrl()).toContain(`/api/v1/resources/${RESOURCE}/files`);
    expect(requestInit()?.method).toBe("POST");
    expect(requestInit()?.body).toBeInstanceOf(FormData);
    expect((requestInit()?.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("sets no Content-Type, so fetch writes the multipart boundary itself", async () => {
    // Setting one by hand omits the boundary and the backend cannot parse it.
    respondWith({ data: stored });

    await uploadResourceFile(RESOURCE, pdf());

    const headers = requestInit()?.headers as Record<string, string>;
    expect(Object.keys(headers ?? {}).map((k) => k.toLowerCase())).not.toContain("content-type");
  });

  it("reads the stored file back out of the data envelope", async () => {
    respondWith({ data: stored });

    const result = await uploadResourceFile(RESOURCE, pdf());

    expect(result.original_filename).toBe("Chapter 3.pdf");
    expect(result.page_count).toBe(12);
  });

  it("reports a file the backend refused", async () => {
    respondWith(
      {
        error: {
          code: "validation_error",
          message: "Only PDF files can be stored here.",
          details: [],
        },
      },
      422,
    );

    await expect(uploadResourceFile(RESOURCE, pdf())).rejects.toBeInstanceOf(ApiError);
  });

  it("reports an over-large file as a conflict-free validation failure", async () => {
    respondWith(
      { error: { code: "validation_error", message: "A file may be at most 25 MB.", details: [] } },
      413,
    );

    await expect(uploadResourceFile(RESOURCE, pdf())).rejects.toMatchObject({ status: 413 });
  });

  it("reports an archived resource as a conflict", async () => {
    respondWith(
      { error: { code: "conflict", message: "This material is archived.", details: [] } },
      409,
    );

    await expect(uploadResourceFile(RESOURCE, pdf())).rejects.toMatchObject({ isConflict: true });
  });

  it("reports an unreachable backend rather than hanging", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("network");
      }),
    );

    await expect(uploadResourceFile(RESOURCE, pdf())).rejects.toMatchObject({
      isUnreachable: true,
    });
  });
});

describe("listResourceFiles", () => {
  it("reads the collection", async () => {
    respondWith({ data: [stored] });

    const files = await listResourceFiles(RESOURCE);

    expect(files).toHaveLength(1);
    expect(requestUrl()).toContain(`/api/v1/resources/${RESOURCE}/files`);
  });

  it("asks for every status by default", async () => {
    respondWith({ data: [stored] });

    await listResourceFiles(RESOURCE);

    expect(requestUrl()).not.toContain("status=");
  });

  it("narrows by status when asked", async () => {
    respondWith({ data: [stored] });

    await listResourceFiles(RESOURCE, { statuses: ["active"] });

    expect(requestUrl()).toContain("status=active");
  });

  it("reports a malformed collection rather than returning one", async () => {
    respondWith({ data: "not a list" });

    await expect(listResourceFiles(RESOURCE)).rejects.toBeInstanceOf(ApiError);
  });
});

describe("updateResourceFile", () => {
  it("patches the documented path with the status alone", async () => {
    respondWith({ data: { ...stored, status: "archived" } });

    await updateResourceFile(FILE, "archived");

    expect(requestUrl()).toContain(`/api/v1/resource-files/${FILE}`);
    expect(requestInit()?.method).toBe("PATCH");
    expect(JSON.parse(requestInit()?.body as string)).toEqual({ status: "archived" });
  });

  it("reports an archived resource as a conflict", async () => {
    respondWith(
      { error: { code: "conflict", message: "This material is archived.", details: [] } },
      409,
    );

    await expect(updateResourceFile(FILE, "archived")).rejects.toMatchObject({
      isConflict: true,
    });
  });
});

describe("fetchResourceFileContent", () => {
  it("asks the documented content path and returns the response unparsed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(new Uint8Array([1, 2, 3]), { status: 200 })),
    );

    const response = await fetchResourceFileContent(FILE);

    expect(requestUrl()).toContain(`/api/v1/resource-files/${FILE}/content`);
    expect(response.status).toBe(200);
  });

  it("reports an unreachable backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("network");
      }),
    );

    await expect(fetchResourceFileContent(FILE)).rejects.toMatchObject({ isUnreachable: true });
  });
});

describe("deleteResourceFile", () => {
  it("sends DELETE to the documented path", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));

    await deleteResourceFile(FILE);

    expect(requestUrl()).toContain(`/api/v1/resource-files/${FILE}`);
    expect(requestInit()?.method).toBe("DELETE");
  });

  it("reads no body, because a 204 has none", async () => {
    // `requestJson` cannot be reused here: it parses a body.
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));

    await expect(deleteResourceFile(FILE)).resolves.toBeUndefined();
  });

  it("reports a file that is already gone", async () => {
    respondWith({ error: { code: "not_found", message: "No such file.", details: [] } }, 404);

    await expect(deleteResourceFile(FILE)).rejects.toMatchObject({ isNotFound: true });
  });

  it("reports archived material as a conflict", async () => {
    respondWith(
      { error: { code: "conflict", message: "This material is archived.", details: [] } },
      409,
    );

    await expect(deleteResourceFile(FILE)).rejects.toMatchObject({ isConflict: true });
  });
});

describe("the only removals in the client are these two", () => {
  it("nothing else deletes anything", async () => {
    // RES-005 -- removing a whole resource -- stays unimplemented, and no bulk
    // removal exists.
    const client = await import("@/lib/api-client");

    expect(Object.keys(client).filter((name) => /delete|remove/i.test(name)).sort()).toEqual([
      "deleteResourceFile",
      "deleteResourceNote",
    ]);
  });
});
