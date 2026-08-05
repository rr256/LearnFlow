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
import type { ApiErrorDetail, ErrorEnvelope } from "@/types/api";
import type {
  CurriculumTree,
  CurriculumTreeResponse,
  LearningProgram,
  LearningProgramCollectionResponse,
  LearningProgramResponse,
} from "@/types/curriculum";
import type {
  LearnerProfile,
  LearnerProfileResponse,
  LearnerProfileUpdate,
} from "@/types/learner";
import type {
  ExaminationSchedule,
  ExaminationScheduleCollectionResponse,
  NewStudyGoal,
  StudyGoal,
  StudyGoalCollectionResponse,
  StudyGoalResponse,
  StudyGoalUpdate,
} from "@/types/study-goal";

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
  /** Field-level reasons a write was rejected; empty for everything else. */
  readonly details: ApiErrorDetail[];

  constructor(
    code: string,
    message: string,
    status: number | null,
    details: ApiErrorDetail[] = [],
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }

  /** True when the addressed record does not exist. */
  get isNotFound(): boolean {
    return this.status === 404;
  }

  /** True when the API could not be reached at all. */
  get isUnreachable(): boolean {
    return this.status === null;
  }

  /**
   * True when the request conflicts with what is already stored.
   *
   * The setup screen shows this differently from a rejected field: an active
   * goal already exists, or more than one learner is stored.
   */
  get isConflict(): boolean {
    return this.status === 409;
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
    const { code, message, details } = envelope.error;
    if (typeof code === "string" && typeof message === "string") {
      return new ApiError(code, message, status, Array.isArray(details) ? details : []);
    }
  }
  return new ApiError("request_failed", `The API returned status ${status}.`, status);
}

/** A request body sent to the API, and the method that carries it. */
interface WriteRequest {
  method: "POST" | "PATCH";
  body: unknown;
}

async function requestJson(path: string, write?: WriteRequest): Promise<unknown> {
  const url = `${resolveApiBaseUrl()}${path}`;

  let response: Response;
  try {
    // `no-store` keeps the view showing what the API holds now, and keeps the
    // production build from trying to reach the API while prerendering.
    response = await fetch(url, {
      method: write?.method ?? "GET",
      cache: "no-store",
      headers: write
        ? { Accept: "application/json", "Content-Type": "application/json" }
        : { Accept: "application/json" },
      body: write ? JSON.stringify(write.body) : undefined,
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
  unwrapCollection(body, "a program collection");

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

/** Reject a success collection that does not match the documented envelope. */
function unwrapCollection(body: unknown, what: string): void {
  const data = unwrapData(body);
  if (!Array.isArray(data) || !isRecord(body) || !isRecord(body.pagination)) {
    throw new ApiError(
      "malformed_response",
      `The API returned ${what} without the expected \`data\` array and \`pagination\` block.`,
      null,
    );
  }
}

/**
 * LRN-001 -- read the local learner's profile.
 *
 * Resolves to `null` before setup has created a learner. That is a documented
 * state of the endpoint, not a failure, so it is not an `ApiError`.
 */
export async function readLearnerProfile(): Promise<LearnerProfile | null> {
  const body = await requestJson("/api/v1/learner/profile");
  const data = unwrapData(body);

  if (data !== null && !isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed profile.", null);
  }
  return (body as LearnerProfileResponse).data;
}

/**
 * LRN-002 -- update the local learner's profile, creating it on first use.
 *
 * A field left out of `changes` is not modified; `display_name: null` removes
 * the stored name.
 */
export async function updateLearnerProfile(
  changes: LearnerProfileUpdate,
): Promise<LearnerProfile> {
  const body = await requestJson("/api/v1/learner/profile", {
    method: "PATCH",
    body: changes,
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed profile.", null);
  }
  return data as unknown as LearnerProfile;
}

/**
 * EXM-001 -- list the published examination schedules a learner can aim at.
 *
 * @param learningProgramId Restrict to one program's schedules.
 */
export async function listExaminationSchedules({
  learningProgramId,
  limit = DEFAULT_PAGE_SIZE,
  offset = 0,
}: {
  learningProgramId?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<ExaminationSchedule[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (learningProgramId) {
    query.set("learning_program_id", learningProgramId);
  }
  const body = await requestJson(`/api/v1/examination-schedules?${query.toString()}`);
  unwrapCollection(body, "an examination schedule collection");

  return (body as ExaminationScheduleCollectionResponse).data;
}

/** GOAL-001 -- create a study goal for the local learner. */
export async function createStudyGoal(goal: NewStudyGoal): Promise<StudyGoal> {
  const body = await requestJson("/api/v1/study-goals", { method: "POST", body: goal });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed study goal.", null);
  }
  return (body as StudyGoalResponse).data;
}

/**
 * GOAL-002 -- list the local learner's study goals.
 *
 * Returns an empty list before setup has created a learner.
 */
export async function listStudyGoals({
  limit = DEFAULT_PAGE_SIZE,
  offset = 0,
}: { limit?: number; offset?: number } = {}): Promise<StudyGoal[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const body = await requestJson(`/api/v1/study-goals?${query.toString()}`);
  unwrapCollection(body, "a study goal collection");

  return (body as StudyGoalCollectionResponse).data;
}

/** GOAL-004 -- change a study goal's examination cycle, target date, or status. */
export async function updateStudyGoal(
  studyGoalId: string,
  changes: StudyGoalUpdate,
): Promise<StudyGoal> {
  const body = await requestJson(
    `/api/v1/study-goals/${encodeURIComponent(studyGoalId)}`,
    { method: "PATCH", body: changes },
  );
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed study goal.", null);
  }
  return (body as StudyGoalResponse).data;
}
