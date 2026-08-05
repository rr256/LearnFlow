import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The control imports the server action, which pulls in `next/cache`. A
// component test exercises the markup, not the write path; the action's own
// parsing is covered by tests/progress-submission.test.ts.
vi.mock("@/features/progress/actions", () => ({ saveTopicStage: vi.fn() }));

const { TopicStageControl } = await import("@/features/progress/TopicStageControl");

afterEach(cleanup);

describe("TopicStageControl", () => {
  it("labels the control with the topic it belongs to", () => {
    render(
      <TopicStageControl learningStage={null} topicId="t1" topicName="CPU scheduling" />,
    );

    expect(screen.getByRole("combobox", { name: /CPU scheduling/ })).toBeDefined();
  });

  it("offers all five stages by their learner-facing labels", () => {
    render(<TopicStageControl learningStage={null} topicId="t1" topicName="CPU scheduling" />);

    const options = screen.getAllByRole("option").map((node) => node.textContent);
    expect(options).toEqual([
      "Not explored",
      "Building foundation",
      "Developing confidence",
      "Practice-ready",
      "Strong understanding",
    ]);
  });

  it("shows a saved stage as the current selection", () => {
    render(
      <TopicStageControl learningStage="practice_ready" topicId="t1" topicName="Deadlock" />,
    );

    const select = screen.getByRole("combobox", { name: /Deadlock/ }) as HTMLSelectElement;
    expect(select.value).toBe("practice_ready");
  });

  it("falls back to Not explored when nothing has been recorded", () => {
    render(<TopicStageControl learningStage={null} topicId="t1" topicName="Deadlock" />);

    const select = screen.getByRole("combobox", { name: /Deadlock/ }) as HTMLSelectElement;
    expect(select.value).toBe("not_explored");
  });

  it("pairs a recorded stage with a next action rather than a verdict", () => {
    render(
      <TopicStageControl
        learningStage="developing_confidence"
        topicId="t1"
        topicName="Deadlock"
      />,
    );

    expect(screen.getByText(/focused practice/i)).toBeDefined();
  });

  it("carries the topic identifier in the submitted form", () => {
    const { container } = render(
      <TopicStageControl learningStage={null} topicId="t1" topicName="Deadlock" />,
    );

    const hidden = container.querySelector('input[name="topic_id"]') as HTMLInputElement;
    expect(hidden.value).toBe("t1");
  });

  it("submits through a button, so it works without JavaScript", () => {
    render(<TopicStageControl learningStage={null} topicId="t1" topicName="Deadlock" />);

    expect(screen.getByRole("button", { name: "Save" })).toBeDefined();
  });
});
