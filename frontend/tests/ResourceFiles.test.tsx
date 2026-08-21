import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ResourceFiles } from "@/features/resources/ResourceFiles";
import { MAX_FILES_PER_RESOURCE, type ResourceFile } from "@/types/resource-file";

vi.mock("@/features/resources/file-actions", () => ({
  uploadResourceFileAction: vi.fn(async () => ({ stored: null, error: null })),
  setResourceFileStatusAction: vi.fn(async () => ({ error: null })),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function file(overrides: Partial<ResourceFile> = {}): ResourceFile {
  return {
    id: "file-1",
    resource_id: "resource-1",
    original_filename: "Chapter 3.pdf",
    byte_size: 1024 * 900,
    page_count: 12,
    content_type: "application/pdf",
    checksum: "a".repeat(64),
    status: "active",
    created_at: null,
    updated_at: null,
    ...overrides,
  };
}

describe("ResourceFiles", () => {
  it("lists a stored PDF with what it is", () => {
    const { container } = render(
      <ResourceFiles files={[file()]} resourceId="resource-1" writable />,
    );

    expect(container.textContent).toContain("Chapter 3.pdf");
    expect(container.textContent).toContain("900 KB");
    expect(container.textContent).toContain("12 pages");
  });

  it("offers a download through LearnFlow's own route, not the backend", () => {
    const { container } = render(
      <ResourceFiles files={[file()]} resourceId="resource-1" writable />,
    );

    const link = container.querySelector<HTMLAnchorElement>("a[download]");
    expect(link?.getAttribute("href")).toBe("/resources/files/file-1");
    // No API address is ever browser-visible.
    expect(container.innerHTML).not.toContain("8000");
    expect(container.innerHTML).not.toContain("/api/v1");
  });

  it("offers a file input that accepts PDFs only", () => {
    const { container } = render(<ResourceFiles files={[]} resourceId="resource-1" writable />);

    const input = container.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input?.getAttribute("name")).toBe("file");
    expect(input?.getAttribute("accept")).toContain("pdf");
  });

  it("posts as multipart so a file can travel", () => {
    const { container } = render(<ResourceFiles files={[]} resourceId="resource-1" writable />);

    expect(container.querySelector("form")?.getAttribute("encType")).toBe("multipart/form-data");
  });

  it("carries the resource it belongs to", () => {
    const { container } = render(<ResourceFiles files={[]} resourceId="resource-9" writable />);

    expect(
      container.querySelector<HTMLInputElement>('input[name="resource_id"]')?.value,
    ).toBe("resource-9");
  });

  it("says where the file is kept and that nothing reads it", () => {
    const { container } = render(<ResourceFiles files={[]} resourceId="resource-1" writable />);

    expect(container.textContent).toMatch(/stored on this computer/i);
    expect(container.textContent).toMatch(/never sent anywhere/i);
    expect(container.textContent).toMatch(/no AI model sees it/i);
  });

  it("names the limits a learner would otherwise hit blindly", () => {
    const { container } = render(<ResourceFiles files={[]} resourceId="resource-1" writable />);

    expect(container.textContent).toContain("25.0 MB");
    expect(container.textContent).toContain("1500 pages");
    expect(container.textContent).toMatch(/password-protected/i);
  });

  it("says so when nothing is stored yet", () => {
    const { container } = render(<ResourceFiles files={[]} resourceId="resource-1" writable />);

    expect(container.textContent).toMatch(/no PDFs are stored/i);
  });

  // -- the lifecycle ----------------------------------------------------------

  it("offers to set an active file aside", () => {
    render(<ResourceFiles files={[file()]} resourceId="resource-1" writable />);

    expect(screen.getByRole("button", { name: "Set this PDF aside" })).toBeDefined();
  });

  it("offers to bring an archived file back", () => {
    render(
      <ResourceFiles files={[file({ status: "archived" })]} resourceId="resource-1" writable />,
    );

    expect(screen.getByRole("button", { name: "Bring this PDF back" })).toBeDefined();
  });

  it("marks an archived file in words rather than by colour", () => {
    const { container } = render(
      <ResourceFiles files={[file({ status: "archived" })]} resourceId="resource-1" writable />,
    );

    expect(container.textContent).toContain("Set aside");
  });

  it("still lists and still offers an archived file for download", () => {
    // Setting material aside hides it; it does not withhold it.
    const { container } = render(
      <ResourceFiles files={[file({ status: "archived" })]} resourceId="resource-1" writable />,
    );

    expect(container.querySelector("a[download]")?.getAttribute("href")).toBe(
      "/resources/files/file-1",
    );
  });

  it("offers no way to delete anything", () => {
    // Nothing in LearnFlow removes a stored file: there is no endpoint behind
    // such a control, and RES-005 stays unimplemented.
    const { container } = render(
      <ResourceFiles files={[file()]} resourceId="resource-1" writable />,
    );

    expect(container.textContent).not.toMatch(/delete|remove permanently|erase/i);
  });

  // -- archived material is read-only ----------------------------------------

  it("offers no upload or status control on material that is put aside", () => {
    const { container } = render(
      <ResourceFiles files={[file()]} resourceId="resource-1" writable={false} />,
    );

    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(container.querySelector("button")).toBeNull();
    expect(container.textContent).toMatch(/still listed and still downloadable/i);
  });

  it("still offers the download when the material is put aside", () => {
    const { container } = render(
      <ResourceFiles files={[file()]} resourceId="resource-1" writable={false} />,
    );

    expect(container.querySelector("a[download]")).not.toBeNull();
  });

  // -- bounds -----------------------------------------------------------------

  it("stops offering an upload once the resource is full, and says why", () => {
    const full = Array.from({ length: MAX_FILES_PER_RESOURCE }, (_, index) =>
      file({ id: `file-${index}` }),
    );

    const { container } = render(
      <ResourceFiles files={full} resourceId="resource-1" writable />,
    );

    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(container.textContent).toMatch(/set one aside before adding another/i);
    expect(container.textContent).toMatch(/nothing is deleted/i);
  });

  it("says nothing is lost when every file is set aside", () => {
    const { container } = render(
      <ResourceFiles
        files={[file({ status: "archived" })]}
        resourceId="resource-1"
        writable
      />,
    );

    expect(container.textContent).toMatch(/nothing has been deleted/i);
  });

  // -- what is never shown ----------------------------------------------------

  it("shows no storage location and no figure about the learner", () => {
    const { container } = render(
      <ResourceFiles files={[file(), file({ id: "file-2" })]} resourceId="resource-1" writable />,
    );

    expect(container.textContent).not.toContain("/var/lib");
    expect(container.textContent).not.toMatch(/storage_key/i);
    // No total across files, and no count of how many the learner has.
    expect(container.textContent).not.toMatch(/2 files|total|\d+ of \d+/i);
  });

  it("renders a filename as text, never as markup", () => {
    const { container } = render(
      <ResourceFiles
        files={[file({ original_filename: "<script>alert(1)</script>.pdf" })]}
        resourceId="resource-1"
        writable
      />,
    );

    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>alert(1)</script>.pdf");
  });
});
