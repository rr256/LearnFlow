import { describe, expect, it } from "vitest";

import {
  INITIAL_STUDY_QUESTION_STATE,
  readStudyQuestionSubmission,
} from "@/features/mentor/submission";

function form(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    data.set(name, value);
  }
  return data;
}

const TOPIC = "11111111-1111-4111-8111-111111111111";

describe("readStudyQuestionSubmission", () => {
  it("reads the topic and the question", () => {
    const submitted = readStudyQuestionSubmission(
      form({ topic_id: TOPIC, question: "How does round robin work?" }),
    );

    expect(submitted).toEqual({ topicId: TOPIC, question: "How does round robin work?" });
  });

  it("trims only the ends of a question", () => {
    // What a learner wrote inside their question is theirs and is sent as typed.
    const submitted = readStudyQuestionSubmission(
      form({ topic_id: TOPIC, question: "  Why does  a   quantum matter?  " }),
    );

    expect(submitted).toEqual({ topicId: TOPIC, question: "Why does  a   quantum matter?" });
  });

  it("asks for a topic when none was chosen", () => {
    const submitted = readStudyQuestionSubmission(form({ question: "Anything?" }));

    expect(submitted).toEqual({ error: "Choose a topic to ask about." });
  });

  it("asks for a question when none was typed", () => {
    const submitted = readStudyQuestionSubmission(form({ topic_id: TOPIC, question: "   " }));

    expect(submitted).toEqual({ error: "Type a question to ask." });
  });

  it("reads a missing field as absent rather than failing", () => {
    const submitted = readStudyQuestionSubmission(form({}));

    expect(submitted).toEqual({ error: "Choose a topic to ask about." });
  });
});

describe("the initial state", () => {
  it("holds no answer, so nothing is shown before anything is asked", () => {
    expect(INITIAL_STUDY_QUESTION_STATE.answer).toBeNull();
    expect(INITIAL_STUDY_QUESTION_STATE.error).toBeNull();
  });

  it("carries no history of previous questions", () => {
    // Nothing is stored: there is no transcript and no earlier question to return
    // to, so the state holds one answer at most.
    expect(Object.keys(INITIAL_STUDY_QUESTION_STATE).sort()).toEqual([
      "answer",
      "error",
      "question",
      "topicId",
    ]);
  });
});
