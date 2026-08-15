import { describe, expect, it } from "vitest";

import { selectStagesBySubject } from "@/features/progress/subject-stages";
import type { Subject, Topic } from "@/types/curriculum";
import type { TopicProgress } from "@/types/progress";

function topic(id: string, name: string, overrides: Partial<Topic> = {}): Topic {
  return {
    id,
    code: null,
    name,
    description: null,
    position: 1,
    is_trackable: true,
    subtopics: [],
    ...overrides,
  };
}

function subject(id: string, name: string, topics: Topic[], code = "CS-OS"): Subject {
  return { id, code, name, description: null, position: 1, topics };
}

function record(overrides: {
  topicId: string;
  topicName: string;
  subjectId: string;
  stage?: string;
  code?: string | null;
}): TopicProgress {
  return {
    id: `progress-${overrides.topicId}`,
    learner_id: "learner-1",
    learning_stage: overrides.stage ?? "building_foundation",
    stage_source: "learner",
    topic: {
      id: overrides.topicId,
      code: overrides.code ?? null,
      name: overrides.topicName,
      is_trackable: true,
      subject_id: overrides.subjectId,
      curriculum_version_id: "version-1",
    },
  };
}

describe("selectStagesBySubject", () => {
  it("gathers the recorded stages under the subject each topic belongs to", () => {
    const subjects = [
      subject("subject-os", "Operating Systems", [topic("topic-1", "CPU scheduling")]),
      subject("subject-db", "Databases", [topic("topic-2", "Normalisation")], "CS-DB"),
    ];
    const records = [
      record({ topicId: "topic-2", topicName: "Normalisation", subjectId: "subject-db" }),
      record({ topicId: "topic-1", topicName: "CPU scheduling", subjectId: "subject-os" }),
    ];

    const groups = selectStagesBySubject(records, subjects);

    expect(groups.map((group) => group.name)).toEqual(["Operating Systems", "Databases"]);
    expect(groups[0]?.topics.map((each) => each.name)).toEqual(["CPU scheduling"]);
    expect(groups[1]?.topics.map((each) => each.name)).toEqual(["Normalisation"]);
  });

  it("keeps the curriculum's own subject order, not the order the records arrived in", () => {
    /* PRG-002 returns newest first, which is not an order to show a syllabus in.
     * Subjects and topics arrive from CUR-003 in the order the syllabus teaches
     * them, and this renders that order rather than sorting by one of its own
     * (docs/development/coding-standards.md#ui-responsibilities). */
    const subjects = [
      subject("subject-os", "Operating Systems", [topic("topic-1", "CPU scheduling")]),
      subject("subject-db", "Databases", [topic("topic-2", "Normalisation")], "CS-DB"),
    ];
    const records = [
      record({ topicId: "topic-2", topicName: "Normalisation", subjectId: "subject-db" }),
      record({ topicId: "topic-1", topicName: "CPU scheduling", subjectId: "subject-os" }),
    ];

    expect(selectStagesBySubject(records, subjects).map((group) => group.id)).toEqual([
      "subject-os",
      "subject-db",
    ]);
  });

  it("keeps the curriculum's own topic order within a subject", () => {
    const subjects = [
      subject("subject-os", "Operating Systems", [
        topic("topic-1", "Processes"),
        topic("topic-2", "CPU scheduling"),
        topic("topic-3", "Deadlock"),
      ]),
    ];
    const records = [
      record({ topicId: "topic-3", topicName: "Deadlock", subjectId: "subject-os" }),
      record({ topicId: "topic-1", topicName: "Processes", subjectId: "subject-os" }),
    ];

    expect(selectStagesBySubject(records, subjects)[0]?.topics.map((each) => each.name)).toEqual([
      "Processes",
      "Deadlock",
    ]);
  });

  it("finds a topic recorded against a subtopic, at any depth", () => {
    const subjects = [
      subject("subject-os", "Operating Systems", [
        topic("topic-1", "Memory management", {
          is_trackable: false,
          subtopics: [topic("topic-2", "Paging", { subtopics: [topic("topic-3", "TLB")] })],
        }),
      ]),
    ];
    const records = [record({ topicId: "topic-3", topicName: "TLB", subjectId: "subject-os" })];

    expect(selectStagesBySubject(records, subjects)[0]?.topics.map((each) => each.name)).toEqual([
      "TLB",
    ]);
  });

  it("shows the label a learner reads rather than the value the API sent", () => {
    const subjects = [subject("subject-os", "Operating Systems", [topic("topic-1", "Deadlock")])];
    const records = [
      record({
        topicId: "topic-1",
        topicName: "Deadlock",
        subjectId: "subject-os",
        stage: "strong_understanding",
      }),
    ];

    expect(selectStagesBySubject(records, subjects)[0]?.topics[0]?.stageLabel).toBe(
      "Strong understanding",
    );
  });

  it("leaves out a subject the learner has recorded nothing in", () => {
    /* Shown as empty it would invite a count beside the name, which is the
     * measurement of a learner that terminology forbids. */
    const subjects = [
      subject("subject-os", "Operating Systems", [topic("topic-1", "CPU scheduling")]),
      subject("subject-db", "Databases", [topic("topic-2", "Normalisation")], "CS-DB"),
    ];
    const records = [
      record({ topicId: "topic-1", topicName: "CPU scheduling", subjectId: "subject-os" }),
    ];

    expect(selectStagesBySubject(records, subjects).map((group) => group.name)).toEqual([
      "Operating Systems",
    ]);
  });

  it("leaves out a topic the learner has recorded nothing against", () => {
    /* A topic with no record reads as *Not explored*, the neutral starting
     * state, and is left where it is in the curriculum view. */
    const subjects = [
      subject("subject-os", "Operating Systems", [
        topic("topic-1", "CPU scheduling"),
        topic("topic-2", "Deadlock"),
      ]),
    ];
    const records = [
      record({ topicId: "topic-1", topicName: "CPU scheduling", subjectId: "subject-os" }),
    ];

    expect(selectStagesBySubject(records, subjects)[0]?.topics.map((each) => each.name)).toEqual([
      "CPU scheduling",
    ]);
  });

  it("returns nothing at all for a learner who has recorded no stage", () => {
    const subjects = [subject("subject-os", "Operating Systems", [topic("topic-1", "Deadlock")])];

    expect(selectStagesBySubject([], subjects)).toEqual([]);
  });

  it("leaves out a stage this build does not recognise", () => {
    /* The same handling `stagesByTopicId` gives one: skipped rather than shown
     * raw, because a `snake_case` identifier is not something to show a
     * learner and the API's catalogue could gain a value first. */
    const subjects = [subject("subject-os", "Operating Systems", [topic("topic-1", "Deadlock")])];
    const records = [
      record({
        topicId: "topic-1",
        topicName: "Deadlock",
        subjectId: "subject-os",
        stage: "exam_ready",
      }),
    ];

    expect(selectStagesBySubject(records, subjects)).toEqual([]);
  });

  it("keeps a record whose topic the curriculum no longer holds, under its own heading", () => {
    /* A re-seed can drop a topic a learner had already recorded. Dropping the
     * record from the screen would under-report what is stored. */
    const subjects = [subject("subject-os", "Operating Systems", [topic("topic-1", "Deadlock")])];
    const records = [
      record({ topicId: "topic-1", topicName: "Deadlock", subjectId: "subject-os" }),
      record({ topicId: "topic-gone", topicName: "A retired topic", subjectId: "subject-os" }),
    ];

    const groups = selectStagesBySubject(records, subjects);

    expect(groups.map((group) => group.name)).toEqual([
      "Operating Systems",
      "Topics no longer in your curriculum",
    ]);
    expect(groups[1]?.topics.map((each) => each.name)).toEqual(["A retired topic"]);
    expect(groups[1]?.code).toBeNull();
  });

  it("records one topic once, however many times it was returned", () => {
    const subjects = [subject("subject-os", "Operating Systems", [topic("topic-1", "Deadlock")])];
    const records = [
      record({ topicId: "topic-1", topicName: "Deadlock", subjectId: "subject-os" }),
      record({
        topicId: "topic-1",
        topicName: "Deadlock",
        subjectId: "subject-os",
        stage: "practice_ready",
      }),
    ];

    expect(selectStagesBySubject(records, subjects)[0]?.topics).toHaveLength(1);
  });

  it("does not order or group the topics of a subject by stage", () => {
    /* Nothing in LearnFlow compares two stages. Ordering by one would say a
     * topic at *Building foundation* is behind one at *Practice-ready*. */
    const subjects = [
      subject("subject-os", "Operating Systems", [
        topic("topic-1", "Processes"),
        topic("topic-2", "Deadlock"),
      ]),
    ];
    const records = [
      record({
        topicId: "topic-1",
        topicName: "Processes",
        subjectId: "subject-os",
        stage: "strong_understanding",
      }),
      record({
        topicId: "topic-2",
        topicName: "Deadlock",
        subjectId: "subject-os",
        stage: "not_explored",
      }),
    ];

    expect(selectStagesBySubject(records, subjects)[0]?.topics.map((each) => each.name)).toEqual([
      "Processes",
      "Deadlock",
    ]);
  });
});
