"""Small helpers for working with PR review output files."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


ISSUE_ROW_PATTERN = re.compile(
    r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*(.+?)\s*\|$"
)
CATEGORY_PATTERN = re.compile(r"`([^`]+)`")


@dataclass
class ReviewIssue:
    number: int
    file: str
    lines: str
    category: str
    description: str


def load_review_text(path: str | Path) -> str:
    """Read a saved review markdown file."""
    return Path(path).read_text(encoding="utf-8")


def load_review_metadata(path: str | Path) -> dict:
    """Load metadata written by `pr_review.py --json`."""
    review_path = Path(path)
    json_path = review_path if review_path.suffix == ".json" else review_path.with_suffix(".json")

    if not json_path.exists():
        raise FileNotFoundError(f"No metadata file found at {json_path}")

    return json.loads(json_path.read_text(encoding="utf-8"))


def parse_review_effort(review_text: str) -> int | None:
    """Extract the 1-5 review effort score from markdown review text."""
    match = re.search(r"\*\*Review effort \[1-5\]\*\*:\s*(\d)", review_text)
    return int(match.group(1)) if match else None


def count_key_issues(review_text: str) -> int:
    """Count rows in the key issues table (excluding header/separator)."""
    in_table = False
    count = 0

    for line in review_text.splitlines():
        if line.strip().startswith("### Key issues"):
            in_table = True
            continue
        if in_table and line.startswith("### "):
            break
        if in_table and line.startswith("|") and not line.startswith("|---"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells and cells[0].isdigit():
                count += 1

    if "No issues found" in review_text:
        return 0

    return count


def parse_key_issues(review_text: str) -> list[ReviewIssue]:
    """Parse issue rows from the key issues markdown table."""
    if "No issues found" in review_text:
        return []

    issues: list[ReviewIssue] = []
    in_table = False

    for line in review_text.splitlines():
        if line.strip().startswith("### Key issues"):
            in_table = True
            continue
        if in_table and line.startswith("### "):
            break
        if not in_table:
            continue

        match = ISSUE_ROW_PATTERN.match(line.strip())
        if not match:
            continue

        category_match = CATEGORY_PATTERN.search(match.group(4))
        issues.append(
            ReviewIssue(
                number=int(match.group(1)),
                file=match.group(2),
                lines=match.group(3).strip(),
                category=category_match.group(1) if category_match else match.group(4).strip(),
                description=match.group(5).strip(),
            )
        )

    return issues


def parse_review_summary(review_text: str) -> str | None:
    """Extract the PR summary paragraph from review markdown."""
    match = re.search(r"\*\*Summary\*\*:\s*(.+)", review_text)
    return match.group(1).strip() if match else None


def issues_by_category(review_text: str) -> dict[str, list[ReviewIssue]]:
    """Group parsed issues by category."""
    grouped: dict[str, list[ReviewIssue]] = {}
    for issue in parse_key_issues(review_text):
        grouped.setdefault(issue.category, []).append(issue)
    return grouped


def review_report(review_path: str | Path) -> dict:
    """Build a structured report from a saved review file."""
    path = Path(review_path)
    text = load_review_text(path)
    issues = parse_key_issues(text)

    metadata = None
    json_path = path.with_suffix(".json")
    if json_path.exists():
        metadata = json.loads(json_path.read_text(encoding="utf-8"))

    return {
        "file": str(path.resolve()),
        "summary": parse_review_summary(text),
        "effort": parse_review_effort(text),
        "issue_count": len(issues),
        "issues": [
            {
                "number": issue.number,
                "file": issue.file,
                "lines": issue.lines,
                "category": issue.category,
                "description": issue.description,
            }
            for issue in issues
        ],
        "categories": {name: len(items) for name, items in issues_by_category(text).items()},
        "metadata": metadata,
    }


def format_report(report: dict) -> str:
    """Render a human-readable report from `review_report()`."""
    lines = [
        f"Review file: {report['file']}",
        f"Summary: {report['summary'] or 'n/a'}",
        f"Effort: {report['effort'] or 'unknown'}/5",
        f"Issues: {report['issue_count']}",
    ]

    if report["categories"]:
        lines.append("Categories:")
        for name, count in sorted(report["categories"].items()):
            lines.append(f"  - {name}: {count}")

    if report["issues"]:
        lines.append("Top issues:")
        for issue in report["issues"][:5]:
            lines.append(
                f"  {issue['number']}. [{issue['category']}] "
                f"{issue['file']}:{issue['lines']} - {issue['description']}"
            )

    if report["metadata"]:
        meta = report["metadata"]
        if meta.get("pr_url"):
            lines.append(f"PR: {meta['pr_url']}")

    return "\n".join(lines)


def summarize_review(review_path: str | Path) -> str:
    """Build a short summary from a saved review markdown file."""
    path = Path(review_path)
    text = load_review_text(path)
    effort = parse_review_effort(text)
    issues = count_key_issues(text)

    effort_label = f"{effort}/5" if effort is not None else "unknown"
    return f"{path.name}: effort={effort_label}, key_issues={issues}"


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect saved PR review output.")
    parser.add_argument("review_file", help="Path to review_output.md")
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print a detailed human-readable report",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured report as JSON",
    )
    return parser


def main() -> None:
    args = build_cli().parse_args()

    if args.json:
        print(json.dumps(review_report(args.review_file), indent=2))
        return

    if args.report:
        print(format_report(review_report(args.review_file)))
        return

    print(summarize_review(args.review_file))


if __name__ == "__main__":
    main()
