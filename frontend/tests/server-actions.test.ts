import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * A `"use server"` module may export only async functions.
 *
 * Exporting anything else -- a constant, an object, a synchronous helper --
 * throws `A "use server" file can only export async functions` on the first
 * request that reaches the module. Neither `tsc --noEmit` nor `next build`
 * reports it, and a component test that mocks the module does not either: the
 * failure was found by running the built server. This test is what keeps it
 * found.
 */

const ROOTS = ["app", "features", "lib"];

function sourceFiles(directory: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) {
      found.push(...sourceFiles(path));
    } else if (path.endsWith(".ts") || path.endsWith(".tsx")) {
      found.push(path);
    }
  }
  return found;
}

function serverActionModules(): { path: string; source: string }[] {
  return ROOTS.flatMap((root) => sourceFiles(root))
    .map((path) => ({ path, source: readFileSync(path, "utf8") }))
    .filter(({ source }) => /^\s*["']use server["'];/m.test(source));
}

/** Every `export` in the module that is not an `async function` or a type. */
function nonAsyncExports(source: string): string[] {
  const offenders: string[] = [];
  for (const [line] of source.matchAll(/^export\s+(?!type\b|interface\b)[^\n]*/gm)) {
    if (!/^export\s+async\s+function\s/.test(line)) {
      offenders.push(line.trim());
    }
  }
  return offenders;
}

describe('"use server" modules', () => {
  it("are present, so this rule is actually being checked", () => {
    expect(serverActionModules().length).toBeGreaterThan(0);
  });

  it.each(serverActionModules())("$path exports only async functions", ({ source }) => {
    expect(nonAsyncExports(source)).toEqual([]);
  });
});
