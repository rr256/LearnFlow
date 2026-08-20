import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StudyQuestionForm } from "@/features/mentor/StudyQuestionForm";
import type { SubjectTopicOptions } from "@/features/resources/topic-options";

// The action is a server action in the running app; rendering the form must not
// call it, which is exactly what the first test below asserts.
vi.mock("@/features/mentor/actions", () => ({
  askStudyQuestionAction: vi.fn(async () => ({
    answer: null,
    error: null,
    topicId: null,
    question: "",
  })),
}));

const { askStudyQuestionAction } = await import("@/features/mentor/actions");

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

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

describe("StudyQuestionForm", () => {
  it("asks nothing when the page merely renders", () => {
    // The model is invoked because a learner submitted, and never otherwise.
    render(<StudyQuestionForm topicGroups={topicGroups} />);

    expect(askStudyQuestionAction).not.toHaveBeenCalled();
  });

  it("offers the curriculum's topics, grouped by subject", () => {
    render(<StudyQuestionForm topicGroups={topicGroups} />);

    expect(screen.getByLabelText("Topic")).toBeDefined();
    expect(screen.getByRole("option", { name: "CPU scheduling" })).toBeDefined();
    expect(screen.getByRole("option", { name: "Deadlock" })).toBeDefined();
  });

  it("offers one question field and nothing else", () => {
    const { container } = render(<StudyQuestionForm topicGroups={topicGroups} />);

    const names = Array.from(container.querySelectorAll("select, input, textarea")).map((field) =>
      field.getAttribute("name"),
    );

    expect(names).toEqual(["topic_id", "question"]);
  });

  it("submits through a server action rather than a GET", () => {
    // A question in the address would land in server logs and browser history.
    const { container } = render(<StudyQuestionForm topicGroups={topicGroups} />);

    const form = container.querySelector("form");
    expect(form?.getAttribute("method")).not.toBe("get");
    expect(form?.getAttribute("action")).not.toContain("?");
  });

  it("bounds the question as a courtesy", () => {
    const { container } = render(<StudyQuestionForm topicGroups={topicGroups} />);

    expect(container.querySelector("textarea")?.getAttribute("maxLength")).toBe("1000");
  });

  it("says what is sent, where it goes, and that nothing is stored", () => {
    const { container } = render(<StudyQuestionForm topicGroups={topicGroups} />);

    expect(container.textContent).toMatch(/running on this computer/i);
    expect(container.textContent).toMatch(/only when you ask/i);
    expect(container.textContent).toMatch(/nothing is stored/i);
  });

  it("says the rest of the learner's study is not sent", () => {
    const { container } = render(<StudyQuestionForm topicGroups={topicGroups} />);

    expect(container.textContent).toMatch(/plan, progress, or practice/i);
  });

  it("offers no model, provider, or temperature control", () => {
    // What a question is sent to is a deployment decision, not a learner's.
    const { container } = render(<StudyQuestionForm topicGroups={topicGroups} />);

    expect(container.textContent).not.toMatch(/\bmodel\b.*\bchoose\b|temperature/i);
    expect(container.querySelector('[name="model"]')).toBeNull();
  });

  it("uses the canonical screen name and not the reserved word", () => {
    // "Ask your notes" is the learner-facing name; *mentor* is reserved for a
    // broader capability that is not built, and survives only in the route and
    // the endpoint family. See docs/domain/terminology.md.
    const { container } = render(<StudyQuestionForm topicGroups={topicGroups} />);

    expect(screen.getByRole("button", { name: "Ask your notes" })).toBeDefined();
    expect(container.textContent).not.toMatch(/mentor/i);
  });

  it("says so when the curriculum could not be read", () => {
    const { container } = render(<StudyQuestionForm topicGroups={[]} />);

    expect(container.textContent).toMatch(/curriculum could not be read/i);
    expect(container.querySelector("select")).toBeNull();
    expect(container.querySelector("textarea")).toBeNull();
  });
});
