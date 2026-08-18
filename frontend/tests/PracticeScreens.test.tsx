import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The forms import the server actions, which pull in `next/cache` and
// `next/navigation`. A component test exercises the markup and the values it
// starts with, not the write path; what each action sends is covered by
// tests/practice-submission.test.ts and by the standalone run with JavaScript
// disabled.
vi.mock("@/features/practice/actions", () => ({
  writeQuestionAction: vi.fn(),
  correctQuestionAction: vi.fn(),
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
const { PracticeHistory } = await import("@/features/practice/PracticeHistory");

import type { HistoryPage } from "@/features/practice/history";
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

function historyPage(overrides: Partial<HistoryPage> = {}): HistoryPage {
  return { attempts: [attempt()], olderOffset: null, newerOffset: null, ...overrides };
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

  it("says a question can be corrected only until a quiz has asked it", () => {
    render(<QuestionForm topicGroups={topicGroups} />);

    expect(screen.getByText(/until a quiz has asked it/i)).toBeTruthy();
    expect(screen.getByText(/set it aside and write another/i)).toBeTruthy();
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
    render(<QuestionBank questions={[question()]} topicGroups={topicGroups} />);

    // The prompt also fills the correction form's textarea, so this asserts it
    // is *shown* as text rather than only being editable.
    const shown = screen.getAllByText("How many bits address 1 KiB?");
    expect(shown.some((node) => node.tagName === "P")).toBe(true);
    // The correction form labels its radios with the same phrase, so this
    // asserts the note the bank writes beside the option itself.
    const named = screen.getAllByText(/the expected answer/i);
    expect(named.some((node) => node.tagName === "SPAN")).toBe(true);
  });

  it("offers a correction form for a question still in use", () => {
    render(<QuestionBank questions={[question()]} topicGroups={topicGroups} />);

    expect(screen.getByText(/correct this question/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /save this correction/i })).toBeTruthy();
  });

  it("starts the correction form filled with what the question already says", () => {
    render(<QuestionBank questions={[question()]} topicGroups={topicGroups} />);

    const prompt = screen.getByRole("textbox", { name: /question/i }) as HTMLTextAreaElement;
    expect(prompt.value).toBe("How many bits address 1 KiB?");
  });

  it("keeps the correction form closed until the learner opens it", () => {
    const { container } = render(<QuestionBank questions={[question()]} topicGroups={topicGroups} />);

    // `details` opens with no JavaScript, so the form is reachable on a page
    // that never hydrates.
    const details = container.querySelector("details");
    expect(details).not.toBeNull();
    expect(details?.hasAttribute("open")).toBe(false);
  });

  it("offers no correction for a question set aside, and says why", () => {
    render(<QuestionBank questions={[question({ status: "retired" })]} topicGroups={topicGroups} />);

    expect(screen.queryByRole("button", { name: /save this correction/i })).toBeNull();
    expect(screen.getByText(/bring this back into use to correct it/i)).toBeTruthy();
  });

  it("still lists a question that has been set aside, so it can be brought back", () => {
    render(<QuestionBank questions={[question({ status: "retired" })]} topicGroups={topicGroups} />);

    expect(screen.getByText("Set aside")).toBeTruthy();
    expect(screen.getByRole("button", { name: /use it again/i })).toBeTruthy();
  });

  it("says so plainly when nothing has been written", () => {
    render(<QuestionBank questions={[]} topicGroups={topicGroups} />);

    expect(screen.getByText(/have not written any yet/i)).toBeTruthy();
  });

  it("states no figure about how many questions there are", () => {
    const { container } = render(<QuestionBank questions={[question(), question({ id: "q2" })]} topicGroups={topicGroups} />);

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
    render(<AttemptHistory attempts={[attempt()]} hasMore={false} />);

    const link = screen.getByRole("link", { name: "Practice: CPU scheduling" });
    expect(link.getAttribute("href")).toBe("/practice/attempts/attempt-1");
  });

  it("marks an attempt that was never submitted, without calling it a failure", () => {
    const { container } = render(
      <AttemptHistory
        attempts={[attempt({ status: "in_progress", submitted_at: null })]}
        hasMore={false}
      />,
    );

    expect(screen.getByText(/Not submitted/)).toBeTruthy();
    expect(container.textContent).not.toMatch(/abandoned|gave up|incomplete|failure/i);
  });

  it("names the topics an attempt covered, so it can be told from another", () => {
    render(
      <AttemptHistory
        attempts={[
          attempt({
            topics: [
              {
                id: "topic-1",
                code: null,
                name: "CPU scheduling",
                subject_id: "subject-1",
                subject_name: "Operating Systems",
              },
            ],
          }),
        ]}
        hasMore={false}
      />,
    );

    expect(screen.getByText(/Operating Systems — CPU scheduling/)).toBeTruthy();
  });

  it("leads to the whole history, so nothing is out of reach from here", () => {
    render(<AttemptHistory attempts={[attempt()]} hasMore />);

    const link = screen.getByRole("link", { name: /See every quiz you have taken/i });
    expect(link.getAttribute("href")).toBe("/practice/history");
  });

  it("says there are earlier ones without saying how many", () => {
    const { container } = render(<AttemptHistory attempts={[attempt()]} hasMore />);

    expect(screen.getByText(/These are your most recent/i)).toBeTruthy();
    expect(container.textContent).not.toMatch(/\b\d+\s*(more|others|earlier|quizzes)\b/i);
  });

  it("says so plainly when nothing has been taken, and offers no history to open", () => {
    render(<AttemptHistory attempts={[]} hasMore={false} />);

    expect(screen.getByText(/None yet/i)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /See every quiz/i })).toBeNull();
  });

  it("sets no attempt against another", () => {
    const { container } = render(
      <AttemptHistory attempts={[attempt(), attempt({ id: "attempt-2" })]} hasMore={false} />,
    );

    expect(container.textContent).not.toMatch(/%|better|worse|improved|best/i);
  });
});

describe("PracticeHistory", () => {
  it("lists every attempt on the page, linking each to its result", () => {
    render(
      <PracticeHistory
        page={historyPage({
          attempts: [attempt(), attempt({ id: "attempt-2", quiz_title: "Practice: Deadlock" })],
        })}
      />,
    );

    expect(
      screen.getByRole("link", { name: "Practice: CPU scheduling" }).getAttribute("href"),
    ).toBe("/practice/attempts/attempt-1");
    expect(screen.getByRole("link", { name: "Practice: Deadlock" }).getAttribute("href")).toBe(
      "/practice/attempts/attempt-2",
    );
  });

  it("says in words what became of each question", () => {
    render(
      <PracticeHistory
        page={historyPage({
          attempts: [
            attempt({
              outcomes: [
                outcome(),
                outcome({ position: 2, question_id: "question-2", is_correct: false }),
                outcome({ position: 3, question_id: "question-3", is_correct: null }),
              ],
            }),
          ],
        })}
      />,
    );

    expect(screen.getByText("You chose the expected answer")).toBeTruthy();
    expect(screen.getByText("Not the expected answer")).toBeTruthy();
    expect(screen.getByText("You did not answer this one")).toBeTruthy();
  });

  it("leaves the expected answer and the explanation to the result view", () => {
    const { container } = render(<PracticeHistory page={historyPage()} />);

    expect(container.textContent).not.toMatch(/1 KiB is 2\^10 bytes/);
    expect(container.textContent).not.toMatch(/Expected:/);
    expect(
      screen.getByRole("link", { name: /Open the full result/i }).getAttribute("href"),
    ).toBe("/practice/attempts/attempt-1");
  });

  it("opens the outcomes with no JavaScript, and keeps them closed to begin with", () => {
    const { container } = render(<PracticeHistory page={historyPage()} />);

    const details = container.querySelector("details");
    expect(details).not.toBeNull();
    expect(details?.hasAttribute("open")).toBe(false);
    expect(container.querySelector("summary")?.textContent).toMatch(/each question/i);
  });

  it("reads back nothing for an attempt that was never submitted", () => {
    const { container } = render(
      <PracticeHistory
        page={historyPage({
          attempts: [attempt({ status: "in_progress", submitted_at: null, evaluated_at: null })],
        })}
      />,
    );

    expect(screen.getByText(/never submitted/i)).toBeTruthy();
    expect(container.querySelector("details")).toBeNull();
    expect(container.textContent).not.toMatch(/You did not answer this one/);
  });

  it("offers a walk back to earlier quizzes and forward to more recent ones", () => {
    render(<PracticeHistory page={historyPage({ olderOffset: 20, newerOffset: 0 })} />);

    expect(screen.getByRole("link", { name: /Earlier quizzes/i }).getAttribute("href")).toBe(
      "/practice/history?offset=20",
    );
    expect(screen.getByRole("link", { name: /More recent quizzes/i }).getAttribute("href")).toBe(
      "/practice/history",
    );
  });

  it("offers no walk in a direction there is nothing in", () => {
    render(<PracticeHistory page={historyPage()} />);

    expect(screen.queryByRole("link", { name: /Earlier quizzes/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /More recent quizzes/i })).toBeNull();
  });

  it("distinguishes an empty first page from the end of the walk back", () => {
    const { rerender } = render(<PracticeHistory page={historyPage({ attempts: [] })} />);
    expect(screen.getByText(/None yet/i)).toBeTruthy();

    rerender(<PracticeHistory page={historyPage({ attempts: [], newerOffset: 0 })} />);
    expect(screen.getByText(/nothing further back/i)).toBeTruthy();
  });

  it("states no score, total, percentage, or count anywhere", () => {
    // The rule ADR-033 fixes, held for a page of attempts rather than one:
    // a history is a list of what happened, and nothing is added up.
    const { container } = render(
      <PracticeHistory
        page={historyPage({
          attempts: [
            attempt({
              outcomes: [
                outcome(),
                outcome({ position: 2, question_id: "question-2", is_correct: false }),
              ],
            }),
            attempt({ id: "attempt-2" }),
          ],
          olderOffset: 20,
          newerOffset: 0,
        })}
      />,
    );

    expect(container.textContent).not.toMatch(/%/);
    expect(container.textContent).not.toMatch(/\b\d+\s*(of|\/)\s*\d+\b/);
    expect(container.textContent).not.toMatch(
      /score|marks|out of|correct answers|streak|average|total/i,
    );
    // No page numbering either: numbering the pages counts them.
    expect(container.textContent).not.toMatch(/page \d+/i);
  });

  it("sets no attempt against another and ranks nothing", () => {
    const { container } = render(
      <PracticeHistory
        page={historyPage({ attempts: [attempt(), attempt({ id: "attempt-2" })] })}
      />,
    );

    expect(container.textContent).not.toMatch(/better|worse|improved|best|worst|progress|rank/i);
  });

  it("offers no control at all, because a record of what happened is not edited", () => {
    const { container } = render(<PracticeHistory page={historyPage()} />);

    expect(container.querySelector("button")).toBeNull();
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector("input")).toBeNull();
    expect(container.querySelector("select")).toBeNull();
  });
});
