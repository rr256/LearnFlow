import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StudyAnswerView } from "@/features/mentor/StudyAnswerView";
import type { NotePassage } from "@/types/note-search";
import type { StudyAnswer } from "@/types/study-answer";

afterEach(cleanup);

const passage: NotePassage = {
  note_id: "note-1",
  note_title: "Round robin",
  resource_id: "resource-1",
  resource_title: "Operating Systems notes",
  resource_type: "note",
  topic_id: "topic-1",
  topic_name: "CPU scheduling",
  subject_name: "Operating Systems",
  passage: "Round robin gives each process a quantum, then moves it to the back.",
};

function answer(overrides: Partial<StudyAnswer> = {}): StudyAnswer {
  return {
    topic_id: "topic-1",
    topic_name: "CPU scheduling",
    subject_name: "Operating Systems",
    question: "How does round robin choose the next process?",
    outcome: "answered",
    answer: "Each process runs for one quantum and then goes to the back of the queue.",
    passages: [passage],
    ...overrides,
  };
}

describe("StudyAnswerView", () => {
  it("shows the answer and the passages it was grounded in together", () => {
    render(<StudyAnswerView answer={answer()} />);

    expect(screen.getByText(/one quantum and then goes to the back/)).toBeDefined();
    expect(screen.getByText(/moves it to the back/)).toBeDefined();
  });

  it("names where each passage came from", () => {
    const { container } = render(<StudyAnswerView answer={answer()} />);

    expect(container.textContent).toContain("Round robin");
    expect(container.textContent).toContain("Operating Systems notes");
  });

  it("echoes the question that was asked", () => {
    const { container } = render(<StudyAnswerView answer={answer()} />);

    expect(container.textContent).toContain("How does round robin choose the next process?");
  });

  it("says the answer came from a model and should be checked", () => {
    const { container } = render(<StudyAnswerView answer={answer()} />);

    expect(container.textContent).toMatch(/local AI model/i);
    expect(container.textContent).toMatch(/check it against them/i);
  });

  it("renders the answer as text, not as markup", () => {
    // A model's output is text arriving over a network like any other.
    const { container } = render(
      <StudyAnswerView
        answer={answer({ answer: "Use <script>alert(1)</script> and vector<int> here." })}
      />,
    );

    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>alert(1)</script>");
    expect(container.textContent).toContain("vector<int>");
  });

  it("renders a passage character for character", () => {
    const { container } = render(
      <StudyAnswerView
        answer={answer({ passages: [{ ...passage, passage: "Compare a < b in vector<int>." }] })}
      />,
    );

    expect(container.textContent).toContain("Compare a < b in vector<int>.");
  });

  it("numbers no citation and shows no figure of any kind", () => {
    // A number would imply the answer pointed at it, and nothing reads a marker
    // out of the prose.
    const { container } = render(<StudyAnswerView answer={answer()} />);

    expect(container.querySelector("ol")).toBeNull();
    expect(container.textContent).not.toMatch(/\b1 source\b|\bconfidence\b|\brelevance\b/i);
    expect(container.textContent).not.toMatch(/\[\d+\]/);
  });

  describe("when nothing was answered", () => {
    it("says no model was asked when the notes did not cover it", () => {
      const { container } = render(
        <StudyAnswerView
          answer={answer({ outcome: "no_matching_passage", answer: null, passages: [] })}
        />,
      );

      expect(container.textContent).toMatch(/do not mention this in words/i);
      expect(container.textContent).toMatch(/No AI model was asked/i);
    });

    it("tells the learner to write a note when nothing is linked", () => {
      const { container } = render(
        <StudyAnswerView
          answer={answer({ outcome: "no_linked_material", answer: null, passages: [] })}
        />,
      );

      expect(container.textContent).toMatch(/not linked any material/i);
      expect(container.textContent).toMatch(/No AI model was asked/i);
    });

    it("keeps the passages when the provider could not answer", () => {
      // The retrieval half succeeded and is worth reading on its own.
      const { container } = render(
        <StudyAnswerView answer={answer({ outcome: "provider_unavailable", answer: null })} />,
      );

      expect(container.textContent).toMatch(/could not be reached/i);
      expect(container.textContent).toContain("moves it to the back");
    });

    it("does not claim a model was declined when the provider failed", () => {
      // "Nothing was asked" and "it was asked and could not answer" are different
      // facts, and a learner needs to know which applies.
      const { container } = render(
        <StudyAnswerView answer={answer({ outcome: "provider_timed_out", answer: null })} />,
      );

      expect(container.textContent).toMatch(/did not answer in time/i);
      expect(container.textContent).not.toMatch(/No AI model was asked/i);
    });

    it("tells a timeout apart from an unreachable provider", () => {
      const { container } = render(
        <StudyAnswerView answer={answer({ outcome: "provider_unusable_reply", answer: null })} />,
      );

      expect(container.textContent).toMatch(/nothing usable/i);
    });

    it("reports an outcome it does not recognise rather than guessing", () => {
      const { container } = render(
        <StudyAnswerView answer={answer({ outcome: "something_new", answer: null })} />,
      );

      expect(container.textContent).toContain("something_new");
      expect(container.textContent).toMatch(/notes are unchanged/i);
    });
  });
});
