import { describe, expect, it } from "vitest";

import {
  readAttemptSubmission,
  readQuestionCorrection,
  readQuestionStatusSubmission,
  readQuestionSubmission,
  readQuizTopics,
} from "@/features/practice/submission";

function form(entries: Array<[string, string]>): FormData {
  const data = new FormData();
  for (const [name, value] of entries) {
    data.append(name, value);
  }
  return data;
}

const A_QUESTION: Array<[string, string]> = [
  ["prompt", "How many bits address 1 KiB?"],
  ["option_0", "8"],
  ["option_1", "10"],
  ["option_2", "16"],
  ["option_3", "1024"],
  ["correct_option", "1"],
  ["topic_ids", "topic-1"],
];

describe("readQuestionSubmission", () => {
  it("reads a prompt, its options, the expected answer, and the topics", () => {
    expect(readQuestionSubmission(form(A_QUESTION))).toEqual({
      prompt: "How many bits address 1 KiB?",
      options: ["8", "10", "16", "1024"],
      correct_option_index: 1,
      explanation: null,
      topic_ids: ["topic-1"],
    });
  });

  it("drops blank option fields so a shorter question needs no different form", () => {
    const submission = readQuestionSubmission(
      form([
        ["prompt", "Is a semaphore a lock?"],
        ["option_0", "Yes"],
        ["option_1", "No"],
        ["option_2", "   "],
        ["option_3", ""],
        ["correct_option", "1"],
        ["topic_ids", "topic-1"],
      ]),
    );

    expect(submission?.options).toEqual(["Yes", "No"]);
  });

  it("re-indexes the expected answer against the options that survived", () => {
    // The learner marked the field in slot 3 correct, but slots 1 and 2 are
    // blank. Sending index 3 unchanged would mark a different option.
    const submission = readQuestionSubmission(
      form([
        ["prompt", "Which is it?"],
        ["option_0", "First"],
        ["option_1", ""],
        ["option_2", ""],
        ["option_3", "Last"],
        ["correct_option", "3"],
        ["topic_ids", "topic-1"],
      ]),
    );

    expect(submission?.options).toEqual(["First", "Last"]);
    expect(submission?.correct_option_index).toBe(1);
  });

  it("keeps an explanation when one was written", () => {
    const submission = readQuestionSubmission(
      form([...A_QUESTION, ["explanation", "1 KiB is 2^10 bytes."]]),
    );

    expect(submission?.explanation).toBe("1 KiB is 2^10 bytes.");
  });

  it("treats a blank explanation as absent rather than as an empty string", () => {
    const submission = readQuestionSubmission(form([...A_QUESTION, ["explanation", "   "]]));

    expect(submission?.explanation).toBeNull();
  });

  it("refuses a question with no prompt", () => {
    const entries = A_QUESTION.filter(([name]) => name !== "prompt");

    expect(readQuestionSubmission(form([...entries, ["prompt", "  "]]))).toBeNull();
  });

  it("refuses a question offering fewer than two options", () => {
    expect(
      readQuestionSubmission(
        form([
          ["prompt", "Only one?"],
          ["option_0", "Yes"],
          ["correct_option", "0"],
          ["topic_ids", "topic-1"],
        ]),
      ),
    ).toBeNull();
  });

  it("refuses a question whose expected answer names a blank option", () => {
    expect(
      readQuestionSubmission(
        form([
          ["prompt", "Which is it?"],
          ["option_0", "First"],
          ["option_1", "Second"],
          ["correct_option", "3"],
          ["topic_ids", "topic-1"],
        ]),
      ),
    ).toBeNull();
  });

  it("refuses a question covering no topic, because no quiz could ask it", () => {
    const entries = A_QUESTION.filter(([name]) => name !== "topic_ids");

    expect(readQuestionSubmission(form(entries))).toBeNull();
  });

  it("keeps every topic a learner selected", () => {
    const submission = readQuestionSubmission(
      form([...A_QUESTION, ["topic_ids", "topic-2"], ["topic_ids", "topic-3"]]),
    );

    expect(submission?.topic_ids).toEqual(["topic-1", "topic-2", "topic-3"]);
  });
});

describe("readQuestionCorrection", () => {
  it("reads the question it corrects alongside the whole content", () => {
    expect(readQuestionCorrection(form([...A_QUESTION, ["question_id", "question-1"]]))).toEqual({
      questionId: "question-1",
      prompt: "How many bits address 1 KiB?",
      options: ["8", "10", "16", "1024"],
      correct_option_index: 1,
      explanation: null,
      topic_ids: ["topic-1"],
    });
  });

  it("clears an explanation the learner emptied, because the content is one group", () => {
    const correction = readQuestionCorrection(
      form([...A_QUESTION, ["question_id", "question-1"], ["explanation", "   "]]),
    );

    expect(correction?.explanation).toBeNull();
  });

  it("sends nothing when the question is not named", () => {
    expect(readQuestionCorrection(form(A_QUESTION))).toBeNull();
  });

  it("sends nothing when the form asks for something unsendable", () => {
    expect(
      readQuestionCorrection(
        form([
          ["question_id", "question-1"],
          ["prompt", "How many bits address 1 KiB?"],
          ["option_0", "8"],
          ["correct_option", "0"],
          ["topic_ids", "topic-1"],
        ]),
      ),
    ).toBeNull();
  });

  it("decides nothing about whether the question may still be corrected", () => {
    // Whether a quiz has asked it is a backend fact this form cannot see, so
    // the reading never refuses on that ground.
    expect(
      readQuestionCorrection(form([...A_QUESTION, ["question_id", "question-1"]])),
    ).not.toBeNull();
  });
});

describe("readQuestionStatusSubmission", () => {
  it("reads a question and the status it is moving to", () => {
    expect(
      readQuestionStatusSubmission(
        form([
          ["question_id", "question-1"],
          ["status", "retired"],
        ]),
      ),
    ).toEqual({ questionId: "question-1", status: "retired" });
  });

  it("reads the reverse direction too, because setting aside is reversible", () => {
    expect(
      readQuestionStatusSubmission(
        form([
          ["question_id", "question-1"],
          ["status", "ready"],
        ]),
      ),
    ).toEqual({ questionId: "question-1", status: "ready" });
  });

  it("refuses a status this build does not offer", () => {
    expect(
      readQuestionStatusSubmission(
        form([
          ["question_id", "question-1"],
          ["status", "draft"],
        ]),
      ),
    ).toBeNull();
  });

  it("refuses a submission naming no question", () => {
    expect(readQuestionStatusSubmission(form([["status", "retired"]]))).toBeNull();
  });
});

describe("readQuizTopics", () => {
  it("reads every topic the learner chose", () => {
    expect(
      readQuizTopics(
        form([
          ["topic_ids", "topic-1"],
          ["topic_ids", "topic-2"],
        ]),
      ),
    ).toEqual(["topic-1", "topic-2"]);
  });

  it("refuses a request choosing nothing, which ADR-008 forbids", () => {
    expect(readQuizTopics(form([]))).toBeNull();
  });
});

describe("readAttemptSubmission", () => {
  it("pairs each answer with the question it belongs to", () => {
    expect(
      readAttemptSubmission(
        form([
          ["quiz_id", "quiz-1"],
          ["answer_question-1", "b"],
          ["answer_question-2", "d"],
        ]),
      ),
    ).toEqual({
      quizId: "quiz-1",
      answers: [
        { question_id: "question-1", option_key: "b" },
        { question_id: "question-2", option_key: "d" },
      ],
    });
  });

  it("leaves an unanswered question out rather than sending a blank", () => {
    // A radio group nobody chose from posts nothing, so the question is simply
    // absent and the backend records it as unanswered rather than as wrong.
    const submission = readAttemptSubmission(
      form([
        ["quiz_id", "quiz-1"],
        ["answer_question-1", "b"],
      ]),
    );

    expect(submission?.answers).toEqual([{ question_id: "question-1", option_key: "b" }]);
  });

  it("allows a submission with nothing answered at all", () => {
    expect(readAttemptSubmission(form([["quiz_id", "quiz-1"]]))).toEqual({
      quizId: "quiz-1",
      answers: [],
    });
  });

  it("refuses a submission that does not name its quiz", () => {
    expect(readAttemptSubmission(form([["answer_question-1", "a"]]))).toBeNull();
  });

  it("ignores fields that are not answers", () => {
    const submission = readAttemptSubmission(
      form([
        ["quiz_id", "quiz-1"],
        ["something_else", "ignored"],
        ["answer_question-1", "a"],
      ]),
    );

    expect(submission?.answers).toEqual([{ question_id: "question-1", option_key: "a" }]);
  });
});
