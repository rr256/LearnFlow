import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurriculumTree as CurriculumTreeData, Subject, Topic } from "@/types/curriculum";
import type { LearningStage } from "@/types/progress";

// The tree renders the stage control, which imports the server action and so
// pulls in `next/cache`. The control's own markup is covered by
// tests/TopicStageControl.test.tsx.
vi.mock("@/features/progress/actions", () => ({ saveTopicStage: vi.fn() }));

const { CurriculumTree } = await import("@/features/curriculum/CurriculumTree");

afterEach(cleanup);

function topic(overrides: Partial<Topic> & Pick<Topic, "id" | "name">): Topic {
  return {
    code: null,
    description: null,
    position: 1,
    is_trackable: true,
    subtopics: [],
    ...overrides,
  };
}

function subject(overrides: Partial<Subject> & Pick<Subject, "id" | "name">): Subject {
  return {
    code: "SUB",
    description: null,
    position: 1,
    topics: [],
    ...overrides,
  };
}

function tree(overrides: Partial<CurriculumTreeData> = {}): CurriculumTreeData {
  return {
    curriculum_version: {
      id: "11111111-1111-4111-8111-111111111111",
      learning_program_id: "22222222-2222-4222-8222-222222222222",
      version_label: "2027",
      status: "active",
      source_reference: null,
      published_at: null,
    },
    subjects: [],
    topic_relationships: [],
    ...overrides,
  };
}

describe("CurriculumTree", () => {
  it("renders subjects, their topics, and nested subtopics", () => {
    render(
      <CurriculumTree
        tree={tree({
          subjects: [
            subject({
              id: "s1",
              code: "OS",
              name: "Operating System",
              topics: [
                topic({
                  id: "t1",
                  name: "Memory management",
                  subtopics: [topic({ id: "t2", name: "Virtual memory" })],
                }),
              ],
            }),
          ],
        })}
      />,
    );

    const heading = screen.getByRole("heading", { name: /Operating System/ });
    expect(heading.tagName).toBe("H3");

    const memoryManagement = screen.getByText("Memory management").closest("li");
    expect(memoryManagement).not.toBeNull();
    expect(within(memoryManagement as HTMLElement).getByText("Virtual memory")).toBeDefined();
  });

  it("says in words that a grouping topic holds no progress of its own", () => {
    render(
      <CurriculumTree
        tree={tree({
          subjects: [
            subject({
              id: "s1",
              name: "Algorithms",
              topics: [topic({ id: "t1", name: "Sorting", is_trackable: false })],
            }),
          ],
        })}
      />,
    );

    expect(screen.getByText("(grouping only)")).toBeDefined();
  });

  it("preserves the order the backend returned rather than re-sorting", () => {
    render(
      <CurriculumTree
        tree={tree({
          subjects: [
            subject({ id: "s1", code: "B", name: "Zebra subject", position: 1 }),
            subject({ id: "s2", code: "A", name: "Alpha subject", position: 2 }),
          ],
        })}
      />,
    );

    const headings = screen.getAllByRole("heading", { level: 3 }).map((node) => node.textContent);
    expect(headings).toEqual(["B Zebra subject", "A Alpha subject"]);
  });

  it("names both topics of a relationship instead of showing identifiers", () => {
    render(
      <CurriculumTree
        tree={tree({
          subjects: [
            subject({
              id: "s1",
              name: "Algorithms",
              topics: [topic({ id: "t1", name: "Recursion" }), topic({ id: "t2", name: "Trees" })],
            }),
          ],
          topic_relationships: [
            { source_topic_id: "t1", target_topic_id: "t2", relationship_type: "recommended_before" },
          ],
        })}
      />,
    );

    const relationships = screen.getByRole("region", { name: "Topic relationships" });
    const entry = within(relationships).getByRole("listitem");
    expect(entry.textContent).toBe("Recursion — recommended before — Trees");
  });

  it("explains an empty curriculum version instead of rendering nothing", () => {
    render(<CurriculumTree tree={tree()} />);

    expect(screen.getByRole("heading", { name: /no subjects yet/i })).toBeDefined();
  });
});

describe("CurriculumTree with recorded progress", () => {
  const withTopics = (topics: Topic[]) =>
    tree({ subjects: [subject({ id: "s1", name: "Operating System", topics })] });

  const stages = (entries: [string, LearningStage][]) => new Map<string, LearningStage>(entries);

  it("shows the saved stage beside a trackable topic", () => {
    render(
      <CurriculumTree
        stages={stages([["t1", "practice_ready"]])}
        tree={withTopics([topic({ id: "t1", name: "CPU scheduling" })])}
      />,
    );

    const select = screen.getByRole("combobox", { name: /CPU scheduling/ }) as HTMLSelectElement;
    expect(select.value).toBe("practice_ready");
  });

  it("shows Not explored for a topic the learner has recorded nothing against", () => {
    render(
      <CurriculumTree
        stages={stages([])}
        tree={withTopics([topic({ id: "t1", name: "CPU scheduling" })])}
      />,
    );

    const select = screen.getByRole("combobox", { name: /CPU scheduling/ }) as HTMLSelectElement;
    expect(select.value).toBe("not_explored");
  });

  it("offers no control on a grouping topic, matching what PRG-004 refuses", () => {
    render(
      <CurriculumTree
        stages={stages([])}
        tree={withTopics([topic({ id: "t1", name: "Deadlock", is_trackable: false })])}
      />,
    );

    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.getByText("(grouping only)")).toBeDefined();
  });

  it("offers a control on a nested subtopic as well as a root topic", () => {
    render(
      <CurriculumTree
        stages={stages([])}
        tree={withTopics([
          topic({
            id: "t1",
            name: "Memory management",
            is_trackable: false,
            subtopics: [topic({ id: "t2", name: "Virtual memory" })],
          }),
        ])}
      />,
    );

    expect(screen.getByRole("combobox", { name: /Virtual memory/ })).toBeDefined();
    expect(screen.getAllByRole("combobox")).toHaveLength(1);
  });

  it("renders the syllabus without controls when no stages are supplied", () => {
    render(<CurriculumTree tree={withTopics([topic({ id: "t1", name: "CPU scheduling" })])} />);

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("still renders the syllabus when progress could not be read", () => {
    render(
      <CurriculumTree
        stages={null}
        tree={withTopics([topic({ id: "t1", name: "CPU scheduling" })])}
      />,
    );

    expect(screen.getByText("CPU scheduling")).toBeDefined();
    expect(screen.queryByRole("combobox")).toBeNull();
  });
});
