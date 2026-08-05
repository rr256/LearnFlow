/**
 * Study goal and examination schedule types, derived from the EXM-001 and
 * GOAL-001 to GOAL-004 response contract in
 * docs/api/endpoints.md#learner-setup-and-goal-endpoints.
 *
 * An examination is always a **window** here, never a single date. An examining
 * body that publishes several sitting days has not named the learner's day, so
 * no type in this file has a field that could hold one.
 *
 * `schedule_status` travels with every set of dates, because a provisional date
 * shown without that word reads as settled fact
 * (docs/domain/terminology.md).
 */

import type { CollectionEnvelope, DataEnvelope } from "@/types/api";

/** Whether an examining body has confirmed a published schedule's dates. */
export type ScheduleStatus = "provisional" | "confirmed";

/** The kinds of dated period an examination schedule holds. */
export type ExaminationPeriodType =
  | "registration"
  | "late_registration"
  | "examination"
  | "results";

/** The span from the first published sitting day to the last. */
export interface ExaminationWindow {
  starts_on: string;
  ends_on: string;
}

/** One dated period. A single-day event starts and ends on the same day. */
export interface ExaminationPeriod {
  period_type: ExaminationPeriodType | string;
  starts_on: string;
  ends_on: string;
}

/** A published examination schedule, with its provenance and its window. */
export interface ExaminationSchedule {
  id: string;
  learning_program_id: string;
  cycle_label: string;
  name: string;
  organising_body: string | null;
  source_reference: string;
  source_checked_on: string;
  schedule_status: ScheduleStatus | string;
  /** Null when the stored schedule publishes no sitting day. */
  examination_window: ExaminationWindow | null;
  periods: ExaminationPeriod[];
}

/** The examination cycle a goal aims at. */
export interface ExaminationGoal {
  id: string;
  cycle_label: string;
  name: string;
  organising_body: string | null;
  source_reference: string;
  source_checked_on: string;
  schedule_status: ScheduleStatus | string;
  examination_window: ExaminationWindow | null;
}

/** The learning program a goal is bound to. */
export interface StudyGoalProgram {
  id: string;
  code: string;
  name: string;
}

/** The curriculum version a goal is bound to; it may since have been retired. */
export interface StudyGoalCurriculumVersion {
  id: string;
  version_label: string;
  status: string;
}

/** Lifecycle of a study goal. */
export type StudyGoalStatus = "active" | "paused" | "completed" | "archived";

/**
 * One study goal.
 *
 * There is no availability summary: `availability_slots` does not exist yet, and
 * GOAL-005 waits on the `day_of_week` numbering decision.
 */
export interface StudyGoal {
  id: string;
  learner_id: string;
  status: StudyGoalStatus | string;
  /** The learner's own completion date, where they set one. */
  target_date: string | null;
  learning_program: StudyGoalProgram;
  curriculum_version: StudyGoalCurriculumVersion;
  /** Null for a goal aiming at a target date alone. */
  examination: ExaminationGoal | null;
}

/** The body GOAL-001 accepts. It carries no learner or curriculum-version id. */
export interface NewStudyGoal {
  learning_program_id: string;
  examination_schedule_id?: string | null;
  target_date?: string | null;
}

/**
 * The body GOAL-004 accepts.
 *
 * A field left out is not changed; an explicit null clears it. The result must
 * still aim at an examination cycle, a target date, or both.
 */
export interface StudyGoalUpdate {
  examination_schedule_id?: string | null;
  target_date?: string | null;
  status?: StudyGoalStatus;
}

/** True when the source still describes a schedule's dates as liable to change. */
export function datesMayChange(schedule: { schedule_status: string }): boolean {
  return schedule.schedule_status === "provisional";
}

export type ExaminationScheduleCollectionResponse = CollectionEnvelope<ExaminationSchedule>;
export type StudyGoalCollectionResponse = CollectionEnvelope<StudyGoal>;
export type StudyGoalResponse = DataEnvelope<StudyGoal>;
