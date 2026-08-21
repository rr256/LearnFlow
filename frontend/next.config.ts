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
  experimental: {
    serverActions: {
      /*
       * How large a server-action request body may be.
       *
       * **Next.js defaults this to 1 MB**, which is far below the 25 MB a
       * learner may upload (RES-014). A PDF above the default is rejected by the
       * framework before it reaches any LearnFlow code, so the learner sees an
       * unstyled "This page couldn't load" page instead of a message naming the
       * rule — and the backend never sees the request at all.
       *
       * Set slightly **above** `MAX_FILE_BYTES` on purpose. The backend must be
       * the thing that refuses an oversized file, because it is the only place
       * that can say so in words the learner can act on; this limit exists to
       * let a legal upload through, not to enforce a second, quieter one. The
       * headroom covers multipart framing and the form's other fields.
       */
      bodySizeLimit: "26mb",
    },
  },
};

export default nextConfig;
