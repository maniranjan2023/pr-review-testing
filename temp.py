"""Small helpers for working with PR review output files."""

from __future__ import annotations

import json
import re
from pathlib import Path


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


def summarize_review(review_path: str | Path) -> str:
    """Build a short summary from a saved review markdown file."""
    path = Path(review_path)
    text = path.read_text(encoding="utf-8")
    effort = parse_review_effort(text)
    issues = count_key_issues(text)

    effort_label = f"{effort}/5" if effort is not None else "unknown"
    return f"{path.name}: effort={effort_label}, key_issues={issues}"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python temp.py <review_output.md>")
        raise SystemExit(1)

    print(summarize_review(sys.argv[1]))
