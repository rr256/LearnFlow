import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ExaminationDates } from "@/features/home/ExaminationDates";
import type { ExaminationGoal, ExaminationPeriod } from "@/types/study-goal";

afterEach(cleanup);

function examination(overrides: Partial<ExaminationGoal> = {}): ExaminationGoal {
  return {
    id: "schedule-1",
    cycle_label: "2027",
    name: "GATE 2027",
    organising_body: "IIT Madras",
    source_reference: "https://example.test/schedule",
    source_checked_on: "2026-08-01",
    schedule_status: "provisional",
    examination_window: { starts_on: "2027-02-06", ends_on: "2027-02-21" },
    ...overrides,
  };
}

const PERIODS: ExaminationPeriod[] = [
  { period_type: "registration", starts_on: "2026-08-28", ends_on: "2026-10-05" },
  { period_type: "late_registration", starts_on: "2026-10-06", ends_on: "2026-10-12" },
  { period_type: "examination", starts_on: "2027-02-06", ends_on: "2027-02-07" },
  { period_type: "examination", starts_on: "2027-02-13", ends_on: "2027-02-14" },
  { period_type: "results", starts_on: "2027-03-16", ends_on: "2027-03-16" },
];

describe("ExaminationDates", () => {
  it("reports the examination as a window rather than a single date", () => {
    render(<ExaminationDates examination={examination()} periods={PERIODS} />);

    expect(screen.getByText(/2027-02-06 to 2027-02-21/)).toBeDefined();
  });

  it("shows the registration deadlines, not only the examination", () => {
    render(<ExaminationDates examination={examination()} periods={PERIODS} />);

    expect(screen.getByText("Registration")).toBeDefined();
    expect(screen.getByText("2026-08-28 to 2026-10-05")).toBeDefined();
    expect(screen.getByText("Late registration")).toBeDefined();
  });

  it("lists every sitting weekend separately rather than spanning the gap between them", () => {
    render(<ExaminationDates examination={examination()} periods={PERIODS} />);

    expect(screen.getByText("2027-02-06 to 2027-02-07")).toBeDefined();
    expect(screen.getByText("2027-02-13 to 2027-02-14")).toBeDefined();
    expect(screen.queryByText("2027-02-06 to 2027-02-14")).toBeNull();
  });

  it("shows a single-day announcement as one date", () => {
    render(<ExaminationDates examination={examination()} periods={PERIODS} />);

    expect(screen.getByText("Results announced")).toBeDefined();
    expect(screen.getByText("2027-03-16")).toBeDefined();
  });

  it("renders the periods in the order the API returned them", () => {
    render(<ExaminationDates examination={examination()} periods={PERIODS} />);

    const labels = screen.getAllByRole("term").map((term) => term.textContent);
    expect(labels).toEqual([
      "Registration",
      "Late registration",
      "Examination",
      "Examination",
      "Results announced",
    ]);
  });

  it("says in words that provisional dates may still change", () => {
    // Terminology requires the status wherever the dates are shown, and colour
    // alone would not carry it.
    render(<ExaminationDates examination={examination()} periods={PERIODS} />);

    expect(screen.getByText(/Provisional/)).toBeDefined();
    expect(screen.getByText(/IIT Madras may still change\s+these dates/)).toBeDefined();
  });

  it("states the provisional status once, not once per panel section", () => {
    render(<ExaminationDates examination={examination()} periods={PERIODS} />);

    expect(screen.getAllByText(/may still change/)).toHaveLength(1);
  });

  it("does not call confirmed dates provisional", () => {
    render(
      <ExaminationDates
        examination={examination({ schedule_status: "confirmed" })}
        periods={PERIODS}
      />,
    );

    expect(screen.queryByText(/Provisional/)).toBeNull();
  });

  it("names the source the dates came from and the day it was read", () => {
    render(<ExaminationDates examination={examination()} periods={PERIODS} />);

    const link = screen.getByRole("link", { name: "IIT Madras" });
    expect(link.getAttribute("href")).toBe("https://example.test/schedule");
    expect(screen.getByText(/read on 2026-08-01/)).toBeDefined();
  });

  it("reports a cycle that has published no sitting day rather than inventing one", () => {
    render(
      <ExaminationDates
        examination={examination({ examination_window: null })}
        periods={PERIODS}
      />,
    );

    expect(screen.getByText(/Sitting days not published/)).toBeDefined();
  });

  it("says the published dates could not be read rather than implying there are none", () => {
    render(<ExaminationDates examination={examination()} periods={null} />);

    expect(screen.getByText(/could not be read/)).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Important dates" })).toBeNull();
    // The window still comes from the goal, so it is shown either way.
    expect(screen.getByText(/2027-02-06 to 2027-02-21/)).toBeDefined();
  });

  it("distinguishes a cycle with no dated periods from one that could not be read", () => {
    render(<ExaminationDates examination={examination()} periods={[]} />);

    expect(screen.getByText(/No dated periods are published/)).toBeDefined();
    expect(screen.queryByText(/could not be read/)).toBeNull();
  });
});
