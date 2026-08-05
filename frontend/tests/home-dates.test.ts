import { describe, expect, it } from "vitest";

import { describeDateSpan, describePeriodType } from "@/features/home/dates";

describe("describeDateSpan", () => {
  it("writes a multi-day period as a span", () => {
    expect(describeDateSpan("2027-02-06", "2027-02-21")).toBe("2027-02-06 to 2027-02-21");
  });

  it("writes a single-day event as one date rather than a span to itself", () => {
    expect(describeDateSpan("2027-03-16", "2027-03-16")).toBe("2027-03-16");
  });

  it("prints the API's own ISO dates, converting nothing", () => {
    // A date-only string parses as UTC midnight, so any locale conversion could
    // move a published sitting day back by a day.
    expect(describeDateSpan("2027-01-01", "2027-01-02")).toBe("2027-01-01 to 2027-01-02");
  });
});

describe("describePeriodType", () => {
  it.each([
    ["registration", "Registration"],
    ["late_registration", "Late registration"],
    ["examination", "Examination"],
    ["results", "Results announced"],
  ])("labels %s as %s", (periodType, expected) => {
    expect(describePeriodType(periodType)).toBe(expected);
  });

  it("shows an unrecognised period type readably rather than hiding the date", () => {
    expect(describePeriodType("admit_card")).toBe("admit card");
  });
});
