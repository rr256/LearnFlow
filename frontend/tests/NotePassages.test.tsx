import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { NotePassages } from "@/features/resources/NotePassages";
import type { NotePassage, TopicNoteSearch } from "@/types/note-search";

afterEach(cleanup);

function passage(overrides: Partial<NotePassage> = {}): NotePassage {
  return {
    note_id: `note-${Math.random()}`,
    note_title: "Round robin",
    resource_id: "resource-1",
    resource_title: "Operating Systems notes",
    resource_type: "note",
    topic_id: "topic-1",
    topic_name: "CPU scheduling",
    subject_name: "Operating Systems",
    passage: "Round robin scheduling gives each process a quantum.",
    ...overrides,
  };
}

function result(overrides: Partial<TopicNoteSearch> = {}): TopicNoteSearch {
  return {
    topic_id: "topic-1",
    topic_name: "CPU scheduling",
    subject_name: "Operating Systems",
    outcome: "found",
    passages: [passage()],
    ...overrides,
  };
}

/** The paragraph a passage's text is displayed in, matched exactly. */
function displayed(container: HTMLElement, text: string): HTMLParagraphElement | undefined {
  return Array.from(container.querySelectorAll("p")).find((p) => p.textContent === text);
}

describe("NotePassages", () => {
  it("shows the learner's own words", () => {
    const { container } = render(<NotePassages result={result()} />);

    expect(
      displayed(container, "Round robin scheduling gives each process a quantum."),
    ).toBeDefined();
  });

  it("names the note, the material, and the topic context beside each passage", () => {
    render(<NotePassages result={result()} />);

    expect(screen.getByText("Round robin")).toBeDefined();
    expect(screen.getByText(/Operating Systems notes/)).toBeDefined();
    expect(screen.getByText(/Operating Systems · CPU scheduling/)).toBeDefined();
  });

  it("renders a passage containing markup as text rather than as elements", () => {
    // React escapes an interpolated string, and nothing here calls
    // dangerouslySetInnerHTML, so a tag in a learner's note is read, not run.
    const pasted = '<script>alert("x")</script><b>bold?</b>';

    const { container } = render(
      <NotePassages result={result({ passages: [passage({ passage: pasted })] })} />,
    );

    expect(displayed(container, pasted)).toBeDefined();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
  });

  it("keeps a passage's line breaks in the text rather than inserting markup", () => {
    const pasted = "Step one:\n\n    indented\n\nStep two.";

    const { container } = render(
      <NotePassages result={result({ passages: [passage({ passage: pasted })] })} />,
    );

    expect(displayed(container, pasted)).toBeDefined();
    expect(container.querySelector("br")).toBeNull();
  });

  it("renders code-like text exactly, including angle brackets", () => {
    // The regression this rewrite exists for. An earlier build rendered the
    // passage through `ts_headline`, whose parser dropped `<int>`.
    const code = "Scheduling: std::vector<int> ready; if (a < b) swap(a, b);";

    const { container } = render(
      <NotePassages result={result({ passages: [passage({ passage: code })] })} />,
    );

    const shown = displayed(container, code);
    expect(shown).toBeDefined();
    expect(shown?.textContent).toBe(code);
    // The brackets are text, not elements.
    expect(container.querySelector("int")).toBeNull();
    expect(container.querySelector("em")).toBeNull();
  });

  it("shows a passage character for character, whatever it contains", () => {
    const awkward = 'A <em>tag</em>, an entity &amp;, a quote " and a backslash \.';

    const { container } = render(
      <NotePassages result={result({ passages: [passage({ passage: awkward })] })} />,
    );

    expect(displayed(container, awkward)?.textContent).toBe(awkward);
    expect(container.querySelector("em")).toBeNull();
  });

  it("joins nothing, so no separator can appear inside a passage", () => {
    // One contiguous window: a joined passage would carry a character the
    // learner never wrote.
    const { container } = render(<NotePassages result={result()} />);

    const shown = container.querySelector("p")?.textContent ?? "";
    expect(shown).not.toContain("…");
    expect(shown).not.toContain("...");
  });

  it("shows no relevance figure, number, or bar", () => {
    const { container } = render(
      <NotePassages
        result={result({
          passages: [passage({ note_title: "First" }), passage({ note_title: "Second" })],
        })}
      />,
    );

    expect(container.textContent).not.toMatch(/\b\d+\s*%/);
    expect(container.textContent).not.toMatch(/relevance|score|rank|match strength/i);
    expect(container.querySelector("progress")).toBeNull();
    expect(container.querySelector("meter")).toBeNull();
  });

  it("counts nothing", () => {
    const { container } = render(
      <NotePassages
        result={result({
          passages: [passage(), passage({ note_title: "Second" }), passage({ note_title: "Third" })],
        })}
      />,
    );

    // No "3 passages", no "3 results", no numbering of entries.
    expect(container.textContent).not.toMatch(/\b3\b/);
    expect(container.querySelector("ol")).toBeNull();
  });

  it("keeps the order the API returned", () => {
    const { container } = render(
      <NotePassages
        result={result({
          passages: [
            passage({ note_title: "First back", passage: "Alpha." }),
            passage({ note_title: "Second back", passage: "Beta." }),
          ],
        })}
      />,
    );

    const shown = Array.from(container.querySelectorAll("li")).map((li) => li.textContent ?? "");
    expect(shown[0]).toContain("Alpha.");
    expect(shown[1]).toContain("Beta.");
  });

  it("says it generated nothing", () => {
    const { container } = render(<NotePassages result={result()} />);

    expect(container.textContent).toMatch(/Nothing here was written or rewritten by LearnFlow/i);
  });

  it("is read-only", () => {
    const { container } = render(<NotePassages result={result()} />);

    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector("button")).toBeNull();
    expect(container.querySelector("input")).toBeNull();
  });

  describe("when nothing was found", () => {
    it("tells apart having linked no material", () => {
      const { container } = render(
        <NotePassages result={result({ outcome: "no_linked_material", passages: [] })} />,
      );

      expect(container.textContent).toMatch(/not linked any material/i);
    });

    it("tells apart having linked material but written no note", () => {
      const { container } = render(
        <NotePassages result={result({ outcome: "no_active_notes", passages: [] })} />,
      );

      expect(container.textContent).toMatch(/no notes on it yet/i);
    });

    it("tells apart notes that do not mention the topic", () => {
      const { container } = render(
        <NotePassages result={result({ outcome: "no_matching_passage", passages: [] })} />,
      );

      expect(container.textContent).toMatch(/do not mention it in words/i);
      // And says plainly that this is not a judgement about the notes.
      expect(container.textContent).toMatch(/not a judgement/i);
    });

    it("reports an outcome it does not recognise rather than guessing", () => {
      const { container } = render(
        <NotePassages result={result({ outcome: "reindexing", passages: [] })} />,
      );

      expect(container.textContent).toMatch(/reindexing/);
      expect(container.textContent).toMatch(/notes are unchanged/i);
    });
  });
});
