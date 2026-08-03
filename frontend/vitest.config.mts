import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Vitest configuration for component and API-client tests.
 *
 * Tests live in `tests/`, mirroring the layout in
 * docs/development/folder-structure.md. They exercise the frontend boundary --
 * response parsing, error mapping, and rendered markup -- and never reach a
 * live backend.
 */
export default defineConfig({
  plugins: [react()],
  // Mirrors the `@/*` path mapping in tsconfig.json, which Vitest does not read.
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    globals: false,
    restoreMocks: true,
  },
});
