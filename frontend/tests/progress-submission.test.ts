import { describe, expect, it } from "vitest";

import { readStageSubmission } from "@/features/progress/submission";
import { LEARNING_STAGES } from "@/types/progress";

function form(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    data.set(name, value);
  }
  return data;
}

describe("readStageSubmission", () => {
  it("reads the topic and the stage the learner chose", () => {
    const read = readStageSubmission(
      form({ topic_id: "t1", learning_stage: "developing_confidence" }),
    );

    expect(read).toEqual({
      submission: { topicId: "t1", learningStage: "developing_confidence" },
    });
  });

  it.each(LEARNING_STAGES)("accepts %s", (stage) => {
    const read = readStageSubmission(form({ topic_id: "t1", learning_stage: stage }));

    expect(read).toEqual({ submission: { topicId: "t1", learningStage: stage } });
  });

  it("reports a submission that names no topic", () => {
    const read = readStageSubmission(form({ learning_stage: "practice_ready" }));

    expect(read).toHaveProperty("problem");
  });

  it("reports a stage the API would not accept, rather than sending it", () => {
    const read = readStageSubmission(form({ topic_id: "t1", learning_stage: "mastered" }));

    expect(read).toHaveProperty("problem");
  });

  it("trims surrounding whitespace before deciding", () => {
    const read = readStageSubmission(
      form({ topic_id: "  t1  ", learning_stage: "  practice_ready  " }),
    );

    expect(read).toEqual({ submission: { topicId: "t1", learningStage: "practice_ready" } });
  });

  it("reports an empty stage rather than clearing the record", () => {
    const read = readStageSubmission(form({ topic_id: "t1", learning_stage: "" }));

    expect(read).toHaveProperty("problem");
  });
});
