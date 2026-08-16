import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TopicResources } from "@/features/resources/TopicResources";
import type { LearningResource } from "@/types/resource";

afterEach(cleanup);

function resource(overrides: Partial<LearningResource> = {}): LearningResource {
  return {
    id: `resource-${Math.random()}`,
    owner_learner_id: "learner-1",
    resource_type: "pyq",
    title: "Scheduling PYQs 2015–2025",
    source_label: null,
    external_reference: "https://example.test/pyq.pdf",
    status: "registered",
    topics: [],
    ...overrides,
  };
}

describe("TopicResources", () => {
  it("lists the material the learner linked to the topic", () => {
    render(<TopicResources resources={[resource()]} topicName="CPU scheduling" />);

    expect(screen.getByRole("link", { name: "Scheduling PYQs 2015–2025" })).toBeDefined();
  });

  it("labels the list with the topic, so several on a page stay distinguishable", () => {
    render(<TopicResources resources={[resource()]} topicName="CPU scheduling" />);

    expect(screen.getByRole("list", { name: "Your material for CPU scheduling" })).toBeDefined();
  });

  it("names the kind of material in words", () => {
    render(<TopicResources resources={[resource()]} topicName="CPU scheduling" />);

    expect(screen.getByText("PYQs")).toBeDefined();
  });

  it("shows offline material as text, with where it is", () => {
    render(
      <TopicResources
        resources={[
          resource({
            title: "Kanodia operating systems",
            external_reference: null,
            source_label: "Printed book on the shelf",
          }),
        ]}
        topicName="CPU scheduling"
      />,
    );

    expect(screen.getByText("Kanodia operating systems")).toBeDefined();
    expect(screen.getByText(/Printed book on the shelf/)).toBeDefined();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("renders nothing for a topic the learner has linked nothing to", () => {
    const { container } = render(<TopicResources resources={[]} topicName="CPU scheduling" />);

    expect(container.textContent).toBe("");
  });

  it("suggests no material of its own", () => {
    const { container } = render(<TopicResources resources={[]} topicName="CPU scheduling" />);

    const text = (container.textContent ?? "").toLowerCase();
    expect(text).not.toContain("recommend");
    expect(text).not.toContain("suggest");
  });

  it("offers no control: adding and putting material aside live elsewhere", () => {
    render(<TopicResources resources={[resource()]} topicName="CPU scheduling" />);

    expect(screen.queryByRole("button")).toBeNull();
    expect(document.querySelector("form")).toBeNull();
  });

  it("counts nothing beside the topic", () => {
    render(
      <TopicResources
        resources={[resource({ title: "One" }), resource({ title: "Two" })]}
        topicName="CPU scheduling"
      />,
    );

    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\b2\b/);
    expect(text).not.toMatch(/%/);
  });

  it("keeps the order the API returned rather than sorting", () => {
    render(
      <TopicResources
        resources={[resource({ title: "Second added" }), resource({ title: "First added" })]}
        topicName="CPU scheduling"
      />,
    );

    const items = screen.getAllByRole("listitem").map((item) => item.textContent ?? "");
    expect(items[0]).toContain("Second added");
    expect(items[1]).toContain("First added");
  });
});
