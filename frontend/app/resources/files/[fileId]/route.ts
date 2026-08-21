import { NextResponse } from "next/server";

import { ApiError, fetchResourceFileContent } from "@/lib/api-client";

/**
 * Download one stored PDF (RES-016), proxied by LearnFlow's own server.
 *
 * **The browser asks this route, never the API.** It calls the backend
 * server-side with `API_BASE_URL`, so no API address is browser-visible and no
 * CORS configuration exists — the guarantee ADR-015 makes, kept for files as it
 * is for every other read.
 *
 * **Authorization is the backend's.** It resolves the effective learner and
 * refuses a file belonging to anyone else with a `404`; this route forwards that
 * verdict rather than deciding it, so there is one place ownership is checked
 * rather than two that could disagree.
 *
 * **The response is an attachment, and the headers are the backend's own.**
 * `Content-Disposition`, `X-Content-Type-Options: nosniff`, and `Cache-Control`
 * are copied from the API rather than re-derived, so the browser saves the PDF
 * instead of rendering it inside LearnFlow's origin. A PDF is an active-content
 * format, and not rendering it in-origin is the mitigation this build offers —
 * **no virus scanning is performed** (ADR-040).
 *
 * A `GET` that writes nothing: no status moves, and no record is kept that a
 * file was downloaded.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ fileId: string }> },
): Promise<Response> {
  const { fileId } = await params;

  let upstream: Response;
  try {
    upstream = await fetchResourceFileContent(fileId);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return NextResponse.json(
      { error: "LearnFlow could not reach its own backend, so that file could not be fetched." },
      { status: 502 },
    );
  }

  if (!upstream.ok) {
    // The backend's refusal is forwarded as a status, not as its body: an error
    // envelope meant for an API caller is not what a browser expecting a file
    // should be handed.
    return NextResponse.json(
      { error: "That file is not available." },
      { status: upstream.status === 404 ? 404 : upstream.status },
    );
  }

  // Streamed onward rather than buffered: the bytes pass through without this
  // process holding a second copy of a file that may be 25 MB.
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/pdf",
      "Content-Disposition":
        upstream.headers.get("content-disposition") ?? "attachment; filename=\"document.pdf\"",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "private, no-store",
    },
  });
}
