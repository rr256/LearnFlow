import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TopicNoteSearchForm } from "@/features/resources/TopicNoteSearchForm";
import type { SubjectTopicOptions } from "@/features/resources/topic-options";

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

describe("TopicNoteSearchForm", () => {
  it("offers the curriculum's topics, grouped by subject", () => {
    render(<TopicNoteSearchForm topicGroups={topicGroups} />);

    expect(screen.getByLabelText("Topic")).toBeDefined();
    expect(screen.getByRole("option", { name: "CPU scheduling" })).toBeDefined();
    expect(screen.getByRole("option", { name: "Deadlock" })).toBeDefined();
  });

  it("submits as a GET so a search writes nothing", () => {
    // A read needs no server action: submitting puts the topic in the address,
    // which is also what makes a result reloadable and bookmarkable.
    const { container } = render(<TopicNoteSearchForm topicGroups={topicGroups} />);

    const form = container.querySelector("form");
    expect(form?.getAttribute("method")).toBe("get");
    expect(form?.getAttribute("action")).toBe("/resources/search");
  });

  it("sends the topic and nothing else", () => {
    const { container } = render(<TopicNoteSearchForm topicGroups={topicGroups} />);

    const names = Array.from(container.querySelectorAll("select, input")).map((field) =>
      field.getAttribute("name"),
    );

    expect(names).toEqual(["topic_id"]);
  });

  it("offers no free-text query field", () => {
    // The topic is the query. A typed query is a different feature.
    const { container } = render(<TopicNoteSearchForm topicGroups={topicGroups} />);

    expect(container.querySelector('input[type="text"]')).toBeNull();
    expect(container.querySelector('input[type="search"]')).toBeNull();
    expect(container.querySelector("textarea")).toBeNull();
  });

  it("keeps the topic the learner already asked about", () => {
    const { container } = render(
      <TopicNoteSearchForm selectedTopicId="topic-2" topicGroups={topicGroups} />,
    );

    expect(container.querySelector<HTMLSelectElement>("select")?.value).toBe("topic-2");
  });

  it("says who reads the notes and when", () => {
    // The privacy position: not "nothing reads it", but which reader, where it
    // runs, and when.
    const { container } = render(<TopicNoteSearchForm topicGroups={topicGroups} />);

    expect(container.textContent).toMatch(/searched on this computer/i);
    expect(container.textContent).toMatch(/only when you ask/i);
  });

  it("says no AI model is involved in this search, without claiming none ever reads a note", () => {
    // MNT-001 made the older, broader promise false: a model does read matching
    // passages when the learner asks a question. The claim is now scoped to this
    // search, and points at where the other reader is.
    const { container } = render(<TopicNoteSearchForm topicGroups={topicGroups} />);

    expect(container.textContent).toMatch(/this search involves no AI model/i);
    expect(container.textContent).not.toMatch(/no AI model reads them/i);
  });

  it("says so when the curriculum could not be read", () => {
    const { container } = render(<TopicNoteSearchForm topicGroups={[]} />);

    expect(container.textContent).toMatch(/curriculum could not be read/i);
    expect(container.querySelector("select")).toBeNull();
  });
});
