import { describe, expect, it, vi } from "vitest";

import { GET, dynamic } from "@/app/health/route";

describe("frontend health route", () => {
  it("reports the frontend process as ready", async () => {
    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
  });

  it("answers in the flat shape probe tooling reads, with no `data` envelope", async () => {
    // It mirrors the backend's operational endpoint rather than the /api/v1
    // envelope, so a probe reads `status` from either service the same way.
    const body: unknown = await (await GET()).json();

    expect(body).not.toHaveProperty("data");
  });

  it("generates no backend traffic, so probing it every interval costs nothing", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await GET();

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("is statically rendered, so a probe costs no work per request", () => {
    expect(dynamic).toBe("force-static");
  });
});
