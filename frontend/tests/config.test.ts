import { describe, expect, it } from "vitest";

import { FrontendConfigurationError, resolveApiBaseUrl } from "@/lib/config";

describe("resolveApiBaseUrl", () => {
  it("falls back to the backend's published loopback address when unset", () => {
    expect(resolveApiBaseUrl({})).toBe("http://127.0.0.1:8000");
  });

  it("falls back when the value is present but blank", () => {
    expect(resolveApiBaseUrl({ API_BASE_URL: "   " })).toBe("http://127.0.0.1:8000");
  });

  it("uses a configured absolute url", () => {
    expect(resolveApiBaseUrl({ API_BASE_URL: "http://backend:8000" })).toBe("http://backend:8000");
  });

  it("removes a trailing slash so request paths do not double up", () => {
    expect(resolveApiBaseUrl({ API_BASE_URL: "http://backend:8000/" })).toBe("http://backend:8000");
  });

  it("rejects a value that is not an absolute url", () => {
    expect(() => resolveApiBaseUrl({ API_BASE_URL: "backend:8000" })).toThrow(
      FrontendConfigurationError,
    );
  });

  it("rejects a scheme the client cannot call", () => {
    expect(() => resolveApiBaseUrl({ API_BASE_URL: "ftp://backend:8000" })).toThrow(
      FrontendConfigurationError,
    );
  });
});
