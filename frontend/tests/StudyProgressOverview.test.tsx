import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StudyProgressOverview } from "@/features/progress/StudyProgressOverview";
import type { RecordedStages } from "@/features/progress/subject-stages";
import type { Revision } from "@/types/revision";
import type { PlanFeasibility, PlanItem, StudyPlan } from "@/types/study-plan";

afterEach(cleanup);

const TODAY = "2026-08-14";
const CURRICULUM_HREF = "/curriculum/programs/program-1";

function item(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: `item-${Math.random()}`,
    topic: {
      id: "topic-1",
      code: null,
      name: "CPU scheduling",
      subject_id: "subject-1",
      subject_name: "Operating Systems",
    },
    action_type: "study",
    scheduled_for: TODAY,
    estimated_minutes: 60,
    priority: 1,
    status: "planned",
    recommendation_reason: "Topic 1 of 60 in syllabus order, from Operating Systems.",
    completed_at: null,
    ...overrides,
  };
}

function week(overrides: Partial<StudyPlan> = {}): StudyPlan {
  return {
    id: "plan-week",
    learner_id: "learner-1",
    study_goal_id: "goal-1",
    plan_type: "weekly",
    period_start: TODAY,
    period_end: "2026-08-20",
    status: "active",
    generation_reason: "The first 3 of 60 topics on your roadmap.",
    item_count: 3,
    items: [item()],
    ...overrides,
  };
}

function roadmap(overrides: Partial<StudyPlan> = {}): StudyPlan {
  return {
    id: "plan-roadmap",
    learner_id: "learner-1",
    study_goal_id: "goal-1",
    plan_type: "roadmap",
    period_start: TODAY,
    period_end: "2027-02-06",
    status: "active",
    generation_reason: "60 topics in syllabus order, to 2027-02-06.",
    item_count: 60,
    items: [item({ id: "roadmap-1", scheduled_for: null })],
    ...overrides,
  };
}

function feasibility(overrides: Partial<PlanFeasibility> = {}): PlanFeasibility {
  return {
    study_goal_id: "goal-1",
    assessed_on: TODAY,
    verdict: "sufficient",
    reason: "Your saved week offers 180 hr before 2027-02-06, and 60 topics need 60 hr.",
    unknown_reason: null,
    horizon_ends_on: "2027-02-06",
    remaining_topic_count: 60,
    session_minutes: 60,
    session_minutes_chosen_by_planner: true,
    study_days: 177,
    available_minutes: 10800,
    required_minutes: 3600,
    shortfall_minutes: 0,
    coverable_topic_count: 60,
    ...overrides,
  };
}

function revision(overrides: Partial<Revision> = {}): Revision {
  return {
    id: `revision-${Math.random()}`,
    topic: {
      id: "topic-2",
      code: null,
      name: "Deadlock",
      subject_id: "subject-1",
      subject_name: "Operating Systems",
    },
    due_on: TODAY,
    scheduled_for: null,
    status: "due",
    trigger_type: "completed_plan_item",
    recommendation_reason: "LearnFlow brings a topic back 7 days after finished study.",
    completed_at: null,
    is_due: true,
    ...overrides,
  };
}

function stages(): RecordedStages {
  return {
    records: [
      {
        id: "progress-1",
        learner_id: "learner-1",
        learning_stage: "practice_ready",
        stage_source: "learner",
        topic: {
          id: "topic-1",
          code: null,
          name: "CPU scheduling",
          is_trackable: true,
          subject_id: "subject-1",
          curriculum_version_id: "version-1",
        },
      },
    ],
    subjects: [
      {
        id: "subject-1",
        code: "CS-OS",
        name: "Operating Systems",
        description: null,
        position: 1,
        topics: [
          {
            id: "topic-1",
            code: null,
            name: "CPU scheduling",
            description: null,
            position: 1,
            is_trackable: true,
            subtopics: [],
          },
        ],
      },
    ],
  };
}

function overview(overrides: Partial<Parameters<typeof StudyProgressOverview>[0]> = {}) {
  return (
    <StudyProgressOverview
      curriculumHref={CURRICULUM_HREF}
      feasibility={feasibility()}
      revisions={[revision()]}
      roadmap={roadmap()}
      stages={stages()}
      today={TODAY}
      week={week()}
      {...overrides}
    />
  );
}

describe("StudyProgressOverview", () => {
  it("says what each active plan covers, using the count the API reported", () => {
    render(overview());

    expect(screen.getByRole("heading", { name: "Where your plan stands" })).toBeDefined();
    expect(screen.getByText(/60 topics, from 2026-08-14 to 2027-02-06/)).toBeDefined();
    expect(screen.getByText("Your roadmap")).toBeDefined();
    expect(screen.getByText("Your week")).toBeDefined();
  });

  it("shows the reason each plan was generated with, rather than composing one", () => {
    render(overview());

    expect(screen.getByText("60 topics in syllabus order, to 2027-02-06.")).toBeDefined();
    expect(screen.getByText("The first 3 of 60 topics on your roadmap.")).toBeDefined();
  });

  it("shows today's work with the reason the plan gave for it", () => {
    render(overview());

    expect(screen.getByRole("heading", { name: "Today" })).toBeDefined();
    expect(screen.getByText(TODAY)).toBeDefined();
    expect(screen.getAllByText("CPU scheduling").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Topic 1 of 60 in syllabus order/).length).toBeGreaterThan(0);
  });

  it("names the action in words rather than by colour alone", () => {
    render(overview());

    expect(screen.getByText("Study")).toBeDefined();
  });

  it("reports outstanding work from earlier days without moving or counting it", () => {
    render(
      overview({
        week: week({
          items: [item({ id: "earlier", scheduled_for: "2026-08-12" }), item({ id: "today" })],
        }),
      }),
    );

    expect(screen.getByText(/Work from earlier days is still outstanding/)).toBeDefined();
    expect(screen.queryByText(/1 item/)).toBeNull();
    expect(screen.queryByText(/2 items/)).toBeNull();
  });

  it("says nothing about earlier days when the learner has settled them", () => {
    render(
      overview({
        week: week({
          items: [
            item({ id: "earlier", scheduled_for: "2026-08-12", status: "completed" }),
            item({ id: "today" }),
          ],
        }),
      }),
    );

    expect(screen.queryByText(/Work from earlier days is still outstanding/)).toBeNull();
  });

  it("renders the feasibility reading the backend composed, with no control beside it", () => {
    render(overview());

    expect(screen.getByRole("heading", { name: "Time to your date" })).toBeDefined();
    expect(
      screen.getByText(/Your saved week offers 180 hr before 2027-02-06/),
    ).toBeDefined();
  });

  it("lists what the learner has marked, in words, under each status", () => {
    render(
      overview({
        week: week({
          items: [
            item({ id: "a", status: "completed" }),
            item({ id: "b", status: "skipped" }),
            item({ id: "c", status: "postponed" }),
          ],
        }),
        roadmap: roadmap({ items: [] }),
      }),
    );

    expect(screen.getByRole("heading", { name: "What you have said about your plan" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Marked completed" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Marked skipped" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Marked postponed" })).toBeDefined();
  });

  it("names which plan a mark was made on", () => {
    render(
      overview({
        week: week({ items: [item({ status: "completed" })] }),
        roadmap: roadmap({ items: [] }),
      }),
    );

    expect(screen.getAllByText(/Operating Systems · Your week/).length).toBeGreaterThan(0);
  });

  it("lists the reviews the backend says are ready, with the reason each exists", () => {
    render(overview());

    expect(screen.getByRole("heading", { name: "Ready to review" })).toBeDefined();
    expect(screen.getByText("Deadlock")).toBeDefined();
    expect(
      screen.getByText(/LearnFlow brings a topic back 7 days after finished study/),
    ).toBeDefined();
  });

  it("leaves out a review whose day has not come", () => {
    render(overview({ revisions: [revision({ due_on: "2026-09-01", is_due: false })] }));

    expect(screen.queryByText("Deadlock")).toBeNull();
    expect(screen.getByText(/Nothing is ready to review today/)).toBeDefined();
  });

  it("offers no control of any kind", () => {
    /* Read-only by decision. Marking work stays on `/plan/today` and `/plan`,
     * generating and adapting stay on `/plan`, and scheduling reviews stays on
     * `/revisions` -- so this screen cannot become a fifth place a status is
     * written. */
    render(
      overview({
        week: week({ items: [item({ status: "completed" })] }),
      }),
    );

    expect(screen.queryByRole("button")).toBeNull();
    expect(document.querySelector("form")).toBeNull();
  });

  it("counts nothing of its own", () => {
    /* The only figures permitted are ones the API reported: a plan's
     * `item_count`, and the counts and durations PLN-006 returned. Terminology
     * forbids counting skips, postponements, and reviews by name, and forbids
     * every percentage, rate, and streak
     * (docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores). */
    render(
      overview({
        week: week({
          items: [
            item({ id: "a", status: "completed" }),
            item({ id: "b", status: "skipped" }),
            item({ id: "c" }),
          ],
        }),
        revisions: [revision({ id: "r1" }), revision({ id: "r2" })],
      }),
    );

    const page = document.body.textContent ?? "";
    expect(page).not.toMatch(/\d+%/);
    expect(page).not.toMatch(/\d+\s*(of|\/)\s*\d+\s*(done|completed|topics done)/i);
    expect(page.toLowerCase()).not.toContain("streak");
    expect(page.toLowerCase()).not.toContain("completion rate");
    expect(page.toLowerCase()).not.toContain("reviews due");
    expect(document.querySelector("progress")).toBeNull();
    expect(document.querySelector("meter")).toBeNull();
  });

  it("describes work, plans, and reviews, never the learner", () => {
    render(
      overview({
        week: week({
          items: [
            item({ id: "earlier", scheduled_for: "2026-08-12" }),
            item({ id: "b", status: "skipped" }),
          ],
        }),
        feasibility: feasibility({
          verdict: "insufficient",
          reason: "Your saved week offers 20 hr before 2027-02-06, and 60 topics need 60 hr.",
          shortfall_minutes: 2400,
          coverable_topic_count: 20,
        }),
      }),
    );

    const page = (document.body.textContent ?? "").toLowerCase();
    for (const wording of [
      "you are behind",
      "falling behind",
      "you failed",
      "you are late",
      "gave up",
      "abandoned",
      "procrastinat",
      "weak topic",
    ]) {
      expect(page).not.toContain(wording);
    }
  });

  it("explains a goal with no plan generated yet", () => {
    render(overview({ roadmap: null, week: null, feasibility: null }));

    expect(screen.getByText(/Nothing has been generated for this goal yet/)).toBeDefined();
    expect(screen.getByRole("link", { name: "Generate a plan" })).toBeDefined();
  });

  it("explains a goal with a roadmap but no dated week", () => {
    render(overview({ week: null }));

    expect(screen.getByText(/no plan for a week, so nothing is placed on a day/)).toBeDefined();
  });

  it("explains a week that ended before today", () => {
    render(overview({ week: week({ period_end: "2026-08-10", items: [] }) }));

    expect(screen.getByText(/dates work to 2026-08-10, which has passed/)).toBeDefined();
  });

  it("explains a day the plan placed no work on", () => {
    render(overview({ week: week({ items: [item({ scheduled_for: "2026-08-15" })] }) }));

    expect(screen.getByText(/places no work on today/)).toBeDefined();
  });

  it("explains a plan the learner has marked nothing on", () => {
    render(overview({ roadmap: roadmap({ items: [] }) }));

    expect(screen.getByText(/have not marked anything on your current plan yet/)).toBeDefined();
  });

  it("explains a learner with no reviews scheduled at all", () => {
    render(overview({ revisions: [] }));

    expect(screen.getByText(/No reviews are scheduled yet/)).toBeDefined();
  });

  it("gathers the recorded learning stages under the subject each topic belongs to", () => {
    render(overview());

    expect(
      screen.getByRole("heading", { name: "Learning stages you have recorded" }),
    ).toBeDefined();
    expect(screen.getByRole("heading", { name: /Operating Systems/ })).toBeDefined();
    expect(screen.getByText("Practice-ready")).toBeDefined();
  });

  it("explains a learner who has recorded no learning stage at all", () => {
    render(overview({ stages: { records: [], subjects: [] } }));

    expect(screen.getByText(/have not recorded a learning stage for any topic yet/)).toBeDefined();
  });

  it("says when the recorded stages could not be read, without emptying the page", () => {
    /* The other five panels state facts of their own, so an unreadable
     * PRG-002 or CUR-003 costs the reader that panel rather than the screen. */
    render(overview({ stages: null }));

    expect(screen.getByText(/could not be read just now/)).toBeDefined();
    expect(screen.getByRole("heading", { name: "Where your plan stands" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Ready to review" })).toBeDefined();
  });

  it("points a learner at the screen where each thing is done", () => {
    render(
      overview({
        week: week({ items: [item({ id: "earlier", scheduled_for: "2026-08-12" })] }),
      }),
    );

    expect(screen.getAllByRole("link", { name: /today's screen/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /your plan/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /reviews/i }).length).toBeGreaterThan(0);
  });
});
