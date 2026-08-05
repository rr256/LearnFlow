import { describe, expect, it } from "vitest";

import { stageFor, stagesByTopicId } from "@/features/progress/stages";
import {
  LEARNING_STAGES,
  LEARNING_STAGE_LABELS,
  LEARNING_STAGE_NEXT_ACTIONS,
  isLearningStage,
  type TopicProgress,
} from "@/types/progress";

function record(topicId: string, learningStage: string): TopicProgress {
  return {
    id: `progress-${topicId}`,
    learner_id: "22222222-2222-4222-8222-222222222222",
    learning_stage: learningStage,
    stage_source: "learner",
    topic: {
      id: topicId,
      code: null,
      name: `Topic ${topicId}`,
      is_trackable: true,
      subject_id: "44444444-4444-4444-8444-444444444444",
      curriculum_version_id: "55555555-5555-4555-8555-555555555555",
    },
  };
}

describe("stagesByTopicId", () => {
  it("indexes each recorded stage by the topic it belongs to", () => {
    const index = stagesByTopicId([record("t1", "practice_ready"), record("t2", "not_explored")]);

    expect(stageFor(index, "t1")).toBe("practice_ready");
    expect(stageFor(index, "t2")).toBe("not_explored");
  });

  it("reports null for a topic the learner has recorded nothing against", () => {
    const index = stagesByTopicId([record("t1", "practice_ready")]);

    expect(stageFor(index, "t2")).toBeNull();
  });

  it("skips a stage this build does not recognise rather than showing it raw", () => {
    const index = stagesByTopicId([record("t1", "mastered")]);

    expect(stageFor(index, "t1")).toBeNull();
  });

  it("handles an empty result", () => {
    expect(stagesByTopicId([]).size).toBe(0);
  });
});

describe("the learning stage vocabulary", () => {
  it("is the five approved stages, in the documented wire form", () => {
    expect(LEARNING_STAGES).toEqual([
      "not_explored",
      "building_foundation",
      "developing_confidence",
      "practice_ready",
      "strong_understanding",
    ]);
  });

  it("labels every stage with the wording terminology.md defines", () => {
    expect(LEARNING_STAGES.map((stage) => LEARNING_STAGE_LABELS[stage])).toEqual([
      "Not explored",
      "Building foundation",
      "Developing confidence",
      "Practice-ready",
      "Strong understanding",
    ]);
  });

  it("pairs every stage with a next action, so none reads as a verdict", () => {
    for (const stage of LEARNING_STAGES) {
      expect(LEARNING_STAGE_NEXT_ACTIONS[stage].length).toBeGreaterThan(0);
    }
  });

  it("uses none of the wording terminology.md tells us to avoid", () => {
    const copy = [
      ...Object.values(LEARNING_STAGE_LABELS),
      ...Object.values(LEARNING_STAGE_NEXT_ACTIONS),
    ]
      .join(" ")
      .toLowerCase();

    for (const avoided of ["weak", "failed", "mastered", "poor", "behind"]) {
      expect(copy).not.toContain(avoided);
    }
  });

  it("recognises exactly the five stages and nothing else", () => {
    for (const stage of LEARNING_STAGES) {
      expect(isLearningStage(stage)).toBe(true);
    }
    expect(isLearningStage("mastered")).toBe(false);
    expect(isLearningStage("")).toBe(false);
  });
});
