import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LearningProgramList } from "@/features/curriculum/LearningProgramList";
import type { LearningProgram } from "@/types/curriculum";

afterEach(cleanup);

function program(overrides: Partial<LearningProgram> & Pick<LearningProgram, "id">): LearningProgram {
  return {
    code: "gate-cse",
    name: "GATE Computer Science",
    description: null,
    active_curriculum_version: null,
    ...overrides,
  };
}

describe("LearningProgramList", () => {
  it("links each program to its own page using the program name", () => {
    render(<LearningProgramList programs={[program({ id: "abc" })]} />);

    const link = screen.getByRole("link", { name: "GATE Computer Science" });
    expect(link.getAttribute("href")).toBe("/curriculum/programs/abc");
  });

  it("reports a program with no published version rather than leaving it blank", () => {
    render(<LearningProgramList programs={[program({ id: "abc" })]} />);

    expect(screen.getByText("None published")).toBeDefined();
  });

  it("shows the active curriculum version label when there is one", () => {
    render(
      <LearningProgramList
        programs={[
          program({
            id: "abc",
            active_curriculum_version: {
              id: "v1",
              learning_program_id: "abc",
              version_label: "2027",
              status: "active",
              source_reference: null,
              published_at: null,
            },
          }),
        ]}
      />,
    );

    expect(screen.getByText("2027")).toBeDefined();
  });

  it("explains an empty collection and names the step that fills it", () => {
    render(<LearningProgramList programs={[]} />);

    expect(screen.getByRole("heading", { name: /No learning programs yet/i })).toBeDefined();
    expect(screen.getByText(/curriculum seed/i)).toBeDefined();
  });
});
