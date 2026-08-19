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
import type {
  CheckpointQuiz,
  CheckpointQuizResponse,
  NewPracticeQuestion,
  PracticeQuestion,
  PracticeQuestionCollectionResponse,
  PracticeQuestionResponse,
  QuestionStatus,
  QuizAttempt,
  QuizAttemptCollectionResponse,
  QuizAttemptResponse,
  SubmittedAnswer,
} from "@/types/practice";
import type {
  LearningResource,
  LearningResourceCollectionResponse,
  LearningResourceResponse,
  LearningResourceUpdate,
  NewLearningResource,
} from "@/types/resource";
import type {
  NewResourceNote,
  ResourceNote,
  ResourceNoteCollectionResponse,
  ResourceNoteResponse,
  ResourceNoteUpdate,
} from "@/types/resource-note";
import type {
  Revision,
  RevisionCollectionResponse,
  RevisionResponse,
  RevisionStatusChange,
  ScheduledRevisions,
  ScheduleRevisionsResponse,
} from "@/types/revision";
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
  TopicProgress,
  TopicProgressCollectionResponse,
  TopicProgressResponse,
} from "@/types/progress";
import type {
  AdaptStudyPlanResponse,
  AdaptedStudyPlans,
  GenerateStudyPlanResponse,
  GeneratedStudyPlans,
  PlanFeasibility,
  PlanFeasibilityResponse,
  PlanItem,
  PlanItemResponse,
  PlanItemStatusChange,
  StudyPlan,
  StudyPlanCollectionResponse,
  StudyPlanResponse,
} from "@/types/study-plan";
import type {
  AvailabilitySlot,
  ExaminationSchedule,
  ExaminationScheduleCollectionResponse,
  NewStudyGoal,
  StudyGoal,
  StudyGoalCollectionResponse,
  StudyGoalResponse,
  StudyGoalUpdate,
  WeeklyAvailability,
  WeeklyAvailabilityResponse,
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
  method: "POST" | "PATCH" | "PUT";
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

/**
 * PRG-002 -- list the stages the local learner has recorded.
 *
 * Only topics with a stored record are returned. A topic that is absent has no
 * recorded stage, which reads as *Not explored*; the curriculum endpoints are
 * where every topic is listed.
 *
 * Returns an empty list before setup has created a learner.
 *
 * @param curriculumVersionId Restrict to topics of one curriculum version.
 */
export async function listTopicProgress({
  curriculumVersionId,
  limit = MAX_PAGE_SIZE,
  offset = 0,
}: {
  curriculumVersionId?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<TopicProgress[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (curriculumVersionId) {
    query.set("curriculum_version_id", curriculumVersionId);
  }
  const body = await requestJson(`/api/v1/progress/topics?${query.toString()}`);
  unwrapCollection(body, "a topic progress collection");

  return (body as TopicProgressCollectionResponse).data;
}

/**
 * PRG-004 -- record the local learner's stage for one topic.
 *
 * Creates the record on first use and rewrites it afterwards. There is no way
 * to clear one: a learner who has changed their mind records `not_explored`.
 *
 * @throws ApiError with `isNotFound` when no such topic is stored, or a
 *   `validation_error` when the topic only groups subtopics.
 */
export async function recordTopicStage(
  topicId: string,
  learningStage: string,
): Promise<TopicProgress> {
  const body = await requestJson(`/api/v1/progress/topics/${encodeURIComponent(topicId)}`, {
    method: "PATCH",
    body: { learning_stage: learningStage },
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a malformed topic progress record.",
      null,
    );
  }
  return (body as TopicProgressResponse).data;
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

/**
 * GOAL-005 -- replace the weekly availability saved against one study goal.
 *
 * A replacement, not a merge: the days in `slots` become the learner's week, and
 * any day left out is removed. An empty list clears the goal's availability.
 *
 * A day is named -- `monday`, not `0` -- so no numbering convention has to be
 * agreed between this client and the API.
 *
 * @throws ApiError with `isNotFound` when the goal is not stored or is not the
 *   local learner's, or a `validation_error` when a day is unknown, named twice,
 *   or claims minutes a day does not hold.
 */
export async function replaceAvailability(
  studyGoalId: string,
  slots: AvailabilitySlot[],
): Promise<WeeklyAvailability> {
  const body = await requestJson(
    `/api/v1/study-goals/${encodeURIComponent(studyGoalId)}/availability`,
    { method: "PUT", body: { slots } },
  );
  const data = unwrapData(body);

  if (!isRecord(data) || !Array.isArray((data as Record<string, unknown>).slots)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a week of availability without a `slots` list.",
      null,
    );
  }
  return (body as WeeklyAvailabilityResponse).data;
}


/**
 * PLN-001 -- generate a study plan for one of the learner's goals.
 *
 * Only the goal is named. Everything the plan is built from -- the curriculum,
 * the horizon, the saved week, the planning preferences, and the recorded stages
 * -- comes from what the learner has already stored, so nothing this client sends
 * can invent a preference on their behalf.
 *
 * Generating again supersedes the goal's existing active plans rather than
 * refusing or duplicating, so calling this twice is safe.
 *
 * @throws ApiError with `isNotFound` when the goal is not stored or is not the
 *   local learner's, or `isConflict` when setup has not created a learner yet.
 */
export async function generateStudyPlan(studyGoalId: string): Promise<GeneratedStudyPlans> {
  const body = await requestJson("/api/v1/study-plans/generate", {
    method: "POST",
    body: { study_goal_id: studyGoalId },
  });
  const data = unwrapData(body);

  if (!isRecord(data) || !Array.isArray((data as Record<string, unknown>).plans)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a generated plan without a `plans` list.",
      null,
    );
  }
  return (body as GenerateStudyPlanResponse).data;
}

/**
 * PLN-002 -- list the local learner's study plans, newest first.
 *
 * Items are not included: `item_count` says how large each plan is, and
 * {@link readStudyPlan} returns the items of the one being shown.
 *
 * Returns an empty list before setup has created a learner.
 *
 * @param studyGoalId Restrict to plans belonging to one goal.
 * @param status Restrict to one plan status, such as `active`.
 */
export async function listStudyPlans({
  studyGoalId,
  status,
  limit = DEFAULT_PAGE_SIZE,
  offset = 0,
}: {
  studyGoalId?: string;
  status?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<StudyPlan[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (studyGoalId) {
    query.set("study_goal_id", studyGoalId);
  }
  if (status) {
    query.set("status", status);
  }
  const body = await requestJson(`/api/v1/study-plans?${query.toString()}`);
  unwrapCollection(body, "a study plan collection");

  return (body as StudyPlanCollectionResponse).data;
}

/**
 * PLN-003 -- read one study plan with its items, in plan order.
 *
 * A superseded plan reads back exactly as it was written, which is the point of
 * superseding rather than deleting.
 *
 * @throws ApiError with `isNotFound` when no such plan is stored or it is not
 *   the local learner's.
 */
export async function readStudyPlan(studyPlanId: string): Promise<StudyPlan> {
  const body = await requestJson(`/api/v1/study-plans/${encodeURIComponent(studyPlanId)}`);
  const data = unwrapData(body);

  if (!isRecord(data) || !Array.isArray((data as Record<string, unknown>).items)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a study plan without an `items` list.",
      null,
    );
  }
  return (body as StudyPlanResponse).data;
}

/**
 * PLN-005 -- adapt the goal's active plans around what has happened.
 *
 * Topics with a completed session are not planned again; items whose day passed
 * with the work undone are marked `postponed` on the plan being set aside, and
 * their topics are re-placed on the new one. The learner asks for this; nothing
 * adapts on its own.
 *
 * Takes no request body: everything adaptation reads is already stored.
 *
 * @throws ApiError with `isNotFound` when the goal is not the local learner's,
 *   or `isConflict` when it has no active plan to adapt.
 */
export async function adaptStudyPlan(studyGoalId: string): Promise<AdaptedStudyPlans> {
  const body = await requestJson(
    `/api/v1/study-goals/${encodeURIComponent(studyGoalId)}/adapt`,
    { method: "POST", body: {} },
  );
  const data = unwrapData(body);

  if (!isRecord(data) || !Array.isArray((data as Record<string, unknown>).plans)) {
    throw new ApiError(
      "malformed_response",
      "The API returned an adapted plan without a `plans` list.",
      null,
    );
  }
  return (body as AdaptStudyPlanResponse).data;
}

/**
 * PLN-004 -- say what became of one plan item, or put it back.
 *
 * `completed`, `skipped`, and `postponed`, and the `planned` that takes any of
 * them back; a learner may move between any two of the four. Sending the status
 * an item already holds is accepted and changes nothing, so a repeated
 * submission does not fail.
 *
 * Nothing else moves: no other item changes and no plan is re-planned. Marking
 * work done is a statement that it happened, not a claim about the topic, and
 * postponing it names no date -- the work is placed again by the learner's next
 * adaptation.
 *
 * @throws ApiError with `isNotFound` when no such item is stored or it is not
 *   the local learner's, or `isConflict` when its plan has been superseded.
 */
export async function updatePlanItemStatus(
  planItemId: string,
  status: PlanItemStatusChange,
): Promise<PlanItem> {
  const body = await requestJson(`/api/v1/plan-items/${encodeURIComponent(planItemId)}`, {
    method: "PATCH",
    body: { status },
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed plan item.", null);
  }
  return (body as PlanItemResponse).data;
}

/**
 * PLN-006 -- whether the learner's saved week reaches their goal's horizon.
 *
 * A reading: it writes nothing, plans nothing, and adapts nothing, so a screen
 * may ask for it on every render. That is what keeps the answer current as the
 * learner edits their week, where a sentence frozen into a plan's
 * `generation_reason` would go stale the moment they changed it.
 *
 * A verdict of `unknown` is an answer rather than a failure, with
 * `unknown_reason` saying which gap caused it.
 *
 * @throws ApiError with `isNotFound` when no such goal is stored or it is not
 *   the local learner's, or `isConflict` when no learner exists yet.
 */
export async function readPlanFeasibility(studyGoalId: string): Promise<PlanFeasibility> {
  const body = await requestJson(
    `/api/v1/study-goals/${encodeURIComponent(studyGoalId)}/plan-feasibility`,
  );
  const data = unwrapData(body);

  if (!isRecord(data) || typeof (data as Record<string, unknown>).verdict !== "string") {
    throw new ApiError(
      "malformed_response",
      "The API returned a feasibility reading without a verdict.",
      null,
    );
  }
  return (body as PlanFeasibilityResponse).data;
}

/**
 * REV-001 -- list the local learner's revisions, earliest due date first.
 *
 * That order is the order a learner works through them and is fixed by the
 * backend, so this never re-sorts what it receives.
 *
 * Returns an empty list before setup has created a learner.
 *
 * @param dueOnly Only revisions nobody has settled yet.
 */
export async function listRevisions({
  dueOnly = false,
  limit = MAX_PAGE_SIZE,
  offset = 0,
}: { dueOnly?: boolean; limit?: number; offset?: number } = {}): Promise<Revision[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (dueOnly) {
    query.set("due_only", "true");
  }
  const body = await requestJson(`/api/v1/revisions?${query.toString()}`);
  unwrapCollection(body, "a revision collection");

  return (body as RevisionCollectionResponse).data;
}

/**
 * REV-003 -- record what became of one revision.
 *
 * Every move between `due`, `completed`, `skipped`, and `postponed` is allowed,
 * from whichever the revision currently holds. Only the named revision moves:
 * no other revision, no plan item, and no learning stage.
 *
 * @throws ApiError with `isNotFound` when no such revision is stored or it is
 *   not the local learner's.
 */
export async function updateRevisionStatus(
  revisionId: string,
  status: RevisionStatusChange,
): Promise<Revision> {
  const body = await requestJson(`/api/v1/revisions/${encodeURIComponent(revisionId)}`, {
    method: "PATCH",
    body: { status },
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed revision.", null);
  }
  return (body as RevisionResponse).data;
}

/**
 * RES-002 -- list the learner's study material, newest first.
 *
 * No status is assumed by the API, so a caller wanting only what is in the
 * catalogue asks for `registered` and one wanting what has been put aside asks
 * for `archived`.
 *
 * Returns an empty list before setup has created a learner.
 *
 * @param topicId Only material linked to this topic, which is how a screen finds
 *   what covers a topic without holding the whole collection.
 * @param status Only material in this state.
 */
export async function listResources({
  topicId,
  status,
  limit = MAX_PAGE_SIZE,
  offset = 0,
}: {
  topicId?: string;
  status?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<LearningResource[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (topicId) {
    query.set("topic_id", topicId);
  }
  if (status) {
    query.set("status", status);
  }
  const body = await requestJson(`/api/v1/resources?${query.toString()}`);
  unwrapCollection(body, "a learning resource collection");

  return (body as LearningResourceCollectionResponse).data;
}

/**
 * RES-001 -- record where one piece of study material is, and what it covers.
 *
 * A resource is a record of where material is, never the material: nothing is
 * uploaded here, and a link must be an http or https address, so no location on
 * the learner's own machine is ever sent.
 *
 * @throws ApiError with a `validation_error` when the material names no
 *   location, names a topic that is not stored, or carries a link the API will
 *   not store, or `isConflict` when setup has not created a learner yet.
 */
export async function registerResource(
  resource: NewLearningResource,
): Promise<LearningResource> {
  const body = await requestJson("/api/v1/resources", { method: "POST", body: resource });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a malformed learning resource.",
      null,
    );
  }
  return (body as LearningResourceResponse).data;
}

/**
 * RES-004 -- correct what a resource says, or put it aside.
 *
 * A field left out of `changes` is not modified; a supplied `topic_ids`
 * replaces the whole link set. Archiving is reversible and destroys nothing —
 * there is no delete.
 *
 * @throws ApiError with `isNotFound` when no such resource is stored or it is
 *   not the local learner's.
 */
export async function updateResource(
  resourceId: string,
  changes: LearningResourceUpdate,
): Promise<LearningResource> {
  const body = await requestJson(`/api/v1/resources/${encodeURIComponent(resourceId)}`, {
    method: "PATCH",
    body: changes,
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a malformed learning resource.",
      null,
    );
  }
  return (body as LearningResourceResponse).data;
}

/**
 * RES-010 -- list the notes kept against one piece of study material.
 *
 * Newest first. No status is assumed by the API, so a caller wanting only what
 * the learner is using asks for `active` and one wanting what has been put aside
 * asks for `archived`.
 *
 * The notes of archived material are still readable: putting material aside
 * stops it being written to and destroys nothing.
 *
 * @throws ApiError with `isNotFound` when no such resource is stored or it is
 *   not the local learner's.
 */
export async function listResourceNotes(
  resourceId: string,
  { status, limit = MAX_PAGE_SIZE, offset = 0 }: {
    status?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<ResourceNote[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (status) {
    query.set("status", status);
  }
  const body = await requestJson(
    `/api/v1/resources/${encodeURIComponent(resourceId)}/notes?${query.toString()}`,
  );
  unwrapCollection(body, "a resource note collection");

  return (body as ResourceNoteCollectionResponse).data;
}

/**
 * RES-009 -- keep one note against a piece of study material.
 *
 * The text is stored and nothing else is done with it: it is not uploaded,
 * fetched, extracted, indexed, searched, or sent to any provider. It comes back
 * exactly as it was written.
 *
 * @throws ApiError with a `validation_error` when the note has no text, no
 *   title, or more text than one note may hold, `isNotFound` when the material
 *   is not the local learner's, or `isConflict` when the material is put aside.
 */
export async function writeResourceNote(
  resourceId: string,
  note: NewResourceNote,
): Promise<ResourceNote> {
  const body = await requestJson(
    `/api/v1/resources/${encodeURIComponent(resourceId)}/notes`,
    { method: "POST", body: note },
  );
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed note.", null);
  }
  return (body as ResourceNoteResponse).data;
}

/**
 * RES-012 -- correct a note, or put it aside.
 *
 * A field left out of `changes` is not modified. A note may be corrected in
 * place as often as the learner likes; putting one aside is reversible and
 * destroys nothing -- there is no delete.
 *
 * @throws ApiError with `isNotFound` when no such note is stored or it is not
 *   the local learner's, or `isConflict` when its material is put aside.
 */
export async function updateResourceNote(
  noteId: string,
  changes: ResourceNoteUpdate,
): Promise<ResourceNote> {
  const body = await requestJson(`/api/v1/resource-notes/${encodeURIComponent(noteId)}`, {
    method: "PATCH",
    body: changes,
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed note.", null);
  }
  return (body as ResourceNoteResponse).data;
}

/**
 * REV-004 -- schedule revisions for topics whose finished work is ready to return.
 *
 * The learner asks; nothing schedules on its own. Asking twice creates nothing
 * the second time, so a repeated form submission cannot duplicate a review.
 *
 * Takes no request body: everything it reads is already stored.
 *
 * @throws ApiError with `isConflict` when no learner exists yet.
 */
export async function scheduleRevisions(): Promise<ScheduledRevisions> {
  const body = await requestJson("/api/v1/revisions/schedule", { method: "POST", body: {} });
  const data = unwrapData(body);

  if (!isRecord(data) || !Array.isArray((data as Record<string, unknown>).created)) {
    throw new ApiError(
      "malformed_response",
      "The API returned a scheduling run without a `created` list.",
      null,
    );
  }
  const payload = (body as ScheduleRevisionsResponse).data;
  return {
    scheduled_on: payload.scheduled_on,
    revisions: payload.created,
    already_scheduled_topic_count: payload.already_scheduled_topic_count,
    reason: payload.reason,
  };
}

/**
 * QZ-009 -- list the practice questions the learner has written.
 *
 * No status is assumed: a caller wanting only what a quiz may ask passes
 * `ready`, and one wanting what has been set aside passes `retired`. The
 * response carries the expected answers, because it is the author reading back
 * what they wrote — a quiz being taken reads `readCheckpointQuiz` instead.
 *
 * @throws ApiError with `isConflict` when more than one learner is stored.
 */
export async function listPracticeQuestions({
  topicId,
  status,
  limit = MAX_PAGE_SIZE,
  offset = 0,
}: {
  topicId?: string;
  status?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<PracticeQuestion[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (topicId) {
    query.set("topic_id", topicId);
  }
  if (status) {
    query.set("status", status);
  }
  const body = await requestJson(`/api/v1/practice-questions?${query.toString()}`);
  unwrapCollection(body, "a practice question collection");

  return (body as PracticeQuestionCollectionResponse).data;
}

/**
 * QZ-008 -- write one practice question against the topics it covers.
 *
 * Option keys are assigned by the backend from each option's position, so
 * nothing here invents one. At least one topic is required: a quiz is assembled
 * by topic, and a question covering none could never be asked.
 *
 * @throws ApiError with `isConflict` when no learner exists yet.
 */
export async function writePracticeQuestion(
  question: NewPracticeQuestion,
): Promise<PracticeQuestion> {
  const body = await requestJson("/api/v1/practice-questions", {
    method: "POST",
    body: question,
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed question.", null);
  }
  return (body as PracticeQuestionResponse).data;
}

/**
 * QZ-010 -- set a practice question aside, or bring it back.
 *
 * Setting aside is reversible and deletes nothing: a quiz already assembled goes
 * on asking the question, because attempts are marked against it.
 *
 * @throws ApiError with `isNotFound` when no such question is stored or another
 *   learner wrote it.
 */
export async function updatePracticeQuestionStatus(
  questionId: string,
  status: QuestionStatus,
): Promise<PracticeQuestion> {
  const body = await requestJson(`/api/v1/practice-questions/${encodeURIComponent(questionId)}`, {
    method: "PATCH",
    body: { status },
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed question.", null);
  }
  return (body as PracticeQuestionResponse).data;
}

/**
 * QZ-010 -- correct a practice question no quiz has asked yet.
 *
 * The content travels as one group: everything the write form sends is sent
 * again, and an explanation left blank clears the stored one.
 *
 * **A question a quiz has already asked cannot be corrected**, and neither can
 * one that has been set aside. Both are refused with `409`, and the refusal
 * explains why -- a stored `is_correct` was decided against the wording as it
 * then stood, so rewriting it would change what a past result says.
 *
 * @throws ApiError with `isConflict` when a quiz has asked the question, or it
 *   has been set aside.
 * @throws ApiError with `isNotFound` when no such question is stored or another
 *   learner wrote it.
 */
export async function correctPracticeQuestion(
  questionId: string,
  question: NewPracticeQuestion,
): Promise<PracticeQuestion> {
  const body = await requestJson(`/api/v1/practice-questions/${encodeURIComponent(questionId)}`, {
    method: "PATCH",
    body: question,
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed question.", null);
  }
  return (body as PracticeQuestionResponse).data;
}

/**
 * QZ-001 -- assemble a checkpoint quiz from the learner's questions.
 *
 * Deterministic and with no AI provider: the quiz asks every ready question the
 * learner wrote for the chosen topics, in the order they wrote them. Nothing is
 * generated, sampled, or selected in preference to anything else.
 *
 * @throws ApiError with `isConflict` when no learner exists yet.
 */
export async function assembleCheckpointQuiz(topicIds: string[]): Promise<CheckpointQuiz> {
  const body = await requestJson("/api/v1/checkpoint-quizzes/generate", {
    method: "POST",
    body: { topic_ids: topicIds },
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed quiz.", null);
  }
  return (body as CheckpointQuizResponse).data;
}

/**
 * QZ-002 -- read a quiz's questions, without their answers.
 *
 * The response carries no expected answer and no explanation, so nothing here
 * has to strip one before rendering.
 *
 * @throws ApiError with `isNotFound` when no such quiz is stored or it is not
 *   the local learner's.
 */
export async function readCheckpointQuiz(quizId: string): Promise<CheckpointQuiz> {
  const body = await requestJson(`/api/v1/checkpoint-quizzes/${encodeURIComponent(quizId)}`);
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed quiz.", null);
  }
  return (body as CheckpointQuizResponse).data;
}

/**
 * QZ-003 -- begin an attempt at a checkpoint quiz.
 *
 * Asking twice starts nothing the second time: an unfinished attempt at the same
 * quiz is returned instead, so a reloaded page cannot litter the learner's
 * history.
 *
 * @throws ApiError with `isNotFound` when no such quiz is stored.
 */
export async function startQuizAttempt(quizId: string): Promise<QuizAttempt> {
  const body = await requestJson(
    `/api/v1/checkpoint-quizzes/${encodeURIComponent(quizId)}/attempts`,
    { method: "POST", body: {} },
  );
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed attempt.", null);
  }
  return (body as QuizAttemptResponse).data;
}

/**
 * QZ-005 -- submit every answer at once, and read the marked result back.
 *
 * A question the learner left alone is omitted from `answers` rather than sent
 * with a null, and reads back as unanswered rather than as wrong. Submitting
 * twice is refused: a record of what happened is not edited afterwards.
 *
 * @throws ApiError with `isConflict` when the attempt has already been marked.
 */
export async function submitQuizAttempt(
  attemptId: string,
  answers: SubmittedAnswer[],
): Promise<QuizAttempt> {
  const body = await requestJson(`/api/v1/quiz-attempts/${encodeURIComponent(attemptId)}/submit`, {
    method: "POST",
    body: { answers },
  });
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed attempt.", null);
  }
  return (body as QuizAttemptResponse).data;
}

/**
 * QZ-006 -- list the learner's quiz attempts, newest first.
 *
 * Nothing is counted, totalled, or compared: the collection is a list of what
 * happened, and no attempt is scored against another.
 *
 * @throws ApiError with `isConflict` when more than one learner is stored.
 */
export async function listQuizAttempts({
  limit = MAX_PAGE_SIZE,
  offset = 0,
}: { limit?: number; offset?: number } = {}): Promise<QuizAttempt[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const body = await requestJson(`/api/v1/quiz-attempts?${query.toString()}`);
  unwrapCollection(body, "a quiz attempt collection");

  return (body as QuizAttemptCollectionResponse).data;
}

/**
 * QZ-007 -- read one attempt and what became of each question.
 *
 * An attempt still in progress reads back without its expected answers and
 * explanations, so opening a result before submitting reveals nothing.
 *
 * @throws ApiError with `isNotFound` when no such attempt is stored or it is not
 *   the local learner's.
 */
export async function readQuizAttempt(attemptId: string): Promise<QuizAttempt> {
  const body = await requestJson(`/api/v1/quiz-attempts/${encodeURIComponent(attemptId)}`);
  const data = unwrapData(body);

  if (!isRecord(data)) {
    throw new ApiError("malformed_response", "The API returned a malformed attempt.", null);
  }
  return (body as QuizAttemptResponse).data;
}
