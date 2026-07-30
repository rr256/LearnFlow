#!/usr/bin/env python
"""Validate LearnFlow documentation front matter and relative links.

Enforces the rules in ``docs/development/documentation-standards.md``:

* every maintained document under ``docs/`` opens with YAML front matter
  carrying ``title``, ``status``, ``owner``, ``last_updated`` and ``related``;
* ``status`` uses the vocabulary that applies to the document's type, because
  normal documents and ADRs use two separate status sets;
* ``last_updated`` is a real ISO date that is not in the future;
* a ``superseded`` document links to its replacement;
* every ``related:`` path and every relative Markdown link resolves,
  including heading anchors.

Root ``README.md`` and ``CLAUDE.md`` are link-checked as well. They are the
entry points into ``docs/``, so a renamed document breaks them silently.

Usage:
    python scripts/validate_docs.py [--root PATH]

Exits 0 when there are no findings and 1 when any finding is reported.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import unquote

import yaml

REQUIRED_FIELDS = ("title", "status", "owner", "last_updated", "related")

NORMAL_STATUSES = frozenset({"draft", "proposed", "approved", "superseded", "template"})
ADR_STATUSES = frozenset({"proposed", "accepted", "superseded", "rejected"})

# Files under docs/adr/ that record a decision are named ADR-NNN-<title>.md.
# ADR-000-template.md is a reusable format rather than a decision, so it
# correctly carries the normal-document status `template`. docs/adr/README.md is
# navigation and is a normal document too.
ADR_FILENAME_PATTERN = re.compile(r"^ADR-\d{3}-.+\.md$")
ADR_TEMPLATE_NAME = "ADR-000-template.md"

# Link-checked but not front-matter-checked: they sit outside docs/.
EXTRA_LINK_SOURCES = ("README.md", "CLAUDE.md")

FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+?)\s*\)")
EXTERNAL_PATTERN = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)")

_HEADING_CACHE: dict[Path, set[str]] = {}


@dataclass(frozen=True)
class Finding:
    """One documentation defect, reported against a repository-relative path."""

    path: str
    line: int
    category: str
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: [{self.category}] {self.message}"


def slugify(heading: str) -> str:
    """Convert heading text to its GitHub-style anchor slug."""
    text = heading.strip().lower()
    text = text.replace("`", "")
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text).strip("-")


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def body_lines(lines: list[str], start: int) -> list[tuple[int, str]]:
    """Return (line number, text) pairs outside fenced code blocks."""
    result: list[tuple[int, str]] = []
    in_fence = False
    for offset, raw in enumerate(lines[start:], start=start + 1):
        if FENCE_PATTERN.match(raw):
            in_fence = not in_fence
            continue
        if not in_fence:
            result.append((offset, raw))
    return result


def headings_of(path: Path) -> set[str]:
    """Return the anchor slugs of every heading in a Markdown file."""
    cached = _HEADING_CACHE.get(path)
    if cached is not None:
        return cached
    slugs: set[str] = set()
    try:
        lines = read_lines(path)
    except OSError, UnicodeDecodeError:
        _HEADING_CACHE[path] = slugs
        return slugs
    for _, text in body_lines(lines, 0):
        match = HEADING_PATTERN.match(text)
        if match:
            slugs.add(slugify(match.group(2)))
    _HEADING_CACHE[path] = slugs
    return slugs


def split_front_matter(
    lines: list[str],
) -> tuple[str | None, int, str | None]:
    """Return (raw YAML, first body line index, error kind)."""
    if not lines or lines[0].strip() != "---":
        return None, 0, "missing"
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "".join(lines[1:index]), index + 1, None
    return None, 0, "unterminated"


def is_adr_decision(relative: str) -> bool:
    """True for ADR files that record a decision, excluding the template."""
    if not relative.startswith("docs/adr/"):
        return False
    name = relative.rsplit("/", 1)[-1]
    return name != ADR_TEMPLATE_NAME and bool(ADR_FILENAME_PATTERN.match(name))


def parse_last_updated(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def check_front_matter(
    path: Path,
    relative: str,
    lines: list[str],
    findings: list[Finding],
) -> tuple[int, object]:
    """Validate front matter; return the body start index and the status."""
    raw, start, error = split_front_matter(lines)
    if error == "missing":
        findings.append(
            Finding(
                relative,
                1,
                "front-matter",
                "document does not open with YAML front matter",
            )
        )
        return 0, None
    if error == "unterminated":
        findings.append(
            Finding(
                relative,
                1,
                "front-matter",
                "front matter opens with --- but is never closed",
            )
        )
        return 0, None

    try:
        data = yaml.safe_load(raw or "")
    except yaml.YAMLError as exc:
        detail = str(exc).splitlines()[0]
        findings.append(
            Finding(
                relative,
                1,
                "front-matter",
                f"front matter is not valid YAML: {detail}",
            )
        )
        return start, None

    if not isinstance(data, dict):
        findings.append(
            Finding(
                relative,
                1,
                "front-matter",
                "front matter must be a YAML mapping of fields",
            )
        )
        return start, None

    for field in REQUIRED_FIELDS:
        if field not in data:
            findings.append(
                Finding(
                    relative,
                    1,
                    "front-matter",
                    f"front matter is missing required field '{field}'",
                )
            )

    status = data.get("status")
    check_status(relative, status, findings)
    # A `template` document carries placeholder front matter by design, so its
    # date is not expected to be a real one.
    if status != "template":
        check_last_updated(relative, data.get("last_updated"), findings)
    check_related(path, relative, data.get("related"), findings)
    return start, status


def check_status(relative: str, status: object, findings: list[Finding]) -> None:
    if status is None:
        return
    is_adr = is_adr_decision(relative)
    allowed = ADR_STATUSES if is_adr else NORMAL_STATUSES
    kind = "an ADR" if is_adr else "a normal document"
    if not isinstance(status, str) or status not in allowed:
        expected = ", ".join(sorted(allowed))
        findings.append(
            Finding(
                relative,
                1,
                "status",
                f"status '{status}' is not valid for {kind}; expected one of: {expected}",
            )
        )


def check_last_updated(relative: str, value: object, findings: list[Finding]) -> None:
    if value is None:
        return
    parsed = parse_last_updated(value)
    if parsed is None:
        findings.append(
            Finding(
                relative,
                1,
                "front-matter",
                f"last_updated '{value}' is not an ISO YYYY-MM-DD date",
            )
        )
        return
    if parsed > date.today():
        findings.append(
            Finding(
                relative,
                1,
                "front-matter",
                f"last_updated {parsed.isoformat()} is in the future",
            )
        )


def check_related(path: Path, relative: str, related: object, findings: list[Finding]) -> None:
    if related is None:
        return
    if not isinstance(related, list):
        findings.append(
            Finding(
                relative,
                1,
                "front-matter",
                "related must be a list of relative Markdown paths",
            )
        )
        return
    for entry in related:
        if not isinstance(entry, str):
            findings.append(
                Finding(
                    relative,
                    1,
                    "front-matter",
                    f"related entry '{entry}' is not a path string",
                )
            )
            continue
        target = (path.parent / entry).resolve()
        if not target.exists():
            findings.append(
                Finding(
                    relative,
                    1,
                    "link",
                    f"related path '{entry}' does not resolve",
                )
            )


def check_superseded(
    relative: str,
    status: object,
    lines: list[str],
    start: int,
    findings: list[Finding],
) -> None:
    if status != "superseded":
        return
    for _, text in body_lines(lines, start):
        for match in LINK_PATTERN.finditer(text):
            if not EXTERNAL_PATTERN.match(match.group(1)):
                return
    findings.append(
        Finding(
            relative,
            1,
            "status",
            "superseded document does not link to its replacement",
        )
    )


def check_links(
    path: Path,
    relative: str,
    lines: list[str],
    start: int,
    findings: list[Finding],
) -> None:
    own_headings = headings_of(path)
    for number, text in body_lines(lines, start):
        for match in LINK_PATTERN.finditer(text):
            target = match.group(1)
            if EXTERNAL_PATTERN.match(target):
                continue
            location, _, anchor = target.partition("#")
            location = unquote(location)
            anchor = unquote(anchor)

            if not location:
                if anchor and anchor not in own_headings:
                    findings.append(
                        Finding(
                            relative,
                            number,
                            "link",
                            f"anchor '#{anchor}' matches no heading in this document",
                        )
                    )
                continue

            resolved = (path.parent / location).resolve()
            if not resolved.exists():
                findings.append(
                    Finding(
                        relative,
                        number,
                        "link",
                        f"link target '{location}' does not exist",
                    )
                )
                continue

            if (
                anchor
                and resolved.is_file()
                and resolved.suffix == ".md"
                and anchor not in headings_of(resolved)
            ):
                findings.append(
                    Finding(
                        relative,
                        number,
                        "link",
                        f"anchor '#{anchor}' matches no heading in '{location}'",
                    )
                )


def relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def validate(root: Path) -> list[Finding]:
    """Validate the documentation tree rooted at ``root``."""
    findings: list[Finding] = []
    docs = root / "docs"

    if not docs.is_dir():
        return [
            Finding(
                "docs",
                1,
                "structure",
                f"documentation directory not found at {docs}",
            )
        ]

    for path in sorted(docs.rglob("*.md")):
        relative = relative_path(path, root)
        lines = read_lines(path)
        start, status = check_front_matter(path, relative, lines, findings)
        check_superseded(relative, status, lines, start, findings)
        check_links(path, relative, lines, start, findings)

    for name in EXTRA_LINK_SOURCES:
        path = root / name
        if not path.is_file():
            continue
        check_links(path, name, read_lines(path), 0, findings)

    return sorted(findings, key=lambda f: (f.path, f.line, f.category))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate LearnFlow documentation front matter and links."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root to validate (defaults to this repository).",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    _HEADING_CACHE.clear()
    findings = validate(root)

    for finding in findings:
        print(finding.format())

    if findings:
        print(f"\n{len(findings)} documentation finding(s).")
        return 1

    print("Documentation validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
