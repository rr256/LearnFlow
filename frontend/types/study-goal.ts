/**
 * Study goal and examination schedule types, derived from the EXM-001 and
 * GOAL-001 to GOAL-005 response contract in
 * docs/api/endpoints.md#learner-setup-and-goal-endpoints.
 *
 * An examination is always a **window** here, never a single date. An examining
 * body that publishes several sitting days has not named the learner's day, so
 * no type in this file has a field that could hold one.
 *
 * `schedule_status` travels with every set of dates, because a provisional date
 * shown without that word reads as settled fact
 * (docs/domain/terminology.md).
 *
 * A day of the week is a name, never an index. The API stores and sends
 * `monday` to `sunday` precisely so no client has to know whose numbering
 * convention is meant (ADR-018).
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
 * The seven days a week of availability may name, in week order.
 *
 * These are the values the API stores and sends. The order is the order a week
 * is shown in; nothing in the contract ranks one day above another.
 */
export const WEEKDAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
] as const;

/** One day of the week, as the API spells it. */
export type Weekday = (typeof WEEKDAYS)[number];

/** The label a learner reads for each day. Renamed here, never in the API. */
export const WEEKDAY_LABELS: Record<Weekday, string> = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday",
};

/** Whether a value is one of the seven days this build knows. */
export function isWeekday(value: string): value is Weekday {
  return (WEEKDAYS as readonly string[]).includes(value);
}

/**
 * The study time available on one day.
 *
 * A day the learner has not set is absent from the week entirely; a day carrying
 * zero minutes is one they deliberately keep free.
 */
export interface AvailabilitySlot {
  day_of_week: Weekday | string;
  available_minutes: number;
}

/**
 * The week saved against one study goal, Monday first.
 *
 * There is no total. Availability is a planning input, and turning a week into
 * an hours figure is planning work the product does not do yet.
 */
export interface WeeklyAvailability {
  slots: AvailabilitySlot[];
}

/**
 * The orders a plan may work through the curriculum in, as the API spells them.
 *
 * Both are derivable from data the backend already holds: `syllabus_order` from
 * the stored position of subjects and topics, `prerequisites_first` from the
 * prerequisite links between topics. There is deliberately no order that ranks
 * topics by evidence, because no evidence is stored.
 */
export const TOPIC_SEQUENCING_CHOICES = ["syllabus_order", "prerequisites_first"] as const;

/** Which order a plan works through the curriculum in. */
export type TopicSequencing = (typeof TOPIC_SEQUENCING_CHOICES)[number];

/** The label a learner reads for each order. Renamed here, never in the API. */
export const TOPIC_SEQUENCING_LABELS: Record<TopicSequencing, string> = {
  syllabus_order: "Syllabus order",
  prerequisites_first: "Prerequisites first",
};

/** What each order means, so a learner chooses knowing rather than guessing. */
export const TOPIC_SEQUENCING_DESCRIPTIONS: Record<TopicSequencing, string> = {
  syllabus_order: "Work through subjects and topics in the order the syllabus lists them.",
  prerequisites_first: "Study a topic's groundwork before the topics that build on it.",
};

/** Whether a value is one of the topic orders this build knows. */
export function isTopicSequencing(value: string): value is TopicSequencing {
  return (TOPIC_SEQUENCING_CHOICES as readonly string[]).includes(value);
}

/** The shortest study block the API accepts; a smaller value is a 422. */
export const MINIMUM_SESSION_MINUTES = 15;

/** The longest study block the API accepts; a larger value is a 422. */
export const MAXIMUM_SESSION_MINUTES = 480;

/**
 * How the learner wants a plan built, for the choices they have made.
 *
 * A null member is "the learner has not said", not a default. Nothing invents a
 * preference, so a planner meeting a null will choose its own default visibly
 * rather than reading a value nobody chose.
 *
 * `preferred_session_minutes` is a duration, not a time of day — the API records
 * nothing about when in a day a session falls.
 */
export interface PlanningPreferences {
  preferred_session_minutes: number | null;
  topic_sequencing: TopicSequencing | string | null;
}

/**
 * One study goal.
 *
 * `availability` is the week saved against it and `planning_preferences` the
 * preferences, each empty rather than null when the learner has set none — so a
 * view needs no branch for a goal created before they did.
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
  availability: WeeklyAvailability;
  planning_preferences: PlanningPreferences;
}

/** The body GOAL-001 accepts. It carries no learner or curriculum-version id. */
export interface NewStudyGoal {
  learning_program_id: string;
  examination_schedule_id?: string | null;
  target_date?: string | null;
  planning_preferences?: PlanningPreferences | null;
}

/**
 * The body GOAL-004 accepts.
 *
 * A field left out is not changed; an explicit null clears it. The result must
 * still aim at an examination cycle, a target date, or both.
 *
 * `planning_preferences` replaces the whole group: a member left out of a
 * supplied group is unset, so an empty object clears them all, as an explicit
 * null does. Leave the field out to keep the stored preferences.
 */
export interface StudyGoalUpdate {
  examination_schedule_id?: string | null;
  target_date?: string | null;
  status?: StudyGoalStatus;
  planning_preferences?: PlanningPreferences | null;
}

/** True when the source still describes a schedule's dates as liable to change. */
export function datesMayChange(schedule: { schedule_status: string }): boolean {
  return schedule.schedule_status === "provisional";
}

/**
 * The body GOAL-005 accepts.
 *
 * It replaces rather than merges: the days named become the week, and a day it
 * does not name is removed. An empty list clears the goal's availability.
 */
export interface ReplaceAvailability {
  slots: AvailabilitySlot[];
}

export type ExaminationScheduleCollectionResponse = CollectionEnvelope<ExaminationSchedule>;
export type StudyGoalCollectionResponse = CollectionEnvelope<StudyGoal>;
export type StudyGoalResponse = DataEnvelope<StudyGoal>;
export type WeeklyAvailabilityResponse = DataEnvelope<WeeklyAvailability>;
