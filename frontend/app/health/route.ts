/**
 * The frontend's own readiness probe.
 *
 * It reports that this Next.js server process is up and serving. It deliberately
 * reaches **nothing** — not the API, not the database, not any other service —
 * and is statically rendered, so a probe every few seconds costs one prerendered
 * response rather than a round trip.
 *
 * That is why it exists rather than probing a page. The home screen would answer
 * the same question, but only by calling the API up to three times to render
 * markup no probe reads. A liveness check should not generate backend traffic.
 *
 * The flat `{"status": "ok"}` body mirrors the backend's operational endpoint
 * (docs/api/conventions.md#operational-endpoints-are-unversioned), so probe
 * tooling reads the same field from either service. This is the frontend
 * process's own endpoint, not part of the LearnFlow HTTP API, and it exposes no
 * learner data and no configuration.
 */

/** Prerendered at build time, so serving a probe fetches and computes nothing. */
export const dynamic = "force-static";

export function GET(): Response {
  return Response.json({ status: "ok" });
}
