import { describe, expect, it } from "vitest";

import {
  describeSessionLength,
  describeTopicSequencing,
  hasPlanningPreferences,
} from "@/features/onboarding/preferences";
import { TOPIC_SEQUENCING_CHOICES } from "@/types/study-goal";

describe("describeSessionLength", () => {
  it("reports minutes as minutes", () => {
    expect(describeSessionLength(90)).toBe("90 minutes");
  });

  it("does not pluralise a single minute", () => {
    expect(describeSessionLength(1)).toBe("1 minute");
  });

  it("returns null for a length the learner has not set", () => {
    expect(describeSessionLength(null)).toBeNull();
  });

  it("never converts minutes to hours", () => {
    // Turning a planning input into an hours figure is arithmetic that belongs
    // to the planner, not to a label -- the rule weekly availability follows.
    expect(describeSessionLength(120)).not.toMatch(/hour/i);
  });
});

describe("describeTopicSequencing", () => {
  it.each(TOPIC_SEQUENCING_CHOICES)("labels the documented order %s", (choice: string) => {
    const label = describeTopicSequencing(choice);

    expect(label).toBeTruthy();
    expect(label).not.toBe(choice);
  });

  it("returns null for an order the learner has not set", () => {
    expect(describeTopicSequencing(null)).toBeNull();
  });

  it("returns null for an order this build does not know", () => {
    // An order added to the contract later is left out rather than printed as a
    // raw identifier, the rule the stage and weekday joins already follow.
    expect(describeTopicSequencing("alphabetical_order")).toBeNull();
  });
});

describe("hasPlanningPreferences", () => {
  it("is false when nothing is set", () => {
    expect(
      hasPlanningPreferences({ preferred_session_minutes: null, topic_sequencing: null }),
    ).toBe(false);
  });

  it("is false for a goal that does not exist yet", () => {
    expect(hasPlanningPreferences(null)).toBe(false);
  });

  it("is true when either preference is set", () => {
    expect(
      hasPlanningPreferences({ preferred_session_minutes: 60, topic_sequencing: null }),
    ).toBe(true);
    expect(
      hasPlanningPreferences({
        preferred_session_minutes: null,
        topic_sequencing: "syllabus_order",
      }),
    ).toBe(true);
  });

  it("is false when the only value set is one this build cannot show", () => {
    expect(
      hasPlanningPreferences({
        preferred_session_minutes: null,
        topic_sequencing: "alphabetical_order",
      }),
    ).toBe(false);
  });
});
