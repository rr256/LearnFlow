import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The forms import the server actions, which pull in `next/cache` and
// `next/navigation`. A component test exercises the markup and the values it
// starts with, not the write path; what each action sends is covered by
// tests/practice-submission.test.ts and by the standalone run with JavaScript
// disabled.
vi.mock("@/features/practice/actions", () => ({
  writeQuestionAction: vi.fn(),
  saveQuestionStatus: vi.fn(),
  startQuizAction: vi.fn(),
  submitAnswersAction: vi.fn(),
}));

const { QuestionForm } = await import("@/features/practice/QuestionForm");
const { QuestionBank } = await import("@/features/practice/QuestionBank");
const { StartQuizForm } = await import("@/features/practice/StartQuizForm");
const { QuizForm } = await import("@/features/practice/QuizForm");
const { AttemptResult } = await import("@/features/practice/AttemptResult");
const { AttemptHistory } = await import("@/features/practice/AttemptHistory");

import type { SubjectTopicOptions } from "@/features/resources/topic-options";
import type {
  AttemptOutcome,
  CheckpointQuiz,
  PracticeQuestion,
  QuizAttempt,
} from "@/types/practice";

afterEach(cleanup);

const topicGroups: SubjectTopicOptions[] = [
  {
    subjectId: "subject-1",
    subjectName: "Operating Systems",
    topics: [
      { id: "topic-1", label: "CPU scheduling" },
      { id: "topic-2", label: "Deadlock" },
    ],
  },
];

const OPTIONS = [
  { key: "a", text: "8" },
  { key: "b", text: "10" },
];

function question(overrides: Partial<PracticeQuestion> = {}): PracticeQuestion {
  return {
    id: "question-1",
    author_learner_id: "learner-1",
    question_type: "multiple_choice",
    source_type: "curated",
    prompt: "How many bits address 1 KiB?",
    options: OPTIONS,
    expected_option_key: "b",
    explanation: "1 KiB is 2^10 bytes.",
    status: "ready",
    written_at: "2026-08-18T09:00:00Z",
    topics: [
      {
        id: "topic-1",
        code: null,
        name: "CPU scheduling",
        subject_id: "subject-1",
        subject_name: "Operating Systems",
      },
    ],
    ...overrides,
  };
}

function quiz(overrides: Partial<CheckpointQuiz> = {}): CheckpointQuiz {
  return {
    id: "quiz-1",
    learner_id: "learner-1",
    title: "Practice: CPU scheduling",
    source_type: "curated",
    status: "ready",
    topics: [
      {
        id: "topic-1",
        code: null,
        name: "CPU scheduling",
        subject_id: "subject-1",
        subject_name: "Operating Systems",
      },
    ],
    questions: [
      {
        position: 1,
        question_id: "question-1",
        prompt: "How many bits address 1 KiB?",
        options: OPTIONS,
      },
    ],
    ...overrides,
  };
}

function outcome(overrides: Partial<AttemptOutcome> = {}): AttemptOutcome {
  return {
    position: 1,
    question_id: "question-1",
    prompt: "How many bits address 1 KiB?",
    options: OPTIONS,
    chosen_option_key: "b",
    expected_option_key: "b",
    explanation: "1 KiB is 2^10 bytes.",
    is_correct: true,
    ...overrides,
  };
}

function attempt(overrides: Partial<QuizAttempt> = {}): QuizAttempt {
  return {
    id: "attempt-1",
    learner_id: "learner-1",
    checkpoint_quiz_id: "quiz-1",
    quiz_title: "Practice: CPU scheduling",
    status: "evaluated",
    started_at: "2026-08-18T09:00:00Z",
    submitted_at: "2026-08-18T09:10:00Z",
    evaluated_at: "2026-08-18T09:10:00Z",
    topics: [],
    outcomes: [outcome()],
    ...overrides,
  };
}

/** Every number rendered anywhere in the container, as strings. */
function digitsIn(container: HTMLElement): string[] {
  return (container.textContent ?? "").match(/\d+(\.\d+)?%?/g) ?? [];
}

describe("QuestionForm", () => {
  it("offers the curriculum's topics grouped by subject", () => {
    render(<QuestionForm topicGroups={topicGroups} />);

    expect(screen.getByRole("group", { name: "Operating Systems" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "CPU scheduling" })).toBeTruthy();
  });

  it("says a question cannot be edited afterwards", () => {
    render(<QuestionForm topicGroups={topicGroups} />);

    expect(screen.getByText(/cannot be edited/i)).toBeTruthy();
  });

  it("offers no way to generate a question", () => {
    // Every question is the learner's own: no AI provider is involved.
    const { container } = render(<QuestionForm topicGroups={topicGroups} />);

    expect(container.textContent).not.toMatch(/generate|suggest|for me/i);
  });

  it("still renders when the curriculum could not be read", () => {
    render(<QuestionForm topicGroups={[]} />);

    expect(screen.getByRole("button", { name: /add this question/i })).toBeTruthy();
  });
});

describe("QuestionBank", () => {
  it("lists what the learner wrote, with the expected answer named in words", () => {
    render(<QuestionBank questions={[question()]} />);

    expect(screen.getByText("How many bits address 1 KiB?")).toBeTruthy();
    expect(screen.getByText(/the expected answer/i)).toBeTruthy();
  });

  it("still lists a question that has been set aside, so it can be brought back", () => {
    render(<QuestionBank questions={[question({ status: "retired" })]} />);

    expect(screen.getByText("Set aside")).toBeTruthy();
    expect(screen.getByRole("button", { name: /use it again/i })).toBeTruthy();
  });

  it("says so plainly when nothing has been written", () => {
    render(<QuestionBank questions={[]} />);

    expect(screen.getByText(/have not written any yet/i)).toBeTruthy();
  });

  it("states no figure about how many questions there are", () => {
    const { container } = render(<QuestionBank questions={[question(), question({ id: "q2" })]} />);

    // The only digits belong to the question text itself, never to a tally.
    expect(digitsIn(container).every((value) => !value.endsWith("%"))).toBe(true);
    expect(container.textContent).not.toMatch(/\b2 questions\b/);
  });
});

describe("StartQuizForm", () => {
  it("says the quiz asks every question written for the chosen topics", () => {
    render(<StartQuizForm topicGroups={topicGroups} />);

    expect(screen.getByText(/every question you have written/i)).toBeTruthy();
  });

  it("offers the curriculum's topics to practise", () => {
    render(<StartQuizForm topicGroups={topicGroups} />);

    expect(screen.getByRole("option", { name: "Deadlock" })).toBeTruthy();
  });
});

describe("QuizForm", () => {
  it("asks the questions the quiz holds, in its own order", () => {
    render(<QuizForm quiz={quiz()} />);

    expect(screen.getByText(/How many bits address 1 KiB\?/)).toBeTruthy();
    expect(screen.getAllByRole("radio")).toHaveLength(2);
  });

  it("pre-selects nothing, so a learner is not made to guess", () => {
    render(<QuizForm quiz={quiz()} />);

    for (const radio of screen.getAllByRole("radio")) {
      expect((radio as HTMLInputElement).checked).toBe(false);
    }
  });

  it("says an unanswered question is not a wrong one", () => {
    render(<QuizForm quiz={quiz()} />);

    expect(screen.getByText(/recorded as unanswered, not/i)).toBeTruthy();
  });

  it("shows no expected answer and no explanation while the quiz is being taken", () => {
    const { container } = render(<QuizForm quiz={quiz()} />);

    expect(container.textContent).not.toMatch(/2\^10/);
    expect(container.textContent).not.toMatch(/expected answer/i);
  });

  it("names each answer after its question, so an option cannot be mispaired", () => {
    const { container } = render(<QuizForm quiz={quiz()} />);

    const radios = container.querySelectorAll('input[type="radio"]');
    for (const radio of radios) {
      expect(radio.getAttribute("name")).toBe("answer_question-1");
    }
  });
});

describe("AttemptResult", () => {
  it("says in words what became of each question", () => {
    render(<AttemptResult attempt={attempt()} />);

    expect(screen.getByText("You chose the expected answer")).toBeTruthy();
  });

  it("distinguishes an unanswered question from a wrong one", () => {
    render(
      <AttemptResult
        attempt={attempt({
          outcomes: [outcome({ chosen_option_key: null, is_correct: null })],
        })}
      />,
    );

    expect(screen.getByText("You did not answer this one")).toBeTruthy();
  });

  it("names a wrong answer without judging the learner", () => {
    const { container } = render(
      <AttemptResult
        attempt={attempt({ outcomes: [outcome({ chosen_option_key: "a", is_correct: false })] })}
      />,
    );

    expect(screen.getByText("Not the expected answer")).toBeTruthy();
    expect(container.textContent).not.toMatch(/wrong|incorrect|failed|weak|poor/i);
  });

  it("shows the explanation once the attempt has been marked", () => {
    render(<AttemptResult attempt={attempt()} />);

    expect(screen.getByText("1 KiB is 2^10 bytes.")).toBeTruthy();
  });

  it("withholds the expected answer while an attempt is still in progress", () => {
    render(
      <AttemptResult
        attempt={attempt({
          status: "in_progress",
          outcomes: [
            outcome({
              chosen_option_key: null,
              expected_option_key: null,
              explanation: null,
              is_correct: null,
            }),
          ],
        })}
      />,
    );

    expect(screen.getByText(/has not been submitted yet/i)).toBeTruthy();
  });

  it("states no score, total, or percentage anywhere", () => {
    // The rule ADR-033 fixes: a result is per-question outcomes and nothing more.
    const { container } = render(
      <AttemptResult
        attempt={attempt({
          outcomes: [
            outcome(),
            outcome({ position: 2, question_id: "question-2", is_correct: false }),
            outcome({ position: 3, question_id: "question-3", is_correct: null }),
          ],
        })}
      />,
    );

    expect(container.textContent).not.toMatch(/%/);
    expect(container.textContent).not.toMatch(/\b\d+\s*(of|\/)\s*\d+\b/);
    expect(container.textContent).not.toMatch(/score|marks|correct answers|out of/i);
  });

  it("offers no control at all, because a result is not edited afterwards", () => {
    const { container } = render(<AttemptResult attempt={attempt()} />);

    expect(container.querySelector("button")).toBeNull();
    expect(container.querySelector("form")).toBeNull();
  });
});

describe("AttemptHistory", () => {
  it("lists what the learner has taken, linking to each result", () => {
    render(<AttemptHistory attempts={[attempt()]} />);

    const link = screen.getByRole("link", { name: "Practice: CPU scheduling" });
    expect(link.getAttribute("href")).toBe("/practice/attempts/attempt-1");
  });

  it("marks an attempt that was never submitted, without calling it a failure", () => {
    const { container } = render(
      <AttemptHistory attempts={[attempt({ status: "in_progress", submitted_at: null })]} />,
    );

    expect(screen.getByText("Not submitted")).toBeTruthy();
    expect(container.textContent).not.toMatch(/abandoned|gave up|incomplete/i);
  });

  it("says so plainly when nothing has been taken", () => {
    render(<AttemptHistory attempts={[]} />);

    expect(screen.getByText(/None yet/i)).toBeTruthy();
  });

  it("sets no attempt against another", () => {
    const { container } = render(
      <AttemptHistory attempts={[attempt(), attempt({ id: "attempt-2" })]} />,
    );

    expect(container.textContent).not.toMatch(/%|better|worse|improved|best/i);
  });
});
