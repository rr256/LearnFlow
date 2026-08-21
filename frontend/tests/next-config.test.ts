import { describe, expect, it } from "vitest";

import nextConfig from "../next.config";
import { MAX_FILE_BYTES } from "@/types/resource-file";

/**
 * The framework limit that sits in front of the upload.
 *
 * This exists because of a real defect: Next.js caps a server-action request
 * body at **1 MB** by default, far below the 25 MB a learner may upload. Any
 * larger PDF was rejected by the framework before reaching LearnFlow at all, so
 * the learner saw an unstyled error page and the backend never saw the request.
 *
 * Every test and every fixture used a PDF of a few kilobytes, which is precisely
 * the size at which the default never bites — so nothing caught it until a real
 * file was chosen. These assertions are the guard that would have.
 */
function limitInBytes(limit: string | number | undefined): number {
  if (typeof limit === "number") {
    return limit;
  }
  const match = /^(\d+(?:\.\d+)?)\s*(b|kb|mb|gb)$/i.exec(String(limit ?? ""));
  const amount = match?.[1];
  const unit = match?.[2]?.toLowerCase();
  if (amount === undefined || unit === undefined) {
    return Number.NaN;
  }
  const units: Record<string, number> = {
    b: 1,
    kb: 1024,
    mb: 1024 * 1024,
    gb: 1024 * 1024 * 1024,
  };
  return Number(amount) * (units[unit] ?? Number.NaN);
}

describe("the server-action body limit", () => {
  it("is configured at all", () => {
    // Without this, the default 1 MB applies and uploads silently break.
    expect(nextConfig.experimental?.serverActions?.bodySizeLimit).toBeDefined();
  });

  it("admits a file at the backend's own maximum", () => {
    const limit = limitInBytes(nextConfig.experimental?.serverActions?.bodySizeLimit);

    expect(Number.isNaN(limit)).toBe(false);
    expect(limit).toBeGreaterThanOrEqual(MAX_FILE_BYTES);
  });

  it("leaves headroom above it, so the backend is what refuses an oversized file", () => {
    // The backend is the only place that can refuse in words a learner can act
    // on. If this limit were the tighter of the two, the framework would reject
    // first and the learner would get an unstyled page instead of a message.
    const limit = limitInBytes(nextConfig.experimental?.serverActions?.bodySizeLimit);

    expect(limit).toBeGreaterThan(MAX_FILE_BYTES);
  });

  it("keeps the standalone output the container image depends on", () => {
    expect(nextConfig.output).toBe("standalone");
  });
});
