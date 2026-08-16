import { describe, expect, it } from "vitest";

import {
  isInCatalogue,
  resourcesByTopicId,
  resourcesFor,
} from "@/features/resources/by-topic";
import { INDENT, topicOptions } from "@/features/resources/topic-options";
import type { Subject } from "@/types/curriculum";
import type { LearningResource } from "@/types/resource";

function resource(overrides: Partial<LearningResource> = {}): LearningResource {
  return {
    id: `resource-${Math.random()}`,
    owner_learner_id: "learner-1",
    resource_type: "note",
    title: "Notes",
    source_label: "Shelf",
    external_reference: null,
    status: "registered",
    topics: [],
    ...overrides,
  };
}

function topic(id: string, name: string) {
  return { id, code: null, name, subject_id: "subject-1", subject_name: "Operating Systems" };
}

describe("resourcesByTopicId", () => {
  it("indexes material under each topic it covers", () => {
    const material = resource({
      topics: [topic("topic-1", "CPU scheduling"), topic("topic-2", "Deadlock")],
    });

    const index = resourcesByTopicId([material]);

    expect(resourcesFor(index, "topic-1")).toEqual([material]);
    expect(resourcesFor(index, "topic-2")).toEqual([material]);
  });

  it("returns an empty list for a topic nothing covers", () => {
    const index = resourcesByTopicId([resource()]);

    expect(resourcesFor(index, "topic-unknown")).toEqual([]);
  });

  it("leaves out material the learner put aside", () => {
    const index = resourcesByTopicId([
      resource({ status: "archived", topics: [topic("topic-1", "CPU scheduling")] }),
    ]);

    expect(resourcesFor(index, "topic-1")).toEqual([]);
  });

  it("keeps the API's order for a topic several pieces cover", () => {
    const first = resource({ title: "First", topics: [topic("topic-1", "CPU scheduling")] });
    const second = resource({ title: "Second", topics: [topic("topic-1", "CPU scheduling")] });

    const index = resourcesByTopicId([first, second]);

    expect(resourcesFor(index, "topic-1").map((entry) => entry.title)).toEqual([
      "First",
      "Second",
    ]);
  });

  it("treats a status this build does not recognise as not in the catalogue", () => {
    const index = resourcesByTopicId([
      resource({ status: "processing", topics: [topic("topic-1", "CPU scheduling")] }),
    ]);

    expect(resourcesFor(index, "topic-1")).toEqual([]);
  });
});

describe("isInCatalogue", () => {
  it("is true only for material the learner is using", () => {
    expect(isInCatalogue(resource())).toBe(true);
    expect(isInCatalogue(resource({ status: "archived" }))).toBe(false);
  });
});

describe("topicOptions", () => {
  const subjects: Subject[] = [
    {
      id: "subject-1",
      code: "operating-systems",
      name: "Operating Systems",
      description: null,
      position: 1,
      topics: [
        {
          id: "topic-1",
          code: null,
          name: "Processes",
          description: null,
          position: 1,
          is_trackable: false,
          subtopics: [
            {
              id: "topic-2",
              code: null,
              name: "CPU scheduling",
              description: null,
              position: 1,
              is_trackable: true,
              subtopics: [],
            },
          ],
        },
      ],
    },
    {
      id: "subject-2",
      code: "empty",
      name: "A subject with no topics",
      description: null,
      position: 2,
      topics: [],
    },
  ];

  it("groups every topic under the subject it belongs to", () => {
    const groups = topicOptions(subjects);

    expect(groups).toHaveLength(1);
    expect(groups[0]?.subjectName).toBe("Operating Systems");
    expect(groups[0]?.topics.map((entry) => entry.id)).toEqual(["topic-1", "topic-2"]);
  });

  it("offers a grouping topic as well as a trackable one", () => {
    const labels = topicOptions(subjects)[0]?.topics.map((entry) => entry.label.trim());

    expect(labels).toContain("Processes");
    expect(labels).toContain("CPU scheduling");
  });

  it("marks a subtopic's depth by indenting its label", () => {
    const topics = topicOptions(subjects)[0]?.topics ?? [];

    expect(topics[0]?.label).toBe("Processes");
    expect(topics[1]?.label).toBe(`${INDENT}CPU scheduling`);
  });

  it("indents with no-break spaces, which an option label does not collapse", () => {
    const topics = topicOptions(subjects)[0]?.topics ?? [];

    // An ordinary leading space is collapsed inside an `<option>`, so the
    // indent would vanish in the one control it exists for.
    expect(INDENT).toBe("  ");
    expect(topics[1]?.label.startsWith(" ")).toBe(true);
  });

  it("leaves out a subject with no topics", () => {
    expect(topicOptions(subjects).map((group) => group.subjectId)).not.toContain("subject-2");
  });

  it("keeps the syllabus order rather than sorting", () => {
    const reversed = [...subjects].reverse();

    expect(topicOptions(reversed).map((group) => group.subjectName)).toEqual([
      "Operating Systems",
    ]);
  });
});
