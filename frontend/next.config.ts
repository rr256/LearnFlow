import type { NextConfig } from "next";

/**
 * Next.js build and runtime configuration.
 *
 * `standalone` output is what makes the runtime image in
 * `docker/frontend.Dockerfile` small: the build emits a self-contained server
 * plus only the traced dependencies, so the image copies no `node_modules`
 * tree. See docs/deployment/docker.md.
 */
const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
