/**
 * Typed client for the LearnFlow API.
 *
 * It runs on the Next.js server only. The browser never calls the backend, so
 * the API needs no CORS allow-list and no API address reaches a client bundle.
 *
 * Every response is checked against the envelope in
 * docs/api/conventions.md before it is handed to a view: a `fetch` returns
 * whatever a server sent, and a view that trusts it renders `undefined` instead
 * of reporting a failure. Failures surface as `ApiError`, which carries the
 * documented `code` so a caller can branch on the rule rather than the prose.
 */

import { resolveApiBaseUrl } from "@/lib/config";
import type { ErrorEnvelope } from "@/types/api";
import type {
  CurriculumTree,
  CurriculumTreeResponse,
  LearningProgram,
  LearningProgramCollectionResponse,
  LearningProgramResponse,
} from "@/types/curriculum";

/** Default page size, matching the API's own default. */
export const DEFAULT_PAGE_SIZE = 25;

/** Upper bound the API enforces on `limit`; a larger value is a 422. */
export const MAX_PAGE_SIZE = 100;

/**
 * A failed API call.
 *
 * `status` is null when the request never produced a response at all -- the
 * backend was unreachable -- which a view reports differently from a backend
 * that answered with an error.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number | null;

  constructor(code: string, message: string, status: number | null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }

  /** True when the addressed record does not exist. */
  get isNotFound(): boolean {
    return this.status === 404;
  }

  /** True when the API could not be reached at all. */
  get isUnreachable(): boolean {
    return this.status === null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Read the documented error envelope out of a failed response.
 *
 * A failure that does not carry one -- a proxy error page, say -- still becomes
 * an `ApiError`, because a caller must not have to distinguish those.
 */
function toApiError(status: number, body: unknown): ApiError {
  if (isRecord(body) && isRecord(body.error)) {
    const envelope = body as unknown as ErrorEnvelope;
    const { code, message } = envelope.error;
    if (typeof code === "string" && typeof message === "string") {
      return new ApiError(code, message, status);
    }
  }
  return new ApiError("request_failed", `The API returned status ${status}.`, status);
}

async function requestJson(path: string): Promise<unknown> {
  const url = `${resolveApiBaseUrl()}${path}`;

  let response: Response;
  try {
    // `no-store` keeps the view showing what the API holds now, and keeps the
    // production build from trying to reach the API while prerendering.
    response = await fetch(url, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError(
      "api_unreachable",
      "The LearnFlow API could not be reached. Check that the backend is running.",
      null,
    );
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    throw toApiError(response.status, body);
  }
  return body;
}

/** Reject a success response that does not match the documented envelope. */
function unwrapData(body: unknown): unknown {
  if (!isRecord(body) || !("data" in body)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a response without the expected `data` envelope.",
      null,
    );
  }
  return body.data;
}

/**
 * CUR-001 -- list the learning programs LearnFlow offers.
 *
 * @param limit Maximum programs to return, 1 to {@link MAX_PAGE_SIZE}.
 * @param offset Programs to skip; 0 or greater.
 */
export async function listLearningPrograms({
  limit = DEFAULT_PAGE_SIZE,
  offset = 0,
}: { limit?: number; offset?: number } = {}): Promise<LearningProgramCollectionResponse> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const body = await requestJson(`/api/v1/curriculum/programs?${query.toString()}`);
  const data = unwrapData(body);

  if (!Array.isArray(data) || !isRecord(body) || !isRecord(body.pagination)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a program collection without the expected `data` array and `pagination` block.",
      null,
    );
  }
  return body as unknown as LearningProgramCollectionResponse;
}

/**
 * CUR-002 -- read one learning program and its active curriculum version.
 *
 * @throws ApiError with `isNotFound` when no such program is stored.
 */
export async function readLearningProgram(programId: string): Promise<LearningProgram> {
  const body = await requestJson(
    `/api/v1/curriculum/programs/${encodeURIComponent(programId)}`,
  );
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed program.", null);
  }
  return (body as LearningProgramResponse).data;
}

/**
 * CUR-003 -- read one curriculum version's subjects, topics, and subtopics.
 *
 * @throws ApiError with `isNotFound` when no such version is stored.
 */
export async function readCurriculumTree(
  curriculumVersionId: string,
): Promise<CurriculumTree> {
  const body = await requestJson(
    `/api/v1/curriculum/versions/${encodeURIComponent(curriculumVersionId)}/tree`,
  );
  const data = unwrapData(body);

  if (!isRecord(data) || !Array.isArray((data as Record<string, unknown>).subjects)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a curriculum tree without a `subjects` list.",
      null,
    );
  }
  return (body as CurriculumTreeResponse).data;
}
