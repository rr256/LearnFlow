# LearnFlow frontend image.
#
# Build context is the repository root, matching backend.Dockerfile, so this
# file can copy from frontend/. See docs/deployment/docker.md for the Compose
# topology and configuration rules.
#
#   docker build -f docker/frontend.Dockerfile .
#   docker compose up --build

# --- Dependencies ------------------------------------------------------------
# Installed from the committed lockfile in their own stage, so a source-only
# change reuses this layer.
FROM node:24-alpine AS dependencies
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# --- Build -------------------------------------------------------------------
FROM node:24-alpine AS build
WORKDIR /app
# Next.js collects anonymous build telemetry by default. LearnFlow is
# local-first (NFR-001), so no build of this image reports anything outward.
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencies /app/node_modules ./node_modules
# .dockerignore excludes node_modules/ and frontend/tests/, so this neither
# overwrites the installed dependencies nor carries tests into the build.
COPY frontend/ ./
# Every curriculum route is `force-dynamic`, so the build reaches no API. It
# needs no API_BASE_URL and no running backend.
RUN npm run build

# --- Runtime -----------------------------------------------------------------
# `output: "standalone"` in next.config.ts emits a self-contained server with
# only the traced dependencies, so this stage copies no node_modules tree.
FROM node:24-alpine AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

# The standalone server must listen on all interfaces to accept connections from
# outside the container, for the same reason the backend sets API_HOST=0.0.0.0;
# see docs/deployment/docker.md.
ENV HOSTNAME=0.0.0.0

COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static

# node:alpine ships an unprivileged `node` user. The server renders HTML and
# needs no write access to its own source.
USER node

# Documents the port the application listens on. Publishing is decided by
# compose.yaml, not here.
EXPOSE 3000

CMD ["node", "server.js"]
